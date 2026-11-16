
"""
Servicio centralizado de embeddings para NutriAI.

- Carga diferida del modelo FastEmbed.
- Singleton protegido frente a concurrencia.
- Interfaz común para generar embeddings.
"""

import logging
from threading import Lock
from typing import Optional

from fastembed import TextEmbedding

logger = logging.getLogger(__name__)

MODEL_NAME = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)

_model: Optional[TextEmbedding] = None
_model_lock = Lock()


def get_embedding_model() -> TextEmbedding:
    """Devuelve la única instancia del modelo de embeddings."""
    global _model

    if _model is not None:
        return _model

    with _model_lock:
        if _model is None:
            logger.info(
                "Loading embedding model: %s",
                MODEL_NAME,
            )

            _model = TextEmbedding(
                model_name=MODEL_NAME
            )

            logger.info("Embedding model loaded successfully.")

    return _model


def embed_text(text: str) -> list[float]:
    """Genera el embedding de un único texto."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("El texto no puede estar vacío.")

    model = get_embedding_model()

    vector = next(
        model.embed([text.strip()])
    )

    return vector.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Genera embeddings para una lista de textos."""
    if not texts:
        return []

    if any(
        not isinstance(text, str) or not text.strip()
        for text in texts
    ):
        raise ValueError(
            "Todos los elementos deben ser textos no vacíos."
        )

    model = get_embedding_model()

    return [
        vector.tolist()
        for vector in model.embed(
            [text.strip() for text in texts]
        )
    ]


def is_model_loaded() -> bool:
    """Indica si el modelo ya está cargado en memoria."""
    return _model is not None
