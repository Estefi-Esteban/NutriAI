"""
clinical_agent.py
------------------
Agente especializado en interpretación clínica de analíticas de sangre.
Recibe los valores extraídos de la analítica y el perfil del usuario,
y devuelve un análisis clínico estructurado en JSON.
"""

import json
import re
import logging
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from backend.config import GROQ_API_KEY
from backend.agents.prompts.prompt_loader import load_prompt
from backend.utils.pdf_extractor import RANGOS_REFERENCIA

logger = logging.getLogger(__name__)


class ClinicalAgent:

    MODEL = "llama-3.3-70b-versatile"
    TEMPERATURE = 0.2   # Baja temperatura — queremos rigor clínico, no creatividad

    def __init__(self):
        self.llm = ChatGroq(
            model=self.MODEL,
            api_key=GROQ_API_KEY,
            temperature=self.TEMPERATURE,
        )
        self.system_prompt = load_prompt("clinical_prompt.md")

    def analizar(self, perfil: dict, valores: dict) -> dict:
        """
        Analiza los valores de la analítica en contexto del perfil del usuario.

        Args:
            perfil: datos del usuario (sexo, edad, objetivo, patologías...)
            valores: dict con los marcadores encontrados y sus valores numéricos
                     Ej: {"glucosa": 95, "ldl": 145, "ferritina": 12}

        Returns:
            Dict con el análisis clínico completo (resumen, alertas,
            recomendaciones, notas para el dietista)
        """
        if not valores:
            return {
                "resumen_general": "No se encontraron valores analíticos para interpretar.",
                "marcadores": {},
                "alertas": [],
                "recomendaciones_nutricionales": [],
                "notas_para_dietista": "",
                "requiere_atencion_medica": False,
                "motivo_atencion_medica": None,
            }

        entrada = {
            "perfil": perfil,
            "valores": valores,
            "rangos": RANGOS_REFERENCIA,
        }

        mensajes = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=json.dumps(entrada, ensure_ascii=False, indent=2)),
        ]

        logger.info("ClinicalAgent: analizando %d marcadores", len(valores))
        respuesta = self.llm.invoke(mensajes)
        return self._parsear_respuesta(respuesta.content)

    def _parsear_respuesta(self, texto: str) -> dict:
        """Extrae el JSON de la respuesta del modelo con fallback en 3 capas."""
        try:
            return json.loads(texto.strip())
        except json.JSONDecodeError:
            pass

        patron = r'\{[\s\S]*\}'
        match = re.search(patron, texto)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        patron_md = r'```(?:json)?\s*([\s\S]*?)```'
        match_md = re.search(patron_md, texto)
        if match_md:
            try:
                return json.loads(match_md.group(1).strip())
            except json.JSONDecodeError:
                pass

        logger.error("ClinicalAgent: no se pudo parsear la respuesta")
        raise ValueError("El modelo no devolvió JSON válido en el análisis clínico")
