
"""
food_search.py
--------------
Búsqueda y verificación de alimentos con Qdrant.

Arquitectura:
1. Qdrant proporciona los payloads externos.
2. Los payloads se convierten a modelos Alimento.
3. La búsqueda textual utiliza normalización genérica, sin alias alimentarios
   inventados ni catálogos de equivalencias escritos manualmente.
4. La búsqueda vectorial actúa como fallback.
5. La validación nutricional es común a todas las rutas.
6. Los resultados públicos conservan el formato dict por compatibilidad
   con los agentes existentes.

Importante:
- Un nutriente desconocido se representa como None, nunca como cero.
- Una coincidencia textual o vectorial no implica verificación nutricional.
- Para verificar un ingrediente se necesitan kcal, proteínas, carbohidratos
  y grasas disponibles.
"""

from __future__ import annotations

import logging
import math
import os
import re
import unicodedata

from collections.abc import Mapping
from typing import Any

from fastembed import TextEmbedding
from qdrant_client import QdrantClient

from backend.config import qdrant_url, qdrant_api_key
from backend.rag.models.food import Alimento

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

MAX_RESULTADOS_VECTORIALES = 100

# Nutrientes imprescindibles para calcular macros.
NUTRIENTES_OBLIGATORIOS = (
    "kcal_100g",
    "proteinas_100g",
    "carbos_100g",
    "grasas_100g",
)


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

_cliente: QdrantClient | None = None
_modelo: TextEmbedding | None = None
_rag_activo: bool | None = None

_indice_alimentos: list[Alimento] | None = None


# ---------------------------------------------------------------------------
# Utilidades numéricas
# ---------------------------------------------------------------------------

def _numero(
    valor: object,
    defecto: float | None = None,
) -> float | None:
    """
    Convierte un valor externo a float.

    No convierte valores desconocidos en cero.
    Conserva el cero real.
    """
    if valor is None or isinstance(valor, bool):
        return defecto

    try:
        numero = float(valor)
    except (TypeError, ValueError, OverflowError):
        return defecto

    if not math.isfinite(numero):
        return defecto

    return numero


def _nutriente_disponible(valor: float | None) -> bool:
    """Indica si un nutriente contiene un valor válido."""
    return (
        valor is not None
        and math.isfinite(valor)
        and valor >= 0.0
    )


def _tiene_nutricion_suficiente(alimento: Alimento) -> bool:
    """
    Comprueba que están disponibles los nutrientes necesarios
    para calcular los macros de un ingrediente.
    """
    nutricion = alimento.nutricion

    return all(
        _nutriente_disponible(getattr(nutricion, campo))
        for campo in NUTRIENTES_OBLIGATORIOS
    )


# ---------------------------------------------------------------------------
# Normalización textual genérica
# ---------------------------------------------------------------------------

def _normalizar_texto(texto: str) -> str:
    """
    Normaliza texto sin introducir equivalencias semánticas.

    Operaciones:
    - minúsculas;
    - eliminación de tildes;
    - sustitución de puntuación;
    - normalización de espacios.
    """
    if not texto:
        return ""

    texto = unicodedata.normalize(
        "NFKD",
        str(texto).casefold().strip(),
    )

    texto = "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )

    texto = re.sub(r"[^\w\s%]", " ", texto)

    return " ".join(texto.split())


def _es_token_numerico(token: str) -> bool:
    """Comprueba si un token representa un número o porcentaje."""
    limpio = token.replace("%", "").replace(",", ".")

    try:
        float(limpio)
        return True
    except (TypeError, ValueError):
        return False


def _palabras(texto: str) -> frozenset[str]:
    """
    Extrae tokens normalizados.

    Solo elimina conectores lingüísticos genéricos.
    No elimina nombres de alimentos ni modificadores alimentarios.
    """
    conectores = {
        "de",
        "la",
        "el",
        "los",
        "las",
        "un",
        "una",
        "unos",
        "unas",
        "y",
        "o",
        "u",
        "en",
        "con",
        "por",
        "para",
        "del",
        "al",
    }

    return frozenset(
        palabra
        for palabra in _normalizar_texto(texto).split()
        if palabra not in conectores
        and not _es_token_numerico(palabra)
    )


