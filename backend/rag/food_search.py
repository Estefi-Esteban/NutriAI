"""
food_search.py
--------------
Búsqueda y verificación de alimentos con Qdrant.

Prioridad:
1. Coincidencia textual segura.
2. Coincidencia textual por núcleo.
3. Fallback semántico filtrado.
4. Validación nutricional común a todas las rutas de búsqueda.

Importante: encontrar un nombre parecido no basta para marcar un ingrediente
como verificado. También se comprueban los valores nutricionales.
"""
import logging
import os
import re
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
MODELO_EMBEDDINGS = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
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
    "de", "la", "a", "con", "en", "para", "un", "una", "el", "los",
    "las", "y", "al", "del", "o", "u", "su", "sus", "por", "como",
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
    "mantequilla": {"mantequilla", "crema"},
    "crema": {"crema", "mantequilla"},
    "brocoli": {"brocoli"},
    "zanahoria": {"zanahoria"},
    "pollo": {"pollo"},
    "pechuga": {"pechuga"},
    "arroz": {"arroz"},
    # Variantes frecuentes que no se resuelven con rstrip("s") ni con
    # la distancia de edición (p. ej. integral/integrales y azúcar/azúcares).
    "integral": {"integral", "integrales"},
    "integrales": {"integral", "integrales"},
    "azucar": {"azucar", "azucares"},
    "azucares": {"azucar", "azucares"},
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
    "huevo": {"huevo", "huevos"},
    "huevos": {"huevo", "huevos"},
    "leche": {"leche"},
    "yogur": {"yogur", "yogurt"},
    "yogurt": {"yogur", "yogurt"},
    "calabacin": {"calabacin", "calabacines"},
    "calabacines": {"calabacin", "calabacines"},
    "lenteja": {"lenteja", "lentejas"},
    "lentejas": {"lenteja", "lentejas"},
    "garbanzo": {"garbanzo", "garbanzos"},
    "garbanzos": {"garbanzo", "garbanzos"},
    "almendra": {"almendra", "almendras"},
    "almendras": {"almendra", "almendras"},
    "nuez": {"nuez", "nueces"},
    "nueces": {"nuez", "nueces"},
}

MODIFICADORES_PRODUCTO = {
    "helado", "harina", "polvo", "potito", "crema", "galleta", "galletas",
    "bizcocho", "croissant", "croissants", "brioche", "compota", "pure",
    "fideos", "alfajor", "barrita", "barritas", "bar", "cereal", "cereales",
    "granola", "snack", "chips", "tarta", "pastel", "magdalena", "muffin",
    "cookie", "cookies", "salsa", "sopa", "sopas", "caldo", "relleno",
    "gratin", "gratinado", "gratinada", "ramen", "brocheta", "pincho",
    "pinchos", "aros", "dados", "varitas", "hamburguesa", "hamburguesas",
    "burger", "burgers", "croquetas", "nuggets", "ahumado", "ahumada",
    "ahumados", "ahumadas", "frito", "frita", "fritos", "fritas", "asado",
    "asada", "asados", "asadas", "rebozado", "rebozada", "empanado",
    "empanada", "zumo", "jugo", "nectar", "bebida", "aceite", "conserva",
    "conservado", "conservada", "enlatado", "enlatada",
}

MODIFICADORES_DESCRIPTIVOS = {
    "golden", "fuji", "gala", "reineta", "roja", "rojo", "verde",
    "blanca", "blanco", "negra", "negro", "amarilla", "amarillo",
    "natural", "naturales", "cremoso", "cremosa", "cremosos", "cremosas",
    "fresco", "fresca", "frescos", "frescas", "bio", "ecologico",
    "ecologica", "ecologicos", "ecologicas", "integral", "integrales",
    "basmati", "jasmine", "jazmin",
}

MODIFICADORES_NUTRICIONALES = {
    "sin", "azucar", "azucares", "zero", "sugar", "bajo", "baja", "bajos",
    "bajas", "ligero", "ligera", "ligeros", "ligeras", "light", "desnatado",
    "desnatada", "desnatados", "desnatadas", "entero", "entera", "enteros",
    "enteras", "natural", "naturales", "sal", "cocido", "cocida", "cocidos",
    "cocidas", "crudo", "cruda", "crudos", "crudas", "neutro", "neutra",
    "sabor",
}

