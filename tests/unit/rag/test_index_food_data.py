
import pandas as pd

from backend.rag.index_food_data import construir_metadata


def test_conserva_ceros_reales():
    row = pd.Series({
        "product_name": "Pechuga de pollo",
        "energy-kcal_100g": 110.0,
        "proteins_100g": 23.0,
        "carbohydrates_100g": 0.0,
        "sugars_100g": 0.0,
        "fat_100g": 1.5,
        "fiber_100g": 0.0,
        "salt_100g": 0.12,
    })

    metadata = construir_metadata(row)

    assert metadata["carbos_100g"] == 0.0
    assert metadata["azucares_100g"] == 0.0
    assert metadata["fibra_100g"] == 0.0


def test_omite_nutrientes_desconocidos():
    row = pd.Series({
        "product_name": "Manzana",
        "energy-kcal_100g": float("nan"),
        "proteins_100g": None,
        "carbohydrates_100g": 0.0,
        "fat_100g": "",
        "fiber_100g": -3,
    })

    metadata = construir_metadata(row)

    assert "kcal_100g" not in metadata
    assert "proteinas_100g" not in metadata
    assert "grasas_100g" not in metadata
    assert "fibra_100g" not in metadata
    assert metadata["carbos_100g"] == 0.0


def test_metadata_no_contiene_valores_none():
    row = pd.Series({
        "product_name": "Alimento de prueba",
    })

    metadata = construir_metadata(row)

    assert all(valor is not None for valor in metadata.values())
    assert metadata["nombre"] == "Alimento de prueba"
