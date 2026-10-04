"""
clinical_knowledge_search.py
----------------------------
Búsqueda semántica en la colección 'conocimiento_clinico' de Qdrant Cloud.
Permite a los agentes encontrar evidencia científica y guías médicas.

Patrón: inicialización lazy singleton para ser ligero y eficiente.
"""

import os
import logging
from dotenv import load_dotenv
from typing import Optional, List, Dict, Any
from qdrant_client import QdrantClient
from fastembed import TextEmbedding

load_dotenv()
logger = logging.getLogger(__name__)

MODELO_EMBEDDINGS = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
COLECCION = "conocimiento_clinico"

_cliente: Optional[QdrantClient] = None
_modelo: Optional[TextEmbedding] = None
_rag_activo: Optional[bool] = None  # None = no inicializado


def _inicializar() -> bool:
    """Inicializa de forma diferida el cliente y el modelo de embeddings."""
    global _cliente, _modelo, _rag_activo

    if _rag_activo is not None:
        return _rag_activo

    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    if not qdrant_url:
        logger.warning("QDRANT_URL no configurada. RAG Clínico desactivado.")
        _rag_activo = False
        return False

    try:
        logger.info("Inicializando cliente Qdrant para RAG Clínico...")
        _cliente = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=10)
        
        # Verificar si existe la colección
        colecciones = [c.name for c in _cliente.get_collections().collections]
        if COLECCION not in colecciones:
            logger.warning(
                "Colección clínica '%s' no encontrada en Qdrant. "
                "Por favor ejecuta: python -m backend.rag.clinical_knowledge_indexer",
                COLECCION
            )
            _rag_activo = False
            return False

        logger.info("Cargando modelo FastEmbed '%s' para búsqueda clínica...", MODELO_EMBEDDINGS)
        _modelo = TextEmbedding(MODELO_EMBEDDINGS)
        logger.info("RAG Clínico inicializado y activo ✓")
        _rag_activo = True
        return True

    except Exception as exc:
        logger.error("Error al inicializar RAG Clínico: %s", exc)
        _rag_activo = False
        return False


def buscar_evidencia(
    query: str,
    tipo: Optional[str] = None,       # "estudio_cientifico" o "guia_clinica"
    n_resultados: int = 3
) -> List[Dict[str, Any]]:
    """
    Busca evidencia clínica relevante para una consulta.

    Args:
        query: consulta semántica, ej. "dietary guidelines for hypothyroidism"
        tipo: filtrar por tipo de documento ("estudio_cientifico" | "guia_clinica" | None)
        n_resultados: número de resultados a devolver

    Returns:
        Lista de fragmentos relevantes ordenados por relevancia.
    """
    if not _inicializar():
        return []

    try:
        # Generar vector con FastEmbed
        vector = list(_modelo.embed([query]))[0].tolist()

        # Configurar filtros si se especifica el tipo
        filtro = None
        if tipo:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            filtro = Filter(
                must=[
                    FieldCondition(
                        key="tipo",
                        match=MatchValue(value=tipo)
                    )
                ]
            )

        resultados_response = _cliente.query_points(
            collection_name=COLECCION,
            query=vector,
            query_filter=filtro,
            limit=n_resultados
        )
        resultados = resultados_response.points

        salida = []
        for r in resultados:
            payload = r.payload
            salida.append({
                "texto": payload.get("texto", ""),
                "titulo": payload.get("titulo", ""),
                "fuente": payload.get("fuente", ""),
                "tipo": payload.get("tipo", ""),
                "año": payload.get("año") or payload.get("año") or 2023,
                "doi": payload.get("doi", ""),
                "autores": payload.get("autores", ""),
                "similitud": round(max(0.0, r.score), 3)
            })

        return salida

    except Exception as e:
        logger.error("Error al buscar evidencia (query=%r): %s", query, e)
        return []
