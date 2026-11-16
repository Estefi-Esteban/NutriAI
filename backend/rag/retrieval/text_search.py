
"""Búsqueda textual inteligente de alimentos en Qdrant.

Recupera candidatos mediante el índice textual y aplica
una puntuación léxica y un ranking unificado.

Los resultados se convierten a modelos tipados antes
de salir de este módulo.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from backend.rag.core.qdrant_service import search_by_text_paginated
from backend.rag.models import (
    Alimento,
    CandidatoAlimento,
    FuenteBusqueda,
)
from backend.rag.normalization import normalizador_alimentos
from backend.rag.retrieval.ranking import ordenar_por_ranking

logger = logging.getLogger(__name__)

MAX_CANDIDATOS_TEXTO = 500
TAMANO_PAGINA_QDRANT = 100


def calcular_score_textual(
    query: str,
    nombre: str,
) -> float:
    """Calcula la relevancia léxica de un alimento.

    La puntuación es una señal interna de ordenación.
    No representa una probabilidad ni una verificación nutricional.
    """

    query_normalizada = normalizador_alimentos.normalizar_texto(
        query
    )
    nombre_normalizado = normalizador_alimentos.normalizar_texto(
        nombre
    )

    if not query_normalizada or not nombre_normalizado:
        return 0.0

    if not normalizador_alimentos.contiene_restricciones_criticas(
        query_normalizada,
        nombre_normalizado,
    ):
        return 0.0

    tokens_query = normalizador_alimentos.obtener_tokens(query)
    tokens_nombre = normalizador_alimentos.obtener_tokens(nombre)

    if not tokens_query:
        return 0.0

    tokens_query_unicos: list[str] = []

    for token in tokens_query:
        if token not in tokens_query_unicos:
            tokens_query_unicos.append(token)

    tokens_nombre_unicos: list[str] = []

    for token in tokens_nombre:
        if token not in tokens_nombre_unicos:
            tokens_nombre_unicos.append(token)

    cobertura = sum(
        1
        for token in tokens_query_unicos
        if token in tokens_nombre_unicos
    ) / len(tokens_query_unicos)

    puntuacion = cobertura * 70.0

    if query_normalizada == nombre_normalizado:
        puntuacion += 40.0

    if query_normalizada in nombre_normalizado:
        puntuacion += 25.0

    if all(
        token in tokens_nombre_unicos
        for token in tokens_query_unicos
    ):
        puntuacion += 15.0

    palabras_adicionales = tuple(
        token
        for token in tokens_nombre_unicos
        if token not in tokens_query_unicos
    )

    puntuacion -= len(palabras_adicionales) * 8.0

    for token in palabras_adicionales:
        puntuacion -= (
            normalizador_alimentos.obtener_penalizacion_modificador(
                token
            )
        )

    return round(max(0.0, puntuacion), 3)


def _obtener_clave_candidato(
    candidato: CandidatoAlimento,
) -> str:
    """Genera una clave estable para evitar duplicados."""

    if candidato.alimento.id is not None:
        return f"id:{candidato.alimento.id}"

    nombre = normalizador_alimentos.normalizar_texto(
        candidato.alimento.nombre
    )

    return f"nombre:{nombre}" if nombre else ""


def buscar_candidatos_por_texto(
    query: str,
    limite: int = 30,
    aplicar_ranking: bool = True,
    propagar_errores: bool = False,
) -> list[CandidatoAlimento]:
    """Recupera candidatos mediante búsqueda textual."""

    if not isinstance(query, str) or not query.strip():
        return []

    if not 1 <= limite <= 100:
        raise ValueError("limite debe estar entre 1 y 100.")

    try:
        consultas = normalizador_alimentos.obtener_consultas_equivalentes(
            query
        )

        claves: list[str] = []
        candidatos: list[CandidatoAlimento] = []

        for consulta in consultas:
            registros = search_by_text_paginated(
                query=consulta,
                max_candidates=MAX_CANDIDATOS_TEXTO,
                page_size=TAMANO_PAGINA_QDRANT,
            )

            for registro in registros:
                payload = registro.payload

                if not isinstance(payload, Mapping):
                    logger.warning(
                        "Registro Qdrant %s sin payload válido.",
                        registro.id,
                    )
                    continue

                nombre = payload.get("nombre")

                if not isinstance(nombre, str) or not nombre.strip():
                    logger.warning(
                        "Registro Qdrant %s sin nombre.",
                        registro.id,
                    )
                    continue

                try:
                    alimento = Alimento.desde_payload(
                        payload=payload,
                        identificador=registro.id,
                    )

                    puntuacion_textual = calcular_score_textual(
                        query,
                        alimento.nombre,
                    )

                    # No permitimos que un candidato que incumple restricciones
                    # críticas entre en la fase de ranking.
                    if puntuacion_textual <= 0:
                        continue

                    candidato = CandidatoAlimento(
                        alimento=alimento,
                        puntuacion_textual=puntuacion_textual,
                        fuentes=(FuenteBusqueda.TEXTUAL,),
                    )

                    clave = _obtener_clave_candidato(candidato)

                    if not clave:
                        continue

                    indice = _buscar_indice_clave(claves, clave)

                    if indice is None:
                        claves.append(clave)
                        candidatos.append(candidato)
                    else:
                        candidato_existente = candidatos[indice]

                        if (
                            candidato.puntuacion_textual
                            > candidato_existente.puntuacion_textual
                        ):
                            candidatos[indice] = candidato

                except (ValueError, TypeError) as error:
                    logger.warning(
                        "No se pudo convertir el registro Qdrant %s: %s",
                        registro.id,
                        error,
                    )

        if aplicar_ranking:
            candidatos = ordenar_por_ranking(
                candidatos,
                query,
            )
        else:
            candidatos.sort(
                key=lambda candidato: candidato.puntuacion_textual,
                reverse=True,
            )

        return candidatos[:limite]

    except Exception:
        if propagar_errores:
            raise

        logger.exception("Error en búsqueda textual")
        return []


def _buscar_indice_clave(
    claves: list[str],
    clave: str,
) -> int | None:
    """Busca una clave sin utilizar diccionarios internos."""

    try:
        return claves.index(clave)
    except ValueError:
        return None


def buscar_por_texto(
    query: str,
    limite: int = 30,
    aplicar_ranking: bool = True,
) -> list[CandidatoAlimento]:
    """Alias público de compatibilidad para la búsqueda textual."""

    return buscar_candidatos_por_texto(
        query=query,
        limite=limite,
        aplicar_ranking=aplicar_ranking,
    )
