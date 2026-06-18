"""
index_food_data.py
--------------------
Indexa el dataset limpio de Open Food Facts en ChromaDB.
Procesa en lotes para no saturar memoria con 143K+ alimentos.

Ejecución:
    python -m backend.rag.index_food_data
"""

import pandas as pd
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path
import time

RUTA_CSV = Path("data/food_db/alimentos_limpios.csv")
RUTA_CHROMA = "./data/vector_db"
TAMANO_LOTE = 500  # alimentos por lote — equilibrio entre velocidad y memoria

# Modelo de embeddings local, multilingüe y ligero
MODELO_EMBEDDINGS = "paraphrase-multilingual-MiniLM-L12-v2"


def construir_texto_descriptivo(row) -> str:
    """Construye el texto que se convertirá en embedding para este alimento."""
    nombre = str(row.get("product_name", "")).strip()
    categorias = str(row.get("categories", "")).strip()

    partes = [nombre]
    if categorias and categorias != "nan":
        # Las categorías de OFF vienen como "es:carnes, es:aves" — limpiamos un poco
        cats_limpias = categorias.replace("es:", "").replace("en:", "")
        partes.append(f"categoria: {cats_limpias}")

    return " - ".join(partes)


def construir_metadata(row) -> dict:
    """Construye los metadatos nutricionales que recuperaremos junto al resultado."""
    def _num(valor, default=0.0):
        try:
            return float(valor)
        except (ValueError, TypeError):
            return default

    return {
        "nombre": str(row.get("product_name", ""))[:200],
        "kcal_100g": _num(row.get("energy-kcal_100g")),
        "proteinas_100g": _num(row.get("proteins_100g")),
        "carbos_100g": _num(row.get("carbohydrates_100g")),
        "azucares_100g": _num(row.get("sugars_100g")),
        "grasas_100g": _num(row.get("fat_100g")),
        "grasas_sat_100g": _num(row.get("saturated-fat_100g")),
        "fibra_100g": _num(row.get("fiber_100g")),
        "sal_100g": _num(row.get("salt_100g")),
        "alergenos": str(row.get("allergens", ""))[:300],
    }


def indexar():
    print("Cargando dataset limpio...")
    df = pd.read_csv(RUTA_CSV)
    total = len(df)
    print(f"Total de alimentos a indexar: {total:,}")

    print(f"\nCargando modelo de embeddings ({MODELO_EMBEDDINGS})...")
    print("(la primera vez descarga el modelo, puede tardar un poco)")

    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=MODELO_EMBEDDINGS
    )

    print("\nConectando con ChromaDB...")
    cliente = chromadb.PersistentClient(path=RUTA_CHROMA)

    # Si la colección ya existe de una ejecución anterior, la recreamos limpia
    try:
        cliente.delete_collection("alimentos")
        print("Coleccion anterior eliminada, empezando de cero.")
    except Exception:
        pass

    coleccion = cliente.create_collection(
        name="alimentos",
        embedding_function=embedding_fn,
    )

    print(f"\nIndexando en lotes de {TAMANO_LOTE}...\n")
    inicio = time.time()
    num_lotes = (total // TAMANO_LOTE) + 1

    for i in range(0, total, TAMANO_LOTE):
        lote = df.iloc[i:i + TAMANO_LOTE]

        ids = [str(idx) for idx in lote.index]
        documentos = [construir_texto_descriptivo(row) for _, row in lote.iterrows()]
        metadatas = [construir_metadata(row) for _, row in lote.iterrows()]

        coleccion.add(
            ids=ids,
            documents=documentos,
            metadatas=metadatas,
        )

        lote_num = (i // TAMANO_LOTE) + 1
        transcurrido = time.time() - inicio
        print(f"  Lote {lote_num}/{num_lotes} - {i + len(lote):,}/{total:,} alimentos - {transcurrido:.0f}s")

    print(f"\nIndexacion completa en {time.time() - inicio:.0f} segundos.")
    print(f"Total indexado: {coleccion.count():,} alimentos")


if __name__ == "__main__":
    indexar()
