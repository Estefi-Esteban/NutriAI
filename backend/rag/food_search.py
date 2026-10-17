"""
food_search.py
--------------
Búsqueda y verificación de alimentos con Qdrant.
Estrategia:
1. Match textual seguro sobre el índice de nombres.
2. Si no existe, fallback semántico con Qdrant.
3. Los modificadores nutricionales ("sin azúcar", "bajo en grasa", etc.)
   se usan para mejorar el ranking, no para confundir el alimento base.
4. corregir_ingrediente() recalcula los macros según la cantidad real.
"""
import logging
import os
import unicodedata
from difflib import SequenceMatcher
from typing import Optional
from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from backend.config import qdrant_url, qdrant_api_key
logger = logging.getLogger(__name__)
# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
MODELO_EMBEDDINGS = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
COLECCION = "alimentos"
UMBRAL_SIMILITUD = 0.75
UMBRAL_VISION = 0.55
SCROLL_BATCH = 1000
# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------
_cliente: Optional[QdrantClient] = None
_modelo: Optional[TextEmbedding] = None
_rag_activo: Optional[bool] = None
_indice_alimentos: Optional[list[dict]] = None
# ---------------------------------------------------------------------------
# Diccionarios de matching
# ---------------------------------------------------------------------------
STOP_WORDS = {
    "de", "la", "a", "con", "en", "para", "un", "una",
    "el", "los", "las", "y", "al", "del", "o", "u",
    "su", "sus", "por", "como",
}
ALIAS = {
    "platano": {"platano", "banana", "banano"},
    "banana": {"platano", "banana", "banano"},
    "banano": {"platano", "banana", "banano"},
    "salmon": {"salmon"},
    "atun": {"atun"},
    "batata": {"batata", "boniato", "camote"},
    "boniato": {"batata", "boniato", "camote"},
    "camote": {"batata", "boniato", "camote"},
    "cacahuete": {"cacahuete", "mani"},
    "mani": {"cacahuete", "mani"},
    # In Spanish food names, "mantequilla de cacahuete" and
    # "crema de cacahuete" commonly refer to the same food category.
    "mantequilla": {"mantequilla", "crema"},
    "crema": {"crema", "mantequilla"},
    "brocoli": {"brocoli"},
    "zanahoria": {"zanahoria"},
    "pollo": {"pollo"},
    "pechuga": {"pechuga"},
    "arroz": {"arroz"},
    "integral": {"integral"},
    "aguacate": {"aguacate", "palta"},
    "palta": {"aguacate", "palta"},
    "patata": {"patata", "papa"},
    "papa": {"patata", "papa"},
    "manzana": {"manzana"},
    "naranja": {"naranja"},
    "tomate": {"tomate"},
    "quinoa": {"quinoa"},
    "avena": {"avena"},
    "pavo": {"pavo"},
    "huevo": {"huevo"},
    "leche": {"leche"},
    "yogur": {"yogur", "yogurt"},
    "yogurt": {"yogur", "yogurt"},
    "lenteja": {"lenteja", "lentejas"},
    "lentejas": {"lenteja", "lentejas"},
    "garbanzo": {"garbanzo", "garbanzos"},
    "garbanzos": {"garbanzo", "garbanzos"},
    "almendra": {"almendra", "almendras"},
    "almendras": {"almendra", "almendras"},
    "nuez": {"nuez", "nueces"},
    "nueces": {"nuez", "nueces"},
}
# Palabras que indican que el candidato es un producto/plato derivado.
MODIFICADORES_PRODUCTO = {
    "helado", "harina", "polvo", "potito", "crema",
    "galleta", "galletas", "bizcocho", "croissant", "croissants",
    "brioche", "compota", "pure", "fideos", "alfajor",
    "barrita", "barritas", "bar", "cereal", "cereales",
    "granola", "snack", "chips", "tarta", "pastel", "magdalena",
    "muffin", "cookie", "cookies", "salsa", "sopa", "sopas",
    "caldo", "relleno", "gratin", "gratinado", "gratinada",
    "ramen", "brocheta", "pincho", "pinchos", "aros", "dados",
    "varitas", "hamburguesa", "hamburguesas", "burger", "burgers",
    "croquetas", "nuggets", "ahumado", "ahumada", "ahumados",
    "ahumadas", "frito", "frita", "fritos", "fritas",
    "asado", "asada", "asados", "asadas", "rebozado",
    "rebozada", "empanado", "empanada", "zumo", "jugo",
    "nectar", "bebida", "aceite", "conserva", "conservado",
    "conservada", "enlatado", "enlatada",
}
# Modificadores que describen una variante del alimento.
MODIFICADORES_DESCRIPTIVOS = {
    "golden", "fuji", "gala", "reineta",
    "roja", "rojo", "verde", "verde",
    "blanca", "blanco", "negra", "negro",
    "amarilla", "amarillo",
    "natural", "naturales",
    "cremoso", "cremosa", "cremosos", "cremosas",
    "fresco", "fresca", "frescos", "frescas",
    "bio", "ecologico", "ecologica", "ecologicos", "ecologicas",
    "integral", "integrales",
    "basmati", "jasmine", "jazmin",
}
MODIFICADORES_NUTRICIONALES = {
    "sin", "azucar", "azucares",
    # Equivalentes en inglés para etiquetas explícitas como "Zero Sugar".
    "zero", "sugar",
    "bajo", "baja", "bajos", "bajas",
    "ligero", "ligera", "ligeros", "ligeras", "light",
    "desnatado", "desnatada", "desnatados", "desnatadas",
    "entero", "entera", "enteros", "enteras",
    "natural", "naturales",
    "sal",
    "cocido", "cocida", "cocidos", "cocidas",
    "crudo", "cruda", "crudos", "crudas",
    "neutro", "neutra",
    "sabor",
}
MODIFICADORES_ESTADO = {
    "cocido", "cocida", "cocidos", "cocidas",
    "crudo", "cruda", "crudos", "crudas",
    "frito", "frita", "fritos", "fritas",
    "asado", "asada", "asados", "asadas",
}
# ---------------------------------------------------------------------------
# Utilidades de texto
# ---------------------------------------------------------------------------
def _normalizar_texto(texto: str) -> str:
    """Normaliza minúsculas, tildes, puntuación y espacios."""
    if not texto:
        return ""
    texto = unicodedata.normalize("NFD", str(texto).lower().strip())
    texto = "".join(
        c for c in texto
        if unicodedata.category(c) != "Mn"
    )
    for caracter in (",", ".", ";", ":", "(", ")", "[", "]", "-", "_", "/", "'", '"' , "\\"):
        texto = texto.replace(caracter, " ")
    return " ".join(texto.split())