def _coincidencias(
    query_words: frozenset[str],
    candidate_words: frozenset[str],
) -> int:
    """Cuenta coincidencias exactas entre tokens normalizados."""
    return len(query_words & candidate_words)


def _cobertura_tokens(
    query_words: frozenset[str],
    candidate_words: frozenset[str],
) -> float:
    """Calcula la proporción de tokens de consulta encontrados."""
    if not query_words:
        return 0.0

    return _coincidencias(
        query_words,
        candidate_words,
    ) / len(query_words)


# ---------------------------------------------------------------------------
# Adaptación del dominio
# ---------------------------------------------------------------------------

def _alimento_desde_payload(
    payload: Mapping[str, Any],
    identificador: str | int | None = None,
) -> Alimento | None:
    """
    Convierte un payload externo en un Alimento.

    La conversión se centraliza en el modelo de dominio.
    """
    try:
        alimento = Alimento.desde_payload(
            payload,
            identificador=identificador,
        )

        if not alimento.nombre.strip():
            return None

        return alimento

    except Exception:
        logger.debug(
            "Payload de alimento inválido. ID=%s",
            identificador,
            exc_info=True,
        )
        return None


def _alimento_a_dict(
    alimento: Alimento,
    similitud: float = 1.0,
) -> dict[str, Any]:
    """
    Adapta el modelo de dominio al formato público histórico.

    Se mantiene la compatibilidad con los consumidores actuales.
    Los nutrientes ausentes siguen siendo None.
    """
    nutricion = alimento.nutricion

    similitud_segura = _numero(similitud, defecto=0.0) or 0.0

    return {
        "id": alimento.id,
        "nombre": alimento.nombre,
        "nombre_normalizado": (
            alimento.nombre_normalizado
            or _normalizar_texto(alimento.nombre)
        ),
        "kcal_100g": nutricion.kcal_100g,
        "proteinas_100g": nutricion.proteinas_100g,
        "carbos_100g": nutricion.carbos_100g,
        "azucares_100g": nutricion.azucares_100g,
        "grasas_100g": nutricion.grasas_100g,
        "fibra_100g": nutricion.fibra_100g,
        "sal_100g": nutricion.sal_100g,
        "alergenos": alimento.alergenos,
        "categorias": alimento.categorias,
        "calidad_nutricional": alimento.calidad_nutricional,
        "score_calidad": alimento.score_calidad,
        "estado_alimento": alimento.estado_alimento,
        "outlier_nutricional": alimento.outlier_nutricional,
        "similitud": round(
            max(0.0, min(1.0, similitud_segura)),
            3,
        ),
    }


def _resultado_limpio(
    item: Alimento | Mapping[str, Any],
    similitud: float = 1.0,
) -> dict[str, Any]:
    """
    Normaliza resultados para los consumidores existentes.

    Acepta Alimento como formato interno y Mapping únicamente
    para mantener compatibilidad con resultados externos.
    """
    if isinstance(item, Alimento):
        return _alimento_a_dict(item, similitud)

    payload = _alimento_desde_payload(item)

    if payload is None:
        return {
            "nombre": "",
            "kcal_100g": None,
            "proteinas_100g": None,
            "carbos_100g": None,
            "azucares_100g": None,
            "grasas_100g": None,
            "fibra_100g": None,
            "sal_100g": None,
            "alergenos": "",
            "calidad_nutricional": "",
            "score_calidad": 0.0,
            "estado_alimento": "",
            "outlier_nutricional": False,
            "similitud": 0.0,
        }

    return _alimento_a_dict(payload, similitud)


# ---------------------------------------------------------------------------
# Qdrant
# ---------------------------------------------------------------------------

def _inicializar() -> bool:
    """Inicializa Qdrant sin cargar el modelo de embeddings."""
    global _cliente, _rag_activo

    if _rag_activo is not None:
        return _rag_activo

    if not qdrant_url:
        logger.warning(
            "QDRANT_URL no configurada. RAG desactivado."
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
            coleccion.name
            for coleccion in _cliente.get_collections().collections
        }

        if COLECCION not in colecciones:
            logger.warning(
                "Colección '%s' no encontrada.",
                COLECCION,
            )
            _rag_activo = False
            return False

        info = _cliente.get_collection(COLECCION)

        logger.info(
            "Qdrant conectado. Colección=%s, puntos=%s",
            COLECCION,
            info.points_count or 0,
        )

        _rag_activo = True
        return True

    except Exception:
        logger.exception(
            "Error inicializando Qdrant. RAG desactivado."
        )
        _cliente = None
        _rag_activo = False
        return False


