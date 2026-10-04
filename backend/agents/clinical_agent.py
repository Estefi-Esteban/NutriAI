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

    MODEL = "openai/gpt-oss-120b"
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

        Los estados respecto a los rangos de referencia se calculan
        determinísticamente en Python. El LLM se utiliza posteriormente
        para interpretar esos resultados y generar el análisis clínico.

        Args:
            perfil: datos del usuario (sexo, edad, objetivo, patologías...)
            valores: dict con los marcadores encontrados y sus valores numéricos

        Returns:
            Dict con el análisis clínico completo.
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

        # Evaluación determinista de los valores respecto a los rangos internos.
        # Esto NO constituye un diagnóstico médico.
        from backend.utils.pdf_extractor import evaluar_valores_analitica

        evaluacion_rangos = evaluar_valores_analitica(
            valores=valores,
            sexo=perfil.get("sexo"),
        )

        entrada = {
            "perfil": perfil,
            "valores": valores,
            "evaluacion_rangos": evaluacion_rangos,
            "rangos": RANGOS_REFERENCIA,
        }   

        # Buscar evidencia en Qdrant
        from backend.rag.clinical_knowledge_search import buscar_evidencia

        query_parts = []

        obj = perfil.get("objetivo_principal")
        if obj:
            query_parts.append(str(obj))

        patologias = list(dict.fromkeys(
            (perfil.get("patologias") or [])
            + (perfil.get("patologias_activas") or [])
        ))

        if patologias:
            query_parts.extend([str(p) for p in patologias])

        if valores:
            query_parts.extend(list(valores.keys()))

        query_rag = (
            " ".join(query_parts)
            if query_parts
            else "blood test clinical markers guidelines"
        )

        evidencia = buscar_evidencia(query_rag, n_resultados=3)

        if evidencia:
            evidencia_texto = "\n\n".join([
                f"--- DOCUMENTO: {e['titulo']} ({e['año']}) ---\n"
                f"Fuente: {e['fuente']} (Tipo: {e['tipo']})\n"
                f"Texto: {e['texto']}"
                for e in evidencia
            ])
        else:
            evidencia_texto = (
                "No se encontró evidencia específica en la base de datos."
            )

        system_prompt = self.system_prompt.replace(
            "{evidencia_cientifica}",
            evidencia_texto,
        )

        mensajes = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=json.dumps(
                    entrada,
                    ensure_ascii=False,
                    indent=2,
                )
            ),
        ]

        logger.info(
            "ClinicalAgent: analizando %d marcadores",
            len(valores),
        )

        respuesta = self.llm.invoke(mensajes)

        resultado = self._parsear_respuesta(respuesta.content)

        resultado = self._sincronizar_estados(
            resultado,
            evaluacion_rangos,
        )    

        return resultado

    def _parsear_respuesta(self, texto: str) -> dict:
        """Extrae y valida el JSON de la respuesta del modelo con fallback en 3 capas."""
        resultado = None

        # Capa 1: JSON limpio
        try:
            resultado = json.loads(texto.strip())
        except json.JSONDecodeError:
            pass

        # Capa 2: JSON dentro de texto
        if resultado is None:
            patron = r'\{[\s\S]*\}'
            match = re.search(patron, texto)
            if match:
                try:
                    resultado = json.loads(match.group())
                except json.JSONDecodeError:
                    pass

        # Capa 3: bloque Markdown
        if resultado is None:
            patron_md = r'```(?:json)?\s*([\s\S]*?)```'
            match_md = re.search(patron_md, texto)
            if match_md:
                try:
                    resultado = json.loads(match_md.group(1).strip())
                except json.JSONDecodeError:
                    pass

        if not isinstance(resultado, dict):
            logger.error("ClinicalAgent: no se pudo parsear la respuesta")
            raise ValueError(
                "El modelo no devolvió JSON válido en el análisis clínico"
            )

        return self._validar_respuesta(resultado)

    def _validar_respuesta(self, resultado: dict) -> dict:
        """
        Valida y normaliza la estructura devuelta por el LLM.

        El modelo puede generar recomendaciones nutricionales,
        pero no debe alterar los estados clínicos calculados
        previamente por Python.
        """

        campos_lista = [
            "alertas",
            "recomendaciones_nutricionales",
        ]

        campos_dict = [
            "marcadores",
        ]

        for campo in campos_lista:
            valor = resultado.get(campo)

            if valor is None:
                resultado[campo] = []
            elif not isinstance(valor, list):
                logger.warning(
                    "ClinicalAgent: campo '%s' no era una lista. "
                    "Se normaliza a lista vacía.",
                    campo,
                )
                resultado[campo] = []

        for campo in campos_dict:
            valor = resultado.get(campo)

            if valor is None:
                resultado[campo] = {}
            elif not isinstance(valor, dict):
                logger.warning(
                    "ClinicalAgent: campo '%s' no era un objeto. "
                    "Se normaliza a diccionario vacío.",
                    campo,
                )
                resultado[campo] = {}

        if not isinstance(resultado.get("resumen_general"), str):
            resultado["resumen_general"] = ""

        if not isinstance(resultado.get("notas_para_dietista"), str):
            resultado["notas_para_dietista"] = ""

        if not isinstance(resultado.get("requiere_atencion_medica"), bool):
            resultado["requiere_atencion_medica"] = False

        if resultado.get("motivo_atencion_medica") is not None and not isinstance(resultado["motivo_atencion_medica"], str):
            resultado["motivo_atencion_medica"] = str(
                resultado["motivo_atencion_medica"]
            )

        return resultado


    def _sincronizar_estados(
        self,
        resultado: dict,
        valuacion_rangos: dict,
    ) -> dict:
        """
        Garantiza que los estados clínicos finales coincidan con los
        calculados determinísticamente en Python.

        El LLM puede explicar los resultados, pero no puede modificar
        su clasificación.
        """

        marcadores = resultado.get("marcadores", {})

        if not isinstance(marcadores, dict):
            marcadores = {}
            resultado["marcadores"] = marcadores

        for nombre, evaluacion in valuacion_rangos.items():
            if not isinstance(evaluacion, dict):
                continue

            estado_python = evaluacion.get("estado")
            valor_python = evaluacion.get("valor")

            if nombre not in marcadores or not isinstance(
                marcadores[nombre],
                dict,
            ):
                marcadores[nombre] = {}

            marcador = marcadores[nombre]

            # Python es la fuente de verdad.
            marcador["estado"] = estado_python
            marcador["valor"] = valor_python

        return resultado