MODIFICADORES_ESTADO = {
    "cocido", "cocida", "cocidos", "cocidas", "crudo", "cruda", "crudos",
    "crudas", "frito", "frita", "fritos", "fritas", "asado", "asada",
    "asados", "asadas",
}

# ---------------------------------------------------------------------------
# Utilidades de texto y números
# ---------------------------------------------------------------------------
def _normalizar_texto(texto: str) -> str:
    """Normaliza minúsculas, tildes, puntuación y espacios."""
    if not texto:
        return ""
    texto = unicodedata.normalize("NFD", str(texto).lower().strip())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    for caracter in (",", ".", ";", ":", "(", ")", "[", "]", "-", "_",
                     "/", "'", '"', "\\"):
        texto = texto.replace(caracter, " ")
    return " ".join(texto.split())


def _es_token_numerico(token: str) -> bool:
    """Indica si un token es solo un número o porcentaje."""
    limpio = token.replace("%", "").replace(",", ".")
    try:
        float(limpio)
        return True
    except ValueError:
        return False


def _palabras(texto: str) -> set[str]:
    """Devuelve palabras normalizadas relevantes, ignorando números."""
    return {
        palabra for palabra in _normalizar_texto(texto).split()
        if palabra not in STOP_WORDS and len(palabra) > 2
        and not _es_token_numerico(palabra)
    }


def _numero(valor, defecto: float = 0.0) -> float:
    """Convierte valores del dataset a float sin propagar None/NaN."""
    try:
        numero = float(valor)
        if numero != numero:  # NaN
            return defecto
        return numero
    except (TypeError, ValueError):
        return defecto


def _son_equivalentes(query: str, candidato: str) -> bool:
    """Comprueba igualdad, alias, singular/plural o pequeño typo."""
    if query == candidato:
        return True
    if candidato in ALIAS.get(query, {query}):
        return True
    if query.rstrip("s") == candidato.rstrip("s") and len(query) >= 4:
        return True
    if len(query) >= 5 and len(candidato) >= 5:
        return SequenceMatcher(None, query, candidato).ratio() >= 0.90
    return False


def _coincidencias(query_words: set[str], candidate_words: set[str]) -> int:
    return sum(
        any(_son_equivalentes(q, c) for c in candidate_words)
        for q in query_words
    )


def _extraer_partes_query(query_words: set[str]) -> tuple[set[str], set[str]]:
    """Separa alimento base y modificadores nutricionales."""
    modificadores = {
        palabra for palabra in query_words
        if palabra in MODIFICADORES_NUTRICIONALES
    }
    base = query_words - modificadores
    if {"bajo", "grasa"} <= query_words or {"baja", "grasa"} <= query_words:
        base.discard("grasa")
        modificadores.add("grasa")
    return base, modificadores


def _contiene_modificador(modificador: str, palabras_candidato: set[str]) -> bool:
    equivalencias = {
        "sin": {"sin", "zero"},
        "azucar": {"azucar", "azucares", "sugar"},
        "azucares": {"azucar", "azucares", "sugar"},
        "zero": {"zero"},
        "sugar": {"sugar", "azucar", "azucares"},
        "bajo": {"bajo", "baja", "bajos", "bajas"},
        "baja": {"bajo", "baja", "bajos", "bajas"},
        "ligero": {"ligero", "ligera", "ligeros", "ligeras", "light"},
        "ligera": {"ligero", "ligera", "ligeros", "ligeras", "light"},
        "desnatado": {"desnatado", "desnatada", "desnatados", "desnatadas"},
        "desnatada": {"desnatado", "desnatada", "desnatados", "desnatadas"},
        "natural": {"natural", "naturales"},
        "cocido": {"cocido", "cocida", "cocidos", "cocidas"},
        "crudo": {"crudo", "cruda", "crudos", "crudas"},
        "neutro": {"neutro", "neutra"},
    }
    return bool(equivalencias.get(modificador, {modificador}) & palabras_candidato)