def _obtener_modelo() -> TextEmbedding:
    """Carga el modelo de embeddings de forma diferida."""
    global _modelo

    if _modelo is None:
        logger.info(
            "Cargando modelo de embeddings: %s",
            MODELO_EMBEDDINGS,
        )

        _modelo = TextEmbedding(MODELO_EMBEDDINGS)

    return _modelo


def _cargar_indice_alimentos() -> list[Alimento]:
    """
    Carga los alimentos de Qdrant en un índice tipado.

    El índice se mantiene en memoria para evitar recorrer Qdrant
    en cada búsqueda textual.
    """
    global _indice_alimentos

    if _indice_alimentos is not None:
        return _indice_alimentos

    if not _inicializar() or _cliente is None:
        return []

    try:
        indice: list[Alimento] = []
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

                alimento = _alimento_desde_payload(
                    payload,
                    identificador=punto.id,
                )

                if alimento is not None:
                    indice.append(alimento)

            if offset is None:
                break

        _indice_alimentos = indice

        logger.info(
            "Índice tipado cargado: %d alimentos",
            len(indice),
        )

        return indice

    except Exception:
        logger.exception(
            "Error cargando el índice textual de Qdrant."
        )
        return []


# ---------------------------------------------------------------------------
# Calidad nutricional
# ---------------------------------------------------------------------------

def _es_outlier(
    item: Alimento | Mapping[str, Any],
) -> bool:
    """Comprueba si el registro está marcado como outlier."""
    if isinstance(item, Alimento):
        return item.outlier_nutricional

    valor = item.get("outlier_nutricional", False)

    if isinstance(valor, bool):
        return valor

    if isinstance(valor, (int, float)):
        return valor != 0

    return str(valor).strip().casefold() in {
        "true",
        "1",
        "yes",
        "si",
        "sí",
    }


def _score_calidad_item(
    item: Alimento | Mapping[str, Any],
) -> float:
    """Devuelve la puntuación de calidad del alimento."""
    if isinstance(item, Alimento):
        return item.score_calidad

    return _numero(
        item.get("score_calidad"),
        defecto=0.0,
    ) or 0.0


def _nutricion_de_item(
    item: Alimento | Mapping[str, Any],
) -> dict[str, float | None]:
    """Obtiene los nutrientes sin convertir ausencias en ceros."""
    if isinstance(item, Alimento):
        nutricion = item.nutricion

        return {
            "kcal_100g": nutricion.kcal_100g,
            "proteinas_100g": nutricion.proteinas_100g,
            "carbos_100g": nutricion.carbos_100g,
            "grasas_100g": nutricion.grasas_100g,
            "azucares_100g": nutricion.azucares_100g,
            "fibra_100g": nutricion.fibra_100g,
            "sal_100g": nutricion.sal_100g,
        }

    return {
        campo: _numero(item.get(campo))
        for campo in (
            "kcal_100g",
            "proteinas_100g",
            "carbos_100g",
            "grasas_100g",
            "azucares_100g",
            "fibra_100g",
            "sal_100g",
        )
    }


def _nombre_de_item(
    item: Alimento | Mapping[str, Any],
) -> str:
    """Obtiene el nombre de un candidato."""
    if isinstance(item, Alimento):
        return item.nombre

    return str(item.get("nombre") or "")


def _nombre_normalizado_de_item(
    item: Alimento | Mapping[str, Any],
) -> str:
    """Obtiene el nombre normalizado o lo calcula."""
    if isinstance(item, Alimento):
        return (
            item.nombre_normalizado
            or _normalizar_texto(item.nombre)
        )

    return str(
        item.get("nombre_normalizado")
        or _normalizar_texto(_nombre_de_item(item))
    )


