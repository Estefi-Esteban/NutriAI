"""
menu_validator.py
-------------------
Valida y corrige los menús generados por el DietistAgent usando
datos reales de ChromaDB (Open Food Facts), en lugar de confiar
ciegamente en las estimaciones del LLM.
"""

import logging
from backend.rag.food_search import corregir_ingrediente

logger = logging.getLogger(__name__)

TOMAS = ["desayuno", "media_manana", "comida", "merienda", "cena"]


def _corregir_comida(comida: dict) -> dict:
    """
    Corrige todos los ingredientes de una comida y recalcula
    sus totales en base a los ingredientes verificados.
    """
    ingredientes_originales = comida.get("ingredientes", [])
    ingredientes_corregidos = [corregir_ingrediente(ing) for ing in ingredientes_originales]

    comida_corregida = comida.copy()
    comida_corregida["ingredientes"] = ingredientes_corregidos

    # Solo recalculamos los totales de la comida si TODOS los ingredientes
    # se verificaron contra ChromaDB. Si falta alguno, mantenemos los valores
    # originales del LLM para no generar un total parcial/engañoso.
    todos_verificados = all(ing["verificado_rag"] for ing in ingredientes_corregidos)

    if todos_verificados and ingredientes_corregidos:
        comida_corregida["calorias"] = round(sum(ing["kcal"] for ing in ingredientes_corregidos), 1)
        comida_corregida["proteinas_g"] = round(sum(ing["proteinas_g"] for ing in ingredientes_corregidos), 1)
        comida_corregida["carbos_g"] = round(sum(ing["carbos_g"] for ing in ingredientes_corregidos), 1)
        comida_corregida["grasas_g"] = round(sum(ing["grasas_g"] for ing in ingredientes_corregidos), 1)
        comida_corregida["macros_verificados"] = True
    else:
        comida_corregida["macros_verificados"] = False

    return comida_corregida


def validar_y_corregir_dia(menu_dia: dict) -> dict:
    """
    Corrige todas las comidas de un día generado por el DietistAgent
    y recalcula los totales del día sumando los valores ya corregidos.

    Args:
        menu_dia: el dict tal como lo devuelve DietistAgent.generar_dia()

    Returns:
        El mismo dict, con ingredientes corregidos donde fue posible,
        y totales_dia recalculados a partir de los valores finales
        de cada comida (corregidos o no).
    """
    menu_corregido = menu_dia.copy()
    comidas_originales = menu_dia.get("comidas", {})
    comidas_corregidas = {}

    comidas_verificadas = 0

    for toma in TOMAS:
        comida = comidas_originales.get(toma)
        if comida is None:
            continue

        comida_corregida = _corregir_comida(comida)
        comidas_corregidas[toma] = comida_corregida

        if comida_corregida.get("macros_verificados"):
            comidas_verificadas += 1

    menu_corregido["comidas"] = comidas_corregidas

    # Recalculamos totales_dia con los valores FINALES (corregidos o no)
    menu_corregido["totales_dia"] = {
        "calorias": round(sum(c.get("calorias", 0) for c in comidas_corregidas.values()), 1),
        "proteinas_g": round(sum(c.get("proteinas_g", 0) for c in comidas_corregidas.values()), 1),
        "carbos_g": round(sum(c.get("carbos_g", 0) for c in comidas_corregidas.values()), 1),
        "grasas_g": round(sum(c.get("grasas_g", 0) for c in comidas_corregidas.values()), 1),
    }

    menu_corregido["validacion_rag"] = {
        "comidas_verificadas": comidas_verificadas,
        "total_comidas": len(comidas_corregidas),
    }

    logger.info(
        "menu_validator: dia %s - %d/%d comidas verificadas contra ChromaDB",
        menu_dia.get("dia", "?"), comidas_verificadas, len(comidas_corregidas)
    )

    return menu_corregido
