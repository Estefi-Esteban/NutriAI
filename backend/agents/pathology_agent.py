"""
pathology_agent.py
-------------------
Agente especializado en traducir patologías y alertas clínicas
en restricciones y prioridades nutricionales concretas.
"""

import json
import re
import logging
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from backend.config import GROQ_API_KEY
from backend.agents.prompts.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

PATOLOGIAS_SOPORTADAS = {
    "diabetes", "prediabetes", "hipertension", "hipotiroidismo",
    "hipertiroidismo", "sop", "gota", "celiaquía", "enfermedad_renal",
    "colesterol_alto", "anemia", "reflujo",
}

# Mapeo de alertas clínicas → patologías que sugieren
ALERTAS_A_PATOLOGIAS = {
    "glucosa":      ["prediabetes"],
    "ldl":          ["colesterol_alto"],
    "trigliceridos":["colesterol_alto"],
    "ferritina":    ["anemia"],
    "tsh":          ["hipotiroidismo"],
    "acido_urico":  ["gota"],
}


class PathologyAgent:

    MODEL = "llama-3.3-70b-versatile"
    TEMPERATURE = 0.1  # máximo rigor — esto es protocolo médico

    def __init__(self):
        self.llm = ChatGroq(
            model=self.MODEL,
            api_key=GROQ_API_KEY,
            temperature=self.TEMPERATURE,
        )
        self.system_prompt = load_prompt("pathology_prompt.md")

    def analizar(
        self,
        perfil: dict,
        patologias_declaradas: list[str],
        alertas_clinicas: list[dict] | None = None,
    ) -> dict:
        """
        Genera el protocolo nutricional basado en patologías y alertas.

        Args:
            perfil: datos del usuario
            patologias_declaradas: lista de patologías del perfil del usuario
            alertas_clinicas: alertas del ClinicalAgent (opcional)

        Returns:
            Dict con restricciones, alimentos prohibidos/prioritarios
            y notas para el dietista
        """
        # Enriquecer con patologías sugeridas por las alertas clínicas
        patologias_sugeridas = self._patologias_de_alertas(alertas_clinicas or [])
        todas_patologias = list(set(patologias_declaradas + patologias_sugeridas))

        # Si no hay nada relevante, devolvemos protocolo vacío directamente
        if not todas_patologias:
            return self._protocolo_vacio()

        entrada = {
            "patologias_declaradas": patologias_declaradas,
            "alertas_clinicas": alertas_clinicas or [],
            "patologias_combinadas": todas_patologias,
            "perfil": {
                "sexo": perfil.get("sexo"),
                "edad": perfil.get("edad"),
                "objetivo_principal": perfil.get("objetivo_principal"),
            },
        }

        mensajes = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=json.dumps(entrada, ensure_ascii=False, indent=2)),
        ]

        logger.info(
            "PathologyAgent: analizando patologías %s", todas_patologias
        )
        respuesta = self.llm.invoke(mensajes)
        return self._parsear_respuesta(respuesta.content)

    def _patologias_de_alertas(self, alertas: list[dict]) -> list[str]:
        """Mapea alertas clínicas a posibles patologías subyacentes."""
        sugeridas = []
        for alerta in alertas:
            marcador = alerta.get("marcador", "")
            if marcador in ALERTAS_A_PATOLOGIAS:
                sugeridas.extend(ALERTAS_A_PATOLOGIAS[marcador])
        return list(set(sugeridas))

    def _protocolo_vacio(self) -> dict:
        return {
            "patologias_identificadas": [],
            "restricciones": [],
            "alimentos_prohibidos": [],
            "alimentos_prioritarios": [],
            "conflictos_detectados": [],
            "notes_dietista": "",  # wait, should this be "notas_dietista"? The schema and prompt use "notas_dietista". Let's check!
            "notas_dietista": "",
            "nivel_restriccion": "bajo",
        }

    def _parsear_respuesta(self, texto: str) -> dict:
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

        logger.error("PathologyAgent: no se pudo parsear la respuesta")
        raise ValueError("El modelo no devolvió JSON válido en el análisis de patologías")
