"""
Agente Dietista — NutriAI
==========================
Genera un día completo de comidas (5 tomas) para un usuario, respetando
sus macros objetivo, restricciones dietéticas y variedad respecto a días
ya generados.

Diseñado para ser llamado 7 veces (una por día de la semana), pasando
en cada iteración los platos anteriores mediante `comidas_previas`.
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


logger = logging.getLogger(__name__)

DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


class DietistAgent:
    """
    Agente que recibe el perfil, los cálculos nutricionales, el análisis del
    nutricionista y el día de la semana a generar, y devuelve un menú diario
    completo estructurado en JSON.

    Uso típico — un día:
        agente = DietistAgent()
        menu_lunes = agente.generar_dia(
            perfil=datos_usuario,
            calculos=resultado_calculador,
            analisis=resultado_nutricionista,
            dia_semana="Lunes",
            comidas_previas=[]
        )

    Uso típico — semana completa:
        menu_semana = agente.generar_semana(
            perfil=datos_usuario,
            calculos=resultado_calculador,
            analisis=resultado_nutricionista,
        )
    """

    MODEL = "llama-3.3-70b-versatile"
    TEMPERATURE = 0.7   # Temperatura media: creatividad culinaria sin perder coherencia nutricional

    def __init__(self):
        self.llm = ChatGroq(
            model=self.MODEL,
            api_key=groq_api_key,
            temperature=self.TEMPERATURE,
        )
        self.system_prompt = load_prompt("dietist_prompt.md")

    # ------------------------------------------------------------------
    # Método principal — un día
    # ------------------------------------------------------------------

    def generar_dia(
        self,
        perfil: dict,
        calculos: dict,
        analisis: dict,
        dia_semana: str,
        comidas_previas: Optional[list[str]] = None,
    ) -> dict:
        """
        Genera el menú completo de un día (5 comidas).

        Args:
            perfil:         Dict con datos del usuario (salida del ProfileAgent).
            calculos:       Dict con macros objetivo (salida de calcular_todo().to_dict()).
            analisis:       Dict con el informe del nutricionista (salida de NutritionAgent.analizar()).
            dia_semana:     Nombre del día a generar: "Lunes", "Martes", ..., "Domingo".
            comidas_previas: Lista de nombres de platos ya generados en días anteriores.
                             Evita repetirlos. Si es el primer día, pasa [] o None.

        Returns:
            Dict con el menú del día:
            {
                "dia": str,
                "comidas": {
                    "desayuno":     {nombre, calorias, proteinas_g, carbos_g, grasas_g,
                                     tiempo_preparacion_min, dificultad, ingredientes, pasos, sustituciones},
                    "media_manana": {...},
                    "comida":       {...},
                    "merienda":     {...},
                    "cena":         {...}
                },
                "totales_dia": {calorias, proteinas_g, carbos_g, grasas_g}
            }

        Raises:
            ValueError:  Si el día no es válido o la respuesta del modelo no es JSON parseable.
            RuntimeError: Si la llamada a la API de Groq falla.
        """
        if dia_semana not in DIAS_SEMANA:
            raise ValueError(
                f"Día '{dia_semana}' no válido. Usa uno de: {DIAS_SEMANA}"
            )

        # Enriquecemos calculos con la distribución calórica en kcal por comida
        calculos_enriquecidos = self._calcular_distribucion_kcal(calculos, analisis)

        mensaje_usuario = self._construir_mensaje(
            perfil=perfil,
            calculos=calculos_enriquecidos,
            analisis=analisis,
            dia_semana=dia_semana,
            comidas_previas=comidas_previas or [],
        )

        texto_respuesta = self._llamar_groq(mensaje_usuario, dia_semana)
        return self._parsear_respuesta(texto_respuesta, dia_semana)

    # ------------------------------------------------------------------
    # Método de conveniencia — semana completa
    # ------------------------------------------------------------------

    def generar_semana(
        self,
        perfil: dict,
        calculos: dict,
        analisis: dict,
    ) -> dict:
        """
        Genera los 7 días de la semana secuencialmente, pasando los platos
        ya generados a cada llamada para garantizar variedad.

        Returns:
            Dict con clave por día: {"Lunes": {...}, "Martes": {...}, ...}
        """
        menu_semana: dict = {}
        comidas_previas: list[str] = []

        for dia in DIAS_SEMANA:
            logger.info("DietistAgent: generando menú para %s...", dia)
            menu_dia = self.generar_dia(
                perfil=perfil,
                calculos=calculos,
                analisis=analisis,
                dia_semana=dia,
                comidas_previas=comidas_previas,
            )
            menu_semana[dia] = menu_dia

            # Recolectamos los nombres de todas las comidas del día para el siguiente
            nuevos_nombres = self._extraer_nombres_platos(menu_dia)
            comidas_previas.extend(nuevos_nombres)

        return menu_semana

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _calcular_distribucion_kcal(self, calculos: dict, analisis: dict) -> dict:
        """
        Enriquece el dict de cálculos con la distribución en kcal por comida,
        derivada de los porcentajes del nutricionista.
        """
        calorias_objetivo = calculos.get("calorias_objetivo", 0)
        distribucion = analisis.get("distribucion_comidas", {})

        kcal_por_comida = {
            "desayuno_kcal":     round(calorias_objetivo * distribucion.get("desayuno_pct", 25) / 100),
            "media_manana_kcal": round(calorias_objetivo * distribucion.get("media_manana_pct", 10) / 100),
            "comida_kcal":       round(calorias_objetivo * distribucion.get("comida_pct", 35) / 100),
            "merienda_kcal":     round(calorias_objetivo * distribucion.get("merienda_pct", 10) / 100),
            "cena_kcal":         round(calorias_objetivo * distribucion.get("cena_pct", 20) / 100),
        }

        calculos_copia = dict(calculos)
        calculos_copia["distribucion_comidas"] = kcal_por_comida
        return calculos_copia

    def _construir_mensaje(
        self,
        perfil: dict,
        calculos: dict,
        analisis: dict,
        dia_semana: str,
        comidas_previas: list[str],
    ) -> str:
        """Serializa todos los datos de entrada en el formato que espera el prompt."""
        entrada = {
            "perfil": perfil,
            "calculos": calculos,
            "analisis": analisis,
            "dia_semana": dia_semana,
            "comidas_previas": comidas_previas,
        }
        return json.dumps(entrada, ensure_ascii=False, indent=2)

    def _llamar_groq(self, mensaje_usuario: str, dia_semana: str) -> str:
        """Hace la llamada a Groq y devuelve el texto de la respuesta."""
        mensajes = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=mensaje_usuario),
        ]

        logger.info(
            "DietistAgent: llamando a Groq (modelo=%s) para %s",
            self.MODEL, dia_semana
        )

        try:
            respuesta = self.llm.invoke(mensajes)
            return respuesta.content
        except Exception as exc:
            logger.error("DietistAgent: error al llamar a Groq — %s", exc)
            raise RuntimeError(f"Error al contactar con Groq: {exc}") from exc

    def _parsear_respuesta(self, texto: str, dia_semana: str) -> dict:
        """
        Extrae y parsea el JSON de la respuesta del modelo.

        Estrategia de 3 capas:
          1. Parseo directo (ideal).
          2. Búsqueda del bloque JSON más grande en el texto.
          3. Extracción de bloque markdown ```json ... ```.
        """
        # 1) Parseo directo
        try:
            return json.loads(texto.strip())
        except json.JSONDecodeError:
            pass

        # 2) Primer bloque {...} grande
        patron = r'\{[\s\S]*\}'
        match = re.search(patron, texto)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # 3) Bloque markdown ```json ... ```
        patron_md = r'```(?:json)?\s*([\s\S]*?)```'
        match_md = re.search(patron_md, texto)
        if match_md:
            try:
                return json.loads(match_md.group(1).strip())
            except json.JSONDecodeError:
                pass

        logger.error(
            "DietistAgent: no se pudo parsear JSON para %s.\nRespuesta:\n%s",
            dia_semana, texto[:500]
        )
        raise ValueError(
            f"El modelo no devolvió JSON válido para {dia_semana}. "
            f"Respuesta recibida:\n{texto[:500]}..."
        )

    def _extraer_nombres_platos(self, menu_dia: dict) -> list[str]:
        """Extrae los nombres de todos los platos de un día para pasarlos como comidas_previas."""
        nombres = []
        comidas = menu_dia.get("comidas", {})
        for toma in comidas.values():
            if isinstance(toma, dict) and "nombre" in toma:
                nombres.append(toma["nombre"])
        return nombres


# ---------------------------------------------------------------------------
# Ejecución directa: python -m backend.agents.dietist_agent
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import io
    from backend.utils.nutrition_calculator import calcular_todo
    from backend.agents.nutrition_agent import NutritionAgent

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    print("=" * 60)
    print("  TEST — DietistAgent: Lunes de Marta")
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

    # Paso 1: cálculos nutricionales
    calculos = calcular_todo(perfil_marta).to_dict()
    print("\n📊 Cálculos:")
    print(json.dumps(calculos, indent=2, ensure_ascii=False))

    # Paso 2: análisis del nutricionista
    print("\n🧑‍⚕️ Llamando al NutritionAgent...")
    nutrition_agente = NutritionAgent()
    analisis = nutrition_agente.analizar(perfil=perfil_marta, calculos=calculos)
    print("✅ Análisis clínico listo.")
    print(f"   Distribución: {analisis.get('distribucion_comidas', {})}")

    # Paso 3: generar el Lunes
    print("\n🍽️  Llamando al DietistAgent para el Lunes...")
    dietist_agente = DietistAgent()
    menu_lunes = dietist_agente.generar_dia(
        perfil=perfil_marta,
        calculos=calculos,
        analisis=analisis,
        dia_semana="Lunes",
        comidas_previas=[],
    )

    print("\n✅ Menú del Lunes generado:\n")
    print(json.dumps(menu_lunes, indent=2, ensure_ascii=False))

    # Verificación de totales
    print("\n📐 Verificación de totales:")
    totales = menu_lunes.get("totales_dia", {})
    print(f"   Calorías objetivo : {calculos['calorias_objetivo']:.0f} kcal")
    print(f"   Calorías generadas: {totales.get('calorias', '?')} kcal")
    print(f"   Proteínas objetivo : {calculos['macros']['proteinas_g']:.0f} g")
    print(f"   Proteínas generadas: {totales.get('proteinas_g', '?')} g")
    print(f"   Carbos objetivo : {calculos['macros']['carbos_g']:.0f} g")
    print(f"   Carbos generados: {totales.get('carbos_g', '?')} g")
    print(f"   Grasas objetivo : {calculos['macros']['grasas_g']:.0f} g")
    print(f"   Grasas generadas: {totales.get('grasas_g', '?')} g")
