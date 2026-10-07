"""
migrate_to_qdrant.py
---------------------
Migra los alimentos de alimentos_limpios.csv a Qdrant Cloud.

IMPORTANTE:
Esta versión RECONSTRUYE la colección "alimentos" antes de migrar.
Por tanto, reemplaza la versión anterior del dataset.

VERSIÓN OPTIMIZADA CON FASTEMBED
"""

import os
import sys
import uuid
import logging
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from fastembed import TextEmbedding


# ── Configuración ────────────────────────────────────────────────────────────

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)

RUTA_CSV = Path("data/food_db/alimentos_limpios.csv")

MODELO_EMBEDDINGS = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

COLECCION = "alimentos"

DIMENSION_VECTOR = 384

TAMANO_LOTE = 1000

LOG_CADA = 5


def _num(valor) -> float:
    """
    Convierte un valor a float.
    Si no es válido, devuelve 0.0.
    """
    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


def _texto_embedding(row: pd.Series) -> str:
    """
    Construye el texto que se utilizará para generar el embedding.

    El embedding representa principalmente:
    - nombre
    - categorías
    """

    nombre = str(
        row.get("nombre", "")
    ).strip()

    cats = str(
        row.get("categories", "")
    ).replace("es:", "").replace("en:", "").strip()

    if cats and cats.lower() != "nan":
        return f"{nombre} — {cats}"

    return nombre


def reconstruir_coleccion(cliente: QdrantClient) -> None:
    """
    Elimina la colección actual "alimentos", si existe,
    y crea una nueva vacía con la configuración correcta.
    """

    colecciones = [
        c.name
        for c in cliente.get_collections().collections
    ]

    if COLECCION in colecciones:

        logger.warning(
            "⚠️ Eliminando colección existente '%s'...",
            COLECCION,
        )

        cliente.delete_collection(
            collection_name=COLECCION
        )

        logger.info(
            "Colección anterior eliminada ✓"
        )

    logger.info(
        "Creando colección '%s'...",
        COLECCION,
    )

    cliente.create_collection(
        collection_name=COLECCION,
        vectors_config=VectorParams(
            size=DIMENSION_VECTOR,
            distance=Distance.COSINE,
        ),
    )

    logger.info(
        "Colección nueva creada ✓"
    )


