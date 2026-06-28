"""
food_search.py
----------------
Búsqueda semántica de alimentos usando Qdrant Cloud.
Funciona tanto en local como en Railway (producción).

Patrón: inicialización lazy singleton — el cliente se crea la primera
vez que se hace una búsqueda, no al importar el módulo.

Si QDRANT_URL no está configurada → RAG desactivado graciosamente
(todas las funciones devuelven [] o None sin lanzar excepciones).
"""

import os
import logging
from typing import Optional

from fastembed import TextEmbedding
from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)

# Usamos el mismo modelo con prefijo para FastEmbed
MODELO_EMBEDDINGS = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
COLECCION = "alimentos"
UMBRAL_SIMILITUD = 0.75     # por debajo de esto, no confiamos en el match

# ── Singletons ────────────────────────────────────────────────────────────────
_cliente: Optional[QdrantClient] = None
_modelo: Optional[TextEmbedding] = None
_rag_activo: Optional[bool] = None  # None = no intentado todavía


def _inicializar() -> bool:
    """
    Inicializa el cliente Qdrant y el modelo de embeddings.
    Se ejecuta solo una vez (patrón singleton).
    Devuelve True si el RAG está listo, False si está desactivado.
    """
    global _cliente, _modelo, _rag_activo

    if _rag_activo is not None:
        return _rag_activo  # ya se intentó inicializar antes

    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    if not qdrant_url:
        logger.warning(
            "QDRANT_URL no configurada — RAG desactivado. "
            "Añade QDRANT_URL y QDRANT_API_KEY al .env o a las variables de Railway."
        )
        _rag_activo = False
        return False

    try:
        logger.info("Inicializando cliente Qdrant: %s", qdrant_url)
        _cliente = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=10)

        # Verificar que la colección existe
        colecciones = [c.name for c in _cliente.get_collections().collections]
        if COLECCION not in colecciones:
            logger.warning(
                "Colección '%s' no encontrada en Qdrant. "
                "Ejecuta: python -m backend.rag.migrate_to_qdrant",
                COLECCION,
            )
            _rag_activo = False
            return False

        logger.info("Cargando modelo de embeddings '%s'...", MODELO_EMBEDDINGS)
        _modelo = TextEmbedding(MODELO_EMBEDDINGS)

        info = _cliente.get_collection(COLECCION)
        logger.info(
            "✅ RAG Qdrant activo — %d alimentos indexados",
            info.points_count or 0,
        )
        _rag_activo = True
        return True

    except Exception as exc:
        logger.error("Error inicializando Qdrant: %s — RAG desactivado", exc)
        _rag_activo = False
        return False


# ── Funciones públicas ────────────────────────────────────────────────────────

def buscar_alimento(query: str, n_resultados: int = 3) -> list[dict]:
    """
    Busca alimentos semánticamente similares a la query.

    Args:
        query: texto de búsqueda, ej: "pechuga de pollo a la plancha"
        n_resultados: cuántos resultados devolver (por defecto 3)

    Returns:
        Lista de dicts con datos nutricionales, ordenados por similitud desc.
        Lista vacía si RAG no disponible o no hay match.

    Ejemplo de resultado:
        {
            "nombre": "Pechuga de pollo",
            "kcal_100g": 110.0,
            "proteinas_100g": 23.0,
            "carbos_100g": 0.0,
            "grasas_100g": 2.0,
            "fibra_100g": 0.0,
            "sal_100g": 0.0,
            "alergenos": "",
            "similitud": 0.89
        }
    """
    if not _inicializar():
        return []

    try:
        # _modelo.embed devuelve un generador, tomamos la primera predicción
        vector = list(_modelo.embed([query]))[0].tolist()
        resultados_response = _cliente.query_points(           # type: ignore[union-attr]
            collection_name=COLECCION,
            query=vector,
            limit=n_resultados,
            score_threshold=0.0,                # devolvemos todos y filtramos manualmente
        )
        resultados = resultados_response.points

        salida = []
        for r in resultados:
            salida.append({
                "nombre":          r.payload.get("nombre", ""),
                "kcal_100g":       r.payload.get("kcal_100g", 0.0),
                "proteinas_100g":  r.payload.get("proteinas_100g", 0.0),
                "carbos_100g":     r.payload.get("carbos_100g", 0.0),
                "azucares_100g":   r.payload.get("azucares_100g", 0.0),
                "grasas_100g":     r.payload.get("grasas_100g", 0.0),
                "fibra_100g":      r.payload.get("fibra_100g", 0.0),
                "sal_100g":        r.payload.get("sal_100g", 0.0),
                "alergenos":       r.payload.get("alergenos", ""),
                "similitud":       round(max(0.0, r.score), 3),
            })

        return salida

    except Exception as exc:
        logger.error("Error en búsqueda Qdrant (query=%r): %s", query, exc)
        return []


