"""
Ranking contextual v2 para NutriAI.

Modulo independiente: no consulta Qdrant, no modifica payloads y no valida
la calidad nutricional. Recibe las funciones de normalizacion/tokenizacion
existentes para evitar duplicar la logica de text_search.py.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


# Modificadores que suelen identificar una preparacion/producto distinto.
# Solo se penalizan si aparecen en el candidato y NO en la consulta.
MODIFICADORES_PRODUCTO = {
    "helado", "harina", "polvo", "galleta", "galletas", "bizcocho",
    "croissant", "granola", "snack", "chips", "tarta", "pastel",
    "magdalena", "muffin", "cookie", "cookies", "salsa", "sopa",
    "caldo", "ramen", "hamburguesa", "hamburguesas", "croquetas",
    "nuggets", "zumo", "jugo", "bebida", "conserva", "enlatado",
    "enlatada", "relleno", "rellena", "rellenos", "empanado",
    "empanada", "rebozado", "pudding", "smoothie", "deshidratado",
    "deshidratada", "frito", "frita", "fritos", "fritas",
    "precocinado", "precocinada", "procesado", "procesada",
}

# Categorias que pueden señalar que una coincidencia de un alimento simple
# pertenece realmente a otra familia de producto.
CATEGORIAS_COMPUESTAS = {
    "lacteos", "dairy", "fermented dairy", "fermented dairy desserts",
    "bebidas", "beverages", "zumos", "juices",
}

# Si la consulta ya contiene una de estas palabras, esa preparacion forma
# parte de la intencion y no se penaliza.
PESO_MODIFICADOR_NO_SOLICITADO = 28.0
PESO_EXTRA_NORMAL = 3.0
PESO_CATEGORIA_INCOMPATIBLE = 35.0
PESO_ORDEN_INVERTIDO = 24.0


def _texto_seguro(valor: Any) -> str:
    """Convierte valores ausentes/NaN a texto vacio sin alterar datos origen."""
    if valor is None:
        return ""
    texto = str(valor).strip()
    if not texto or texto.lower() in {"nan", "none", "null"}:
        return ""
    return texto


def _longitud_subsecuencia_ordenada(query_tokens: list[str],
                                    nombre_tokens: list[str]) -> int:
    """Cuenta tokens de consulta encontrados respetando su orden."""
    posicion = 0
    encontrados = 0
    for token in query_tokens:
        try:
            indice = nombre_tokens.index(token, posicion)
        except ValueError:
            continue
        encontrados += 1
        posicion = indice + 1
    return encontrados


def _frase_contigua(query_normalizada: str, nombre_normalizado: str) -> bool:
    if not query_normalizada or not nombre_normalizado:
        return False
    return f" {query_normalizada} " in f" {nombre_normalizado} "


def _categoria_incompatible(query_tokens: set[str], categorias: str) -> bool:
    categorias_norm = categorias.casefold()
    if not categorias_norm:
        return False

    familia_compuesta = any(
        marcador in categorias_norm for marcador in CATEGORIAS_COMPUESTAS
    )
    if not familia_compuesta:
        return False

    # No penalizar si el usuario ha pedido explícitamente esa familia.
    terminos_familia = {
        "yogurt", "yogur", "leche", "lacteo", "lacteos",
        "bebida", "zumo", "jugo",
    }
    return not bool(query_tokens & terminos_familia)


def calcular_score_ranking(
    query: str,
    producto: Mapping[str, Any],
    *,
    normalizar_texto: Callable[[str], str],
    obtener_tokens: Callable[[str], list[str]],
) -> dict[str, Any]:
    """
    Calcula una puntuacion contextual sin modificar el producto.

    Devuelve score, desglose y señales explicables. No es una probabilidad
    ni una puntuacion de calidad nutricional.
    """
    nombre = _texto_seguro(producto.get("nombre"))
    query_original = _texto_seguro(query)

    q_norm = normalizar_texto(query_original)
    n_norm = normalizar_texto(nombre)

    if not q_norm or not n_norm:
        return {"score": 0.0, "desglose": {}, "senales": ["texto_vacio"]}

    q_tokens = obtener_tokens(q_norm)
    n_tokens = obtener_tokens(n_norm)
    if not q_tokens or not n_tokens:
        return {"score": 0.0, "desglose": {}, "senales": ["sin_tokens"]}

    q_set = set(q_tokens)
    n_set = set(n_tokens)
    coincidencias = q_set & n_set
    cobertura = len(coincidencias) / len(q_set)

    if cobertura == 0:
        return {"score": 0.0, "desglose": {}, "senales": ["sin_coincidencias"]}

    desglose: dict[str, float] = {}
    senales: list[str] = []

    desglose["cobertura"] = cobertura * 70.0

    if q_norm == n_norm:
        desglose["nombre_exacto"] = 100.0
        senales.append("nombre_exacto")
    else:
        desglose["nombre_exacto"] = 0.0

    frase = _frase_contigua(q_norm, n_norm)
    desglose["frase_completa"] = 35.0 if frase else 0.0
    if frase:
        senales.append("frase_completa")

    todos_presentes = q_set.issubset(n_set)
    desglose["todos_los_terminos"] = 15.0 if todos_presentes else 0.0
    if todos_presentes:
        senales.append("todos_los_terminos")

    orden = _longitud_subsecuencia_ordenada(q_tokens, n_tokens)
    proporcion_orden = orden / len(q_tokens)
    desglose["orden"] = 12.0 * proporcion_orden
    if proporcion_orden == 1.0:
        senales.append("orden_completo")

    extras = n_set - q_set
    extras_modificadores = extras & MODIFICADORES_PRODUCTO
    extras_normales = extras - extras_modificadores

    desglose["extras_normales"] = -min(
        15.0, len(extras_normales) * PESO_EXTRA_NORMAL
    )
    desglose["modificadores_no_solicitados"] = -min(
        56.0, len(extras_modificadores) * PESO_MODIFICADOR_NO_SOLICITADO
    )
    if extras_modificadores:
        senales.append("preparacion_no_solicitada")

    # Detecta consultas de dos o mas terminos que aparecen en orden inverso.
    if len(q_tokens) >= 2 and todos_presentes and orden < len(q_tokens):
        desglose["orden_invertido"] = -PESO_ORDEN_INVERTIDO
        senales.append("orden_no_coincidente")
    else:
        desglose["orden_invertido"] = 0.0

    categorias = _texto_seguro(producto.get("categorias"))
    categoria_incompatible = _categoria_incompatible(q_set, categorias)
    desglose["categoria_incompatible"] = (
        -PESO_CATEGORIA_INCOMPATIBLE if categoria_incompatible else 0.0
    )
    if categoria_incompatible:
        senales.append("categoria_posiblemente_incompatible")

    score = sum(desglose.values())

    return {
        "score": round(max(0.0, score), 3),
        "desglose": desglose,
        "senales": senales,
    }


def ordenar_por_ranking(
    query: str,
    resultados: list[dict[str, Any]],
    *,
    normalizar_texto: Callable[[str], str],
    obtener_tokens: Callable[[str], list[str]],
) -> list[dict[str, Any]]:
    """
    Devuelve una nueva lista ordenada. No muta los diccionarios originales.
    Conserva todos los campos y agrega score_ranking/desglose_ranking.
    """
    ordenados = []
    for producto in resultados:
        evaluacion = calcular_score_ranking(
            query,
            producto,
            normalizar_texto=normalizar_texto,
            obtener_tokens=obtener_tokens,
        )
        copia = dict(producto)
        copia["score_ranking"] = evaluacion["score"]
        copia["desglose_ranking"] = evaluacion["desglose"]
        copia["senales_ranking"] = evaluacion["senales"]
        ordenados.append(copia)

    ordenados.sort(
        key=lambda item: (
            -item["score_ranking"],
            len(_texto_seguro(item.get("nombre"))),
            _texto_seguro(item.get("nombre")).casefold(),
            _texto_seguro(item.get("id")),
        )
    )
    return ordenados
