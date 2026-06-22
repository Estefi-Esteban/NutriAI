"""
vision_agent.py
----------------
Agente de Visión — analiza fotos de platos de comida.

Flujo:
1. Recibe una imagen (bytes) en base64
2. La envía al modelo multimodal de Groq (llama-3.2-90b-vision-preview)
3. Obtiene lista de alimentos con cantidades estimadas en gramos
4. Enriquece cada alimento buscando macros verificados en ChromaDB
5. Calcula los totales del plato y devuelve el resultado estructurado

El modelo SOLO identifica qué hay y cuánto (estimación visual).
Los macros reales vienen de ChromaDB, nunca del modelo.
"""

import base64
import json
import re
import logging
from typing import Optional

import httpx
from backend.config import GROQ_API_KEY
from backend.agents.prompts.prompt_loader import load_prompt
from backend.rag.food_search import buscar_mejor_match

logger = logging.getLogger(__name__)

# Modelos con fallback: el grande primero, si hay rate-limit usamos el pequeño
_MODELOS_VISION = [
    "llama-3.2-90b-vision-preview",
    "llama-3.2-11b-vision-preview",
]

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
UMBRAL_CONFIANZA_RAG = 0.65  # similitud mínima en ChromaDB para aceptar el match


class VisionAgent:

    def __init__(self):
        self.system_prompt = load_prompt("vision_prompt.md")
        self.headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Punto de entrada principal
    # ------------------------------------------------------------------

    def analizar_plato(self, imagen_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
        """
        Analiza una imagen de plato y devuelve macros totales con detalle por alimento.

        Args:
            imagen_bytes: contenido binario de la imagen (jpg, png, webp)
            mime_type: tipo MIME de la imagen

        Returns:
            Dict con alimentos, macros por alimento y totales del plato
        """
        b64_imagen = base64.b64encode(imagen_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64_imagen}"

        # Paso 1 — Detección visual (LLM multimodal)
        deteccion = self._detectar_alimentos(data_url)

        # Paso 2 — Enriquecimiento con ChromaDB
        alimentos_enriquecidos = self._enriquecer_con_rag(
            deteccion.get("alimentos_detectados", [])
        )

        # Paso 3 — Calcular totales
        totales = self._calcular_totales(alimentos_enriquecidos)

        return {
            "descripcion_plato": deteccion.get("descripcion_plato", ""),
            "calidad_imagen": deteccion.get("calidad_imagen", "ACEPTABLE"),
            "advertencia": deteccion.get("advertencia"),
            "alimentos": alimentos_enriquecidos,
            "totales": totales,
            "disclaimer": (
                "⚠️ Las cantidades son estimaciones visuales. "
                "Los macros reales pueden variar un ±20% según la preparación exacta. "
                "Corrígelas si conoces los pesos reales."
            ),
        }

    # ------------------------------------------------------------------
    # Paso 1: Llamada al modelo multimodal
    # ------------------------------------------------------------------

    def _detectar_alimentos(self, data_url: str) -> dict:
        """Envía la imagen al modelo Groq Vision y parsea la respuesta."""
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
                                "Analiza este plato de comida y devuelve la información "
                                "en el formato JSON indicado."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url},
                        },
                    ],
                },
            ],
            "temperature": 0.1,
            "max_tokens": 1024,
        }

        for modelo in _MODELOS_VISION:
            payload["model"] = modelo
            try:
                logger.info("VisionAgent: usando modelo %s", modelo)
                respuesta = httpx.post(
                    GROQ_ENDPOINT,
                    headers=self.headers,
                    json=payload,
                    timeout=60.0,
                )
                respuesta.raise_for_status()
                contenido = respuesta.json()["choices"][0]["message"]["content"]
                return self._parsear_deteccion(contenido)

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and modelo != _MODELOS_VISION[-1]:
                    logger.warning(
                        "VisionAgent: rate-limit en %s, intentando con %s",
                        modelo,
                        _MODELOS_VISION[1],
                    )
                    continue
                logger.error("VisionAgent: error HTTP %s — %s", e.response.status_code, e)
                raise

        raise RuntimeError("VisionAgent: todos los modelos fallaron o están rate-limited")

    def _parsear_deteccion(self, texto: str) -> dict:
        """Extrae el JSON de la respuesta del modelo (3 capas de fallback)."""
        # Capa 1: JSON puro
        try:
            return json.loads(texto.strip())
        except json.JSONDecodeError:
            pass

        # Capa 2: JSON dentro de ```json ... ```
        match_md = re.search(r"```(?:json)?\s*([\s\S]*?)```", texto)
        if match_md:
            try:
                return json.loads(match_md.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Capa 3: primer { ... } de la respuesta
        match_raw = re.search(r"\{[\s\S]*\}", texto)
        if match_raw:
            try:
                return json.loads(match_raw.group())
            except json.JSONDecodeError:
                pass

        logger.error("VisionAgent: no se pudo parsear la detección visual")
        return {"alimentos_detectados": [], "descripcion_plato": texto[:200], "calidad_imagen": "MALA"}

    # ------------------------------------------------------------------
    # Paso 2: Enriquecimiento con ChromaDB
    # ------------------------------------------------------------------

    def _enriquecer_con_rag(self, alimentos_detectados: list[dict]) -> list[dict]:
        """
        Para cada alimento detectado, busca sus macros verificados en ChromaDB
        y calcula los valores para la cantidad estimada.
        """
        resultado = []

        for alimento in alimentos_detectados:
            nombre = alimento.get("nombre", "")
            cantidad_g = float(alimento.get("cantidad_estimada_g", 100))
            confianza_vision = alimento.get("confianza", "MEDIA")
            notas = alimento.get("notas")

            entrada = {
                "nombre_detectado": nombre,
                "cantidad_g": cantidad_g,
                "confianza_vision": confianza_vision,
                "notas_vision": notas,
                "verificado_rag": False,
                "nombre_rag": None,
                "similitud_rag": None,
                "kcal": None,
                "proteinas_g": None,
                "carbos_g": None,
                "grasas_g": None,
            }

            try:
                match = buscar_mejor_match(nombre)
                if match and match["similitud"] >= UMBRAL_CONFIANZA_RAG:
                    factor = cantidad_g / 100.0
                    entrada["verificado_rag"] = True
                    entrada["nombre_rag"] = match["nombre"]
                    entrada["similitud_rag"] = match["similitud"]
                    entrada["kcal"] = round(match["kcal_100g"] * factor, 1)
                    entrada["proteinas_g"] = round(match["proteinas_100g"] * factor, 1)
                    entrada["carbos_g"] = round(match["carbos_100g"] * factor, 1)
                    entrada["grasas_g"] = round(match["grasas_100g"] * factor, 1)
                else:
                    logger.info(
                        "VisionAgent: sin match RAG para '%s' (similitud: %s)",
                        nombre,
                        match["similitud"] if match else "N/A",
                    )
            except Exception as e:
                logger.warning("VisionAgent: error RAG para '%s': %s", nombre, e)

            resultado.append(entrada)

        return resultado

    # ------------------------------------------------------------------
    # Paso 3: Totales del plato
    # ------------------------------------------------------------------

    def _calcular_totales(self, alimentos: list[dict]) -> dict:
        """Suma los macros de todos los alimentos verificados por RAG."""
        totales = {
            "kcal": 0.0,
            "proteinas_g": 0.0,
            "carbos_g": 0.0,
            "grasas_g": 0.0,
            "alimentos_sin_datos": [],
        }

        for a in alimentos:
            if a["verificado_rag"]:
                totales["kcal"] += a["kcal"] or 0.0
                totales["proteinas_g"] += a["proteinas_g"] or 0.0
                totales["carbos_g"] += a["carbos_g"] or 0.0
                totales["grasas_g"] += a["grasas_g"] or 0.0
            else:
                totales["alimentos_sin_datos"].append(a["nombre_detectado"])

        # Redondear
        for k in ["kcal", "proteinas_g", "carbos_g", "grasas_g"]:
            totales[k] = round(totales[k], 1)

        return totales
