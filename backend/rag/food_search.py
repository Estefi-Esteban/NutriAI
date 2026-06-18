"""
food_search.py
----------------
Búsqueda semántica de alimentos en la base vectorial ChromaDB.
Usado por el Agente Dietista para obtener valores nutricionales
reales en lugar de estimarlos.
"""

import logging
import time
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions

RUTA_CHROMA = "./data/vector_db"
MODELO_EMBEDDINGS = "paraphrase-multilingual-MiniLM-L12-v2"

# Cliente y colección — se inicializan una sola vez (patrón singleton simple)
_cliente = None
_coleccion = None

logger = logging.getLogger(__name__)

# ChromaDB 1.x Rust-backend raises InternalError when the HNSW compactor
# fails on first open after a large batch write from another process.
# We import it defensively — older versions don't have it.
try:
    from chromadb.errors import InternalError as ChromaInternalError
except ImportError:
    ChromaInternalError = Exception  # fallback: catch-all


def _crear_coleccion():
    """Abre una conexión fresca a ChromaDB y devuelve la colección."""
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=MODELO_EMBEDDINGS
    )
    cliente = chromadb.PersistentClient(path=RUTA_CHROMA)
    coleccion = cliente.get_collection(
        name="alimentos",
        embedding_function=embedding_fn,
    )
    return cliente, coleccion


def _obtener_coleccion():
    """
    Devuelve la colección ChromaDB, inicializándola si es la primera vez.
    Expone también el cliente para poder resetearlo ante errores.
    """
    global _cliente, _coleccion

    if _coleccion is None:
        _cliente, _coleccion = _crear_coleccion()

    return _coleccion


def _reset_coleccion():
    """Descarta la conexión actual para forzar una reconexión en el próximo uso."""
    global _cliente, _coleccion
    _cliente = None
    _coleccion = None



def buscar_alimento(query: str, n_resultados: int = 3) -> list[dict]:
    """
    Busca alimentos semánticamente similares a la query.

    Args:
        query: texto de búsqueda, ej: "pechuga de pollo a la plancha"
        n_resultados: cuántos resultados devolver (por defecto 3, para
                      poder elegir el más adecuado si el primero no cuadra)

    Returns:
        Lista de dicts con los datos nutricionales de cada resultado,
        ordenados de más a menos similar. Lista vacía si no hay match.

    Ejemplo de un resultado:
        {
            "nombre": "Pechuga de pollo",
            "kcal_100g": 110.0,
            "proteinas_100g": 23.0,
            "carbos_100g": 0.0,
            "grasas_100g": 2.0,
            "fibra_100g": 0.0,
            "alergenos": "",
            "similitud": 0.89   # 0 a 1, más alto = más parecido
        }
    """
    coleccion = _obtener_coleccion()

    for intento in range(2):  # intento 0: normal; intento 1: tras reconexión
        try:
            resultados = coleccion.query(
                query_texts=[query],
                n_results=n_resultados,
            )
            break  # éxito — salimos del bucle
        except ChromaInternalError as exc:
            if intento == 0:
                logger.warning(
                    "ChromaDB InternalError en consulta (intento %d/2), reconectando... %s",
                    intento + 1, exc,
                )
                _reset_coleccion()
                time.sleep(1)
                coleccion = _obtener_coleccion()
            else:
                logger.error("ChromaDB InternalError persistente tras reconexión: %s", exc)
                return []

    if not resultados["ids"] or not resultados["ids"][0]:
        return []

    salida = []
    metadatas = resultados["metadatas"][0]
    distancias = resultados["distances"][0]  # más bajo = más similar

    for metadata, distancia in zip(metadatas, distancias):
        similitud = max(0.0, 1.0 - distancia)  # convertimos distancia a "similitud" 0-1

        salida.append({
            "nombre": metadata.get("nombre", ""),
            "kcal_100g": metadata.get("kcal_100g", 0.0),
            "proteinas_100g": metadata.get("proteinas_100g", 0.0),
            "carbos_100g": metadata.get("carbos_100g", 0.0),
            "azucares_100g": metadata.get("azucares_100g", 0.0),
            "grasas_100g": metadata.get("grasas_100g", 0.0),
            "fibra_100g": metadata.get("fibra_100g", 0.0),
            "sal_100g": metadata.get("sal_100g", 0.0),
            "alergenos": metadata.get("alergenos", ""),
            "similitud": round(similitud, 3),
        })

    return salida


def buscar_mejor_match(query: str) -> Optional[dict]:
    """
    Devuelve solo el alimento más parecido (el primer resultado).
    Conveniencia para cuando no necesitas comparar varias opciones.
    """
    resultados = buscar_alimento(query, n_resultados=1)
    return resultados[0] if resultados else None


# ---------------------------------------------------------------------------
# Corrección de ingredientes con datos verificados
# ---------------------------------------------------------------------------

UMBRAL_SIMILITUD = 0.75  # por debajo de esto, no confiamos en el match


def corregir_ingrediente(ingrediente: dict) -> dict:
    """
    Busca el ingrediente en ChromaDB y, si encuentra un match fiable,
    recalcula sus macros en base a la cantidad real y los valores
    verificados por 100g.

    Args:
        ingrediente: dict con al menos {nombre, cantidad, unidad}

    Returns:
        El mismo ingrediente, con un campo añadido "verificado_rag" (bool)
        y, si se verificó, los macros corregidos del ingrediente
        (campos nuevos: kcal, proteinas_g, carbos_g, grasas_g — a nivel
        de ESTE ingrediente, no de la comida completa).
    """
    nombre = ingrediente.get("nombre", "")
    cantidad = ingrediente.get("cantidad", 0)
    unidad = ingrediente.get("unidad", "g")

    resultado = ingrediente.copy()
    resultado["verificado_rag"] = False

    # Solo podemos corregir con garantías si la unidad es de peso/volumen estándar
    if unidad not in ("g", "ml"):
        return resultado

    match = buscar_mejor_match(nombre)

    if match is None or match["similitud"] < UMBRAL_SIMILITUD:
        return resultado

    # Factor de escala: los valores de ChromaDB son por 100g/100ml
    factor = cantidad / 100.0

    resultado["verificado_rag"] = True
    resultado["nombre_verificado"] = match["nombre"]
    resultado["kcal"] = round(match["kcal_100g"] * factor, 1)
    resultado["proteinas_g"] = round(match["proteinas_100g"] * factor, 1)
    resultado["carbos_g"] = round(match["carbos_100g"] * factor, 1)
    resultado["grasas_g"] = round(match["grasas_100g"] * factor, 1)

    return resultado