def _es_token_numerico(token: str) -> bool:
    """Indica si un token es solo un número o porcentaje (p. ej. 100%)."""
    limpio = token.replace("%", "").replace(",", ".")
    try:
        float(limpio)
        return True
    except ValueError:
        return False
def _palabras(texto: str) -> set[str]:
    """Devuelve palabras normalizadas relevantes, ignorando números."""
    return {
        palabra
        for palabra in _normalizar_texto(texto).split()
        if (
            palabra not in STOP_WORDS
            and len(palabra) > 2
            and not _es_token_numerico(palabra)
        )
    }
def _son_equivalentes(query: str, candidato: str) -> bool:
    """Comprueba igualdad, alias, singular/plural o pequeño typo."""
    if query == candidato:
        return True
    if candidato in ALIAS.get(query, {query}):
        return True
    if (
        query.rstrip("s") == candidato.rstrip("s")
        and len(query) >= 4
    ):
        return True
    if len(query) >= 5 and len(candidato) >= 5:
        return SequenceMatcher(None, query, candidato).ratio() >= 0.90
    return False
def _coincidencias(query_words: set[str], candidate_words: set[str]) -> int:
    return sum(
        any(_son_equivalentes(q, c) for c in candidate_words)
        for q in query_words
    )
def _extraer_partes_query(
    query_words: set[str],
) -> tuple[set[str], set[str]]:
    """
    Separa alimento base y modificadores.
    Ejemplo:
        yogur griego bajo en grasa
        -> base: yogur, griego
        -> modificadores: bajo, grasa
        granola sin azucar
        -> base: granola
        -> modificadores: sin, azucar
    """
    modificadores = {
        palabra
        for palabra in query_words
        if palabra in MODIFICADORES_NUTRICIONALES
    }
    base = query_words - modificadores
    # "grasa" solo es modificador cuando forma parte de
    # "bajo/baja en grasa". Evitamos tratar "grasa" como alimento base.
    if {"bajo", "grasa"} <= query_words:
        base.discard("grasa")
        modificadores.add("grasa")
    if {"baja", "grasa"} <= query_words:
        base.discard("grasa")
        modificadores.add("grasa")
    return base, modificadores
