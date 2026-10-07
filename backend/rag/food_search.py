"""
food_search.py

----------------

Búsqueda semántica y textual de alimentos usando Qdrant Cloud.

Funciona tanto en local como en producción.

Patrón:
    inicialización lazy singleton — el cliente se crea la primera
    vez que se hace una búsqueda, no al importar el módulo.

Si QDRANT_URL no está configurada:
    RAG desactivado graciosamente.
"""

import os
import logging
import unicodedata
from difflib import SequenceMatcher
from typing import Optional

from fastembed import TextEmbedding
from qdrant_client import QdrantClient

from backend.config import qdrant_url, qdrant_api_key


logger = logging.getLogger(__name__)


# ── Configuración ─────────────────────────────────────────────────────────────

MODELO_EMBEDDINGS = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

COLECCION = "alimentos"

UMBRAL_SIMILITUD = 0.75


# ── Singletons ────────────────────────────────────────────────────────────────

_cliente: Optional[QdrantClient] = None
_modelo: Optional[TextEmbedding] = None
_rag_activo: Optional[bool] = None

# Índice textual en memoria.
#
# Cada elemento contiene:
#   nombre
#   nombre_normalizado
#   datos nutricionales
#
# Así no tenemos que volver a consultar Qdrant cuando encontramos
# una coincidencia textual.
_indice_alimentos: Optional[list[dict]] = None


# ── Inicialización ────────────────────────────────────────────────────────────