def buscar_mejor_match(query: str) -> Optional[dict]:
    """
    Devuelve el alimento más parecido a la query usando una búsqueda híbrida
    (vectorial + re-ranking de coincidencia de palabras clave por prefijo).
    
    Devuelve None si:
    - RAG no disponible
    - No hay resultados
    - El mejor resultado re-ordenado no supera el umbral de similitud base (0.75)
    """
    # Buscamos los 40 candidatos principales en Qdrant
    resultados = buscar_alimento(query, n_resultados=40)
    if not resultados:
        return None

    # Extraer palabras clave de la consulta (limpiando puntuación y palabras de parada)
    query_clean = query.lower().replace(",", " ").replace(".", " ").replace(";", " ")
    query_words = set(query_clean.split())
    stop_words = {
        "de", "la", "a", "con", "en", "para", "un", "una", "el", "los", "las", 
        "y", "al", "del", "o", "u", "su", "sus", "por", "como", "plana", "plancha"
    }
    query_keywords = {w for w in query_words if w not in stop_words and len(w) > 2}

    best_item = None
    best_score = -1.0

    for r in resultados:
        nombre_clean = r["nombre"].lower().replace(",", " ").replace(".", " ").replace(";", " ")
        nombre_words = set(nombre_clean.split())
        nombre_keywords = {w for w in nombre_words if w not in stop_words and len(w) > 2}
        
        # Calcular coincidencia de palabras clave (con soporte de prefijos para tolerar typos)
        overlap = 0
        for qw in query_keywords:
            for nw in nombre_keywords:
                # Comprobación directa o si comparten un prefijo de al menos 4 letras (ej. mantequeilla -> mantequilla)
                if qw in nw or nw in qw or (len(qw) > 3 and len(nw) > 3 and qw[:4] == nw[:4]):
                    overlap += 1
                    break
        
        # Puntuación final combinada: similitud base + 0.15 por palabra clave coincidente
        score = r["similitud"] + (overlap * 0.15)
        
        if score > best_score:
            best_score = score
            best_item = r

    # Para ser válido, la similitud base (vectorial pura) del mejor candidato re-ordenado 
    # no debe ser inferior al umbral, pero si tiene buen match de palabras clave (overlap >= 2)
    # permitimos ser un poco más flexibles (umbral rebajado a 0.70)
    umbral = UMBRAL_SIMILITUD
    if best_item:
        best_name_clean = best_item["nombre"].lower().replace(",", " ").replace(".", " ").replace(";", " ")
        best_name_words = set(best_name_clean.split())
        best_name_keywords = {w for w in best_name_words if w not in stop_words and len(w) > 2}
        best_overlap = 0
        for qw in query_keywords:
            for nw in best_name_keywords:
                if qw in nw or nw in qw or (len(qw) > 3 and len(nw) > 3 and qw[:4] == nw[:4]):
                    best_overlap += 1
                    break
        
        if best_overlap >= 2:
            umbral = 0.70

        if best_item["similitud"] < umbral:
            logger.debug(
                "Match re-rankeado '%s' descartado: similitud base %.3f < umbral %.2f",
                best_item["nombre"], best_item["similitud"], umbral,
            )
            return None

    return best_item


