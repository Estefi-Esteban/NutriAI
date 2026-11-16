
"""
Recuperación vectorial de alimentos para NutriAI.

Genera embeddings mediante el servicio centralizado
y recupera candidatos desde Qdrant.
"""

import logging
from typing import Any

from backend.rag.core.embedding_service import embed_text
from backend.rag.core.qdrant_service import (
    COLLECTION_FOOD,
    search_by_vector,
)

logger = logging.getLogger(__name__)


from collections.abc import Mapping

from backend.rag.models import (
    Alimento,
    CandidatoAlimento,
    FuenteBusqueda,
)


def buscar_candidatos_por_vector(
    query: str,
    limite: int = 30,
    umbral_similitud: float | None = None,
) -> list[CandidatoAlimento]:
    """
    Recupera alimentos mediante búsqueda vectorial.

    Convierte los payloads externos de Qdrant en modelos
    tipados antes de devolverlos al resto de la aplicación.
    """
    if not isinstance(query, str) or not query.strip():
        return []

    if not 1 <= limite <= 100:
        raise ValueError("limite debe estar entre 1 y 100.")

    if umbral_similitud is not None:
        if not 0.0 <= umbral_similitud <= 1.0:
            raise ValueError(
                "umbral_similitud debe estar entre 0 y 1."
            )

    vector = embed_text(query.strip())

    puntos = search_by_vector(
        vector=vector,
        limit=limite,
        collection_name=COLLECTION_FOOD,
        score_threshold=umbral_similitud,
    )

    candidatos: list[CandidatoAlimento] = []

    for punto in puntos:
        payload = punto.payload

        if not isinstance(payload, Mapping):
            logger.warning(
                "Punto Qdrant %s sin payload válido.",
                punto.id,
            )
            continue

        nombre = payload.get("nombre")

        if not isinstance(nombre, str) or not nombre.strip():
            logger.warning(
                "Punto Qdrant %s sin nombre de alimento.",
                punto.id,
            )
            continue

        try:
            alimento = Alimento.desde_payload(
                payload=payload,
                identificador=punto.id,
            )

            candidato = CandidatoAlimento(
                alimento=alimento,
                similitud=float(punto.score),
                fuentes=(FuenteBusqueda.VECTORIAL,),
            )

            candidatos.append(candidato)

        except (ValueError, TypeError) as error:
            logger.warning(
                "No se pudo convertir el punto Qdrant %s: %s",
                punto.id,
                error,
            )

    return candidatos


def buscar_por_vector(
    query: str,
    limite: int = 30,
    umbral_similitud: float | None = None,
) -> list[dict[str, Any]]:
    """
    Recupera alimentos semánticamente similares.

    Devuelve el payload original de Qdrant y añade:
        - id
        - similitud
        - tipo_coincidencia

    No verifica datos nutricionales ni modifica los resultados.
    """
    if not isinstance(query, str) or not query.strip():
        return []

    if not 1 <= limite <= 100:
        raise ValueError("limite debe estar entre 1 y 100.")

    if umbral_similitud is not None:
        if not 0.0 <= umbral_similitud <= 1.0:
            raise ValueError(
                "umbral_similitud debe estar entre 0 y 1."
            )

    try:
        vector = embed_text(query)

        puntos = search_by_vector(
            vector=vector,
            limit=limite,
            collection_name=COLLECTION_FOOD,
            score_threshold=umbral_similitud,
        )

        resultados = []

        for punto in puntos:
            resultado = dict(punto.payload or {})

            resultado["id"] = str(punto.id)
            resultado["similitud"] = round(
                float(punto.score),
                6,
            )
            resultado["tipo_coincidencia"] = "vectorial"
            resultado["verificado_rag"] = False

            resultados.append(resultado)

        return resultados

    except Exception:
        logger.exception(
            "Error en búsqueda vectorial para: %s",
            query,
        )
        return []
