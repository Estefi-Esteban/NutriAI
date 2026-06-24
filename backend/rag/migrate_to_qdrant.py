"""
migrate_to_qdrant.py
---------------------
Migra los alimentos de alimentos_limpios.csv a Qdrant Cloud.
VERSIÓN OPTIMIZADA CON FASTEMBED (Ultra-rápido en CPU)
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
# 1. Importamos TextEmbedding de fastembed en lugar de SentenceTransformers
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
# 2. El prefijo "sentence-transformers/" es necesario para FastEmbed
MODELO_EMBEDDINGS = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
COLECCION = "alimentos"
DIMENSION_VECTOR = 384          
# 3. Al ser mucho más rápido, podemos subir de 1000 en 1000 para saturar la red y ahorrar tiempo
TAMANO_LOTE = 1000              
LOG_CADA = 5                    


def _num(valor) -> float:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


def _texto_embedding(row: pd.Series) -> str:
    nombre = str(row.get("product_name", "")).strip()
    cats = str(row.get("categories", "")).replace("es:", "").replace("en:", "").strip()
    if cats and cats.lower() != "nan":
        return f"{nombre} — {cats}"
    return nombre


def migrar() -> None:
    # ── 1. Validar variables de entorno ─────────────────────────────────────
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    if not qdrant_url:
        logger.error("❌ QDRANT_URL no está configurada en el .env")
        sys.exit(1)

    logger.info("Conectando a Qdrant Cloud: %s", qdrant_url)
    cliente = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

    # ── 2. Cargar modelo de embeddings (Optimizado para CPU) ────────────────
    logger.info("Cargando modelo FastEmbed '%s'...", MODELO_EMBEDDINGS)
    # Esto usa ONNX por debajo. Aprovechará todos tus núcleos automáticamente.
    modelo = TextEmbedding(MODELO_EMBEDDINGS)
    logger.info("Modelo cargado ✓")

    # ── 3. Crear o verificar colección ──────────────────────────────────────
    colecciones_existentes = [c.name for c in cliente.get_collections().collections]
    if COLECCION in colecciones_existentes:
        info = cliente.get_collection(COLECCION)
        puntos_actuales = info.points_count or 0
        logger.info(
            "Colección '%s' ya existe con %d puntos — añadiendo los que falten",
            COLECCION, puntos_actuales,
        )
    else:
        logger.info("Creando colección '%s'...", COLECCION)
        cliente.create_collection(
            collection_name=COLECCION,
            vectors_config=VectorParams(
                size=DIMENSION_VECTOR,
                distance=Distance.COSINE,
            ),
        )
        logger.info("Colección creada ✓")

    # ── 4. Cargar CSV ────────────────────────────────────────────────────────
    if not RUTA_CSV.exists():
        logger.error("❌ CSV no encontrado: %s", RUTA_CSV.resolve())
        sys.exit(1)

    logger.info("Leyendo %s ...", RUTA_CSV)
    df = pd.read_csv(RUTA_CSV, low_memory=False)
    total = len(df)
    logger.info("Total alimentos: %d", total)

    # ── 5. Migración por lotes ───────────────────────────────────────────────
    subidos = 0
    errores = 0
    lotes_totales = (total + TAMANO_LOTE - 1) // TAMANO_LOTE

    for n_lote, inicio in enumerate(range(0, total, TAMANO_LOTE)):
        lote = df.iloc[inicio : inicio + TAMANO_LOTE]

        # Generar textos para embedding
        textos = [_texto_embedding(row) for _, row in lote.iterrows()]

        # Generar vectores: FastEmbed devuelve un generador, lo convertimos a lista
        vectores = list(modelo.embed(textos))

        # Construir PointStruct para cada fila
        puntos: list[PointStruct] = []
        for j, (_, row) in enumerate(lote.iterrows()):
            puntos.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vectores[j],
                    payload={
                        "nombre":          str(row.get("product_name", ""))[:200],
                        "kcal_100g":       _num(row.get("energy-kcal_100g")),
                        "proteinas_100g":  _num(row.get("proteins_100g")),
                        "carbos_100g":     _num(row.get("carbohydrates_100g")),
                        "azucares_100g":   _num(row.get("sugars_100g")),
                        "grasas_100g":     _num(row.get("fat_100g")),
                        "fibra_100g":      _num(row.get("fiber_100g")),
                        "sal_100g":        _num(row.get("salt_100g")),
                        "alergenos":       str(row.get("allergens", ""))[:300],
                    },
                )
            )

        # Subir lote a Qdrant
        try:
            cliente.upsert(collection_name=COLECCION, points=puntos)
            subidos += len(puntos)
        except Exception as exc:
            logger.warning("Error en lote %d/%d: %s", n_lote + 1, lotes_totales, exc)
            errores += len(puntos)
            continue

        # Progreso
        if (n_lote + 1) % LOG_CADA == 0 or (n_lote + 1) == lotes_totales:
            pct = 100 * subidos // total
            logger.info(
                "  Lote %d/%d — %d/%d alimentos subidos (%d%%)",
                n_lote + 1, lotes_totales, subidos, total, pct,
            )

    # ── 6. Resumen final ─────────────────────────────────────────────────────
    info_final = cliente.get_collection(COLECCION)
    logger.info("─" * 50)
    logger.info("✅ Migración completada")
    logger.info("   Subidos:  %d", subidos)
    logger.info("   Errores:  %d", errores)
    logger.info("   Puntos en Qdrant: %d", info_final.points_count or 0)
    logger.info("─" * 50)


if __name__ == "__main__":
    migrar()