def _cumple_modificadores_criticos(
    modificadores_query: set[str],
    palabras_candidato: set[str],
) -> bool:
    """Evita relajar restricciones explícitas como 'sin azúcar'."""
    if "sin" in modificadores_query:
        sin_espanol = "sin" in palabras_candidato and bool(
            {"azucar", "azucares"} & palabras_candidato
        )
        zero_sugar_ingles = {"zero", "sugar"} <= palabras_candidato
        if not (sin_espanol or zero_sugar_ingles):
            return False
    return True


def _nutricionalmente_plausible_para_query(query: str, item: dict) -> bool:
    """
    Filtro conservador de plausibilidad nutricional.

    No certifica científicamente cada alimento: rechaza valores claramente
    imposibles/inconsistentes y variantes que contradicen la consulta.
    Se aplica a todas las rutas de matching, incluida la semántica.
    """
    palabras_query = _palabras(query)
    palabras_item = _palabras(
        item.get("nombre_normalizado") or item.get("nombre", "")
    )
    conjunto = palabras_query | palabras_item

    kcal = _numero(item.get("kcal_100g"))
    proteina = _numero(item.get("proteinas_100g"))
    carbos = _numero(item.get("carbos_100g"))
    grasa = _numero(item.get("grasas_100g"))
    sal = _numero(item.get("sal_100g"))

    if kcal <= 0 or kcal > 900:
        return False
    if min(proteina, carbos, grasa, sal) < 0:
        return False
    if max(proteina, carbos, grasa) > 100:
        return False

    # Atwater aproximado con tolerancia amplia para fibra, redondeos y etiquetas incompletas.
    energia_aprox = proteina * 4 + carbos * 4 + grasa * 9
    if energia_aprox > 0:
        diferencia = abs(kcal - energia_aprox)
        if diferencia > max(150.0, energia_aprox * 0.85):
            return False

    # Rechaza fichas incompatibles con una crema de cacahuete convencional.
    es_crema_cacahuete = (
        bool({"cacahuete", "mani"} & conjunto)
        and bool({"mantequilla", "crema"} & conjunto)
    )
    if es_crema_cacahuete and grasa >= 20 and proteina < 5:
        return False

    # Calabacín sin preparación explícita: evitar productos fritos con nombre genérico.
    es_calabacin = bool({"calabacin", "calabacines"} & conjunto)
    preparacion_explicita = bool({
        "frito", "frita", "fritos", "fritas", "rebozado", "rebozada",
        "empanado", "empanada", "braseado", "braseada", "salteado",
        "salteada", "asado", "asada", "plancha", "horno",
    } & palabras_query)
    if es_calabacin and not preparacion_explicita:
        if kcal > 80 or grasa > 5 or sal > 1:
            return False

    # Un huevo corriente no puede tener cientos de kcal por 100 g.
    es_huevo = bool({"huevo", "huevos"} & conjunto)
    if es_huevo and kcal > 250:
        return False

    # "0 %" es una condición explícita: no confirmar una variante con demasiada grasa.
    solicita_cero_grasa = bool(
        re.search(r"\b0\s*%", query.lower())
        or "desnatado" in palabras_query
        or "desnatada" in palabras_query
    )
    es_yogur = bool({"yogur", "yogurt"} & conjunto)
    if es_yogur and solicita_cero_grasa and grasa > 1.5:
        return False

    # Si la consulta y el candidato declaran estados de preparación distintos, rechazar.
    estados_query = MODIFICADORES_ESTADO & palabras_query
    estados_item = MODIFICADORES_ESTADO & palabras_item
    if estados_query and estados_item and not any(
        _son_equivalentes(q, c) for q in estados_query for c in estados_item
    ):
        return False

    return True


