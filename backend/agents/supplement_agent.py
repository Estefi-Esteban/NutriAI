"""
supplement_agent.py
--------------------
Agente que genera recomendaciones de suplementación personalizadas
basadas en el perfil, analítica y protocolo de patologías del usuario.

Sin publicidad, sin marcas — solo evidencia científica.

Clasifica en tres categorías:
  - Necesarios: déficit real demostrado o riesgo muy alto
  - Opcionales: mejoran el objetivo sin ser imprescindibles
  - Innecesarios: gasto evitable con justificación honesta
"""

import json
import re
import logging
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from backend.config import GROQ_API_KEY
from backend.agents.prompts.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


class SupplementAgent:

    MODEL = "llama-3.3-70b-versatile"
    TEMPERATURE = 0.2  # bajo para respuestas consistentes y basadas en evidencia

    def __init__(self):
        self.llm = ChatGroq(
            model=self.MODEL,
            api_key=GROQ_API_KEY,
            temperature=self.TEMPERATURE,
        )
        self.system_prompt = load_prompt("supplement_prompt.md")

    def recomendar(
        self,
        perfil: dict,
        analisis_clinico: dict | None = None,
        protocolo_patologias: dict | None = None,
    ) -> dict:
        """
        Genera recomendaciones de suplementación personalizadas.

        Args:
            perfil: datos completos del usuario (objetivo, dieta, actividad,
                    edad, sexo, peso, patologías declaradas)
            analisis_clinico: output del ClinicalAgent, si el usuario subió
                              una analítica (puede ser None)
            protocolo_patologias: output del PathologyAgent con restricciones
                                  activas (puede ser None)

        Returns:
            Dict con:
              - suplementos_necesarios: list[dict]
              - suplementos_opcionales: list[dict]
              - suplementos_innecesarios: list[dict]
              - notas: str
              - resumen: str
        """
        entrada = {
            "perfil": {
                "objetivo_principal": perfil.get("objetivo_principal"),
                "dieta_tipo": perfil.get("dieta_tipo"),
                "dias_entrenamiento": perfil.get("dias_entrenamiento"),
                "tipo_entrenamiento": perfil.get("tipo_entrenamiento"),
                "nivel_actividad": perfil.get("nivel_actividad"),
                "edad": perfil.get("edad"),
                "sexo": perfil.get("sexo"),
                "peso_kg": perfil.get("peso_kg"),
                "patologias": perfil.get("patologias", []),
                "alergias": perfil.get("alergias", []),
                "medicacion": perfil.get("medicacion"),
            },
            "analisis_clinico": analisis_clinico,
            "protocolo_patologias": protocolo_patologias,
        }

        mensajes = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=json.dumps(entrada, ensure_ascii=False, indent=2)),
        ]

        logger.info("SupplementAgent: generando recomendaciones para perfil con objetivo '%s'",
                    perfil.get("objetivo_principal", "desconocido"))
        respuesta = self.llm.invoke(mensajes)
        return self._parsear_respuesta(respuesta.content)

    def _parsear_respuesta(self, texto: str) -> dict:
        """Extrae el JSON de la respuesta con 3 capas de fallback."""
        # Capa 1: JSON puro
        try:
            return json.loads(texto.strip())
        except json.JSONDecodeError:
            pass

        # Capa 2: JSON dentro de ```json ... ```
        patron_md = r"```(?:json)?\s*([\s\S]*?)```"
        match_md = re.search(patron_md, texto)
        if match_md:
            try:
                return json.loads(match_md.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Capa 3: primer { ... } de la respuesta
        patron_raw = r"\{[\s\S]*\}"
        match_raw = re.search(patron_raw, texto)
        if match_raw:
            try:
                return json.loads(match_raw.group())
            except json.JSONDecodeError:
                pass

        logger.error("SupplementAgent: no se pudo parsear la respuesta del modelo")
        raise ValueError("El modelo no devolvió JSON válido en las recomendaciones de suplementación")