def _contiene_modificador(
    modificador: str,
    palabras_candidato: set[str],
) -> bool:
    equivalencias = {
        # Solo equiparamos "sin azúcar" con "zero sugar" cuando el nombre
        # del candidato contiene ambos términos; no con "low sugar".
        "sin": {"sin", "zero"},
        "azucar": {"azucar", "azucares", "sugar"},
        "azucares": {"azucar", "azucares", "sugar"},
        "zero": {"zero"},
        "sugar": {"sugar", "azucar", "azucares"},
        "bajo": {"bajo", "baja", "bajos", "bajas"},
        "baja": {"bajo", "baja", "bajos", "bajas"},
        "ligero": {"ligero", "ligera", "ligeros", "ligeras", "light"},
        "ligera": {"ligero", "ligera", "ligeros", "ligeras", "light"},
        "desnatado": {
            "desnatado", "desnatada", "desnatados", "desnatadas"
        },
        "desnatada": {
            "desnatado", "desnatada", "desnatados", "desnatadas"
        },
        "natural": {"natural", "naturales"},
        "cocido": {"cocido", "cocida", "cocidos", "cocidas"},
        "crudo": {"crudo", "cruda", "crudos", "crudas"},
        "neutro": {"neutro", "neutra"},
    }
    return bool(
        equivalencias.get(modificador, {modificador})
        & palabras_candidato
    )
def _cumple_modificadores_criticos(
    modificadores_query: set[str],
    palabras_candidato: set[str],
) -> bool:
    """
    Evita relajar restricciones explícitas importantes.
    Por ejemplo, "sin azúcar" no debe aceptar "bajo en azúcar"
    si el candidato no declara también "sin".
    """
    if "sin" in modificadores_query:
        sin_espanol = "sin" in palabras_candidato and bool(
            {"azucar", "azucares"} & palabras_candidato
        )
        zero_sugar_ingles = {"zero", "sugar"} <= palabras_candidato
        if not (sin_espanol or zero_sugar_ingles):
            return False
    return True


def _nutricionalmente_plausible_para_query(query: str, item: dict) -> bool:
    """Descarta registros claramente incompletos para alimentos concretos."""
    palabras_query = _palabras(query)
    palabras_item = _palabras(item.get("nombre_normalizado", item.get("nombre", "")))
    es_crema_cacahuete = (
        bool({"cacahuete", "mani"} & (palabras_query | palabras_item))
        and bool({"mantequilla", "crema"} & (palabras_query | palabras_item))
    )
    if es_crema_cacahuete:
        try:
            proteina = float(item.get("proteinas_100g", 0) or 0)
            grasa = float(item.get("grasas_100g", 0) or 0)
        except (TypeError, ValueError):
            return False
        # Una crema de cacahuete con mucha grasa y 0–1 g de proteína/100 g
        # es un registro sospechoso: mejor no verificar macros dudosos.
        if grasa >= 20 and proteina < 5:
            return False
    return True