def buscar_mejor_match_vision(query: str) -> Optional[dict]:
    """
    Versión más permisiva para el agente de visión.
    Umbral más bajo (0.55) porque los nombres vienen del modelo de visión
    y pueden no coincidir exactamente con la BD.
    """
    # Buscamos los 40 candidatos principales en Qdrant
    resultados = buscar_alimento(query, n_resultados=40)
    if not resultados:
        return None

    # Extraer palabras clave de la consulta (limpiando puntuación y palabras de parada)
    query_clean = query.lower().replace(",", " ").replace(".", " ").replace(";", " ")
    query_words = set(query_clean.split())
    stop_words = {
        "de", "la", "a", "con", "en", "para", "un", "una", "el", "los", "las", 
        "y", "al", "del", "o", "u", "su", "sus", "por", "como", "plana", "plancha"
    }
    query_keywords = {w for w in query_words if w not in stop_words and len(w) > 2}

    best_item = None
    best_score = -1.0

    for r in resultados:
        nombre_clean = r["nombre"].lower().replace(",", " ").replace(".", " ").replace(";", " ")
        nombre_words = set(nombre_clean.split())
        nombre_keywords = {w for w in nombre_words if w not in stop_words and len(w) > 2}
        
        # Calcular coincidencia de palabras clave (con soporte de prefijos para tolerar typos)
        overlap = 0
        for qw in query_keywords:
            for nw in nombre_keywords:
                if qw in nw or nw in qw or (len(qw) > 3 and len(nw) > 3 and qw[:4] == nw[:4]):
                    overlap += 1
                    break
        
        # Puntuación final combinada: similitud base + 0.15 por palabra clave coincidente
        score = r["similitud"] + (overlap * 0.15)
        
        if score > best_score:
            best_score = score
            best_item = r

    # Usamos un umbral mucho más bajo (0.55) para el agente de visión
    umbral = 0.55
    if best_item:
        if best_item["similitud"] < umbral:
            logger.debug(
                "Match de visión '%s' descartado: similitud base %.3f < umbral %.2f",
                best_item["nombre"], best_item["similitud"], umbral,
            )
            return None

    return best_item


# ── Corrección de ingredientes con datos verificados ─────────────────────────

def corregir_ingrediente(ingrediente: dict) -> dict:
    """
    Busca el ingrediente en Qdrant y, si encuentra un match fiable,
    recalcula sus macros en base a la cantidad real y los valores
    verificados por 100g.

    Args:
        ingrediente: dict con al menos {nombre, cantidad, unidad}

    Returns:
        El mismo dict, con campo "verificado_rag" (bool) añadido.
        Si se verificó, añade además los macros corregidos:
        kcal, proteinas_g, carbos_g, grasas_g (a nivel de ESTE ingrediente).
    """
    nombre   = ingrediente.get("nombre", "")
    cantidad = ingrediente.get("cantidad", 0)
    unidad   = ingrediente.get("unidad", "g")

    resultado = ingrediente.copy()
    resultado["verificado_rag"] = False

    # Solo podemos corregir si la unidad es de peso/volumen estándar
    if unidad not in ("g", "ml"):
        return resultado

    match = buscar_mejor_match(nombre)
    if match is None:
        return resultado

    # Factor de escala: valores en Qdrant son por 100g/100ml
    factor = cantidad / 100.0

    resultado["verificado_rag"]     = True
    resultado["nombre_verificado"]  = match["nombre"]
    resultado["kcal"]               = round(match["kcal_100g"]      * factor, 1)
    resultado["proteinas_g"]        = round(match["proteinas_100g"] * factor, 1)
    resultado["carbos_g"]           = round(match["carbos_100g"]    * factor, 1)
    resultado["grasas_g"]           = round(match["grasas_100g"]    * factor, 1)

    return resultado


def estado_rag() -> dict:
    """
    Devuelve información de diagnóstico sobre el estado del RAG.
    Útil para un endpoint de health check.
    """
    activo = _inicializar()

    if not activo or _cliente is None:
        return {
            "activo": False,
            "url": os.getenv("QDRANT_URL", "no configurada"),
            "puntos": 0,
            "coleccion": COLECCION,
        }

    try:
        info = _cliente.get_collection(COLECCION)
        return {
            "activo": True,
            "url": os.getenv("QDRANT_URL", ""),
            "coleccion": COLECCION,
            "puntos": info.points_count or 0,
            "modelo_embeddings": MODELO_EMBEDDINGS,
        }
    except Exception as exc:
        return {"activo": False, "error": str(exc)}
