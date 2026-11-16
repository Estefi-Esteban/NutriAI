
from __future__ import annotations

import pytest

from backend.agents.vision_agent import VisionAgent
from backend.rag import food_search
from backend.rag import menu_validator


def test_parsear_deteccion_acepta_json_en_markdown():
    agente = VisionAgent.__new__(VisionAgent)

    resultado = agente._parsear_deteccion(
        '```json\n{"alimentos_detectados": []}\n```'
    )

    assert resultado == {"alimentos_detectados": []}


def test_parsear_deteccion_rechaza_json_invalido():
    agente = VisionAgent.__new__(VisionAgent)

    with pytest.raises(ValueError):
        agente._parsear_deteccion("esto no es json")


def test_extraer_valor_no_convierte_ausencia_en_cero():
    agente = VisionAgent.__new__(VisionAgent)

    assert agente._extraer_valor_tolerante(
        {"kcal_estimado": None},
        ("kcal_estimado",),
    ) is None

    assert agente._extraer_valor_tolerante(
        {"kcal_estimado": "dato"},
        ("kcal_estimado",),
    ) is None


def test_enriquecer_separa_macros_verificados_y_estimados(monkeypatch):
    agente = VisionAgent.__new__(VisionAgent)

    monkeypatch.setattr(
        "backend.agents.vision_agent.buscar_mejor_match_vision",
        lambda nombre: {
            "nombre": "Pollo",
            "similitud": 0.91,
            "kcal_100g": 165,
            "proteinas_100g": 31,
            "carbos_100g": 0,
            "grasas_100g": 3.6,
        },
    )

    resultado = agente._enriquecer_con_rag(
        [{
            "nombre": "pollo a la plancha",
            "cantidad_estimada_g": 150,
            "kcal_estimado": 250,
            "proteinas_estimadas": 20,
        }]
    )[0]

    assert resultado["verificado_rag"] is True
    assert resultado["origen_macros"] == "qdrant"
    assert resultado["macros_verificados"]["kcal"] == 247.5
    assert resultado["macros_estimados"]["kcal"] == 250


def test_enriquecer_no_verifica_si_falta_un_macro_rag(monkeypatch):
    agente = VisionAgent.__new__(VisionAgent)

    monkeypatch.setattr(
        "backend.agents.vision_agent.buscar_mejor_match_vision",
        lambda nombre: {
            "nombre": "Pollo",
            "similitud": 0.95,
            "kcal_100g": 165,
            "proteinas_100g": 31,
            "carbos_100g": None,
            "grasas_100g": 3.6,
        },
    )

    resultado = agente._enriquecer_con_rag(
        [{
            "nombre": "pollo",
            "cantidad_estimada_g": 100,
            "kcal_estimado": 180,
        }]
    )[0]

    assert resultado["verificado_rag"] is False
    assert resultado["origen_macros"] == "estimacion_visual"
    assert resultado["kcal"] == 180
    assert resultado["carbos_g"] is None


def test_enriquecer_no_busca_si_cantidad_no_es_valida(monkeypatch):
    agente = VisionAgent.__new__(VisionAgent)

    def fallo_si_se_invoca(_):
        raise AssertionError("No debería buscar con cantidad inválida.")

    monkeypatch.setattr(
        "backend.agents.vision_agent.buscar_mejor_match_vision",
        fallo_si_se_invoca,
    )

    resultado = agente._enriquecer_con_rag(
        [{"nombre": "pollo", "cantidad_estimada_g": -5}]
    )[0]

    assert resultado["verificado_rag"] is False
    assert resultado["cantidad_g"] is None
    assert resultado["motivo_no_verificado"] == "cantidad_no_valida"


def test_totales_visual_separan_estimaciones_y_rag():
    agente = VisionAgent.__new__(VisionAgent)

    totales = agente._calcular_totales([
        {
            "nombre_detectado": "pollo",
            "verificado_rag": True,
            "macros_verificados": {
                "kcal": 200,
                "proteinas_g": 30,
                "carbos_g": 0,
                "grasas_g": 5,
            },
            "macros_estimados": {},
        },
        {
            "nombre_detectado": "salsa",
            "verificado_rag": False,
            "macros_verificados": None,
            "macros_estimados": {
                "kcal": 50,
                "proteinas_g": None,
                "carbos_g": 4,
                "grasas_g": 2,
            },
        },
    ])

    assert totales["totales_verificados"]["kcal"] == 200
    assert totales["totales_estimados"]["kcal"] == 50
    assert totales["totales_combinados"]["kcal"] == 250

    # No inventamos proteínas: falta el dato estimado de la salsa.
    assert totales["totales_estimados"]["proteinas_g"] is None
    assert totales["totales_combinados"]["proteinas_g"] is None


def test_menu_preserva_none_en_estimaciones():
    resultado = menu_validator._corregir_comida({
        "calorias": None,
        "proteinas_g": 20,
        "carbos_g": None,
        "grasas_g": 5,
        "ingredientes": [],
    })

    assert resultado["macros_estimados_llm"]["calorias"] is None
    assert resultado["macros_estimados_llm"]["carbos_g"] is None
    assert resultado["macros_verificados"] is False


def test_menu_no_presenta_parcial_como_total_completo(monkeypatch):
    def corregir(ingrediente):
        salida = ingrediente.copy()
        salida.update({
            "verificado_rag": ingrediente["nombre"] == "pollo",
            "kcal": 100 if ingrediente["nombre"] == "pollo" else None,
            "proteinas_g": 20 if ingrediente["nombre"] == "pollo" else None,
            "carbos_g": 0 if ingrediente["nombre"] == "pollo" else None,
            "grasas_g": 2 if ingrediente["nombre"] == "pollo" else None,
        })
        return salida

    monkeypatch.setattr(
        menu_validator,
        "corregir_ingrediente",
        corregir,
    )

    resultado = menu_validator._corregir_comida({
        "calorias": 300,
        "proteinas_g": 25,
        "carbos_g": 30,
        "grasas_g": 10,
        "ingredientes": [
            {"nombre": "pollo"},
            {"nombre": "salsa"},
        ],
    })

    assert resultado["macros_verificados"] is False
    assert resultado["calorias"] == 300
    assert resultado["macros_rag"]["calorias"] == 100
    assert resultado["validacion_rag"]["es_parcial"] is True


def test_corregir_ingrediente_no_asume_densidad_para_ml(monkeypatch):
    def fallo_si_se_invoca(_):
        raise AssertionError("No debe buscar ni convertir ml a gramos.")

    monkeypatch.setattr(
        food_search,
        "buscar_mejor_match",
        fallo_si_se_invoca,
    )

    resultado = food_search.corregir_ingrediente({
        "nombre": "leche",
        "cantidad": 200,
        "unidad": "ml",
    })

    assert resultado["verificado_rag"] is False
    assert resultado["motivo_no_verificado"] == (
        "unidad_sin_conversion_de_densidad"
    )