def _resultado_limpio(item: dict, similitud: float = 1.0) -> dict:
    """Normaliza el formato de salida del matcher."""
    return {
        "nombre": item.get("nombre", ""),
        "kcal_100g": item.get("kcal_100g", 0.0),
        "proteinas_100g": item.get("proteinas_100g", 0.0),
        "carbos_100g": item.get("carbos_100g", 0.0),
        "azucares_100g": item.get("azucares_100g", 0.0),
        "grasas_100g": item.get("grasas_100g", 0.0),
        "fibra_100g": item.get("fibra_100g", 0.0),
        "sal_100g": item.get("sal_100g", 0.0),
        "alergenos": item.get("alergenos", ""),
        "calidad_nutricional": item.get("calidad_nutricional", ""),
        "score_calidad": item.get("score_calidad", 0.0),
        "estado_alimento": item.get("estado_alimento", ""),
        "outlier_nutricional": item.get("outlier_nutricional", False),
        "similitud": round(float(similitud), 3),
    }
# ---------------------------------------------------------------------------
# Qdrant
# ---------------------------------------------------------------------------
def _inicializar() -> bool:
    """Inicializa Qdrant y el modelo de embeddings una sola vez."""
    global _cliente, _modelo, _rag_activo
    if _rag_activo is not None:
        return _rag_activo
    if not qdrant_url:
        logger.warning(
            "QDRANT_URL no configurada — RAG desactivado."
        )
        _rag_activo = False
        return False
    try:
        _cliente = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key,
            timeout=10,
        )
        colecciones = {
            c.name
            for c in _cliente.get_collections().collections
        }
        if COLECCION not in colecciones:
            logger.warning(
                "Colección '%s' no encontrada en Qdrant.",
                COLECCION,
            )
            _rag_activo = False
            return False
        logger.info(
            "Cargando modelo de embeddings '%s'...",
            MODELO_EMBEDDINGS,
        )
        _modelo = TextEmbedding(MODELO_EMBEDDINGS)
        info = _cliente.get_collection(COLECCION)
        logger.info(
            "RAG Qdrant activo — %d alimentos indexados",
            info.points_count or 0,
        )
        _rag_activo = True
        return True
    except Exception as exc:
        logger.error(
            "Error inicializando Qdrant: %s — RAG desactivado",
            exc,
        )
        _rag_activo = False
        return False
