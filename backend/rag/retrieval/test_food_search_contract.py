
import pytest

from backend.rag import food_search


def alimento(
    nombre="Pechuga de pollo",
    kcal=110.0,
    proteinas=23.0,
    carbos=0.0,
    grasas=1.5,
    similitud=0.90,
):
    return {
        "nombre": nombre,
        "nombre_normalizado": food_search._normalizar_texto(nombre),
        "kcal_100g": kcal,
        "proteinas_100g": proteinas,
        "carbos_100g": carbos,
        "azucares_100g": None,
        "grasas_100g": grasas,
        "fibra_100g": None,
        "sal_100g": None,
        "similitud": similitud,
        "outlier_nutricional": False,
    }


def test_buscar_mejor_match_devuelve_coincidencia_textual(monkeypatch):
    esperado = alimento()

    monkeypatch.setattr(
        food_search,
        "_cargar_indice_alimentos",
        lambda: [esperado],
    )

    resultado = food_search.buscar_mejor_match("Pechuga de pollo")

    assert resultado is not None
    assert resultado["nombre"] == "Pechuga de pollo"


def test_buscar_mejor_match_no_consulta_vector_si_texto_encuentra(
    monkeypatch,
):
    esperado = alimento()

    monkeypatch.setattr(
        food_search,
        "_cargar_indice_alimentos",
        lambda: [esperado],
    )

    def busqueda_vectorial_no_esperada(*args, **kwargs):
        pytest.fail("No debería ejecutar búsqueda vectorial")

    monkeypatch.setattr(
        food_search,
        "buscar_alimento",
        busqueda_vectorial_no_esperada,
    )

    resultado = food_search.buscar_mejor_match("Pechuga de pollo")

    assert resultado is not None


def test_buscar_mejor_match_devuelve_none_si_no_hay_candidatos(
    monkeypatch,
):
    monkeypatch.setattr(
        food_search,
        "_cargar_indice_alimentos",
        lambda: [],
    )

    monkeypatch.setattr(
        food_search,
        "buscar_alimento",
        lambda *args, **kwargs: [],
    )

    resultado = food_search.buscar_mejor_match("alimento inexistente")

    assert resultado is None


def test_buscar_mejor_match_vision_acepta_resultado_sobre_umbral(
    monkeypatch,
):
    candidato = alimento(similitud=0.80)

    monkeypatch.setattr(
        food_search,
        "buscar_alimento",
        lambda *args, **kwargs: [candidato],
    )

    resultado = food_search.buscar_mejor_match_vision("pollo")

    assert resultado is not None
    assert resultado["nombre"] == "Pechuga de pollo"


def test_buscar_mejor_match_vision_rechaza_resultado_bajo_umbral(
    monkeypatch,
):
    candidato = alimento(similitud=0.40)

    monkeypatch.setattr(
        food_search,
        "buscar_alimento",
        lambda *args, **kwargs: [candidato],
    )

    resultado = food_search.buscar_mejor_match_vision("pollo")

    assert resultado is None


def test_corregir_ingrediente_no_verifica_si_faltan_macros(
    monkeypatch,
):
    candidato = alimento(proteinas=None)

    monkeypatch.setattr(
        food_search,
        "buscar_mejor_match",
        lambda query: candidato,
    )

    ingrediente = {
        "nombre": "Pechuga de pollo",
        "cantidad": 150,
        "unidad": "g",
    }

    resultado = food_search.corregir_ingrediente(ingrediente)

    assert resultado["verificado_rag"] is False
    assert "kcal" not in resultado
    assert "proteinas_g" not in resultado


def test_corregir_ingrediente_calcula_macros_con_datos_completos(
    monkeypatch,
):
    candidato = alimento()

    monkeypatch.setattr(
        food_search,
        "buscar_mejor_match",
        lambda query: candidato,
    )

    ingrediente = {
        "nombre": "Pechuga de pollo",
        "cantidad": 150,
        "unidad": "g",
    }

    resultado = food_search.corregir_ingrediente(ingrediente)

    assert resultado["verificado_rag"] is True
    assert resultado["nombre_verificado"] == "Pechuga de pollo"
    assert resultado["kcal"] == 165.0
    assert resultado["proteinas_g"] == 34.5
    assert resultado["carbos_g"] == 0.0
    assert resultado["grasas_g"] == 2.2
