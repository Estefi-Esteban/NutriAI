
"""
Servicio centralizado de Qdrant para NutriAI.

Responsabilidades:
- Mantener un único cliente Qdrant.
- Inicializarlo de forma segura.
- Consultar colecciones e índices.
- Recuperar candidatos por texto.
- Recuperar candidatos por similitud vectorial.
"""

import logging
from threading import Lock
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchText,
)

from backend.config import qdrant_url, qdrant_api_key

logger = logging.getLogger(__name__)

COLLECTION_FOOD = "alimentos"
TEXT_FIELD_FOOD = "nombre_normalizado"

_client: Optional[QdrantClient] = None
_client_lock = Lock()


def get_qdrant_client() -> QdrantClient:
    """Obtiene la instancia única del cliente Qdrant."""
    global _client

    if _client is not None:
        return _client

    with _client_lock:
        if _client is None:
            if not qdrant_url:
                raise RuntimeError(
                    "QDRANT_URL no está configurada."
                )

            _client = QdrantClient(
                url=qdrant_url,
                api_key=qdrant_api_key,
                timeout=15,
            )

            logger.info("Qdrant client initialized.")

    return _client


def check_collection(
    collection_name: str = COLLECTION_FOOD,
) -> bool:
    """Comprueba si existe una colección."""
    client = get_qdrant_client()

    collections = client.get_collections().collections

    return any(
        collection.name == collection_name
        for collection in collections
    )


def get_collection_info(
    collection_name: str = COLLECTION_FOOD,
):
    """Obtiene información de una colección."""
    return get_qdrant_client().get_collection(
        collection_name
    )


def check_text_index(
    collection_name: str = COLLECTION_FOOD,
    field_name: str = TEXT_FIELD_FOOD,
) -> bool:
    """Comprueba que existe el índice textual esperado."""
    info = get_collection_info(collection_name)

    schema = info.payload_schema or {}
    field = schema.get(field_name)

    if field is None:
        return False

    data_type = getattr(field, "data_type", None)

    return (
        getattr(data_type, "value", data_type)
        == "text"
    )


def search_by_text(
    query: str,
    limit: int = 30,
    collection_name: str = COLLECTION_FOOD,
    field_name: str = TEXT_FIELD_FOOD,
):
    """
    Recupera candidatos mediante el índice textual.

    No descarga la colección completa.
    El orden de scroll no debe interpretarse como ranking.
    """
    query = (query or "").strip()

    if not query:
        return []

    if not 1 <= limit <= 100:
        raise ValueError(
            "limit debe estar entre 1 y 100."
        )

    query_filter = Filter(
        must=[
            FieldCondition(
                key=field_name,
                match=MatchText(text=query),
            )
        ]
    )

    records, _ = get_qdrant_client().scroll(
        collection_name=collection_name,
        scroll_filter=query_filter,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )

    return records


def search_by_text_paginated(
    query: str,
    max_candidates: int = 500,
    page_size: int = 100,
    collection_name: str = COLLECTION_FOOD,
    field_name: str = TEXT_FIELD_FOOD,
) -> list:
    """
    Recupera candidatos textuales recorriendo páginas de Qdrant.

    `scroll()` no ordena por relevancia. Esta función únicamente amplía
    el conjunto de candidatos para que el ranking local pueda evaluarlos.
    La lectura queda acotada por `max_candidates` y nunca descarga vectores.
    No modifica la colección ni sus índices.
    """
    query = (query or "").strip()
    if not query:
        return []

    if not 1 <= max_candidates <= 2000:
        raise ValueError("max_candidates debe estar entre 1 y 2000.")
    if not 1 <= page_size <= 100:
        raise ValueError("page_size debe estar entre 1 y 100.")

    query_filter = Filter(
        must=[
            FieldCondition(
                key=field_name,
                match=MatchText(text=query),
            )
        ]
    )

    client = get_qdrant_client()
    offset = None
    records = []

    while len(records) < max_candidates:
        remaining = max_candidates - len(records)
        batch_limit = min(page_size, remaining)

        batch, next_offset = client.scroll(
            collection_name=collection_name,
            scroll_filter=query_filter,
            limit=batch_limit,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        if not batch:
            break

        records.extend(batch)

        if next_offset is None:
            break

        offset = next_offset

    return records


def search_by_vector(
    vector: list[float],
    limit: int = 30,
    collection_name: str = COLLECTION_FOOD,
    score_threshold: Optional[float] = None,
):
    """Recupera candidatos ordenados por similitud vectorial."""
    if not vector:
        raise ValueError("El vector no puede estar vacío.")

    if not 1 <= limit <= 100:
        raise ValueError(
            "limit debe estar entre 1 y 100."
        )

    response = get_qdrant_client().query_points(
        collection_name=collection_name,
        query=vector,
        limit=limit,
        score_threshold=score_threshold,
        with_payload=True,
        with_vectors=False,
    )

    return response.points


def close_qdrant_client() -> None:
    """Cierra el cliente compartido."""
    global _client

    with _client_lock:
        if _client is not None:
            _client.close()
            _client = None

            logger.info("Qdrant client closed.")
