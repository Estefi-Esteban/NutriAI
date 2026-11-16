"""
Agente de visión para análisis nutricional de platos.

La visión identifica alimentos, estima cantidades y puede aportar una estimación
nutricional de la ración visible. Qdrant aporta los valores nutricionales de
referencia por 100 g. Ambas fuentes se mantienen separadas y nunca se confunden.
"""
from __future__ import annotations

import base64
import json
import logging
import math
import re
from collections.abc import Mapping
from typing import Any

import httpx

from backend.config import GROQ_API_KEY
from backend.agents.prompts.prompt_loader import load_prompt
from backend.rag.food_search import buscar_mejor_match_vision

logger = logging.getLogger(__name__)

_MODELOS_VISION = (
    "qwen/qwen3.8-27b",
)

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
UMBRAL_CONFIANZA_RAG = 0.55
TIMEOUT_GROQ = 60.0
MAX_CANTIDAD_G = 2000.0

MACROS = ("kcal", "proteinas_g", "carbos_g", "grasas_g")
CLAVES_ESTIMADAS = {
    "kcal": ("kcal_estimado", "kcal_estimada", "kcal", "calorias", "calorías"),
    "proteinas_g": (
        "proteinas_estimadas", "proteinas_estimadas_g", "proteinas_g",
        "proteinas", "proteína", "proteínas",
    ),
    "carbos_g": (
        "carbos_estimados", "carbos_estimados_g", "carbos_g",
        "carbos", "carbohidratos",
    ),
    "grasas_g": (
        "grasas_estimadas", "grasas_estimadas_g", "grasas_g",
        "grasas", "grasa",
    ),
}

INSTRUCCIONES_MACROS_VISION = """
IMPORTANTE SOBRE LAS ESTIMACIONES NUTRICIONALES:
- Si incluyes kcal, proteínas, carbohidratos o grasas, estima los valores
  correspondientes a la RACIÓN COMPLETA de ese alimento que aparece en la foto.
- No devuelvas valores nutricionales por 100 gramos.
- No inventes valores: si no puedes estimar razonablemente un macro, omite su
  campo o devuelve null.
- cantidad_estimada_g debe ser la cantidad estimada en gramos de esa misma
  ración visible.
- Los valores nutricionales que proporciones son estimaciones visuales, nunca
  datos verificados de una base nutricional.
"""


def _numero_valido(valor: object) -> float | None:
    """Convierte números finitos no negativos; ausencias siguen siendo None."""
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(numero) or numero < 0:
        return None
    return numero


def _sumar_fuente(
    alimentos: list[dict[str, Any]],
    campo_origen: str,
) -> tuple[dict[str, float | None], list[str]]:
    """
    Suma una fuente sin convertir ausencias en cero.

    Si falta un macro en cualquiera de los alimentos incluidos, el total de ese
    macro se devuelve como None y se informa en macros_incompletos.
    """
    totales: dict[str, float | None] = {}
    incompletos: list[str] = []

    if not alimentos:
        return {macro: None for macro in MACROS}, list(MACROS)

    for macro in MACROS:
        valores: list[float] = []
        for alimento in alimentos:
            datos = alimento.get(campo_origen)
            valor = _numero_valido(datos.get(macro)) if isinstance(datos, Mapping) else None
            if valor is None:
                incompletos.append(macro)
                break
            valores.append(valor)
        else:
            totales[macro] = round(sum(valores), 1)
            continue

        totales[macro] = None

    return totales, sorted(set(incompletos))


