
"""
Ranking unificado de recuperación híbrida para NutriAI.

Combina señales léxicas y semánticas:
- Coincidencia exacta.
- Cobertura de términos.
- Frase completa.
- Orden de palabras.
- Similitud vectorial.
- Consenso entre recuperación textual y vectorial.

No utiliza diccionarios de alimentos ni reglas específicas
de categorías nutricionales.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from typing import Any


# Pesos experimentales iniciales.
PESOS_RANKING = {
    "nombre_exacto": 30.0,
    "cobertura": 25.0,
    "frase_completa": 15.0,
    "orden": 10.0,
    "similitud_vectorial": 15.0,
    "consenso": 5.0,
}


def _texto_seguro(valor: Any) -> str:
    """Convierte un valor en texto seguro."""
    if valor is None:
        return ""

    texto = str(valor).strip()

    if texto.casefold() in {"", "nan", "none", "null"}:
        return ""

    return texto


def _numero_seguro(valor: Any) -> float:
    """Convierte un valor numérico y evita NaN e infinitos."""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return 0.0

    if not math.isfinite(numero):
        return 0.0

    return max(0.0, min(1.0, numero))


def _coincidencia_frase(
    query_normalizada: str,
    nombre_normalizado: str,
) -> bool:
    """Comprueba si la consulta aparece como frase completa."""
    if not query_normalizada or not nombre_normalizado:
        return False

    return (
        f" {query_normalizada} "
        in f" {nombre_normalizado} "
    )


def _proporcion_ordenada(
    query_tokens: list[str],
    nombre_tokens: list[str],
) -> float:
    """
    Calcula qué proporción de términos aparece en el mismo orden.

    Utiliza una subsecuencia común ordenada.
    No exige que las palabras estén juntas.
    """
    if not query_tokens:
        return 0.0

    posicion = 0
    encontrados = 0

    for token in query_tokens:
        try:
            indice = nombre_tokens.index(token, posicion)
        except ValueError:
            continue

        encontrados += 1
        posicion = indice + 1

    return encontrados / len(query_tokens)


def _calcular_consenso(
    producto: Mapping[str, Any],
) -> float:
    """
    Evalúa cuántas fuentes independientes recuperaron el candidato.

    Dos fuentes: 1.0
    Una fuente: 0.5
    Ninguna fuente identificada: 0.0
    """
    fuentes = producto.get("fuentes_recuperacion") or []

    if isinstance(fuentes, str):
        fuentes = [fuentes]

    fuentes_validas = {
        str(fuente).strip().lower()
        for fuente in fuentes
        if fuente
    }

    conocidas = {"textual", "vectorial"}

    return len(fuentes_validas & conocidas) / 2.0


def calcular_score_ranking(
    query: str,
    producto: Mapping[str, Any],
    *,
    normalizar_texto: Callable[[str], str],
    obtener_tokens: Callable[[str], list[str]],
) -> dict[str, Any]:
    """
    Calcula la relevancia de un candidato.

    Devuelve:
        score: puntuación final entre 0 y 100.
        desglose: aportación de cada señal.
        senales: características detectadas.
        metricas: valores originales calculados.
    """
    nombre = _texto_seguro(producto.get("nombre"))

    query_normalizada = normalizar_texto(
        _texto_seguro(query)
    )

    nombre_normalizado = normalizar_texto(nombre)

    if not query_normalizada or not nombre_normalizado:
        return {
            "score": 0.0,
            "desglose": {},
            "senales": ["texto_vacio"],
            "metricas": {},
        }

    query_tokens = obtener_tokens(query_normalizada)
    nombre_tokens = obtener_tokens(nombre_normalizado)

    if not query_tokens or not nombre_tokens:
        return {
            "score": 0.0,
            "desglose": {},
            "senales": ["sin_tokens"],
            "metricas": {},
        }

    query_set = set(query_tokens)
    nombre_set = set(nombre_tokens)

    # 1. Coincidencia exacta.
    exacto = query_normalizada == nombre_normalizado

    # 2. Cobertura de términos.
    cobertura = (
        len(query_set & nombre_set) / len(query_set)
    )

    # 3. Coincidencia de frase.
    frase = _coincidencia_frase(
        query_normalizada,
        nombre_normalizado,
    )

    # 4. Orden de palabras.
    orden = _proporcion_ordenada(
        query_tokens,
        nombre_tokens,
    )

    # 5. Similitud vectorial.
    similitud = _numero_seguro(
        producto.get("similitud")
    )

    # 6. Consenso de recuperación.
    consenso = _calcular_consenso(producto)

    metricas = {
        "nombre_exacto": exacto,
        "cobertura": round(cobertura, 6),
        "frase_completa": float(frase),
        "orden": round(orden, 6),
        "similitud_vectorial": round(similitud, 6),
        "consenso": round(consenso, 6),
    }

    desglose = {
        "nombre_exacto": (
            PESOS_RANKING["nombre_exacto"]
            if exacto else 0.0
        ),
        "cobertura": (
            cobertura * PESOS_RANKING["cobertura"]
        ),
        "frase_completa": (
            float(frase) * PESOS_RANKING["frase_completa"]
        ),
        "orden": (
            orden * PESOS_RANKING["orden"]
        ),
        "similitud_vectorial": (
            similitud * PESOS_RANKING["similitud_vectorial"]
        ),
        "consenso": (
            consenso * PESOS_RANKING["consenso"]
        ),
    }

    senales = []

    if exacto:
        senales.append("nombre_exacto")

    if cobertura == 1.0:
        senales.append("cobertura_completa")

    if frase:
        senales.append("frase_completa")

    if orden == 1.0:
        senales.append("orden_completo")

    if similitud > 0:
        senales.append("similitud_vectorial")

    if consenso == 1.0:
        senales.append("consenso_ambas_fuentes")

    score = sum(desglose.values())

    return {
        "score": round(score, 3),
        "desglose": {
            clave: round(valor, 3)
            for clave, valor in desglose.items()
        },
        "senales": senales,
        "metricas": metricas,
    }


def ordenar_por_ranking(
    query: str,
    resultados: list[dict[str, Any]],
    *,
    normalizar_texto: Callable[[str], str],
    obtener_tokens: Callable[[str], list[str]],
) -> list[dict[str, Any]]:
    """
    Ordena candidatos mediante el ranking unificado.

    Conserva los campos originales y añade información
    explicativa del ranking.
    """
    ordenados = []

    for indice, producto in enumerate(resultados):
        evaluacion = calcular_score_ranking(
            query,
            producto,
            normalizar_texto=normalizar_texto,
            obtener_tokens=obtener_tokens,
        )

        copia = dict(producto)

        copia["score_ranking"] = evaluacion["score"]
        copia["desglose_ranking"] = evaluacion["desglose"]
        copia["senales_ranking"] = evaluacion["senales"]
        copia["metricas_ranking"] = evaluacion["metricas"]

        copia["_indice_original_ranking"] = indice

        ordenados.append(copia)

    ordenados.sort(
        key=lambda item: (
            -item["score_ranking"],
            -item["_indice_original_ranking"],
        )
    )

    for item in ordenados:
        item.pop("_indice_original_ranking", None)

    return ordenados
