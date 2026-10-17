"""
menu_validator.py
-----------------
Valida los menús del DietistAgent con datos nutricionales de Qdrant.

Distingue entre:
- macros_estimados_llm: valores propuestos originalmente por el LLM.
- macros_rag: suma de los ingredientes que sí se han podido verificar.
- macros_verificados: True únicamente si todos los ingredientes tienen match.

Importante: macros_rag y totales_dia_verificados pueden ser parciales si hay
ingredientes sin verificar; no deben presentarse como el total completo real.
"""

import logging
from backend.rag.food_search import corregir_ingrediente

logger = logging.getLogger(__name__)

TOMAS = ["desayuno", "media_manana", "comida", "merienda", "cena"]
MACROS = ("calorias", "proteinas_g", "carbos_g", "grasas_g")


def _sumar_macros(items: list[dict], campos: tuple[str, ...] = MACROS) -> dict:
    return {
        campo: round(sum(float(item.get(campo, 0) or 0) for item in items), 1)
        for campo in campos
    }


def _corregir_comida(comida: dict) -> dict:
    """Verifica ingredientes y conserva separados macros estimados y RAG."""
    comida_corregida = comida.copy()

    # Guardamos las estimaciones originales antes de cualquier corrección.
    macros_estimados = {
        campo: comida.get(campo, 0)
        for campo in MACROS
    }
    comida_corregida["macros_estimados_llm"] = macros_estimados

    ingredientes_originales = comida.get("ingredientes", []) or []
    ingredientes_corregidos = [
        corregir_ingrediente(ingrediente)
        for ingrediente in ingredientes_originales
    ]
    comida_corregida["ingredientes"] = ingredientes_corregidos

    ingredientes_verificados = [
        ingrediente for ingrediente in ingredientes_corregidos
        if ingrediente.get("verificado_rag", False)
    ]
    total_ingredientes = len(ingredientes_corregidos)
    total_verificados = len(ingredientes_verificados)
    todos_verificados = total_ingredientes > 0 and total_verificados == total_ingredientes

    macros_rag = {
        "calorias": round(sum(float(i.get("kcal", 0) or 0) for i in ingredientes_verificados), 1),
        "proteinas_g": round(sum(float(i.get("proteinas_g", 0) or 0) for i in ingredientes_verificados), 1),
        "carbos_g": round(sum(float(i.get("carbos_g", 0) or 0) for i in ingredientes_verificados), 1),
        "grasas_g": round(sum(float(i.get("grasas_g", 0) or 0) for i in ingredientes_verificados), 1),
    }

    comida_corregida["macros_rag"] = macros_rag
    comida_corregida["macros_verificados"] = todos_verificados
    comida_corregida["validacion_rag"] = {
        "ingredientes_verificados": total_verificados,
        "total_ingredientes": total_ingredientes,
        "cobertura": round(total_verificados / total_ingredientes, 3) if total_ingredientes else 0.0,
    }

    # Solo sustituimos los macros principales cuando TODOS los ingredientes
    # están verificados. Si hay ingredientes sin match, no mostramos el parcial
    # como si fuera el total de la comida.
    if todos_verificados:
        comida_corregida["calorias"] = macros_rag["calorias"]
        comida_corregida["proteinas_g"] = macros_rag["proteinas_g"]
        comida_corregida["carbos_g"] = macros_rag["carbos_g"]
        comida_corregida["grasas_g"] = macros_rag["grasas_g"]

    return comida_corregida


def validar_y_corregir_dia(menu_dia: dict) -> dict:
    """
    Valida las comidas del día y devuelve totales estimados y RAG por separado.

    `totales_dia_estimados` conserva la suma de los macros originales del LLM.
    `totales_dia_verificados` suma solo ingredientes verificados y por ello puede
    ser parcial. `totales_dia` se mantiene como alias compatible de los macros
    estimados originales; los consumidores nuevos deberían elegir un campo
    explícito según necesiten estimación o datos verificados.
    """
    menu_corregido = menu_dia.copy()
    comidas_originales = menu_dia.get("comidas", {}) or {}
    comidas_corregidas = {}

    for toma in TOMAS:
        comida = comidas_originales.get(toma)
        if comida is not None:
            comidas_corregidas[toma] = _corregir_comida(comida)

    menu_corregido["comidas"] = comidas_corregidas

    totales_estimados = {
        campo: round(sum(float(c.get("macros_estimados_llm", {}).get(campo, 0) or 0) for c in comidas_corregidas.values()), 1)
        for campo in MACROS
    }
    totales_verificados = {
        campo: round(sum(float(c.get("macros_rag", {}).get(campo, 0) or 0) for c in comidas_corregidas.values()), 1)
        for campo in MACROS
    }

    comidas_verificadas = sum(1 for c in comidas_corregidas.values() if c.get("macros_verificados", False))
    total_ingredientes = sum(c.get("validacion_rag", {}).get("total_ingredientes", 0) for c in comidas_corregidas.values())
    ingredientes_verificados = sum(c.get("validacion_rag", {}).get("ingredientes_verificados", 0) for c in comidas_corregidas.values())

    menu_corregido["totales_dia_estimados"] = totales_estimados
    menu_corregido["totales_dia_verificados"] = totales_verificados
    # Compatibilidad con consumidores existentes: este campo sigue siendo la
    # estimación del LLM. Para mostrar datos verificados, usar el campo explícito.
    menu_corregido["totales_dia"] = totales_estimados.copy()
    menu_corregido["validacion_rag"] = {
        "comidas_verificadas": comidas_verificadas,
        "total_comidas": len(comidas_corregidas),
        "ingredientes_verificados": ingredientes_verificados,
        "total_ingredientes": total_ingredientes,
        "cobertura_ingredientes": round(ingredientes_verificados / total_ingredientes, 3) if total_ingredientes else 0.0,
        "totales_verificados_completos": ingredientes_verificados == total_ingredientes and total_ingredientes > 0,
    }

    logger.info(
        "menu_validator: día %s - %d/%d comidas verificadas | %d/%d ingredientes verificados contra RAG",
        menu_dia.get("dia", "?"),
        comidas_verificadas, len(comidas_corregidas),
        ingredientes_verificados, total_ingredientes,
    )
    return menu_corregido
