"""Ranking contextual v3 aislado para NutriAI."""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from typing import Any

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
CATEGORIAS_COMPUESTAS = {
    "lacteos", "dairy", "fermented dairy", "fermented dairy desserts",
    "bebidas", "beverages", "zumos", "juices", "refrescos",
}
PESO_MODIFICADOR_NO_SOLICITADO = 28.0
PESO_EXTRA_NORMAL = 3.0
PESO_CATEGORIA_INCOMPATIBLE = 18.0
PESO_ORDEN_INVERTIDO = 18.0


def _texto_seguro(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and math.isnan(valor):
        return ""
    texto = str(valor).strip()
    return "" if texto.casefold() in {"", "nan", "none", "null"} else texto


def _valores_textuales(valor: Any) -> list[str]:
    if isinstance(valor, (list, tuple, set)):
        return [t for item in valor if (t := _texto_seguro(item))]
    texto = _texto_seguro(valor)
    return [texto] if texto else []


def _longitud_subsecuencia_ordenada(query_tokens: list[str], nombre_tokens: list[str]) -> int:
    posicion = encontrados = 0
    for token in query_tokens:
        try:
            indice = nombre_tokens.index(token, posicion)
        except ValueError:
            continue
        encontrados += 1
        posicion = indice + 1
    return encontrados


def _frase_contigua(query_normalizada: str, nombre_normalizado: str) -> bool:
    return bool(query_normalizada and f" {query_normalizada} " in f" {nombre_normalizado} ")


def _categoria_incompatible(query_tokens: set[str], categorias: Any,
                            normalizar_texto: Callable[[str], str]) -> bool:
    categorias_norm = " ".join(
        normalizar_texto(valor) for valor in _valores_textuales(categorias)
    )
    if not categorias_norm:
        return False
    familia = any(normalizar_texto(m) in categorias_norm for m in CATEGORIAS_COMPUESTAS)
    if not familia:
        return False
    terminos_familia = {
        "yogurt", "yogur", "leche", "lacteo", "lacteos",
        "bebida", "zumo", "jugo", "refresco",
    }
    return not bool(query_tokens & terminos_familia)


def calcular_score_ranking(query: str, producto: Mapping[str, Any], *,
                           normalizar_texto: Callable[[str], str],
                           obtener_tokens: Callable[[str], list[str]]) -> dict[str, Any]:
    nombre = _texto_seguro(producto.get("nombre"))
    q_norm = normalizar_texto(_texto_seguro(query))
    n_norm = normalizar_texto(nombre)
    if not q_norm or not n_norm:
        return {"score": 0.0, "desglose": {}, "senales": ["texto_vacio"], "metricas": {}}

    q_tokens = obtener_tokens(q_norm)
    n_tokens = obtener_tokens(n_norm)
    if not q_tokens or not n_tokens:
        return {"score": 0.0, "desglose": {}, "senales": ["sin_tokens"], "metricas": {}}

    q_set, n_set = set(q_tokens), set(n_tokens)
    cobertura = len(q_set & n_set) / len(q_set)
    if cobertura == 0:
        return {
            "score": 0.0, "desglose": {}, "senales": ["sin_coincidencias"],
            "metricas": {"cobertura": 0.0, "orden": 0.0,
                         "modificadores_no_solicitados": 0, "extras": len(n_set)},
        }

    desglose: dict[str, float] = {}
    senales: list[str] = []
    desglose["cobertura"] = cobertura * 70.0
    exacto = q_norm == n_norm
    desglose["nombre_exacto"] = 100.0 if exacto else 0.0
    if exacto:
        senales.append("nombre_exacto")

    frase = _frase_contigua(q_norm, n_norm)
    desglose["frase_completa"] = 35.0 if frase else 0.0
    if frase:
        senales.append("frase_completa")

    todos = q_set.issubset(n_set)
    desglose["todos_los_terminos"] = 15.0 if todos else 0.0
    if todos:
        senales.append("todos_los_terminos")

    orden = _longitud_subsecuencia_ordenada(q_tokens, n_tokens)
    proporcion_orden = orden / len(q_tokens)
    desglose["orden"] = 12.0 * proporcion_orden
    if proporcion_orden == 1.0:
        senales.append("orden_completo")

    extras = n_set - q_set
    mods = extras & MODIFICADORES_PRODUCTO
    desglose["extras_normales"] = -min(15.0, len(extras - mods) * PESO_EXTRA_NORMAL)
    desglose["modificadores_no_solicitados"] = -min(
        56.0, len(mods) * PESO_MODIFICADOR_NO_SOLICITADO
    )
    if mods:
        senales.append("preparacion_no_solicitada")

    invertido = len(q_tokens) >= 2 and todos and orden < len(q_tokens)
    desglose["orden_invertido"] = -PESO_ORDEN_INVERTIDO if invertido else 0.0
    if invertido:
        senales.append("orden_no_coincidente")

    categoria = _categoria_incompatible(
        q_set, producto.get("categorias"), normalizar_texto
    )
    desglose["categoria_incompatible"] = (
        -PESO_CATEGORIA_INCOMPATIBLE if categoria else 0.0
    )
    if categoria:
        senales.append("categoria_posiblemente_incompatible")

    metricas = {
        "cobertura": round(cobertura, 6),
        "orden": round(proporcion_orden, 6),
        "modificadores_no_solicitados": len(mods),
        "extras": len(extras),
        "nombre_exacto": exacto,
    }
    return {
        "score": round(max(0.0, sum(desglose.values())), 3),
        "desglose": desglose, "senales": senales, "metricas": metricas,
    }


def ordenar_por_ranking(query: str, resultados: list[dict[str, Any]], *,
                         normalizar_texto: Callable[[str], str],
                         obtener_tokens: Callable[[str], list[str]]) -> list[dict[str, Any]]:
    ordenados = []
    for indice, producto in enumerate(resultados):
        evaluacion = calcular_score_ranking(
            query, producto,
            normalizar_texto=normalizar_texto,
            obtener_tokens=obtener_tokens,
        )
        copia = dict(producto)
        copia["score_ranking"] = evaluacion["score"]
        copia["desglose_ranking"] = evaluacion["desglose"]
        copia["senales_ranking"] = evaluacion["senales"]
        copia["metricas_ranking"] = evaluacion["metricas"]
        copia["_indice_original_ranking"] = indice
        ordenados.append(copia)

    def clave(item: dict[str, Any]) -> tuple[Any, ...]:
        metricas = item.get("metricas_ranking") or {}
        try:
            textual = float(item.get("score_textual") or 0.0)
            if not math.isfinite(textual):
                textual = 0.0
        except (TypeError, ValueError):
            textual = 0.0
        nombre = _texto_seguro(item.get("nombre"))
        return (
            -float(item["score_ranking"]), -textual,
            -float(metricas.get("cobertura", 0.0)),
            -float(metricas.get("orden", 0.0)),
            int(metricas.get("modificadores_no_solicitados", 0)),
            int(metricas.get("extras", 0)), len(nombre),
            nombre.casefold(), int(item["_indice_original_ranking"]),
        )

    ordenados.sort(key=clave)
    for item in ordenados:
        item.pop("_indice_original_ranking", None)
    return ordenados