def _resultado_limpio(item: dict, similitud: float = 1.0) -> dict:
    """Normaliza el formato de salida del matcher."""
    return {
        "nombre": item.get("nombre", ""),
        "kcal_100g": _numero(item.get("kcal_100g")),
        "proteinas_100g": _numero(item.get("proteinas_100g")),
        "carbos_100g": _numero(item.get("carbos_100g")),
        "azucares_100g": _numero(item.get("azucares_100g")),
        "grasas_100g": _numero(item.get("grasas_100g")),
        "fibra_100g": _numero(item.get("fibra_100g")),
        "sal_100g": _numero(item.get("sal_100g")),
        "alergenos": item.get("alergenos", ""),
        "calidad_nutricional": item.get("calidad_nutricional", ""),
        "score_calidad": _numero(item.get("score_calidad")),
        "estado_alimento": item.get("estado_alimento", ""),
        "outlier_nutricional": _es_outlier(item),
        "similitud": round(max(0.0, min(1.0, _numero(similitud))), 3),
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
        logger.warning("QDRANT_URL no configurada — RAG desactivado.")
        _rag_activo = False
        return False
    try:
        _cliente = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=10)
        colecciones = {c.name for c in _cliente.get_collections().collections}
        if COLECCION not in colecciones:
            logger.warning("Colección '%s' no encontrada en Qdrant.", COLECCION)
            _rag_activo = False
            return False
        logger.info("Cargando modelo de embeddings '%s'...", MODELO_EMBEDDINGS)
        _modelo = TextEmbedding(MODELO_EMBEDDINGS)
        info = _cliente.get_collection(COLECCION)
        logger.info("RAG Qdrant activo — %d alimentos indexados", info.points_count or 0)
        _rag_activo = True
        return True
    except Exception as exc:
        logger.error("Error inicializando Qdrant: %s — RAG desactivado", exc)
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
                collection_name=COLECCION, limit=SCROLL_BATCH, offset=offset,
                with_payload=True, with_vectors=False,
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
        logger.info("Índice textual cargado: %d alimentos", len(indice))
        return indice
    except Exception as exc:
        logger.error("Error cargando índice textual de Qdrant: %s", exc)
        return []


def buscar_alimento(query: str, n_resultados: int = 3) -> list[dict]:
    """Busca alimentos semánticamente similares en Qdrant."""
    if not _inicializar() or _modelo is None or _cliente is None:
        return []
    try:
        vector = list(_modelo.embed([query]))[0].tolist()
        response = _cliente.query_points(
            collection_name=COLECCION, query=vector, limit=n_resultados,
            score_threshold=0.0,
        )
        return [
            _resultado_limpio(r.payload or {}, max(0.0, r.score))
            for r in response.points
        ]
    except Exception as exc:
        logger.error("Error en búsqueda Qdrant (query=%r): %s", query, exc)
        return []


# ---------------------------------------------------------------------------
# Calidad y restricciones del matching
# ---------------------------------------------------------------------------
def _score_calidad_item(item: dict) -> float:
    """Devuelve el score de calidad del alimento, si está disponible."""
    return _numero(item.get("score_calidad"))


def _es_outlier(item: dict) -> bool:
    """Interpreta booleanos del CSV/Qdrant, incluidos strings."""
    valor = item.get("outlier_nutricional", False)
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (int, float)):
        return valor != 0
    return str(valor).strip().lower() in {"true", "1", "yes", "si", "sí"}



def _extras_son_validos(palabras_extra: list[str]) -> bool:
    """Permite extras descriptivos/nutricionales y avena como ingrediente de granola."""
    extras_permitidas = (
        MODIFICADORES_DESCRIPTIVOS
        | MODIFICADORES_NUTRICIONALES
    )

    return not any(
        palabra not in extras_permitidas
        and palabra != "avena"
        for palabra in palabras_extra
    )