def _cargar_indice_alimentos() -> list[dict]:
    """Carga el índice textual de Qdrant una sola vez."""
    global _indice_alimentos
    if _indice_alimentos is not None:
        return _indice_alimentos
    if not _inicializar() or _cliente is None:
        return []
    try:
        indice = []
        offset = None
        while True:
            puntos, offset = _cliente.scroll(
                collection_name=COLECCION,
                limit=SCROLL_BATCH,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for punto in puntos:
                payload = punto.payload or {}
                nombre = str(payload.get("nombre", "")).strip()
                if not nombre:
                    continue
                indice.append({
                    "nombre": nombre,
                    "nombre_normalizado": (
                        str(payload.get("nombre_normalizado", "")).strip()
                        or _normalizar_texto(nombre)
                    ),
                    "kcal_100g": payload.get("kcal_100g", 0.0),
                    "proteinas_100g": payload.get("proteinas_100g", 0.0),
                    "carbos_100g": payload.get("carbos_100g", 0.0),
                    "azucares_100g": payload.get("azucares_100g", 0.0),
                    "grasas_100g": payload.get("grasas_100g", 0.0),
                    "fibra_100g": payload.get("fibra_100g", 0.0),
                    "sal_100g": payload.get("sal_100g", 0.0),
                    "alergenos": payload.get("alergenos", ""),
                    "calidad_nutricional": payload.get("calidad_nutricional", ""),
                    "score_calidad": payload.get("score_calidad", 0.0),
                    "estado_alimento": payload.get("estado_alimento", ""),
                    "outlier_nutricional": payload.get("outlier_nutricional", False),
                })
            if offset is None:
                break
        _indice_alimentos = indice
        logger.info(
            "Índice textual cargado: %d alimentos",
            len(indice),
        )
        return indice
    except Exception as exc:
        logger.error(
            "Error cargando índice textual de Qdrant: %s",
            exc,
        )
        return []
def buscar_alimento(
    query: str,
    n_resultados: int = 3,
) -> list[dict]:
    """Busca alimentos semánticamente similares en Qdrant."""
    if not _inicializar() or _modelo is None or _cliente is None:
        return []
    try:
        vector = list(_modelo.embed([query]))[0].tolist()
        response = _cliente.query_points(
            collection_name=COLECCION,
            query=vector,
            limit=n_resultados,
            score_threshold=0.0,
        )
        return [
            _resultado_limpio(
                r.payload or {},
                max(0.0, r.score),
            )
            for r in response.points
        ]
    except Exception as exc:
        logger.error(
            "Error en búsqueda Qdrant (query=%r): %s",
            query,
            exc,
        )
        return []
# ---------------------------------------------------------------------------
# Calidad y restricciones del matching
# ---------------------------------------------------------------------------
def _score_calidad_item(item: dict) -> float:
    """Devuelve el score de calidad del alimento, si está disponible."""
    try:
        return float(item.get("score_calidad", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0
def _es_outlier(item: dict) -> bool:
    return bool(item.get("outlier_nutricional", False))
def _extras_son_validos(
    palabras_extra: list[str],
) -> bool:
    """Permite solo extras que describen la variante, no otro alimento."""
    return not any(
        palabra not in MODIFICADORES_DESCRIPTIVOS
        and palabra not in MODIFICADORES_NUTRICIONALES
        for palabra in palabras_extra
    )
# ---------------------------------------------------------------------------
# Matching textual
# ---------------------------------------------------------------------------
def _match_textual(
    query: str,
    indice: list[dict],
) -> Optional[dict]:
    """Busca un match textual seguro y devuelve el mejor candidato."""
    query_normalizada = _normalizar_texto(query)
    query_words = _palabras(query)
    if not query_words:
        return None
    base_query, modificadores_query = _extraer_partes_query(query_words)
    candidatos = []
    for item in indice:
        nombre = item["nombre_normalizado"]
        candidate_words = _palabras(nombre)
        if not candidate_words:
            continue
        if not _cumple_modificadores_criticos(
            modificadores_query, candidate_words
        ):
            continue
        # Todo el núcleo del alimento debe estar presente.
        coincidencias_base = _coincidencias(
            base_query,
            candidate_words,
        )
        if base_query and coincidencias_base < len(base_query):
            continue
        # Palabras adicionales del candidato.
        palabras_extra = [
            palabra
            for palabra in candidate_words
            if not any(
                _son_equivalentes(palabra, q)
                for q in base_query
            )
        ]
        # No aceptar un producto/plato derivado cuando buscamos
        # el alimento base.
        if any(
            palabra in MODIFICADORES_PRODUCTO
            for palabra in palabras_extra
        ):
            continue
        # Las palabras extra solo pueden ser variantes descriptivas
        # o nutricionales.
        extras_invalidas = [
            palabra
            for palabra in palabras_extra
            if (
                palabra not in MODIFICADORES_DESCRIPTIVOS
                and palabra not in MODIFICADORES_NUTRICIONALES
            )
        ]
        if extras_invalidas:
            continue
        if _es_outlier(item) or not _nutricionalmente_plausible_para_query(query, item):
            continue
        # ¿Cuántos modificadores de la consulta aparecen en el candidato?
        modificadores_cubiertos = sum(
            _contiene_modificador(modificador, candidate_words)
            for modificador in modificadores_query
        )
        porcentaje_base = (
            coincidencias_base / len(base_query)
            if base_query else 0.0
        )
        porcentaje_modificadores = (
            modificadores_cubiertos / len(modificadores_query)
            if modificadores_query else 0.0
        )
        # Coincidencias exactas del nombre tienen máxima prioridad.
        if nombre == query_normalizada:
            score = 1000.0
        else:
            score = (
                porcentaje_base * 100
                + porcentaje_modificadores * 25
                - len(palabras_extra) * 2
            )
        candidatos.append((
            score,
            porcentaje_base,
            porcentaje_modificadores,
            -len(palabras_extra),
            _score_calidad_item(item),
            item,
        ))
    if not candidatos:
        return None
    candidatos.sort(
        key=lambda x: (x[0], x[1], x[2], x[4], x[3]),
        reverse=True,
    )
    return _resultado_limpio(candidatos[0][5])
# ---------------------------------------------------------------------------
# Mejor match
# ---------------------------------------------------------------------------
def _match_textual_por_nucleo(
    query: str,
    indice: list[dict],
) -> Optional[dict]:
    """
    Busca una coincidencia donde todas las palabras del alimento base
    aparecen en el candidato.
    Ejemplo:
        "jugo de limón" -> "Jugo 100% de limón"
    No acepta candidatos que añadan otro alimento/plato principal:
        "jugo de limón" -> "Atún con jugo de limón"
    """
    query_words = _palabras(query)
    base_query, modificadores_query = _extraer_partes_query(query_words)
    if not base_query:
        return None
    candidatos = []
    for item in indice:
        candidate_words = _palabras(item.get("nombre_normalizado", ""))
        if not candidate_words:
            continue
        if not _cumple_modificadores_criticos(
            modificadores_query, candidate_words
        ):
            continue
        coincidencias_base = _coincidencias(base_query, candidate_words)
        if coincidencias_base < len(base_query):
            continue
        palabras_extra = [
            palabra
            for palabra in candidate_words
            if not any(
                _son_equivalentes(palabra, q)
                for q in base_query
            )
        ]
        if any(
            palabra in MODIFICADORES_PRODUCTO
            for palabra in palabras_extra
        ):
            continue
        extras_invalidas = [
            palabra
            for palabra in palabras_extra
            if (
                palabra not in MODIFICADORES_DESCRIPTIVOS
                and palabra not in MODIFICADORES_NUTRICIONALES
                and palabra not in STOP_WORDS
            )
        ]
        if extras_invalidas or _es_outlier(item):
            continue
        modificadores_cubiertos = sum(
            _contiene_modificador(modificador, candidate_words)
            for modificador in modificadores_query
        )
        porcentaje_modificadores = (
            modificadores_cubiertos / len(modificadores_query)
            if modificadores_query
            else 0.0
        )
        # Núcleo completo > modificadores > calidad.
        score = 100.0 + porcentaje_modificadores * 25.0
        if (
            _normalizar_texto(item.get("nombre", ""))
            == _normalizar_texto(query)
        ):
            score += 1000.0
        candidatos.append(
            (
                score,
                porcentaje_modificadores,
                _score_calidad_item(item),
                -len(palabras_extra),
                item,
            )
        )
    if not candidatos:
        return None
    candidatos.sort(
        key=lambda x: (x[0], x[1], x[2], x[3]),
        reverse=True,
    )
    mejor = candidatos[0][4]
    return _resultado_limpio(
        mejor,
        similitud=round(candidatos[0][0] / 100.0, 3),
    )
def buscar_mejor_match(query: str) -> Optional[dict]:
    """
    Encuentra el alimento más fiable para una consulta.
    Prioridad:
    1. Match textual exacto/seguro.
    2. Match textual por núcleo/variante.
    3. Fallback semántico filtrado.
    """
    if not query or not query.strip():
        return None
    indice = _cargar_indice_alimentos()
    # 1. Textual exacto/seguro.
    match = _match_textual(query, indice)
    if match is not None:
        return match
    # 2. Textual por núcleo.
    # Permite variantes como "jugo 100% de limón" sin abrir
    # la puerta a "atún con jugo de limón".
    match = _match_textual_por_nucleo(query, indice)
    if match is not None:
        return match
    # 3. Semántico.
    resultados = buscar_alimento(query, n_resultados=100)
    if not resultados:
        return None
    query_words = _palabras(query)
    base_query, modificadores_query = _extraer_partes_query(query_words)
    candidatos = []
    for resultado in resultados:
        if _es_outlier(resultado):
            continue
        nombre_words = _palabras(resultado["nombre"])
        if not nombre_words:
            continue
        if not _cumple_modificadores_criticos(
            modificadores_query, nombre_words
        ):
            continue
        coincidencias_base = _coincidencias(
            base_query,
            nombre_words,
        )
        cobertura_base = (
            coincidencias_base / len(base_query)
            if base_query else 0.0
        )
        # Si el alimento tiene varias palabras núcleo, exigimos que
        # estén todas presentes. Así evitamos:
        #   "verduras mixtas" -> "albóndigas mixtas"
        #   "jugo de limón" -> "atún con jugo de limón"
        if len(base_query) >= 2 and cobertura_base < 1.0:
            continue
        palabras_extra = [
            palabra
            for palabra in nombre_words
            if not any(
                _son_equivalentes(palabra, q)
                for q in base_query
            )
        ]
        # El candidato no puede introducir otro alimento/plato.
        if not _extras_son_validos(palabras_extra):
            continue
        cobertura_modificadores = (
            sum(
                _contiene_modificador(m, nombre_words)
                for m in modificadores_query
            )
            / len(modificadores_query)
            if modificadores_query
            else 0.0
        )
        score = (
            resultado["similitud"] * 0.70
            + cobertura_base * 0.25
            + cobertura_modificadores * 0.05
        )
        # Penalizamos variantes que no cumplen modificadores explícitos.
        if modificadores_query and cobertura_modificadores == 0:
            score -= 0.15
        candidatos.append((
            score,
            resultado["similitud"],
            cobertura_base,
            cobertura_modificadores,
            _score_calidad_item(resultado),
            resultado,
        ))
    if not candidatos:
        return None
    candidatos.sort(
        key=lambda x: (x[0], x[1], x[2], x[3], x[4]),
        reverse=True,
    )
    mejor_score, similitud, _, _, _, mejor = candidatos[0]
    if similitud < UMBRAL_SIMILITUD:
        return None
    logger.debug(
        "Match semántico aceptado: '%s' -> '%s' | "
        "similitud=%.3f | score=%.3f",
        query,
        mejor["nombre"],
        similitud,
        mejor_score,
    )
    return mejor
# ---------------------------------------------------------------------------
# Matching para visión
# ---------------------------------------------------------------------------
def buscar_mejor_match_vision(query: str) -> Optional[dict]:
    """
    Match más permisivo para nombres procedentes del modelo de visión.
    """
    resultados = buscar_alimento(query, n_resultados=40)
    if not resultados:
        return None
    query_words = _palabras(query)
    mejor = None
    mejor_score = -1.0
    for resultado in resultados:
        nombre_words = _palabras(resultado["nombre"])
        if not nombre_words:
            continue
        overlap = _coincidencias(query_words, nombre_words)
        score = resultado["similitud"] + overlap * 0.15
        if score > mejor_score:
            mejor_score = score
            mejor = resultado
    if mejor is None or mejor["similitud"] < UMBRAL_VISION:
        return None
    return mejor
# ---------------------------------------------------------------------------
# Corrección nutricional
# ---------------------------------------------------------------------------
def corregir_ingrediente(ingrediente: dict) -> dict:
    """
    Verifica un ingrediente contra Qdrant y recalcula sus macros
    según la cantidad indicada.
    """
    resultado = ingrediente.copy()
    resultado["verificado_rag"] = False
    nombre = ingrediente.get("nombre", "")
    cantidad = ingrediente.get("cantidad", 0)
    unidad = ingrediente.get("unidad", "g")
    if unidad not in ("g", "ml"):
        return resultado
    try:
        cantidad = float(cantidad)
    except (TypeError, ValueError):
        return resultado
    if cantidad <= 0:
        return resultado
    match = buscar_mejor_match(nombre)
    if match is None:
        return resultado
    factor = cantidad / 100.0
    resultado.update({
        "verificado_rag": True,
        "nombre_verificado": match["nombre"],
        "kcal": round(match["kcal_100g"] * factor, 1),
        "proteinas_g": round(match["proteinas_100g"] * factor, 1),
        "carbos_g": round(match["carbos_100g"] * factor, 1),
        "grasas_g": round(match["grasas_100g"] * factor, 1),
    })
    return resultado
# ---------------------------------------------------------------------------
# Estado del RAG
# ---------------------------------------------------------------------------
def estado_rag() -> dict:
    """Devuelve información de diagnóstico del RAG."""
    if not _inicializar() or _cliente is None:
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
        return {
            "activo": False,
            "error": str(exc),
        }