def _nutricionalmente_plausible_para_query(
    query: str,
    item: Alimento | Mapping[str, Any],
) -> bool:
    """
    Aplica validaciones nutricionales generales.

    No utiliza reglas especiales para alimentos concretos.

    La función rechaza:
    - registros marcados como outlier;
    - nutrientes obligatorios desconocidos;
    - cantidades nutricionales negativas;
    - valores superiores a los límites físicos generales;
    - inconsistencias energéticas muy grandes.

    No certifica científicamente la calidad del dato.
    """
    if _es_outlier(item):
        return False

    nutrientes = _nutricion_de_item(item)

    if not all(
        _nutriente_disponible(nutrientes.get(campo))
        for campo in NUTRIENTES_OBLIGATORIOS
    ):
        return False

    kcal = nutrientes["kcal_100g"]
    proteinas = nutrientes["proteinas_100g"]
    carbos = nutrientes["carbos_100g"]
    grasas = nutrientes["grasas_100g"]
    sal = nutrientes["sal_100g"]

    assert kcal is not None
    assert proteinas is not None
    assert carbos is not None
    assert grasas is not None

    if kcal > 900:
        return False

    if max(proteinas, carbos, grasas) > 100:
        return False

    if sal is not None and sal > 100:
        return False

    suma_macros = proteinas + carbos + grasas

    if suma_macros > 100.5:
        return False

    energia_aproximada = (
        proteinas * 4
        + carbos * 4
        + grasas * 9
    )

    if energia_aproximada > 0:
        diferencia = abs(kcal - energia_aproximada)

        tolerancia = max(
            150.0,
            energia_aproximada * 0.85,
        )

        if diferencia > tolerancia:
            return False

    return True


# ---------------------------------------------------------------------------
# Búsqueda textual
# ---------------------------------------------------------------------------

def _match_textual(
    query: str,
    indice: list[Alimento],
) -> dict[str, Any] | None:
    """
    Busca una coincidencia textual conservadora.

    No utiliza:
    - diccionarios de sinónimos alimentarios;
    - equivalencias inventadas;
    - singularización indiscriminada;
    - similitud difusa para identificar alimentos diferentes.
    """
    query_normalizada = _normalizar_texto(query)
    query_words = _palabras(query)

    if not query_words:
        return None

    candidatos: list[
        tuple[
            float,
            float,
            float,
            Alimento,
        ]
    ] = []

    for alimento in indice:
        if not _nutricionalmente_plausible_para_query(
            query,
            alimento,
        ):
            continue

        nombre = _nombre_normalizado_de_item(alimento)
        candidate_words = _palabras(nombre)

        if not candidate_words:
            continue

        cobertura = _cobertura_tokens(
            query_words,
            candidate_words,
        )

        # Una coincidencia textual segura exige que estén presentes
        # todos los términos significativos de la consulta.
        if cobertura < 1.0:
            continue

        coincidencia_exacta = (
            nombre == query_normalizada
        )

        extras = len(candidate_words - query_words)

        # Se prioriza el nombre exacto y después el menor número
        # de términos adicionales.
        score = (
            1000.0
            if coincidencia_exacta
            else 100.0 - extras * 5.0
        )

        candidatos.append(
            (
                score,
                cobertura,
                _score_calidad_item(alimento),
                alimento,
            )
        )

    if not candidatos:
        return None

    candidatos.sort(
        key=lambda candidato: (
            candidato[0],
            candidato[1],
            candidato[2],
        ),
        reverse=True,
    )

    return _resultado_limpio(
        candidatos[0][3],
        similitud=1.0,
    )


def _match_textual_por_nucleo(
    query: str,
    indice: list[Alimento],
) -> dict[str, Any] | None:
    """
    Busca por coincidencia de todos los tokens de consulta.

    Es una segunda oportunidad textual, no una búsqueda por sinónimos.
    """
    return _match_textual(
        query,
        indice,
    )


# ---------------------------------------------------------------------------
# Búsqueda vectorial
# ---------------------------------------------------------------------------