# ---------------------------------------------------------------------------
# Matching textual
# ---------------------------------------------------------------------------
def _match_textual(query: str, indice: list[dict]) -> Optional[dict]:
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
        if not _cumple_modificadores_criticos(modificadores_query, candidate_words):
            continue
        coincidencias_base = _coincidencias(base_query, candidate_words)
        if base_query and coincidencias_base < len(base_query):
            continue

        palabras_extra = [
            palabra for palabra in candidate_words
            if not any(_son_equivalentes(palabra, q) for q in base_query)
        ]
        if any(palabra in MODIFICADORES_PRODUCTO for palabra in palabras_extra):
            continue
        extras_invalidas = [
            palabra for palabra in palabras_extra
            if palabra not in MODIFICADORES_DESCRIPTIVOS
            and palabra not in MODIFICADORES_NUTRICIONALES
        ]
        if extras_invalidas:
            continue
        if _es_outlier(item) or not _nutricionalmente_plausible_para_query(query, item):
            continue

        modificadores_cubiertos = sum(
            _contiene_modificador(modificador, candidate_words)
            for modificador in modificadores_query
        )
        porcentaje_base = coincidencias_base / len(base_query) if base_query else 0.0
        porcentaje_modificadores = (
            modificadores_cubiertos / len(modificadores_query)
            if modificadores_query else 0.0
        )
        score = 1000.0 if nombre == query_normalizada else (
            porcentaje_base * 100 + porcentaje_modificadores * 25
            - len(palabras_extra) * 2
        )
        candidatos.append((
            score, porcentaje_base, porcentaje_modificadores,
            -len(palabras_extra), _score_calidad_item(item), item,
        ))

    if not candidatos:
        return None
    candidatos.sort(key=lambda x: (x[0], x[1], x[2], x[4], x[3]), reverse=True)
    return _resultado_limpio(candidatos[0][5])


def _match_textual_por_nucleo(query: str, indice: list[dict]) -> Optional[dict]:
    """Busca una coincidencia por núcleo sin aceptar otro plato/alimento."""
    query_words = _palabras(query)
    base_query, modificadores_query = _extraer_partes_query(query_words)
    if not base_query:
        return None
    candidatos = []

    for item in indice:
        candidate_words = _palabras(item.get("nombre_normalizado", ""))
        if not candidate_words:
            continue
        if not _cumple_modificadores_criticos(modificadores_query, candidate_words):
            continue
        coincidencias_base = _coincidencias(base_query, candidate_words)
        if coincidencias_base < len(base_query):
            continue

        palabras_extra = [
            palabra for palabra in candidate_words
            if not any(_son_equivalentes(palabra, q) for q in base_query)
        ]
        if any(palabra in MODIFICADORES_PRODUCTO for palabra in palabras_extra):
            continue
        extras_invalidas = [
            palabra for palabra in palabras_extra
            if palabra not in MODIFICADORES_DESCRIPTIVOS
            and palabra not in MODIFICADORES_NUTRICIONALES
            and palabra not in STOP_WORDS
            and palabra != "avena"
        ]
        if extras_invalidas:
            continue
        if _es_outlier(item) or not _nutricionalmente_plausible_para_query(query, item):
            continue

        modificadores_cubiertos = sum(
            _contiene_modificador(modificador, candidate_words)
            for modificador in modificadores_query
        )
        porcentaje_modificadores = (
            modificadores_cubiertos / len(modificadores_query)
            if modificadores_query else 0.0
        )
        score = 100.0 + porcentaje_modificadores * 25.0
        if _normalizar_texto(item.get("nombre", "")) == _normalizar_texto(query):
            score += 1000.0
        candidatos.append((
            score, porcentaje_modificadores, _score_calidad_item(item),
            -len(palabras_extra), item,
        ))

    if not candidatos:
        return None
    candidatos.sort(key=lambda x: (x[0], x[1], x[2], x[3]), reverse=True)
    mejor = candidatos[0][4]
    # El score de ranking no es una similitud de embedding; no debe superar 1.
    return _resultado_limpio(mejor, similitud=1.0)


