"""
Validación nutricional de menús mediante Qdrant.

Mantiene separadas las estimaciones del LLM y las sumas de ingredientes
verificados. Los totales RAG se identifican como parciales cuando corresponde.
"""
from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from typing import Any

from backend.rag.food_search import corregir_ingrediente

logger = logging.getLogger(__name__)

TOMAS = ("desayuno", "media_manana", "comida", "merienda", "cena")
MACROS = ("calorias", "proteinas_g", "carbos_g", "grasas_g")
MACROS_INGREDIENTE = {
    "calorias": "kcal",
    "proteinas_g": "proteinas_g",
    "carbos_g": "carbos_g",
    "grasas_g": "grasas_g",
}


def _numero_no_negativo(valor: object) -> float | None:
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(numero) or numero < 0:
        return None
    return numero


def _sumar_macros(
    items: list[Mapping[str, Any]],
    campos: tuple[str, ...] = MACROS,
) -> dict[str, float | None]:
    """Suma valores conocidos; no transforma ausencias en cero."""
    resultado: dict[str, float | None] = {}
    for campo in campos:
        valores = [_numero_no_negativo(item.get(campo)) for item in items]
        conocidos = [valor for valor in valores if valor is not None]
        resultado[campo] = round(sum(conocidos), 1) if conocidos else None
    return resultado


def _macros_estimados_comida(comida: Mapping[str, Any]) -> dict[str, float | None]:
    return {
        campo: _numero_no_negativo(comida.get(campo))
        for campo in MACROS
    }


def _corregir_comida(comida: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(comida, dict):
        raise TypeError("Cada comida del menú debe ser un objeto.")

    comida_corregida = comida.copy()
    macros_estimados = _macros_estimados_comida(comida)
    comida_corregida["macros_estimados_llm"] = macros_estimados

    ingredientes_originales = comida.get("ingredientes") or []
    if not isinstance(ingredientes_originales, list):
        raise TypeError("'ingredientes' debe ser una lista.")

    ingredientes_corregidos: list[dict[str, Any]] = []
    for indice, ingrediente in enumerate(ingredientes_originales):
        if not isinstance(ingrediente, dict):
            logger.warning("Ingrediente %d ignorado: formato no válido.", indice)
            ingredientes_corregidos.append(
                {
                    "nombre": str(ingrediente),
                    "verificado_rag": False,
                    "error_validacion": "formato_invalido",
                }
            )
            continue
        try:
            ingredientes_corregidos.append(corregir_ingrediente(ingrediente))
        except Exception:
            logger.exception(
                "No se pudo verificar el ingrediente %s.",
                ingrediente.get("nombre", indice),
            )
            copia = ingrediente.copy()
            copia["verificado_rag"] = False
            copia["error_validacion"] = "fallo_verificacion"
            ingredientes_corregidos.append(copia)

    verificados = [
        ingrediente
        for ingrediente in ingredientes_corregidos
        if ingrediente.get("verificado_rag") is True
    ]
    total_ingredientes = len(ingredientes_corregidos)
    total_verificados = len(verificados)
    todos_verificados = (
        total_ingredientes > 0 and total_verificados == total_ingredientes
    )

    macros_rag: dict[str, float | None] = {}
    for macro_comida, macro_ingrediente in MACROS_INGREDIENTE.items():
        valores = [
            _numero_no_negativo(ingrediente.get(macro_ingrediente))
            for ingrediente in verificados
        ]
        # Un ingrediente verificado debe tener los cuatro macros completos.
        completos = all(valor is not None for valor in valores)
        macros_rag[macro_comida] = (
            round(sum(valor for valor in valores if valor is not None), 1)
            if valores and completos
            else (0.0 if not valores else None)
        )

    comida_corregida.update(
        {
            "ingredientes": ingredientes_corregidos,
            "macros_rag": macros_rag,
            "macros_verificados": todos_verificados,
            "validacion_rag": {
                "ingredientes_verificados": total_verificados,
                "total_ingredientes": total_ingredientes,
                "cobertura": (
                    round(total_verificados / total_ingredientes, 3)
                    if total_ingredientes
                    else 0.0
                ),
                "es_parcial": total_verificados < total_ingredientes,
            },
        }
    )

    # No reemplazamos los macros estimados originales por un parcial.
    if todos_verificados and all(v is not None for v in macros_rag.values()):
        for campo in MACROS:
            comida_corregida[campo] = macros_rag[campo]

    return comida_corregida


def validar_y_corregir_dia(menu_dia: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(menu_dia, dict):
        raise TypeError("El menú diario debe ser un objeto.")

    menu_corregido = menu_dia.copy()
    comidas_originales = menu_dia.get("comidas") or {}
    if not isinstance(comidas_originales, dict):
        raise TypeError("'comidas' debe ser un objeto.")

    comidas_corregidas: dict[str, Any] = {}
    for toma in TOMAS:
        comida = comidas_originales.get(toma)
        if comida is not None:
            comidas_corregidas[toma] = _corregir_comida(comida)

    # Conserva tomas adicionales sin modificarlas para no romper el contrato.
    for toma, comida in comidas_originales.items():
        if toma not in TOMAS:
            comidas_corregidas[toma] = comida

    menu_corregido["comidas"] = comidas_corregidas

    comidas = list(comidas_corregidas.values())
    estimaciones = [
        comida.get("macros_estimados_llm", {})
        for comida in comidas
        if isinstance(comida, dict)
    ]
    verificados_por_comida = [
        comida.get("macros_rag", {})
        for comida in comidas
        if isinstance(comida, dict)
    ]

    totales_estimados = _sumar_macros(estimaciones)
    totales_verificados = _sumar_macros(verificados_por_comida)

    comidas_verificadas = sum(
        1 for comida in comidas
        if isinstance(comida, dict) and comida.get("macros_verificados") is True
    )
    total_ingredientes = sum(
        comida.get("validacion_rag", {}).get("total_ingredientes", 0)
        for comida in comidas
        if isinstance(comida, dict)
    )
    ingredientes_verificados = sum(
        comida.get("validacion_rag", {}).get("ingredientes_verificados", 0)
        for comida in comidas
        if isinstance(comida, dict)
    )

    menu_corregido.update(
        {
            "totales_dia_estimados": totales_estimados,
            "totales_dia_verificados": totales_verificados,
            # Alias histórico: sigue representando los valores del LLM.
            "totales_dia": totales_estimados.copy(),
            "validacion_rag": {
                "comidas_verificadas": comidas_verificadas,
                "total_comidas": len(comidas),
                "ingredientes_verificados": ingredientes_verificados,
                "total_ingredientes": total_ingredientes,
                "cobertura_ingredientes": (
                    round(ingredientes_verificados / total_ingredientes, 3)
                    if total_ingredientes
                    else 0.0
                ),
                "totales_verificados_completos": (
                    total_ingredientes > 0
                    and ingredientes_verificados == total_ingredientes
                ),
            },
        }
    )

    logger.info(
        "menu_validator: día %s — %d/%d comidas completas; %d/%d ingredientes verificados",
        menu_dia.get("dia", "?"),
        comidas_verificadas,
        len(comidas),
        ingredientes_verificados,
        total_ingredientes,
    )
    return menu_corregido