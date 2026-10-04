"""
pdf_extractor.py
-----------------
Extrae texto de analíticas de sangre en formato PDF o imagen.
Soporta dos modos:
  - PDF digital (texto embebido) → pdfplumber
  - PDF escaneado o imagen (foto) → OCR con pytesseract
"""

import os
import re
import logging
from pathlib import Path
from typing import Optional

import pdfplumber
from PIL import Image
import pytesseract

from backend.config import TESSERACT_PATH

logger = logging.getLogger(__name__)

# Configurar ruta de Tesseract si está en .env
if TESSERACT_PATH:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


def extraer_texto_pdf(ruta_pdf: str) -> str:
    """
    Extrae todo el texto de un PDF digital (con texto embebido).
    Si el PDF está escaneado y no tiene texto, devuelve string vacío.
    """
    texto_total = []

    with pdfplumber.open(ruta_pdf) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text()
            if texto:
                texto_total.append(texto)

    return "\n".join(texto_total)


def extraer_texto_imagen(ruta_imagen: str) -> str:
    """
    Extrae texto de una imagen (foto de analítica) usando OCR.
    Acepta: JPG, PNG, WEBP, BMP
    """
    imagen = Image.open(ruta_imagen)

    # Preprocesamiento básico para mejorar el OCR
    imagen = imagen.convert("L")          # escala de grises
    imagen = imagen.point(lambda x: 0 if x < 140 else 255)  # binarizar

    texto = pytesseract.image_to_string(
        imagen,
        lang="spa",          # español
        config="--psm 6",    # bloque de texto uniforme
    )

    return texto


def extraer_texto_analitica(ruta_archivo: str) -> str:
    """
    Punto de entrada principal. Detecta automáticamente si es PDF o imagen
    y usa el método de extracción adecuado.
    """
    extension = Path(ruta_archivo).suffix.lower()

    if extension == ".pdf":
        texto = extraer_texto_pdf(ruta_archivo)
        if not texto.strip():
            logger.info("PDF sin texto embebido, intentando OCR...")
            # Si el PDF no tenía texto, intentamos convertirlo a imagen
            # (requiere poppler — lo añadimos en una iteración posterior si hace falta)
            return ""
        return texto

    elif extension in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
        return extraer_texto_imagen(ruta_archivo)

    else:
        raise ValueError(f"Formato no soportado: {extension}. Usa PDF, JPG o PNG.")


# ── Parser de valores numéricos ──────────────────────────────────────────────

# Valores de referencia clínicos estándar
RANGOS_REFERENCIA = {
    "glucosa":       {"min": 70,   "max": 100,  "unidad": "mg/dL"},
    "hba1c":         {"min": 0,    "max": 5.7,  "unidad": "%"},
    "colesterol":    {"min": 0,    "max": 200,  "unidad": "mg/dL"},
    "ldl":           {"min": 0,    "max": 130,  "unidad": "mg/dL"},
    "hdl_hombre":    {"min": 40,   "max": 999,  "unidad": "mg/dL"},
    "hdl_mujer":     {"min": 50,   "max": 999,  "unidad": "mg/dL"},
    "trigliceridos": {"min": 0,    "max": 150,  "unidad": "mg/dL"},
    "ferritina_h":   {"min": 30,   "max": 400,  "unidad": "ng/mL"},
    "ferritina_m":   {"min": 13,   "max": 150,  "unidad": "ng/mL"},
    "vitamina_d":    {"min": 30,   "max": 100,  "unidad": "ng/mL"},
    "tsh":           {"min": 0.4,  "max": 4.0,  "unidad": "mIU/L"},
    "vitamina_b12":  {"min": 200,  "max": 900,  "unidad": "pg/mL"},
    "acido_urico_h": {"min": 3.5,  "max": 7.2,  "unidad": "mg/dL"},
    "acido_urico_m": {"min": 2.6,  "max": 6.0,  "unidad": "mg/dL"},
    "pcr":           {"min": 0,    "max": 1.0,  "unidad": "mg/L"},
}

