"""
Agente Nutricionista — NutriAI
===============================
Analiza el perfil completo del usuario y los cálculos nutricionales,
y devuelve un informe clínico estructurado en JSON.

A diferencia del Agente de Perfil, este agente NO conversa.
Hace una sola llamada a Groq con todos los datos y devuelve el análisis.
"""

from __future__ import annotations

import json
import re
import logging
from typing import Optional

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from backend.config import groq_api_key
from backend.agents.prompts.prompt_loader import load_prompt
from backend.utils.decorators import reintentar_llamada_llm


logger = logging.getLogger(__name__)


class NutritionAgent:
    """
    Agente que recibe el perfil del usuario y los cálculos nutricionales,
    y devuelve un análisis clínico estructurado en JSON.

    Uso típico:
        agente = NutritionAgent()
        resultado = agente.analizar(perfil=datos_usuario, calculos=resultado_calculador)
    """

    MODEL = "llama-3.3-70b-versatile"
    TEMPERATURE = 0.3   # Baja temperatura para análisis consistente y clínico

    def __init__(self):
        self.llm = ChatGroq(
            model=self.MODEL,
            api_key=groq_api_key,
            temperature=self.TEMPERATURE,
        )
        self.system_prompt = load_prompt("nutrition_prompt.md")

    # ------------------------------------------------------------------
    # Método principal
    # ------------------------------------------------------------------

    def analizar(self, perfil: dict, calculos: dict) -> dict:
        """
        Analiza el perfil y los cálculos nutricionales del usuario.

        Args:
            perfil:   Dict con todos los datos del usuario (salida del ProfileAgent).
            calculos: Dict con los resultados del motor nutricional (salida de calcular_todo().to_dict()).

        Returns:
            Dict con el análisis clínico estructurado:
            {
                "resumen_perfil":         str,
                "justificacion_calorias": str,
                "justificacion_macros": {
                    "proteinas": str,
                    "carbos":    str,
                    "grasas":    str
                },
                "recomendaciones":    list[str],
                "alertas":            list[str],
                "distribucion_comidas": {
                    "desayuno_pct":     int,
                    "media_manana_pct": int,
                    "comida_pct":       int,
                    "merienda_pct":     int,
                    "cena_pct":         int
                },
                "notas_para_dietista": str
            }

        Raises:
            ValueError: Si la respuesta del modelo no contiene JSON parseable.
            RuntimeError: Si la llamada a la API de Groq falla.
        """
        from backend.rag.clinical_knowledge_search import buscar_evidencia

        # Buscar evidencia en Qdrant
        query_parts = []
        obj = perfil.get("objetivo_principal")
        if obj:
            query_parts.append(str(obj))
        pats = perfil.get("patologias")
        if pats:
            query_parts.extend([str(p) for p in pats])
        
        query_rag = " ".join(query_parts) if query_parts else "nutrition healthy guidelines"
        
        evidencia = buscar_evidencia(query_rag, n_resultados=3)
        if evidencia:
            evidencia_texto = "\n\n".join([
                f"--- DOCUMENTO: {e['titulo']} ({e['año']}) ---\nFuente: {e['fuente']} (Tipo: {e['tipo']})\nTexto: {e['texto']}"
                for e in evidencia
            ])
        else:
            evidencia_texto = "No se encontró evidencia específica en la base de datos."

        # Reemplazar placeholder en el prompt del sistema
        system_prompt = self.system_prompt.replace("{evidencia_cientifica}", evidencia_texto)

        mensaje_usuario = self._construir_mensaje(perfil, calculos)
        texto_respuesta = self._llamar_groq(mensaje_usuario, system_prompt)
        return self._parsear_respuesta(texto_respuesta)

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _construir_mensaje(self, perfil: dict, calculos: dict) -> str:
        """Serializa perfil + cálculos en el formato de entrada que espera el prompt."""
        entrada = {
            "perfil": perfil,
            "calculos": calculos,
        }
        return json.dumps(entrada, ensure_ascii=False, indent=2)

    @reintentar_llamada_llm(max_intentos=3, retardo_inicial=15.0, backoff=1.5)
    def _llamar_groq(self, mensaje_usuario: str, system_prompt: str) -> str:
        """Hace la llamada a Groq y devuelve el texto de la respuesta."""
        mensajes = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=mensaje_usuario),
        ]

        logger.info("NutritionAgent: llamando a Groq con modelo %s", self.MODEL)

        respuesta = self.llm.invoke(mensajes)
        return respuesta.content

    def _parsear_respuesta(self, texto: str) -> dict:
        """
        Extrae y parsea el JSON de la respuesta del modelo.

        El prompt instruye al modelo a devolver SOLO JSON sin bloques markdown,
        pero añadimos un fallback por si incluye backticks.
        """
        # 1) Intentamos parsear directo (caso ideal)
        try:
            return json.loads(texto.strip())
        except json.JSONDecodeError:
            pass

        # 2) Fallback: buscamos el primer bloque JSON en el texto
        patron = r'\{[\s\S]*\}'
        match = re.search(patron, texto)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # 3) Fallback: intentamos extraer de bloque ```json ... ```
        patron_md = r'```(?:json)?\s*([\s\S]*?)```'
        match_md = re.search(patron_md, texto)
        if match_md:
            try:
                return json.loads(match_md.group(1).strip())
            except json.JSONDecodeError:
                pass

        logger.error("NutritionAgent: no se pudo parsear el JSON.\nRespuesta recibida:\n%s", texto)
        raise ValueError(
            "El modelo no devolvió un JSON válido. "
            f"Respuesta recibida:\n{texto[:500]}..."
        )


# ---------------------------------------------------------------------------
# Ejecución directa: python -m backend.agents.nutrition_agent
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import io
    from backend.utils.nutrition_calculator import calcular_todo

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    print("=" * 60)
    print("  TEST — NutritionAgent con perfil de Marta")
    print("=" * 60)

    perfil_marta = {
        "nombre": "Marta",
        "edad": 21,
        "sexo": "mujer",
        "peso_kg": 68.0,
        "altura_cm": 163,
        "porcentaje_grasa": None,
        "objetivo_principal": "recomposicion_corporal",
        "objetivo_secundario": "ganar energía",
        "dias_entrenamiento": 3,
        "tipo_entrenamiento": "fuerza",
        "minutos_sesion": 60,
        "dieta_tipo": "omnivora",
        "alergias": [],
        "intolerancias": [],
        "tiempo_cocina_min": 30,
        "personas_en_casa": 1,
        "presupuesto_semanal_eur": 60,
        "patologias": [],
        "medicacion": "",
        "tiene_analitica": False,
        "nivel_actividad": "sedentario",
    }

    # Calculamos los macros con el motor nutricional
    calculos = calcular_todo(perfil_marta).to_dict()

    print("\n📊 Cálculos de entrada:")
    print(json.dumps(calculos, indent=2, ensure_ascii=False))

    # Llamamos al agente
    agente = NutritionAgent()
    print("\n🤖 Llamando al agente nutricionista...")
    resultado = agente.analizar(perfil=perfil_marta, calculos=calculos)

    print("\n✅ Análisis clínico generado:\n")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))