def _inicializar() -> bool:
    """
    Inicializa el cliente Qdrant y el modelo de embeddings.

    Se ejecuta solo una vez.

    Devuelve:
        True  -> RAG disponible.
        False -> RAG desactivado.
    """

    global _cliente, _modelo, _rag_activo

    if _rag_activo is not None:
        return _rag_activo

    if not qdrant_url:
        logger.warning(
            "QDRANT_URL no configurada — RAG desactivado. "
            "Añade QDRANT_URL y QDRANT_API_KEY al .env "
            "o a las variables de Render."
        )

        _rag_activo = False
        return False

    try:
        logger.info(
            "Inicializando cliente Qdrant: %s",
            qdrant_url,
        )

        _cliente = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key,
            timeout=10,
        )

        # Verificar que la colección existe.
        colecciones = [
            c.name
            for c in _cliente.get_collections().collections
        ]

        if COLECCION not in colecciones:
            logger.warning(
                "Colección '%s' no encontrada en Qdrant. "
                "Ejecuta: python -m backend.rag.migrate_to_qdrant",
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


# ── Normalización textual ─────────────────────────────────────────────────────


def _normalizar_texto(texto: str) -> str:
    """
    Normaliza un texto para comparación de nombres.

    - minúsculas
    - elimina tildes
    - sustituye puntuación por espacios
    - elimina espacios duplicados
    """

    texto = str(texto).lower().strip()

    texto = unicodedata.normalize("NFD", texto)

    texto = "".join(
        c
        for c in texto
        if unicodedata.category(c) != "Mn"
    )

    for caracter in [
        ",",
        ".",
        ";",
        ":",
        "(",
        ")",
        "[",
        "]",
        "-",
        "_",
        "/",
        "'",
        '"',
    ]:
        texto = texto.replace(caracter, " ")

    return " ".join(texto.split())


# ── Índice textual ────────────────────────────────────────────────────────────


def _cargar_indice_alimentos() -> list[dict]:
    """
    Carga una sola vez los alimentos desde Qdrant.

    El índice se mantiene en memoria para evitar hacer un scroll
    completo de la colección en cada búsqueda.

    Además de los nombres, se guardan los datos nutricionales
    necesarios para que una coincidencia textual pueda devolverse
    directamente sin otra consulta a Qdrant.
    """

    global _indice_alimentos

    if _indice_alimentos is not None:
        return _indice_alimentos

    if not _inicializar() or _cliente is None:
        return []

    try:
        logger.info(
            "Cargando índice textual de alimentos desde Qdrant..."
        )

        indice = []
        offset = None

        while True:
            puntos, offset = _cliente.scroll(
                collection_name=COLECCION,
                limit=1000,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            for punto in puntos:
                payload = punto.payload or {}

                nombre = str(
                    payload.get("nombre", "")
                ).strip()

                if not nombre:
                    continue

                nombre_normalizado = str(
                    payload.get("nombre_normalizado", "")
                ).strip()

                indice.append(
                    {
                        "nombre": nombre,

                        "nombre_normalizado": (
                            nombre_normalizado
                            or _normalizar_texto(nombre)
                        ),

                        "kcal_100g": payload.get(
                            "kcal_100g",
                            0.0,
                        ),

                        "proteinas_100g": payload.get(
                            "proteinas_100g",
                            0.0,
                        ),

                        "carbos_100g": payload.get(
                            "carbos_100g",
                            0.0,
                        ),

                        "azucares_100g": payload.get(
                            "azucares_100g",
                            0.0,
                        ),

                        "grasas_100g": payload.get(
                            "grasas_100g",
                            0.0,
                        ),

                        "fibra_100g": payload.get(
                            "fibra_100g",
                            0.0,
                        ),

                        "sal_100g": payload.get(
                            "sal_100g",
                            0.0,
                        ),

                        "alergenos": payload.get(
                            "alergenos",
                            "",
                        ),
                    }
                )

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


# ── Búsqueda semántica ────────────────────────────────────────────────────────


def buscar_alimento(
    query: str,
    n_resultados: int = 3,
) -> list[dict]:
    """
    Busca alimentos semánticamente similares a la query.

    Args:
        query:
            Texto de búsqueda.

        n_resultados:
            Número máximo de resultados.

    Returns:
        Lista de alimentos ordenados por similitud.
    """

    if not _inicializar():
        return []

    if _modelo is None or _cliente is None:
        return []

    try:
        vector = list(
            _modelo.embed([query])
        )[0].tolist()

        resultados_response = _cliente.query_points(
            collection_name=COLECCION,
            query=vector,
            limit=n_resultados,
            score_threshold=0.0,
        )

        resultados = resultados_response.points

        salida = []

        for r in resultados:
            payload = r.payload or {}

            salida.append(
                {
                    "nombre": payload.get(
                        "nombre",
                        "",
                    ),

                    "kcal_100g": payload.get(
                        "kcal_100g",
                        0.0,
                    ),

                    "proteinas_100g": payload.get(
                        "proteinas_100g",
                        0.0,
                    ),

                    "carbos_100g": payload.get(
                        "carbos_100g",
                        0.0,
                    ),

                    "azucares_100g": payload.get(
                        "azucares_100g",
                        0.0,
                    ),

                    "grasas_100g": payload.get(
                        "grasas_100g",
                        0.0,
                    ),

                    "fibra_100g": payload.get(
                        "fibra_100g",
                        0.0,
                    ),

                    "sal_100g": payload.get(
                        "sal_100g",
                        0.0,
                    ),

                    "alergenos": payload.get(
                        "alergenos",
                        "",
                    ),

                    "similitud": round(
                        max(0.0, r.score),
                        3,
                    ),
                }
            )

        return salida

    except Exception as exc:
        logger.error(
            "Error en búsqueda Qdrant (query=%r): %s",
            query,
            exc,
        )

        return []


# ── Mejor coincidencia ───────────────────────────────────────────────────────


def buscar_mejor_match(
    query: str,
) -> Optional[dict]:
    """
    Busca el alimento más adecuado para una consulta.

    Estrategia:

    1. Coincidencia textual exacta.
    2. Coincidencia textual por nombre normalizado.
    3. Coincidencia por alias/variantes válidas.
    4. Si no hay coincidencia textual segura, usa Qdrant semántico.
    5. Rechaza productos derivados o con ingredientes adicionales.
    """

    if not query or not query.strip():
        return None

    # ---------------------------------------------------------
    # 1. NORMALIZACIÓN
    # ---------------------------------------------------------

    query_normalizada = _normalizar_texto(query)

    if not query_normalizada:
        return None

    query_words = query_normalizada.split()

    STOP_WORDS = {
        "de",
        "la",
        "a",
        "con",
        "en",
        "para",
        "un",
        "una",
        "el",
        "los",
        "las",
        "y",
        "al",
        "del",
        "o",
        "u",
        "su",
        "sus",
        "por",
        "como",
        "sin",
        "bajo",
        "baja",
    }

    query_words = {
        palabra
        for palabra in query_words
        if palabra not in STOP_WORDS
        and len(palabra) > 2
    }

    if not query_words:
        return None

    # ---------------------------------------------------------
    # 2. ALIAS
    # ---------------------------------------------------------

    ALIAS = {
        "platano": {
            "platano",
            "banana",
            "banano",
        },

        "banana": {
            "platano",
            "banana",
            "banano",
        },

        "banano": {
            "platano",
            "banana",
            "banano",
        },

        "salmon": {
            "salmon",
        },

        "atun": {
            "atun",
            "atún",
        },

        "batata": {
            "batata",
            "boniato",
            "camote",
        },

        "boniato": {
            "batata",
            "boniato",
            "camote",
        },

        "camote": {
            "batata",
            "boniato",
            "camote",
        },

        "cacahuete": {
            "cacahuete",
            "mani",
        },

        "mani": {
            "cacahuete",
            "mani",
        },

        "brocoli": {
            "brocoli",
        },

        "zanahoria": {
            "zanahoria",
        },

        "pollo": {
            "pollo",
        },

        "pechuga": {
            "pechuga",
        },

        "arroz": {
            "arroz",
        },

        "integral": {
            "integral",
        },

        "aguacate": {
            "aguacate",
            "palta",
        },

        "palta": {
            "aguacate",
            "palta",
        },

        "patata": {
            "patata",
            "papa",
        },

        "papa": {
            "patata",
            "papa",
        },

        "manzana": {
            "manzana",
        },

        "naranja": {
            "naranja",
        },

        "tomate": {
            "tomate",
        },

        "quinoa": {
            "quinoa",
        },

        "avena": {
            "avena",
        },

        "pavo": {
            "pavo",
        },

        "huevo": {
            "huevo",
        },

        "leche": {
            "leche",
        },

        "yogur": {
            "yogur",
            "yogurt",
        },

        "lenteja": {
            "lenteja",
            "lentejas",
        },

        "lentejas": {
            "lenteja",
            "lentejas",
        },

        "garbanzo": {
            "garbanzo",
            "garbanzos",
        },

        "garbanzos": {
            "garbanzo",
            "garbanzos",
        },

        "almendra": {
            "almendra",
            "almendras",
        },

        "almendras": {
            "almendra",
            "almendras",
        },

        "nuez": {
            "nuez",
            "nueces",
        },

        "nueces": {
            "nuez",
            "nueces",
        },
    }

    # ---------------------------------------------------------
    # 3. MODIFICADORES DE PRODUCTO
    # ---------------------------------------------------------

    MODIFICADORES_PRODUCTO = {
        "helado",
        "harina",
        "polvo",
        "potito",
        "crema",
        "galleta",
        "galletas",
        "bizcocho",
        "croissant",
        "croissants",
        "brioche",
        "compota",
        "pure",
        "fideos",
        "alfajor",
        "barrita",
        "barritas",
        "bar",
        "cereal",
        "cereales",
        "granola",
        "snack",
        "chips",
        "tarta",
        "pastel",
        "magdalena",
        "muffin",
        "cookie",
        "cookies",
        "salsa",
        "sopas",
        "sopa",
        "caldo",
        "relleno",
        "gratin",
        "gratinado",
        "gratinada",
        "ramen",
        "brocheta",
        "pincho",
        "pinchos",
        "aros",
        "dados",
        "varitas",
        "hamburguesa",
        "hamburguesas",
        "croquetas",
        "nuggets",
        "ahumado",
        "ahumada",
        "ahumados",
        "ahumadas",
        "frito",
        "frita",
        "fritos",
        "fritas",
        "asado",
        "asada",
        "asados",
        "asadas",
        "rebozado",
        "rebozada",
        "empanado",
        "empanada",
        "zumo",
        "jugo",
        "nectar",
        "bebida",
        "aceite",
        "conserva",
        "conservado",
        "conservada",
        "enlatado",
        "enlatada",
    }

    # ---------------------------------------------------------
    # 4. MODIFICADORES DESCRIPTIVOS VÁLIDOS
    # ---------------------------------------------------------

    MODIFICADORES_DESCRIPTIVOS = {
        "golden",
        "fuji",
        "gala",
        "reineta",
        "roja",
        "verde",
        "blanca",
        "blanco",
        "negra",
        "negro",
        "amarilla",
        "amarillo",
        "natural",
        "fresco",
        "fresca",
        "frescos",
        "frescas",
        "bio",
        "ecologico",
        "ecologica",
        "ecologicos",
        "ecologicas",
        "integral",
        "basmati",
        "jasmine",
        "jazmin",
    }

    # ---------------------------------------------------------
    # 5. COMPARACIÓN DE PALABRAS
    # ---------------------------------------------------------

    def son_equivalentes(
        palabra_query: str,
        palabra_candidato: str,
    ) -> bool:

        if palabra_query == palabra_candidato:
            return True

        alias_query = ALIAS.get(
            palabra_query,
            {palabra_query},
        )

        if palabra_candidato in alias_query:
            return True

        # Singular/plural sencillo.
        if (
            palabra_query.rstrip("s")
            == palabra_candidato.rstrip("s")
            and len(palabra_query) >= 4
        ):
            return True

        # Pequeños errores ortográficos.
        if (
            len(palabra_query) >= 5
            and len(palabra_candidato) >= 5
        ):
            ratio = SequenceMatcher(
                None,
                palabra_query,
                palabra_candidato,
            ).ratio()

            if ratio >= 0.90:
                return True

        return False

    # ---------------------------------------------------------
    # 6. CARGAR ÍNDICE TEXTUAL
    # ---------------------------------------------------------

    indice = _cargar_indice_alimentos()

    # ---------------------------------------------------------
    # 7. BUSCAR COINCIDENCIA TEXTUAL SEGURA
    # ---------------------------------------------------------

    candidatos_textuales = []

    for item in indice:

        nombre_original = item["nombre"]

        nombre = item["nombre_normalizado"]

        candidate_words = {
            palabra
            for palabra in nombre.split()
            if palabra not in STOP_WORDS
            and len(palabra) > 2
        }

        if not candidate_words:
            continue

        # Todas las palabras de la query deben aparecer.
        palabras_no_cubiertas = []

        for qword in query_words:

            encontrada = any(
                son_equivalentes(
                    qword,
                    cword,
                )
                for cword in candidate_words
            )

            if not encontrada:
                palabras_no_cubiertas.append(qword)

        if palabras_no_cubiertas:
            continue

        # Identificar palabras adicionales.
        palabras_extra = []

        for cword in candidate_words:

            encontrado = any(
                son_equivalentes(
                    qword,
                    cword,
                )
                for qword in query_words
            )

            if not encontrado:
                palabras_extra.append(cword)

        # Rechazar productos derivados.
        extras_producto = [
            palabra
            for palabra in palabras_extra
            if palabra in MODIFICADORES_PRODUCTO
        ]

        if extras_producto:
            continue

        # Rechazar ingredientes adicionales.
        extras_no_descriptivos = [
            palabra
            for palabra in palabras_extra
            if palabra not in MODIFICADORES_DESCRIPTIVOS
        ]

        if extras_no_descriptivos:
            continue

        # Score textual.
        coincidencias_exactas = sum(
            1
            for qword in query_words
            if qword in candidate_words
        )

        porcentaje_exactitud = (
            coincidencias_exactas
            / max(len(query_words), 1)
        )

        # Prioridad:
        # 1. nombre exacto
        # 2. misma base con variante descriptiva
        # 3. pequeños errores/alias

        if nombre == query_normalizada:
            score_textual = 1000.0

        else:
            score_textual = (
                porcentaje_exactitud * 100
                - len(palabras_extra) * 2
            )

        candidatos_textuales.append(
            (
                score_textual,
                len(palabras_extra),
                nombre_original,
                item,
            )
        )

    # ---------------------------------------------------------
    # 8. SI HAY MATCH TEXTUAL, USARLO
    # ---------------------------------------------------------

    if candidatos_textuales:

        candidatos_textuales.sort(
            key=lambda x: (
                x[0],
                -x[1],
            ),
            reverse=True,
        )

        mejor = candidatos_textuales[0][3]

        # Ya tenemos todos los datos nutricionales en memoria.
        return {
            "nombre": mejor["nombre"],
            "kcal_100g": mejor["kcal_100g"],
            "proteinas_100g": mejor["proteinas_100g"],
            "carbos_100g": mejor["carbos_100g"],
            "azucares_100g": mejor["azucares_100g"],
            "grasas_100g": mejor["grasas_100g"],
            "fibra_100g": mejor["fibra_100g"],
            "sal_100g": mejor["sal_100g"],
            "alergenos": mejor["alergenos"],
            "similitud": 1.0,
        }

    # ---------------------------------------------------------
    # 9. FALLBACK SEMÁNTICO
    # ---------------------------------------------------------

    resultados = buscar_alimento(
        query,
        n_resultados=100,
    )

    if not resultados:
        return None

    candidatos_validos = []

    for resultado in resultados:

        nombre_original = resultado.get(
            "nombre",
            "",
        )

        nombre = _normalizar_texto(
            nombre_original
        )

        if not nombre:
            continue

        candidate_words = {
            palabra
            for palabra in nombre.split()
            if palabra not in STOP_WORDS
            and len(palabra) > 2
        }

        if not candidate_words:
            continue

        palabras_no_cubiertas = []

        for qword in query_words:

            encontrada = any(
                son_equivalentes(
                    qword,
                    cword,
                )
                for cword in candidate_words
            )

            if not encontrada:
                palabras_no_cubiertas.append(qword)

        if palabras_no_cubiertas:
            continue

        palabras_extra = []

        for cword in candidate_words:

            encontrado = any(
                son_equivalentes(
                    qword,
                    cword,
                )
                for qword in query_words
            )

            if not encontrado:
                palabras_extra.append(cword)

        extras_producto = [
            palabra
            for palabra in palabras_extra
            if palabra in MODIFICADORES_PRODUCTO
        ]

        if extras_producto:
            continue

        extras_no_descriptivos = [
            palabra
            for palabra in palabras_extra
            if palabra not in MODIFICADORES_DESCRIPTIVOS
        ]

        if extras_no_descriptivos:
            continue

        similitud = float(
            resultado.get(
                "similitud",
                0.0,
            )
        )

        coincidencias_exactas = sum(
            1
            for qword in query_words
            if qword in candidate_words
        )

        porcentaje_exactitud = (
            coincidencias_exactas
            / max(len(query_words), 1)
        )

        score = (
            similitud * 0.70
            + porcentaje_exactitud * 0.30
        )

        candidatos_validos.append(
            (
                score,
                similitud,
                resultado,
            )
        )

    if not candidatos_validos:
        return None

    candidatos_validos.sort(
        key=lambda x: (
            x[0],
            x[1],
        ),
        reverse=True,
    )

    (
        mejor_score,
        mejor_similitud,
        mejor_resultado,
    ) = candidatos_validos[0]

    if mejor_similitud < UMBRAL_SIMILITUD:
        return None

    logger.debug(
        "Match semántico aceptado: '%s' -> '%s' | "
        "similitud=%.3f | score=%.3f",
        query,
        mejor_resultado["nombre"],
        mejor_similitud,
        mejor_score,
    )

    return mejor_resultado


# ── Búsqueda específica para visión ──────────────────────────────────────────


def buscar_mejor_match_vision(
    query: str,
) -> Optional[dict]:
    """
    Versión más permisiva para el agente de visión.

    Umbral más bajo (0.55) porque los nombres vienen del modelo
    de visión y pueden no coincidir exactamente con la BD.

    Esta función sigue utilizando búsqueda semántica.
    """

    resultados = buscar_alimento(
        query,
        n_resultados=40,
    )

    if not resultados:
        return None

    # Extraer palabras clave de la consulta.
    query_clean = (
        query
        .lower()
        .replace(",", " ")
        .replace(".", " ")
        .replace(";", " ")
    )

    query_words = set(
        query_clean.split()
    )

    stop_words = {
        "de",
        "la",
        "a",
        "con",
        "en",
        "para",
        "un",
        "una",
        "el",
        "los",
        "las",
        "y",
        "al",
        "del",
        "o",
        "u",
        "su",
        "sus",
        "por",
        "como",
        "plana",
        "plancha",
    }

    query_keywords = {
        w
        for w in query_words
        if w not in stop_words
        and len(w) > 2
    }

    best_item = None
    best_score = -1.0

    for r in resultados:

        nombre_clean = (
            r["nombre"]
            .lower()
            .replace(",", " ")
            .replace(".", " ")
            .replace(";", " ")
        )

        nombre_words = set(
            nombre_clean.split()
        )

        nombre_keywords = {
            w
            for w in nombre_words
            if w not in stop_words
            and len(w) > 2
        }

        # Calcular coincidencia de palabras clave.
        overlap = 0

        for qw in query_keywords:

            for nw in nombre_keywords:

                if (
                    qw in nw
                    or nw in qw
                    or (
                        len(qw) > 3
                        and len(nw) > 3
                        and qw[:4] == nw[:4]
                    )
                ):
                    overlap += 1
                    break

        # Puntuación final combinada.
        score = (
            r["similitud"]
            + (overlap * 0.15)
        )

        if score > best_score:
            best_score = score
            best_item = r

    # Umbral más bajo para visión.
    umbral = 0.55

    if best_item:

        if best_item["similitud"] < umbral:
            logger.debug(
                "Match de visión '%s' descartado: "
                "similitud base %.3f < umbral %.2f",
                best_item["nombre"],
                best_item["similitud"],
                umbral,
            )

            return None

    return best_item


# ── Corrección de ingredientes ────────────────────────────────────────────────


def corregir_ingrediente(
    ingrediente: dict,
) -> dict:
    """
    Busca el ingrediente en Qdrant y, si encuentra un match fiable,
    recalcula sus macros en base a la cantidad real y los valores
    verificados por 100g.

    Args:
        ingrediente:
            Dict con al menos:
                nombre
                cantidad
                unidad

    Returns:
        El mismo dict con:
            verificado_rag

        Si se verificó:
            nombre_verificado
            kcal
            proteinas_g
            carbos_g
            grasas_g
    """

    nombre = ingrediente.get(
        "nombre",
        "",
    )

    cantidad = ingrediente.get(
        "cantidad",
        0,
    )

    unidad = ingrediente.get(
        "unidad",
        "g",
    )

    resultado = ingrediente.copy()

    resultado["verificado_rag"] = False

    # Solo podemos corregir si la unidad es peso/volumen estándar.
    if unidad not in ("g", "ml"):
        return resultado

    match = buscar_mejor_match(nombre)

    if match is None:
        return resultado

    # Los valores de Qdrant son por 100g/100ml.
    factor = cantidad / 100.0

    resultado["verificado_rag"] = True

    resultado["nombre_verificado"] = match[
        "nombre"
    ]

    resultado["kcal"] = round(
        match["kcal_100g"] * factor,
        1,
    )

    resultado["proteinas_g"] = round(
        match["proteinas_100g"] * factor,
        1,
    )

    resultado["carbos_g"] = round(
        match["carbos_100g"] * factor,
        1,
    )

    resultado["grasas_g"] = round(
        match["grasas_100g"] * factor,
        1,
    )

    return resultado


# ── Estado del RAG ────────────────────────────────────────────────────────────


def estado_rag() -> dict:
    """
    Devuelve información de diagnóstico sobre el estado del RAG.

    Útil para un endpoint de health check.
    """

    activo = _inicializar()

    if not activo or _cliente is None:
        return {
            "activo": False,
            "url": os.getenv(
                "QDRANT_URL",
                "no configurada",
            ),
            "puntos": 0,
            "coleccion": COLECCION,
        }

    try:
        info = _cliente.get_collection(
            COLECCION
        )

        return {
            "activo": True,
            "url": os.getenv(
                "QDRANT_URL",
                "",
            ),
            "coleccion": COLECCION,
            "puntos": info.points_count or 0,
            "modelo_embeddings": MODELO_EMBEDDINGS,
        }

    except Exception as exc:
        return {
            "activo": False,
            "error": str(exc),
        }