def buscar_alimento(
    query: str,
    n_resultados: int = 3,
) -> list[dict[str, Any]]:
    """
    Busca alimentos semánticamente similares en Qdrant.

    Devuelve el formato de diccionario público para mantener
    la compatibilidad con los consumidores existentes.
    """
    if not query or not query.strip():
        return []

    if not _inicializar() or _cliente is None:
        return []

    if n_resultados < 1:
        return []

    try:
        modelo = _obtener_modelo()

        vector = list(
            modelo.embed([query])
        )[0].tolist()

        response = _cliente.query_points(
            collection_name=COLECCION,
            query=vector,
            limit=n_resultados,
            score_threshold=0.0,
        )

        resultados: list[dict[str, Any]] = []

        for punto in response.points:
            alimento = _alimento_desde_payload(
                punto.payload or {},
                identificador=punto.id,
            )

            if alimento is None:
                continue

            resultados.append(
                _resultado_limpio(
                    alimento,
                    similitud=punto.score,
                )
            )

        return resultados

    except Exception:
        logger.exception(
            "Error en búsqueda Qdrant. Query=%r",
            query,
        )
        return []


# ---------------------------------------------------------------------------
# Búsqueda principal
# ---------------------------------------------------------------------------

def buscar_mejor_match(
    query: str,
) -> dict[str, Any] | None:
    """
    Busca el alimento más fiable.

    Orden:
    1. Coincidencia textual.
    2. Coincidencia textual secundaria.
    3. Recuperación vectorial.
    4. Filtros de cobertura y plausibilidad nutricional.
    """
    if not query or not query.strip():
        return None

    indice = _cargar_indice_alimentos()

    match = _match_textual(
        query,
        indice,
    )

    if match is not None:
        return match

    match = _match_textual_por_nucleo(
        query,
        indice,
    )

    if match is not None:
        return match

    resultados = buscar_alimento(
        query,
        n_resultados=MAX_RESULTADOS_VECTORIALES,
    )

    if not resultados:
        return None

    query_words = _palabras(query)

    candidatos: list[
        tuple[
            float,
            float,
            float,
            float,
            dict[str, Any],
        ]
    ] = []

    for resultado in resultados:
        if not _nutricionalmente_plausible_para_query(
            query,
            resultado,
        ):
            continue

        nombre_words = _palabras(
            resultado["nombre"]
        )

        if not nombre_words:
            continue

        cobertura = _cobertura_tokens(
            query_words,
            nombre_words,
        )

        # No aceptamos un candidato semántico que no contenga
        # todos los términos relevantes de la consulta.
        if cobertura < 1.0:
            continue

        similitud = _numero(
            resultado.get("similitud"),
            defecto=0.0,
        ) or 0.0

        if similitud < UMBRAL_SIMILITUD:
            continue

        extras = len(nombre_words - query_words)

        score = (
            similitud * 0.85
            + cobertura * 0.15
            - extras * 0.01
        )

        candidatos.append(
            (
                score,
                similitud,
                cobertura,
                _score_calidad_item(resultado),
                resultado,
            )
        )

    if not candidatos:
        return None

    candidatos.sort(
        key=lambda candidato: (
            candidato[0],
            candidato[1],
            candidato[2],
            candidato[3],
        ),
        reverse=True,
    )

    mejor = candidatos[0][4]

    logger.debug(
        "Match vectorial aceptado: %s -> %s | similitud=%.3f",
        query,
        mejor["nombre"],
        mejor["similitud"],
    )

    return mejor


# ---------------------------------------------------------------------------
# Matching para visión
# ---------------------------------------------------------------------------