class VisionAgent:
    def __init__(self) -> None:
        prompt = load_prompt("vision_prompt.md")
        self.system_prompt = f"{prompt}\n\n{INSTRUCCIONES_MACROS_VISION}"
        self.headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }

    def analizar_plato(
        self,
        imagen_bytes: bytes,
        mime_type: str = "image/jpeg",
    ) -> dict[str, Any]:
        if not imagen_bytes:
            raise ValueError("La imagen está vacía.")
        if mime_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError("Tipo MIME de imagen no permitido.")

        data_url = (
            f"data:{mime_type};base64,"
            f"{base64.b64encode(imagen_bytes).decode('ascii')}"
        )
        deteccion = self._detectar_alimentos(data_url)
        detectados = deteccion.get("alimentos_detectados", [])
        if not isinstance(detectados, list):
            raise ValueError("El modelo no devolvió una lista de alimentos.")

        alimentos = self._enriquecer_con_rag(detectados)
        totales = self._calcular_totales(alimentos)

        advertencias: list[str] = []
        advertencia_modelo = deteccion.get("advertencia")
        if advertencia_modelo:
            advertencias.append(str(advertencia_modelo))

        if totales["alimentos_sin_datos"]:
            advertencias.append(
                "Hay alimentos sin información nutricional suficiente."
            )
        if totales["alimentos_con_error_rag"]:
            advertencias.append(
                "No se pudo consultar la base nutricional para algunos alimentos."
            )

        return {
            "descripcion_plato": str(deteccion.get("descripcion_plato") or ""),
            "calidad_imagen": self._calidad_imagen(
                deteccion.get("calidad_imagen")
            ),
            "advertencia": " ".join(advertencias) or None,
            "alimentos": alimentos,
            # Campo histórico: ahora representa explícitamente el total combinado.
            "totales": totales["totales_combinados"],
            "totales_estimados": totales["totales_estimados"],
            "totales_verificados": totales["totales_verificados"],
            "totales_combinados": totales["totales_combinados"],
            "validacion_nutricional": {
                "alimentos_verificados": totales["alimentos_verificados"],
                "total_alimentos": len(alimentos),
                "totales_verificados_completos": totales[
                    "totales_verificados_completos"
                ],
                "alimentos_con_error_rag": totales["alimentos_con_error_rag"],
            },
            "disclaimer": (
                "Las cantidades y los macros estimados por visión son "
                "aproximaciones de la ración visible. Los macros verificados "
                "proceden de Qdrant y se calculan según la cantidad estimada. "
                "Los totales combinados pueden incluir ambas fuentes."
            ),
        }

    @staticmethod
    def _calidad_imagen(valor: object) -> str:
        calidad = str(valor or "ACEPTABLE").strip().upper()
        return calidad if calidad in {"BUENA", "ACEPTABLE", "MALA"} else "ACEPTABLE"

    def _detectar_alimentos(self, data_url: str) -> dict[str, Any]:
        payload = {
            "model": _MODELOS_VISION[0],
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Analiza este plato. Devuelve únicamente el JSON "
                                "solicitado en las instrucciones."
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            "temperature": 0.1,
            "max_tokens": 1200,
        }

        ultimo_error: Exception | None = None
        for indice, modelo in enumerate(_MODELOS_VISION):
            payload["model"] = modelo
            try:
                logger.info("VisionAgent: consultando modelo %s", modelo)
                with httpx.Client(timeout=TIMEOUT_GROQ) as cliente:
                    respuesta = cliente.post(
                        GROQ_ENDPOINT,
                        headers=self.headers,
                        json=payload,
                    )
                respuesta.raise_for_status()
                contenido = respuesta.json()["choices"][0]["message"]["content"]
                if not isinstance(contenido, str) or not contenido.strip():
                    raise ValueError("Respuesta vacía del modelo de visión.")
                return self._parsear_deteccion(contenido)

            except httpx.HTTPStatusError as exc:
                ultimo_error = exc
                if exc.response.status_code == 429 and indice < len(_MODELOS_VISION) - 1:
                    logger.warning(
                        "Rate limit en %s; probando modelo alternativo.", modelo
                    )
                    continue
                raise RuntimeError(
                    f"El proveedor de visión respondió HTTP {exc.response.status_code}."
                ) from exc
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
                ultimo_error = exc
                logger.warning("Fallo con modelo %s: %s", modelo, exc)
                if indice < len(_MODELOS_VISION) - 1:
                    continue

        raise RuntimeError("No se pudo completar el análisis visual.") from ultimo_error

    @staticmethod
    def _parsear_deteccion(texto: str) -> dict[str, Any]:
        """Acepta JSON directo o contenido dentro de un bloque Markdown."""
        texto = texto.strip()
        candidatos = [texto]
        bloque = re.search(r"```(?:json)?\s*(.*?)```", texto, flags=re.I | re.S)
        if bloque:
            candidatos.insert(0, bloque.group(1).strip())

        for candidato in candidatos:
            try:
                datos = json.loads(candidato)
            except json.JSONDecodeError:
                continue
            if isinstance(datos, dict):
                return datos

        decoder = json.JSONDecoder()
        for indice, caracter in enumerate(texto):
            if caracter != "{":
                continue
            try:
                datos, _ = decoder.raw_decode(texto[indice:])
            except json.JSONDecodeError:
                continue
            if isinstance(datos, dict):
                return datos

        raise ValueError("El modelo de visión no devolvió un JSON válido.")

    @staticmethod
    def _extraer_valor_tolerante(
        alimento: Mapping[str, Any],
        claves: tuple[str, ...] | list[str],
        default: float | None = None,
    ) -> float | None:
        for clave in claves:
            if clave in alimento:
                valor = _numero_valido(alimento[clave])
                if valor is not None:
                    return valor
        return default

    def _enriquecer_con_rag(
        self,
        alimentos_detectados: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        resultado: list[dict[str, Any]] = []

        for alimento in alimentos_detectados:
            if not isinstance(alimento, Mapping):
                logger.warning("Elemento de detección ignorado: no es un objeto.")
                continue

            nombre = str(alimento.get("nombre") or "").strip()
            cantidad = _numero_valido(alimento.get("cantidad_estimada_g"))
            cantidad_valida = cantidad is not None and 0 < cantidad <= MAX_CANTIDAD_G
            cantidad_g = cantidad if cantidad_valida else None

            confianza = str(alimento.get("confianza") or "MEDIA").strip().upper()
            if confianza not in {"ALTA", "MEDIA", "BAJA"}:
                confianza = "MEDIA"

            macros_estimados = {
                macro: self._extraer_valor_tolerante(
                    alimento, CLAVES_ESTIMADAS[macro]
                )
                for macro in MACROS
            }

            entrada: dict[str, Any] = {
                "nombre_detectado": nombre or "Alimento no identificado",
                "cantidad_g": cantidad_g,
                "confianza_vision": confianza,
                "notas_vision": alimento.get("notas"),
                "verificado_rag": False,
                "nombre_rag": None,
                "similitud_rag": None,
                "origen_macros": (
                    "estimacion_visual"
                    if any(v is not None for v in macros_estimados.values())
                    else "sin_datos"
                ),
                "motivo_no_verificado": None,
                "kcal": None,
                "proteinas_g": None,
                "carbos_g": None,
                "grasas_g": None,
                "macros_estimados": macros_estimados,
                "macros_verificados": None,
            }

            if not cantidad_valida:
                entrada["motivo_no_verificado"] = "cantidad_no_valida"
            elif not nombre:
                entrada["motivo_no_verificado"] = "nombre_no_disponible"
            else:
                try:
                    match = buscar_mejor_match_vision(nombre)
                except Exception:
                    logger.exception("Error RAG al buscar '%s'.", nombre)
                    entrada["motivo_no_verificado"] = "error_rag"
                    match = None

                if match is not None:
                    similitud = _numero_valido(match.get("similitud"))
                    campos_rag = {
                        "kcal": _numero_valido(match.get("kcal_100g")),
                        "proteinas_g": _numero_valido(match.get("proteinas_100g")),
                        "carbos_g": _numero_valido(match.get("carbos_100g")),
                        "grasas_g": _numero_valido(match.get("grasas_100g")),
                    }

                    if similitud is None or similitud < UMBRAL_CONFIANZA_RAG:
                        entrada["motivo_no_verificado"] = "similitud_insuficiente"
                    elif not all(v is not None for v in campos_rag.values()):
                        entrada["motivo_no_verificado"] = "datos_rag_incompletos"
                    else:
                        factor = cantidad_g / 100.0
                        macros_verificados = {
                            macro: round(valor * factor, 1)
                            for macro, valor in campos_rag.items()
                        }
                        entrada.update(
                            {
                                "verificado_rag": True,
                                "nombre_rag": str(match.get("nombre") or ""),
                                "similitud_rag": similitud,
                                "origen_macros": "qdrant",
                                "motivo_no_verificado": None,
                                "macros_verificados": macros_verificados,
                                **macros_verificados,
                            }
                        )
                elif entrada["motivo_no_verificado"] is None:
                    entrada["motivo_no_verificado"] = "sin_coincidencia"

            if not entrada["verificado_rag"]:
                # Las estimaciones se expresan para la ración visible completa.
                # No se escalan por gramos ni se presentan como datos de Qdrant.
                entrada.update(macros_estimados)

            resultado.append(entrada)

        return resultado

    def _calcular_totales(self, alimentos: list[dict[str, Any]]) -> dict[str, Any]:
        verificados = [a for a in alimentos if a.get("verificado_rag")]
        no_verificados = [a for a in alimentos if not a.get("verificado_rag")]

        solo_estimados = [
            a for a in no_verificados
            if any(
                _numero_valido((a.get("macros_estimados") or {}).get(m)) is not None
                for m in MACROS
            )
        ]

        valores_verificados, incompletos_verificados = _sumar_fuente(
            verificados, "macros_verificados"
        )
        valores_estimados, incompletos_estimados = _sumar_fuente(
            solo_estimados, "macros_estimados"
        )

        # Total combinado: por alimento se utiliza una sola fuente, nunca ambas.
        fuente_por_alimento = [
            {
                "macros": (
                    a.get("macros_verificados")
                    if a.get("verificado_rag")
                    else a.get("macros_estimados")
                )
            }
            for a in alimentos
        ]
        valores_combinados, incompletos_combinados = _sumar_fuente(
            fuente_por_alimento, "macros"
        )

        nombres_sin_datos = [
            a["nombre_detectado"]
            for a in no_verificados
            if not any(
                _numero_valido((a.get("macros_estimados") or {}).get(m)) is not None
                for m in MACROS
            )
        ]
        errores_rag = [
            a["nombre_detectado"]
            for a in no_verificados
            if a.get("motivo_no_verificado") == "error_rag"
        ]

        return {
            "totales_estimados": {
                **valores_estimados,
                "alimentos_incluidos": [a["nombre_detectado"] for a in solo_estimados],
                "macros_incompletos": incompletos_estimados,
            },
            "totales_verificados": {
                **valores_verificados,
                "alimentos_incluidos": [a["nombre_detectado"] for a in verificados],
                "macros_incompletos": incompletos_verificados,
                "es_parcial": len(verificados) != len(alimentos),
            },
            "totales_combinados": {
                **valores_combinados,
                "alimentos_incluidos": [a["nombre_detectado"] for a in alimentos],
                "macros_incompletos": incompletos_combinados,
            },
            "alimentos_sin_datos": nombres_sin_datos,
            "alimentos_con_error_rag": errores_rag,
            "alimentos_verificados": len(verificados),
            "totales_verificados_completos": (
                bool(alimentos)
                and len(verificados) == len(alimentos)
                and not incompletos_verificados
            ),
        }
