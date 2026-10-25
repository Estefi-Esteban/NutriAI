"""
Agente Dietista — NutriAI
==========================
Genera un día completo de comidas (5 tomas) para un usuario,
respetando macros, restricciones dietéticas y variedad.

Está diseñado para generar la semana secuencialmente, pero con
control estricto del tamaño de las peticiones a Groq para reducir
el consumo de TPM en el plan gratuito.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from backend.config import groq_api_key
from backend.agents.prompts.prompt_loader import load_prompt
from backend.rag.menu_validator import validar_y_corregir_dia
from backend.utils.decorators import reintentar_llamada_llm
from backend.utils.groq_token_budget import groq_token_budget


logger = logging.getLogger(__name__)


DIAS_SEMANA = [
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
    "Domingo",
]


class DietistAgent:
    """
    Agente que genera un menú diario de 5 comidas.

    Control de consumo:
    - Prompt compacto.
    - RAG limitado.
    - Máximo de comidas previas limitado.
    - JSON de entrada sin espacios innecesarios.
    - Máximo de tokens de respuesta controlado.
    - Protección local aproximada contra exceso de TPM.
    """

    MODEL = "openai/gpt-oss-120b"

    # Temperatura baja para favorecer respuestas consistentes.
    TEMPERATURE = 0.2

    # No aumentarlo mientras estemos controlando el TPM gratuito.
    MAX_COMPLETION_TOKENS = 2200

    # Máximo de nombres de platos que se mandan como historial.
    MAX_COMIDAS_PREVIAS = 10

    # Evidencia RAG.
    MAX_EVIDENCIA_RESULTADOS = 2
    MAX_EVIDENCIA_CHARS = 900
    

    def __init__(self):
        self.llm = ChatGroq(
            model=self.MODEL,
            api_key=groq_api_key,
            temperature=self.TEMPERATURE,
            reasoning_effort="low",
            model_kwargs={
                "response_format": {"type": "json_object"},
                "max_completion_tokens": self.MAX_COMPLETION_TOKENS,
                "include_reasoning": False,
            },
        )

        self.system_prompt = load_prompt("dietist_prompt.md")

        logger.info(
            "DietistAgent inicializado | modelo=%s | max_completion_tokens=%s | "
            "presupuesto TPM global=%s",
            self.MODEL,
            self.MAX_COMPLETION_TOKENS,
            groq_token_budget.budget,
        )

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
        """

        if dia_semana not in DIAS_SEMANA:
            raise ValueError(
                f"Día '{dia_semana}' no válido. Usa uno de: {DIAS_SEMANA}"
            )

        # --------------------------------------------------------------
        # 1. Limitar comidas previas
        # --------------------------------------------------------------

        comidas_previas = list(comidas_previas or [])
        comidas_previas = comidas_previas[-self.MAX_COMIDAS_PREVIAS:]

        logger.info(
            "DietistAgent: generando %s | comidas_previas=%d",
            dia_semana,
            len(comidas_previas),
        )

        # --------------------------------------------------------------
        # 2. Calcular distribución de kcal sin perder horarios
        # --------------------------------------------------------------

        calculos_enriquecidos = self._calcular_distribucion_kcal(
            calculos,
            analisis,
        )

        # --------------------------------------------------------------
        # 3. Buscar evidencia RAG
        # --------------------------------------------------------------

        evidencia_texto = self._obtener_evidencia_rag(
            perfil=perfil,
        )

        # --------------------------------------------------------------
        # 4. Preparar system prompt
        # --------------------------------------------------------------

        system_prompt = self.system_prompt.replace(
            "{evidencia_cientifica}",
            evidencia_texto,
        )

        # --------------------------------------------------------------
        # 5. Preparar mensaje compacto
        # --------------------------------------------------------------

        mensaje_usuario = self._construir_mensaje(
            perfil=perfil,
            calculos=calculos_enriquecidos,
            analisis=analisis,
            dia_semana=dia_semana,
            comidas_previas=comidas_previas,
        )

        # --------------------------------------------------------------
        # 6. Llamar a Groq
        # --------------------------------------------------------------

        texto_respuesta = self._llamar_groq(
            mensaje_usuario=mensaje_usuario,
            dia_semana=dia_semana,
            system_prompt=system_prompt,
        )

        # --------------------------------------------------------------
        # 7. Parsear JSON
        # --------------------------------------------------------------

        menu_dia = self._parsear_respuesta(
            texto_respuesta,
            dia_semana,
        )

        # --------------------------------------------------------------
        # 8. Validación/corrección nutricional
        # --------------------------------------------------------------

        menu_dia_corregido = validar_y_corregir_dia(menu_dia)

        # --------------------------------------------------------------
        # 9. Detector de alérgenos
        # --------------------------------------------------------------

        from backend.utils.allergen_detector import detectar_alergenos_dia

        menu_con_alergenos = detectar_alergenos_dia(
            menu_dia_corregido
        )

        logger.info(
            "DietistAgent: %s generado correctamente.",
            dia_semana,
        )

        return menu_con_alergenos

    # ------------------------------------------------------------------
    # Semana completa
    # ------------------------------------------------------------------

    def generar_semana(
        self,
        perfil: dict,
        calculos: dict,
        analisis: dict,
    ) -> dict:
        """
        Genera los 7 días secuencialmente.

        Solo mantiene los últimos MAX_COMIDAS_PREVIAS platos para
        controlar el tamaño del prompt.
        """

        menu_semana: dict = {}
        comidas_previas: list[str] = []

        for dia in DIAS_SEMANA:
            logger.info(
                "DietistAgent: generando menú para %s...",
                dia,
            )

            menu_dia = self.generar_dia(
                perfil=perfil,
                calculos=calculos,
                analisis=analisis,
                dia_semana=dia,
                comidas_previas=comidas_previas,
            )

            menu_semana[dia] = menu_dia

            # ----------------------------------------------------------
            # Recoger platos del día
            # ----------------------------------------------------------

            nuevos_nombres = self._extraer_nombres_platos(
                menu_dia
            )

            comidas_previas.extend(nuevos_nombres)

            # IMPORTANTE:
            # No dejamos crecer esta lista hasta 30-35 platos.
            comidas_previas = comidas_previas[
                -self.MAX_COMIDAS_PREVIAS:
            ]

            logger.info(
                "DietistAgent: historial de platos para siguiente día=%d",
                len(comidas_previas),
            )

        return menu_semana

    # ------------------------------------------------------------------
    # Distribución kcal
    # ------------------------------------------------------------------

    def _calcular_distribucion_kcal(
        self,
        calculos: dict,
        analisis: dict,
    ) -> dict:
        """
        Añade kcal por comida sin eliminar información previa como
        horarios o porcentajes.
        """

        calorias_objetivo = calculos.get(
            "calorias_objetivo",
            0,
        )

        distribucion = (
            analisis.get("distribucion_comidas", {})
            or {}
        )

        definiciones = {
            "desayuno": (
                "desayuno_pct",
                25,
            ),
            "media_manana": (
                "media_manana_pct",
                10,
            ),
            "comida": (
                "comida_pct",
                35,
            ),
            "merienda": (
                "merienda_pct",
                10,
            ),
            "cena": (
                "cena_pct",
                20,
            ),
        }

        distribucion_resultado = {}

        for nombre, (clave_pct, porcentaje_default) in definiciones.items():
            porcentaje = distribucion.get(
                clave_pct,
                porcentaje_default,
            )

            kcal = round(
                calorias_objetivo * porcentaje / 100
            )

            # Intentamos conservar información de horario si existe.
            bloque_original = distribucion.get(nombre)

            hora = None

            if isinstance(bloque_original, dict):
                hora = bloque_original.get("hora")

            elif isinstance(bloque_original, str):
                hora = bloque_original

            distribucion_resultado[nombre] = {
                "kcal": kcal,
                "porcentaje": porcentaje,
                "hora": hora,
            }

        calculos_copia = dict(calculos)

        calculos_copia[
            "distribucion_comidas"
        ] = distribucion_resultado

        return calculos_copia

    # ------------------------------------------------------------------
    # RAG
    # ------------------------------------------------------------------

    def _obtener_evidencia_rag(
        self,
        perfil: dict,
    ) -> str:
        """
        Busca una cantidad pequeña de evidencia científica y la
        recorta para evitar inflar el prompt.
        """

        try:
            from backend.rag.clinical_knowledge_search import (
                buscar_evidencia,
            )

            query_parts = []

            objetivo = perfil.get(
                "objetivo_principal"
            )

            if objetivo:
                query_parts.append(
                    str(objetivo)
                )

            patologias = list(
                dict.fromkeys(
                    (perfil.get("patologias") or [])
                    + (
                        perfil.get("patologias_activas")
                        or []
                    )
                )
            )

            if patologias:
                query_parts.extend(
                    str(p)
                    for p in patologias
                )

            query_rag = (
                " ".join(query_parts)
                if query_parts
                else "nutrition diet healthy meals"
            )

            logger.info(
                "DietistAgent RAG query: %s",
                query_rag,
            )

            evidencia = buscar_evidencia(
                query_rag,
                n_resultados=self.MAX_EVIDENCIA_RESULTADOS,
            )

            if not evidencia:
                return (
                    "No se encontró evidencia específica."
                )

            bloques = []

            for e in evidencia:
                texto = str(
                    e.get("texto", "")
                )[
                    : self.MAX_EVIDENCIA_CHARS
                ]

                bloque = (
                    f"--- {e.get('titulo', 'Documento')} "
                    f"({e.get('año', '')}) ---\n"
                    f"Fuente: {e.get('fuente', '')}\n"
                    f"Texto: {texto}"
                )

                bloques.append(bloque)

            return "\n\n".join(bloques)

        except Exception as exc:
            # El RAG no debe impedir generar el menú si falla.
            logger.warning(
                "DietistAgent: error buscando evidencia RAG: %s",
                exc,
            )

            return (
                "No se encontró evidencia específica."
            )

    # ------------------------------------------------------------------
    # Construcción del mensaje
    # ------------------------------------------------------------------

    def _construir_mensaje(
        self,
        perfil: dict,
        calculos: dict,
        analisis: dict,
        dia_semana: str,
        comidas_previas: list[str],
    ) -> str:
        """
        Construye el JSON de entrada para el modelo.

        Se evita indent=2 para ahorrar tokens.
        """

        entrada = {
            "perfil": perfil,
            "calculos": calculos,
            "analisis": analisis,
            "dia_semana": dia_semana,
            "comidas_previas": comidas_previas[
                -self.MAX_COMIDAS_PREVIAS:
            ],
        }

        return json.dumps(
            entrada,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    # ------------------------------------------------------------------
    # Estimación de tokens
    # ------------------------------------------------------------------

    @staticmethod
    def _estimar_tokens(texto: str) -> int:
        """
        Estimación conservadora de tokens.

        No sustituye el contador real de Groq, pero sirve como
        protección local para evitar peticiones demasiado grandes.
        """

        if not texto:
            return 0

        # Aproximación conservadora para texto español/JSON.
        return max(
            1,
            (len(texto) + 3) // 4,
        )


    # ------------------------------------------------------------------
    # Llamada Groq
    # ------------------------------------------------------------------
    @reintentar_llamada_llm(
        max_intentos=3,
        retardo_inicial=15.0,
        backoff=1.5,
    )
    def _llamar_groq(
        self,
        mensaje_usuario: str,
        dia_semana: str,
        system_prompt: str,
    ) -> str:
        """
        Hace la llamada a Groq utilizando el presupuesto TPM global.
        """

        tokens_prompt = (
            self._estimar_tokens(system_prompt)
            + self._estimar_tokens(mensaje_usuario)
        )

        tokens_peticion = (
            tokens_prompt
            + self.MAX_COMPLETION_TOKENS
        )

        logger.info(
            "DietistAgent: estimación petición %s | "
            "prompt≈%d tokens | max_completion=%d | "
            "total potencial≈%d",
            dia_semana,
            tokens_prompt,
            self.MAX_COMPLETION_TOKENS,
            tokens_peticion,
        )

        # --------------------------------------------------------------
        # Protección contra una petición individual demasiado grande.
        # --------------------------------------------------------------

        if tokens_peticion > groq_token_budget.budget:
            raise ValueError(
                "Petición demasiado grande para el presupuesto "
                f"seguro de Groq: ≈{tokens_peticion} tokens "
                f"(límite local={groq_token_budget.budget}). "
                "Reduce prompt/RAG/datos antes de llamar."
            )

        # --------------------------------------------------------------
        # Reservar espacio en el presupuesto GLOBAL.
        # --------------------------------------------------------------

        groq_token_budget.esperar_disponibilidad(
            tokens_peticion
        )

        mensajes = [
            SystemMessage(
                content=system_prompt
            ),
            HumanMessage(
                content=mensaje_usuario
            ),
        ]

        logger.info(
            "DietistAgent: llamando a Groq "
            "(modelo=%s) para %s",
            self.MODEL,
            dia_semana,
        )

        respuesta = self.llm.invoke(
            mensajes
        )

        # --------------------------------------------------------------
        # Información de diagnóstico
        # --------------------------------------------------------------

        logger.info(
            "DietistAgent: respuesta recibida para %s",
            dia_semana,
        )

        logger.info(
            "DietistAgent: finish_reason=%s",
            getattr(
                respuesta,
                "response_metadata",
                {},
            ).get(
                "finish_reason"
            ),
        )

        logger.info(
            "DietistAgent: content_length=%d",
            len(
                respuesta.content or ""
            ),
        )

        logger.debug(
            "DietistAgent content: %r",
            respuesta.content,
        )

        contenido = (
            respuesta.content or ""
        ).strip()

        if not contenido:
            raise ValueError(
                f"El modelo devolvió una respuesta vacía "
                f"para {dia_semana}."
            )

        return contenido

    # ------------------------------------------------------------------
    # Parsear respuesta
    # ------------------------------------------------------------------

    def _parsear_respuesta(
        self,
        texto: str,
        dia_semana: str,
    ) -> dict:
        """
        Parsea la respuesta JSON devuelta por Groq.
        """

        if not texto or not texto.strip():
            raise ValueError(
                f"El modelo devolvió una respuesta vacía "
                f"para {dia_semana}."
            )

        texto = texto.strip()

        # --------------------------------------------------------------
        # 1. JSON directo
        # --------------------------------------------------------------

        try:
            resultado = json.loads(
                texto
            )

            if not isinstance(
                resultado,
                dict,
            ):
                raise ValueError(
                    f"El JSON devuelto para {dia_semana} "
                    "no es un objeto."
                )

            return resultado

        except json.JSONDecodeError:
            pass

        # --------------------------------------------------------------
        # 2. Fallback por si Groq envolviera el JSON en texto
        # --------------------------------------------------------------

        patron = r"\{[\s\S]*\}"

        match = re.search(
            patron,
            texto,
        )

        if match:
            try:
                resultado = json.loads(
                    match.group()
                )

                if isinstance(
                    resultado,
                    dict,
                ):
                    return resultado

            except json.JSONDecodeError:
                pass

        logger.error(
            "DietistAgent: respuesta no parseable "
            "para %s:\n%s",
            dia_semana,
            texto[:2000],
        )

        raise ValueError(
            f"El modelo no devolvió JSON válido "
            f"para {dia_semana}. "
            f"Respuesta recibida:\n"
            f"{texto[:1000]}"
        )

    # ------------------------------------------------------------------
    # Extraer nombres
    # ------------------------------------------------------------------

    def _extraer_nombres_platos(
        self,
        menu_dia: dict,
    ) -> list[str]:
        """
        Extrae los nombres de los platos de un día.
        """

        nombres = []

        comidas = menu_dia.get(
            "comidas",
            {},
        )

        if not isinstance(
            comidas,
            dict,
        ):
            return nombres

        for toma in comidas.values():

            if (
                isinstance(toma, dict)
                and toma.get("nombre")
            ):
                nombres.append(
                    str(toma["nombre"])
                )

        return nombres


# ---------------------------------------------------------------------------
# Ejecución directa
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import io

    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer,
        encoding="utf-8",
        errors="replace",
    )

    print("=" * 60)
    print(" TEST — DietistAgent")
    print("=" * 60)

    print()
    print(
        "IMPORTANTE: este test directo está desactivado "
        "para evitar llamadas innecesarias a Groq."
    )
    print()
    print(
        "Prueba primero el endpoint normal de generación "
        "de un solo día."
    )