def buscar_mejor_match_vision(
    query: str,
) -> dict[str, Any] | None:
    """
    Búsqueda vectorial para reconocimiento visual.

    Mantiene el umbral específico de visión, pero exige:
    - cobertura completa de los términos;
    - nutrientes obligatorios disponibles;
    - plausibilidad nutricional.
    """
    if not query or not query.strip():
        return None

    resultados = buscar_alimento(
        query,
        n_resultados=40,
    )

    if not resultados:
        return None

    query_words = _palabras(query)

    candidatos: list[
        tuple[
            float,
            float,
            float,
            dict[str, Any],
        ]
    ] = []

    for resultado in resultados:
        if not _nutricionalmente_plausible_para_query(
            query,
            resultado,
        ):
            continue

        nombre_words = _palabras(
            resultado["nombre"]
        )

        if not nombre_words:
            continue

        # En visión la consulta puede incluir preparación, presentación o
        # contexto visual que no forma parte del nombre del alimento en Qdrant.
        # Exigimos solapamiento suficiente respecto al nombre candidato, no que
        # cada palabra descriptiva de la consulta aparezca en el nombre.
        coincidencias = _coincidencias(query_words, nombre_words)
        cobertura_candidato = coincidencias / len(nombre_words)

        if coincidencias == 0 or cobertura_candidato < 0.5:
            continue

        similitud = _numero(
            resultado.get("similitud"),
            defecto=0.0,
        ) or 0.0

        if similitud < UMBRAL_VISION:
            continue

        cobertura_consulta = _cobertura_tokens(query_words, nombre_words)
        extras = len(nombre_words - query_words)

        score = (
            similitud
            + cobertura_candidato * 0.15
            + cobertura_consulta * 0.05
            - extras * 0.01
        )

        candidatos.append(
            (
                score,
                similitud,
                cobertura_candidato,
                resultado,
            )
        )

    if not candidatos:
        return None

    candidatos.sort(
        key=lambda candidato: (
            candidato[0],
            candidato[1],
            candidato[2],
        ),
        reverse=True,
    )

    return candidatos[0][3]


# ---------------------------------------------------------------------------
# Corrección nutricional de ingredientes
# ---------------------------------------------------------------------------

def corregir_ingrediente(
    ingrediente: dict[str, Any],
) -> dict[str, Any]:
    """
    Verifica un ingrediente contra Qdrant y calcula sus macros.

    No modifica los valores originales si no existe una coincidencia
    válida o si faltan nutrientes imprescindibles.

    Las unidades ml se mantienen por compatibilidad, pero la conversión
    a gramos es una aproximación que no considera densidad.
    """
    resultado = ingrediente.copy()

    resultado["verificado_rag"] = False

    nombre = str(
        ingrediente.get("nombre") or ""
    ).strip()

    unidad = str(
        ingrediente.get("unidad") or "g"
    ).strip().casefold()

    cantidad = _numero(
        ingrediente.get("cantidad"),
    )

    # No asumimos densidad: 1 ml no equivale necesariamente a 1 g.
    # Hasta disponer de densidad específica del alimento, solo verificamos g.
    if unidad != "g":
        resultado["motivo_no_verificado"] = "unidad_sin_conversion_de_densidad"
        return resultado

    if not nombre or cantidad is None or cantidad <= 0:
        return resultado

    match = buscar_mejor_match(nombre)

    if match is None:
        return resultado

    nutrientes = (
        "kcal_100g",
        "proteinas_100g",
        "carbos_100g",
        "grasas_100g",
    )

    valores: dict[str, float] = {}

    for campo in nutrientes:
        valor = _numero(match.get(campo))

        if valor is None or valor < 0:
            return resultado

        valores[campo] = valor

    factor = cantidad / 100.0

    resultado.update(
        {
            "verificado_rag": True,
            "nombre_verificado": match["nombre"],
            "kcal": round(
                valores["kcal_100g"] * factor,
                1,
            ),
            "proteinas_g": round(
                valores["proteinas_100g"] * factor,
                1,
            ),
            "carbos_g": round(
                valores["carbos_100g"] * factor,
                1,
            ),
            "grasas_g": round(
                valores["grasas_100g"] * factor,
                1,
            ),
        }
    )

    return resultado


# ---------------------------------------------------------------------------
# Estado del RAG
# ---------------------------------------------------------------------------

def estado_rag() -> dict[str, Any]:
    """Comprueba el estado de Qdrant sin cargar embeddings."""
    if not _inicializar() or _cliente is None:
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
            "url": os.getenv("QDRANT_URL", ""),
            "coleccion": COLECCION,
            "puntos": info.points_count or 0,
            "modelo_embeddings": MODELO_EMBEDDINGS,
            "modelo_cargado": _modelo is not None,
            "indice_textual_cargado": (
                _indice_alimentos is not None
            ),
            "alimentos_en_indice": (
                len(_indice_alimentos)
                if _indice_alimentos is not None
                else 0
            ),
        }

    except Exception as exc:
        logger.exception(
            "Error comprobando el estado de Qdrant."
        )

        return {
            "activo": False,
            "coleccion": COLECCION,
            "error": str(exc),
        }
