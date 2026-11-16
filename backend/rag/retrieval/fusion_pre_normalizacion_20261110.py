
"""
Fusión de candidatos recuperados mediante búsqueda textual y vectorial.

Utiliza Reciprocal Rank Fusion (RRF) para combinar rankings
sin mezclar directamente puntuaciones de escalas diferentes.
"""

import re
import unicodedata
from typing import Any


def _normalizar_nombre(nombre: str) -> str:
    """Normaliza un nombre para identificar duplicados exactos."""
    if not isinstance(nombre, str):
        return ""

    texto = unicodedata.normalize("NFD", nombre.lower().strip())
    texto = "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)

    return " ".join(texto.split())


def _obtener_clave(candidato: dict[str, Any]) -> str:
    """
    Genera una clave conservadora de identidad.

    Prioriza el nombre normalizado para poder fusionar registros
    aunque una de las fuentes no proporcione el ID de Qdrant.
    """
    nombre = _normalizar_nombre(candidato.get("nombre", ""))

    if nombre:
        return f"nombre:{nombre}"

    identificador = candidato.get("id")

    if identificador is not None:
        return f"id:{identificador}"

    return ""


def fusionar_resultados(
    resultados_textuales: list[dict[str, Any]],
    resultados_vectoriales: list[dict[str, Any]],
    k: int = 60,
) -> list[dict[str, Any]]:
    """
    Fusiona dos rankings mediante Reciprocal Rank Fusion.

    RRF(d) = sum(1 / (k + posicion))

    Las posiciones empiezan en 1. Los candidatos presentes
    en ambas fuentes acumulan las contribuciones de los dos rankings.

    Conserva los campos originales de los candidatos y añade:
        - score_rrf
        - fuentes_recuperacion
        - ranking_textual
        - ranking_vectorial
    """
    if k < 1:
        raise ValueError("k debe ser mayor o igual que 1.")

    candidatos: dict[str, dict[str, Any]] = {}

    fuentes = (
        ("textual", resultados_textuales),
        ("vectorial", resultados_vectoriales),
    )

    for nombre_fuente, resultados in fuentes:
        for posicion, original in enumerate(resultados, start=1):
            if not isinstance(original, dict):
                continue

            clave = _obtener_clave(original)

            if not clave:
                continue

            contribucion = 1.0 / (k + posicion)

            if clave not in candidatos:
                candidatos[clave] = {
                    **original,
                    "score_rrf": 0.0,
                    "fuentes_recuperacion": [],
                    "ranking_textual": None,
                    "ranking_vectorial": None,
                }
            else:
                candidato = candidatos[clave]

                # Conserva los datos existentes y completa los campos
                # ausentes con la información de la otra fuente.
                for campo, valor in original.items():
                    if campo not in candidato or candidato[campo] is None:
                        candidato[campo] = valor

            candidato = candidatos[clave]
            candidato["score_rrf"] += contribucion

            if nombre_fuente not in candidato["fuentes_recuperacion"]:
                candidato["fuentes_recuperacion"].append(nombre_fuente)

            campo_ranking = (
                "ranking_textual"
                if nombre_fuente == "textual"
                else "ranking_vectorial"
            )

            candidato[campo_ranking] = posicion

    resultado = list(candidatos.values())

    resultado.sort(
        key=lambda item: item["score_rrf"],
        reverse=True,
    )

    return resultado
