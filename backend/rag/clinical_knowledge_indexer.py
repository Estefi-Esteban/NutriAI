"""
clinical_knowledge_indexer.py
------------------------------
Orquesta la extracción, descarga, vectorización e indexación de artículos científicos
y guías clínicas en la colección 'conocimiento_clinico' de Qdrant Cloud.
"""

import os
import sys
import uuid
import logging
from pathlib import Path
from dotenv import load_dotenv

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from fastembed import TextEmbedding

from backend.rag.sources.pubmed_fetcher import PubMedFetcher
from backend.rag.sources.pdf_processor import PDFProcessor

# Cargar variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Configuraciones
MODELO_EMBEDDINGS = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
COLECCION = "conocimiento_clinico"
DIMENSION_VECTOR = 384
TAMANO_LOTE = 100               # al ser textos de abstract y guías más largos (500 palabras), bajamos a 100
MAX_PUBMED_POR_TERMINO = 5      # limitado para no exceder recursos en la demostración (puedes subirlo)


def indexar_todo() -> None:
    # ── 1. Validar variables de entorno ─────────────────────────────────────
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    if not qdrant_url:
        logger.error("❌ QDRANT_URL no está configurada en el .env")
        sys.exit(1)

    logger.info("Conectando a Qdrant Cloud: %s", qdrant_url)
    cliente = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=60)

    # ── 2. Cargar modelo FastEmbed ──────────────────────────────────────────
    logger.info("Cargando modelo FastEmbed '%s'...", MODELO_EMBEDDINGS)
    modelo = TextEmbedding(MODELO_EMBEDDINGS)
    logger.info("Modelo cargado ✓")

    # ── 3. Crear colección ──────────────────────────────────────────────────
    colecciones_existentes = [c.name for c in cliente.get_collections().collections]
    if COLECCION in colecciones_existentes:
        logger.info("Colección '%s' ya existe. Los nuevos puntos se añadirán/reemplazarán.", COLECCION)
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

    # ── 4. Recopilar datos: PubMed ──────────────────────────────────────────
    logger.info("Fase 1: Buscando artículos científicos en PubMed...")
    fetcher = PubMedFetcher()
    articulos_pubmed = fetcher.fetch_todo(max_por_termino=MAX_PUBMED_POR_TERMINO)
    logger.info("Fase 1 completada. %d artículos recuperados de PubMed.", len(articulos_pubmed))

    # ── 5. Recopilar datos: PDFs de Guías Clínicas ──────────────────────────
    logger.info("Fase 2: Descargando y procesando PDFs de guías clínicas...")
    pdf_proc = PDFProcessor(chunk_words=500, overlap_words=50)
    chunks_guias = pdf_proc.procesar_todas()
    logger.info("Fase 2 completada. %d chunks generados a partir de guías clínicas.", len(chunks_guias))

    # ── 6. Combinar y preparar puntos para indexar ─────────────────────────
    logger.info("Preparando datos para vectorizar...")
    todos_items = []

    # Mapear PubMed
    for art in articulos_pubmed:
        # Texto descriptivo para el embedding
        texto_para_embedding = f"Título: {art['titulo']}\nRevista: {art['revista']} ({art['año']})\nAutores: {art['autores']}\nAbstract: {art['abstract']}"
        todos_items.append({
            "texto": texto_para_embedding,
            "metadata": {
                "titulo": art["titulo"],
                "fuente": "PubMed",
                "tipo": "estudio_cientifico",
                "año": art["año"],
                "doi": art["doi"],
                "autores": art["autores"],
                "terminos": [art.get("termino_origen", "")]
            }
        })

    # Mapear Guías Clínicas (ya formateadas)
    for chunk in chunks_guias:
        todos_items.append({
            "texto": chunk["texto"],
            "metadata": chunk["metadata"]
        })

    total_documentos = len(todos_items)
    logger.info("Total documentos a indexar: %d", total_documentos)

    if total_documentos == 0:
        logger.warning("No hay ningún documento para indexar. Finalizando.")
        return

    # ── 7. Vectorizar e indexar por lotes ──────────────────────────────────
    subidos = 0
    errores = 0
    lotes_totales = (total_documentos + TAMANO_LOTE - 1) // TAMANO_LOTE

    for n_lote, inicio in enumerate(range(0, total_documentos, TAMANO_LOTE)):
        lote = todos_items[inicio : inicio + TAMANO_LOTE]
        
        # Extraer textos para vectorizar
        textos = [item["texto"] for item in lote]
        
        try:
            logger.info("Vectorizando lote %d/%d (%d textos)...", n_lote + 1, lotes_totales, len(textos))
            vectores = list(modelo.embed(textos))
            
            puntos = []
            for j, item in enumerate(lote):
                # Generamos una ID UUID consistente usando el hash del texto o un random UUID
                point_id = str(uuid.uuid4())
                puntos.append(
                    PointStruct(
                        id=point_id,
                        vector=vectores[j],
                        payload={
                            "texto": item["texto"],
                            **item["metadata"]
                        }
                    )
                )
                
            logger.info("Subiendo lote %d/%d a Qdrant...", n_lote + 1, lotes_totales)
            cliente.upsert(collection_name=COLECCION, points=puntos)
            subidos += len(puntos)
        except Exception as exc:
            logger.error("Error en lote %d/%d: %s", n_lote + 1, lotes_totales, exc)
            errores += len(lote)
            continue

    # ── 8. Resumen final ─────────────────────────────────────────────────────
    info_final = cliente.get_collection(COLECCION)
    logger.info("─" * 50)
    logger.info("✅ Indexación de Conocimiento Clínico Completada")
    logger.info("   Subidos:  %d", subidos)
    logger.info("   Errores:  %d", errores)
    logger.info("   Puntos en Qdrant: %d", info_final.points_count or 0)
    logger.info("─" * 50)


if __name__ == "__main__":
    indexar_todo()
