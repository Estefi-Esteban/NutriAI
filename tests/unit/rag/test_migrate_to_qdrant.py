
import pandas as pd

from backend.rag.migrate_to_qdrant import (
    _filtrar_nutrientes_desconocidos,
    _nutriente,
    _num,
    _texto,
    _limpiar_categorias,
    _texto_embedding,
    _construir_payload,
)


def test_nutriente_conserva_cero_real():
    assert _nutriente(0) == 0.0


def test_nutriente_desconocido_devuelve_none():
    assert _nutriente(None) is None


def test_nutriente_invalido_devuelve_none():
    assert _nutriente("nan") is None
    assert _nutriente(float("inf")) is None
    assert _nutriente(-3) is None


def test_filtra_nutrientes_desconocidos():
    payload = {
        "nombre": "Manzana",
        "kcal_100g": 52.0,
        "proteinas_100g": None,
        "carbos_100g": 0.0,
        "fibra_100g": None,
    }

    resultado = _filtrar_nutrientes_desconocidos(payload)

    assert resultado == {
        "nombre": "Manzana",
        "kcal_100g": 52.0,
        "carbos_100g": 0.0,
    }


def test_num_general_conserva_comportamiento():
    assert _num(None) == 0.0
    assert _num(92) == 92.0


# ------------------------------------------------------------------
# Normalización de texto
# ------------------------------------------------------------------


def test_texto_conserva_texto_valido():
    assert _texto("Carne de res") == "Carne de res"


def test_texto_elimina_espacios_exteriores():
    assert _texto("  Carne de res  ") == "Carne de res"


def test_texto_convierte_valores_ausentes_en_vacio():
    assert _texto(None) == ""
    assert _texto(float("nan")) == ""
    assert _texto(pd.NA) == ""
    assert _texto(pd.NaT) == ""


def test_texto_rechaza_cadenas_de_ausencia():
    assert _texto("nan") == ""
    assert _texto(" NaN ") == ""
    assert _texto("None") == ""
    assert _texto("null") == ""
    assert _texto("<NA>") == ""


def test_texto_conserva_cadena_vacia():
    assert _texto("") == ""
    assert _texto("   ") == ""


def test_texto_respeta_limite_de_longitud():
    assert _texto("ABCDEFGHIJ", limite=5) == "ABCDE"


def test_texto_sin_limite_conserva_longitud():
    texto = "A" * 600
    assert _texto(texto) == texto



def test_limpiar_categorias_elimina_prefijos():
    assert _limpiar_categorias(
        "es: carnes, en: meat"
    ) == "carnes, meat"


def test_limpiar_categorias_elimina_duplicados():
    assert _limpiar_categorias(
        "es: carnes, carnes, en: CARNES"
    ) == "carnes"


def test_limpiar_categorias_ignora_valores_vacios():
    assert _limpiar_categorias(None) == ""
    assert _limpiar_categorias(float("nan")) == ""
    assert _limpiar_categorias("") == ""


def test_limpiar_categorias_conserva_categorias_validas():
    assert _limpiar_categorias(
        "es: alimentos, es: carnes, en: fresh food"
    ) == "alimentos, carnes, fresh food"


def test_texto_embedding_combina_nombre_y_categorias():
    row = pd.Series({
        "nombre": "Carne de ternera",
        "categories": "es: carnes, es: alimentos",
    })

    assert _texto_embedding(row) == (
        "Carne de ternera — carnes, alimentos"
    )


def test_texto_embedding_sin_categorias():
    row = pd.Series({
        "nombre": "Manzana",
        "categories": None,
    })

    assert _texto_embedding(row) == "Manzana"


def test_texto_embedding_sin_nombre_devuelve_vacio():
    row = pd.Series({
        "nombre": None,
        "categories": "es: frutas",
    })

    assert _texto_embedding(row) == ""


def test_texto_embedding_rechaza_nombre_nan():
    row = pd.Series({
        "nombre": float("nan"),
        "categories": "es: carnes",
    })

    assert _texto_embedding(row) == ""



def test_payload_conserva_datos_validos():
    row = pd.Series({
        "nombre": "Manzana",
        "nombre_normalizado": "manzana",
        "energy-kcal_100g": 52,
        "proteins_100g": 0.3,
        "carbohydrates_100g": 14,
        "fat_100g": 0.2,
        "categories": "es: frutas",
        "allergens": None,
        "estado_alimento": "fresco",
        "calidad_nutricional": "alta",
    })

    payload = _construir_payload(row)

    assert payload is not None
    assert payload["nombre"] == "Manzana"
    assert payload["kcal_100g"] == 52.0
    assert payload["proteinas_100g"] == 0.3
    assert payload["categorias"] == "frutas"
    assert payload["estado_alimento"] == "fresco"


def test_payload_omite_nutrientes_desconocidos():
    row = pd.Series({
        "nombre": "Manzana",
        "energy-kcal_100g": 52,
        "proteins_100g": None,
        "carbohydrates_100g": float("nan"),
        "fat_100g": 0.0,
    })

    payload = _construir_payload(row)

    assert payload is not None
    assert "proteinas_100g" not in payload
    assert "carbos_100g" not in payload
    assert payload["grasas_100g"] == 0.0


def test_payload_rechaza_nombre_vacio():
    row = pd.Series({
        "nombre": None,
        "categories": "es: frutas",
    })

    assert _construir_payload(row) is None


def test_payload_rechaza_nombre_nan():
    row = pd.Series({
        "nombre": float("nan"),
    })

    assert _construir_payload(row) is None


def test_payload_limpia_categorias_y_alergenos():
    row = pd.Series({
        "nombre": "Leche",
        "categories": "es: lácteos, en: dairy",
        "allergens": "  leche  ",
    })

    payload = _construir_payload(row)

    assert payload is not None
    assert payload["categorias"] == "lácteos, dairy"
    assert payload["alergenos"] == "leche"


def test_payload_rechaza_nutrientes_negativos():
    row = pd.Series({
        "nombre": "Alimento",
        "energy-kcal_100g": -10,
        "proteins_100g": -5,
    })

    payload = _construir_payload(row)

    assert payload is not None
    assert "kcal_100g" not in payload
    assert "proteinas_100g" not in payload