def migrar() -> None:

    # ── 1. Variables de entorno ──────────────────────────────────────────────

    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    if not qdrant_url:
        logger.error(
            "❌ QDRANT_URL no está configurada en el .env"
        )
        sys.exit(1)

    if not qdrant_api_key:
        logger.error(
            "❌ QDRANT_API_KEY no está configurada en el .env"
        )
        sys.exit(1)

    logger.info(
        "Conectando a Qdrant Cloud: %s",
        qdrant_url,
    )

    cliente = QdrantClient(
        url=qdrant_url,
        api_key=qdrant_api_key,
    )

    # ── 2. Comprobar CSV ────────────────────────────────────────────────────

    if not RUTA_CSV.exists():

        logger.error(
            "❌ CSV no encontrado: %s",
            RUTA_CSV.resolve(),
        )

        sys.exit(1)

    logger.info(
        "Leyendo %s ...",
        RUTA_CSV,
    )

    df = pd.read_csv(
        RUTA_CSV,
        low_memory=False,
    )

    total = len(df)

    logger.info(
        "Total alimentos: %d",
        total,
    )

    if total == 0:

        logger.error(
            "❌ El CSV está vacío."
        )

        sys.exit(1)

    # ── 3. Cargar modelo ────────────────────────────────────────────────────

    logger.info(
        "Cargando modelo FastEmbed '%s'...",
        MODELO_EMBEDDINGS,
    )

    modelo = TextEmbedding(
        MODELO_EMBEDDINGS
    )

    logger.info(
        "Modelo cargado ✓"
    )

    # ── 4. RECONSTRUIR COLECCIÓN ────────────────────────────────────────────

    logger.warning(
        "⚠️ Se va a RECONSTRUIR la colección '%s'.",
        COLECCION,
    )

    reconstruir_coleccion(cliente)

    # ── 5. Migración por lotes ───────────────────────────────────────────────

    subidos = 0
    errores = 0

    lotes_totales = (
        total + TAMANO_LOTE - 1
    ) // TAMANO_LOTE

    for n_lote, inicio in enumerate(
        range(0, total, TAMANO_LOTE)
    ):

        lote = df.iloc[
            inicio : inicio + TAMANO_LOTE
        ]

        # Generar textos para embeddings

        textos = [
            _texto_embedding(row)
            for _, row in lote.iterrows()
        ]

        # FastEmbed devuelve un generador

        vectores = list(
            modelo.embed(textos)
        )

        # Construir puntos

        puntos: list[PointStruct] = []

        for j, (_, row) in enumerate(
            lote.iterrows()
        ):

            puntos.append(
                PointStruct(
                    id=str(uuid.uuid4()),

                    vector=vectores[j],

                    payload={

                        # Identificación
                        "nombre": str(
                            row.get(
                                "nombre",
                                ""
                            )
                        )[:200],

                        "nombre_normalizado": str(
                            row.get(
                                "nombre_normalizado",
                                ""
                            )
                        )[:200],

                        # Información nutricional
                        "kcal_100g": _num(
                            row.get(
                                "energy-kcal_100g"
                            )
                        ),

                        "kcal_estimadas_100g": _num(
                            row.get(
                                "kcal_estimadas_100g"
                            )
                        ),

                        "diferencia_kcal_relativa": _num(
                            row.get(
                                "diferencia_kcal_relativa"
                            )
                        ),

                        "calidad_nutricional": str(
                            row.get(
                                "calidad_nutricional",
                                ""
                            )
                        ),

                        "proteinas_100g": _num(
                            row.get(
                                "proteins_100g"
                            )
                        ),

                        "carbos_100g": _num(
                            row.get(
                                "carbohydrates_100g"
                            )
                        ),

                        "azucares_100g": _num(
                            row.get(
                                "sugars_100g"
                            )
                        ),

                        "grasas_100g": _num(
                            row.get(
                                "fat_100g"
                            )
                        ),

                        "fibra_100g": _num(
                            row.get(
                                "fiber_100g"
                            )
                        ),

                        "sal_100g": _num(
                            row.get(
                                "salt_100g"
                            )
                        ),

                        # Información adicional
                        "alergenos": str(
                            row.get(
                                "allergens",
                                ""
                            )
                        )[:300],

                        "categorias": str(
                            row.get(
                                "categories",
                                ""
                            )
                        )[:500],
                    },
                )
            )

        # Subir lote

        try:

            cliente.upsert(
                collection_name=COLECCION,
                points=puntos,
            )

            subidos += len(puntos)

        except Exception as exc:

            logger.warning(
                "Error en lote %d/%d: %s",
                n_lote + 1,
                lotes_totales,
                exc,
            )

            errores += len(puntos)

            continue

        # Mostrar progreso

        if (
            (n_lote + 1) % LOG_CADA == 0
            or
            (n_lote + 1) == lotes_totales
        ):

            pct = (
                100 * subidos // total
            )

            logger.info(
                "  Lote %d/%d — "
                "%d/%d alimentos subidos (%d%%)",
                n_lote + 1,
                lotes_totales,
                subidos,
                total,
                pct,
            )

    # ── 6. Verificación final ───────────────────────────────────────────────

    info_final = cliente.get_collection(
        COLECCION
    )

    puntos_finales = (
        info_final.points_count or 0
    )

    logger.info(
        "─" * 60
    )

    logger.info(
        "✅ MIGRACIÓN COMPLETADA"
    )

    logger.info(
        "   Alimentos del CSV: %d",
        total,
    )

    logger.info(
        "   Subidos correctamente: %d",
        subidos,
    )

    logger.info(
        "   Errores: %d",
        errores,
    )

    logger.info(
        "   Puntos en Qdrant: %d",
        puntos_finales,
    )

    logger.info(
        "─" * 60
    )

    # Comprobación de seguridad

    if (
        errores == 0
        and puntos_finales == total
    ):

        logger.info(
            "🎉 Qdrant coincide exactamente con el dataset."
        )

    else:

        logger.warning(
            "⚠️ Qdrant NO coincide exactamente "
            "con el dataset. Hay que investigar antes "
            "de continuar."
        )


if __name__ == "__main__":
    migrar()