def buscar_mejor_match(query: str) -> Optional[dict]:
    """Busca el alimento más fiable usando texto y, como último recurso, Qdrant."""
    if not query or not query.strip():
        return None

    indice = _cargar_indice_alimentos()
    match = _match_textual(query, indice)
    if match is not None:
        return match

    match = _match_textual_por_nucleo(query, indice)
    if match is not None:
        return match

    resultados = buscar_alimento(query, n_resultados=100)
    if not resultados:
        return None

    query_words = _palabras(query)
    base_query, modificadores_query = _extraer_partes_query(query_words)
    candidatos = []

    for resultado in resultados:
        if _es_outlier(resultado) or not _nutricionalmente_plausible_para_query(query, resultado):
            continue
        nombre_words = _palabras(resultado["nombre"])
        if not nombre_words:
            continue
        if not _cumple_modificadores_criticos(modificadores_query, nombre_words):
            continue

        coincidencias_base = _coincidencias(base_query, nombre_words)
        cobertura_base = coincidencias_base / len(base_query) if base_query else 0.0
        if len(base_query) >= 2 and cobertura_base < 1.0:
            continue

        palabras_extra = [
            palabra for palabra in nombre_words
            if not any(_son_equivalentes(palabra, q) for q in base_query)
        ]
        if not _extras_son_validos(palabras_extra):
            continue

        cobertura_modificadores = (
            sum(_contiene_modificador(m, nombre_words) for m in modificadores_query)
            / len(modificadores_query)
            if modificadores_query else 0.0
        )
        similitud = _numero(resultado.get("similitud"))
        score = similitud * 0.70 + cobertura_base * 0.25 + cobertura_modificadores * 0.05
        if modificadores_query and cobertura_modificadores == 0:
            score -= 0.15
        candidatos.append((
            score, similitud, cobertura_base, cobertura_modificadores,
            _score_calidad_item(resultado), resultado,
        ))

    if not candidatos:
        return None
    candidatos.sort(key=lambda x: (x[0], x[1], x[2], x[3], x[4]), reverse=True)
    mejor_score, similitud, _, _, _, mejor = candidatos[0]
    if similitud < UMBRAL_SIMILITUD:
        return None
    logger.debug(
        "Match semántico aceptado: '%s' -> '%s' | similitud=%.3f | score=%.3f",
        query, mejor["nombre"], similitud, mejor_score,
    )
    return mejor


# ---------------------------------------------------------------------------
# Matching para visión
# ---------------------------------------------------------------------------
def buscar_mejor_match_vision(query: str) -> Optional[dict]:
    """Match de visión más permisivo, pero filtra outliers y nutrientes absurdos."""
    resultados = buscar_alimento(query, n_resultados=40)
    if not resultados:
        return None
    query_words = _palabras(query)
    mejor = None
    mejor_score = -1.0

    for resultado in resultados:
        if _es_outlier(resultado) or not _nutricionalmente_plausible_para_query(query, resultado):
            continue
        nombre_words = _palabras(resultado["nombre"])
        if not nombre_words:
            continue
        overlap = _coincidencias(query_words, nombre_words)
        score = _numero(resultado.get("similitud")) + overlap * 0.15
        if score > mejor_score:
            mejor_score = score
            mejor = resultado

    if mejor is None or _numero(mejor.get("similitud")) < UMBRAL_VISION:
        return None
    return mejor


# ---------------------------------------------------------------------------
# Corrección nutricional
# ---------------------------------------------------------------------------
def corregir_ingrediente(ingrediente: dict) -> dict:
    """
    Verifica un ingrediente contra Qdrant y recalcula sus macros según cantidad.

    Las cantidades en ml se mantienen por compatibilidad con el esquema actual.
    Como el dataset está expresado por 100 g, en líquidos esta conversión es
    aproximada salvo que se conozca la densidad del alimento.
    """
    resultado = ingrediente.copy()
    resultado["verificado_rag"] = False
    nombre = str(ingrediente.get("nombre", "") or "").strip()
    cantidad = ingrediente.get("cantidad", 0)
    unidad = str(ingrediente.get("unidad", "g") or "g").strip().lower()

    if unidad not in ("g", "ml") or not nombre:
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

    kcal = _numero(match.get("kcal_100g"), -1)
    proteinas = _numero(match.get("proteinas_100g"), -1)
    carbos = _numero(match.get("carbos_100g"), -1)
    grasas = _numero(match.get("grasas_100g"), -1)
    if min(kcal, proteinas, carbos, grasas) < 0:
        return resultado

    factor = cantidad / 100.0
    resultado.update({
        "verificado_rag": True,
        "nombre_verificado": match["nombre"],
        "kcal": round(kcal * factor, 1),
        "proteinas_g": round(proteinas * factor, 1),
        "carbos_g": round(carbos * factor, 1),
        "grasas_g": round(grasas * factor, 1),
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
        return {"activo": False, "error": str(exc)}
