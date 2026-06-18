"""
clean_food_data.py
-------------------
Limpia y filtra el CSV de Open Food Facts (España) para quedarnos
solo con productos útiles para generación de menús:
  - Tienen nombre
  - Tienen valores nutricionales completos (kcal, proteínas, carbos, grasas)
  - Están en español o tienen nombre genérico reconocible

Genera un CSV limpio mucho más pequeño y manejable.
"""

import pandas as pd
from pathlib import Path

RUTA_ENTRADA = Path("data/food_db/openfoodfacts_es.csv")
RUTA_SALIDA = Path("data/food_db/alimentos_limpios.csv")

# Columnas que realmente necesitamos del CSV gigante
COLUMNAS_NECESARIAS = [
    "product_name",
    "categories",
    "energy-kcal_100g",
    "proteins_100g",
    "carbohydrates_100g",
    "sugars_100g",
    "fat_100g",
    "saturated-fat_100g",
    "fiber_100g",
    "salt_100g",
    "allergens",
]


def limpiar_dataset():
    print("[*] Cargando CSV (esto puede tardar unos minutos)...")

    # El CSV usa tabulador como separador, no coma
    df = pd.read_csv(
        RUTA_ENTRADA,
        sep="\t",
        usecols=lambda col: col in COLUMNAS_NECESARIAS,
        low_memory=False,
        on_bad_lines="skip",
    )

    print(f"[+] Cargado: {len(df):,} productos totales")

    # Filtro 1 — debe tener nombre
    df = df.dropna(subset=["product_name"])
    df = df[df["product_name"].str.strip() != ""]
    print(f"   Tras filtrar sin nombre: {len(df):,}")

    # Filtro 2 — debe tener los 4 valores nutricionales básicos
    columnas_macro = ["energy-kcal_100g", "proteins_100g", "carbohydrates_100g", "fat_100g"]
    df = df.dropna(subset=columnas_macro)
    print(f"   Tras filtrar sin macros: {len(df):,}")

    # Filtro 3 — valores razonables (descartamos basura/errores de entrada)
    df = df[
        (df["energy-kcal_100g"] > 0) & (df["energy-kcal_100g"] < 900) &
        (df["proteins_100g"] >= 0) & (df["proteins_100g"] < 100) &
        (df["carbohydrates_100g"] >= 0) & (df["carbohydrates_100g"] < 100) &
        (df["fat_100g"] >= 0) & (df["fat_100g"] < 100)
    ]
    print(f"   Tras filtrar valores no razonables: {len(df):,}")

    # Filtro 4 — eliminar duplicados por nombre, quedándonos con el primero
    df = df.drop_duplicates(subset=["product_name"], keep="first")
    print(f"   Tras eliminar duplicados: {len(df):,}")

    # Rellenar columnas opcionales que puedan faltar
    for col in ["sugars_100g", "saturated-fat_100g", "fiber_100g", "salt_100g"]:
        if col not in df.columns:
            df[col] = None
    df["allergens"] = df.get("allergens", "").fillna("")
    df["categories"] = df.get("categories", "").fillna("")

    # Guardar resultado limpio
    RUTA_SALIDA.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(RUTA_SALIDA, index=False)
    print(f"\n[+] Dataset limpio guardado en: {RUTA_SALIDA}")
    print(f"   Total de alimentos útiles: {len(df):,}")


if __name__ == "__main__":
    limpiar_dataset()