def evaluar_valores_analitica(valores: dict, sexo: str | None = None) -> dict:
    """
    Compara los valores analíticos extraídos con los rangos de referencia
    internos de NutriAI.

    Importante:
    - Estos rangos son orientativos y pueden variar según el laboratorio.
    - La función no realiza diagnósticos.
    - Devuelve únicamente una clasificación numérica respecto a los rangos
      configurados.
    """
    resultados = {}

    sexo_normalizado = str(sexo or "").lower().strip()

    for marcador, valor in valores.items():
        try:
            valor = float(valor)
        except (TypeError, ValueError):
            continue

        clave_rango = marcador

        if marcador == "hdl":
            if sexo_normalizado in {"hombre", "masculino", "m"}:
                clave_rango = "hdl_hombre"
            elif sexo_normalizado in {"mujer", "femenino", "f"}:
                clave_rango = "hdl_mujer"
            else:
                resultados[marcador] = {
                    "valor": valor,
                    "estado": "sin_rango_sexo",
                }
                continue

        elif marcador == "ferritina":
            if sexo_normalizado in {"hombre", "masculino", "m"}:
                clave_rango = "ferritina_h"
            elif sexo_normalizado in {"mujer", "femenino", "f"}:
                clave_rango = "ferritina_m"
            else:
                resultados[marcador] = {
                    "valor": valor,
                    "estado": "sin_rango_sexo",
                }
                continue

        elif marcador == "acido_urico":
            if sexo_normalizado in {"hombre", "masculino", "m"}:
                clave_rango = "acido_urico_h"
            elif sexo_normalizado in {"mujer", "femenino", "f"}:
                clave_rango = "acido_urico_m"
            else:
                resultados[marcador] = {
                    "valor": valor,
                    "estado": "sin_rango_sexo",
                }
                continue

        rango = RANGOS_REFERENCIA.get(clave_rango)

        if not rango:
            resultados[marcador] = {
                "valor": valor,
                "estado": "sin_rango",
            }
            continue

        minimo = rango["min"]
        maximo = rango["max"]

        if valor < minimo:
            estado = "bajo"
        elif valor > maximo:
            estado = "alto"
        else:
            estado = "normal"

        resultados[marcador] = {
            "valor": valor,
            "estado": estado,
            "rango_referencia": {
                "min": minimo,
                "max": maximo,
                "unidad": rango["unidad"],
            },
        }

    return resultados


def parsear_valores_analitica(texto: str) -> dict:
    """
    Busca valores numéricos conocidos en el texto extraído de la analítica.
    Devuelve un dict con los marcadores encontrados y sus valores.

    Estrategia: patrones regex para buscar el nombre del marcador
    seguido del valor numérico (con decimales y posibles unidades).
    """
    valores = {}

    patrones = {
        "glucosa":       r"glucosa[^\d]*(\d+[.,]?\d*)",
        "hba1c":         r"hb\s*a1c[^\d]*(\d+[.,]\d+)",
        "colesterol":    r"colesterol\s*total[^\d]*(\d+[.,]?\d*)",
        "ldl":           r"ldl[^\d]*(\d+[.,]?\d*)",
        "hdl":           r"hdl[^\d]*(\d+[.,]?\d*)",
        "trigliceridos": r"triglic[eé]ridos[^\d]*(\d+[.,]?\d*)",
        "ferritina":     r"ferritina[^\d]*(\d+[.,]?\d*)",
        "vitamina_d":    r"vitamina\s*d[^\d]*(\d+[.,]?\d*)",
        "tsh":           r"tsh[^\d]*(\d+[.,]\d+)",
        "vitamina_b12":  r"(?:vitamina\s*b12|cobalamina)[^\d]*(\d+[.,]?\d*)",
        "acido_urico":   r"[aá]cido\s*[uú]rico[^\d]*(\d+[.,]?\d*)",
        "pcr":           r"(?:pcr|prote[ií]na\s*c\s*reactiva)[^\d]*(\d+[.,]\d+)",
    }

    texto_lower = texto.lower()

    for marcador, patron in patrones.items():
        match = re.search(patron, texto_lower)
        if match:
            valor_str = match.group(1).replace(",", ".")
            try:
                valores[marcador] = float(valor_str)
            except ValueError:
                pass

    logger.info("Valores encontrados en analítica: %s", list(valores.keys()))
    return valores
