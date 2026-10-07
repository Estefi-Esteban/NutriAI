# test_openfoodfacts_original.py

import pandas as pd

RUTA = "data/food_db/openfoodfacts_es.csv"

df = pd.read_csv(
    RUTA,
    sep="\t",
    usecols=[
        "product_name",
        "energy-kcal_100g",
        "proteins_100g",
        "carbohydrates_100g",
        "fat_100g",
    ],
    low_memory=False,
)

for nombre in ["Banana", "Tomate", "Salmon fresco", "Pechuga de pollo"]:

    print("\n" + "=" * 90)
    print(f"BUSCANDO EXACTAMENTE: {nombre}")

    encontrados = df[
        df["product_name"]
        .astype(str)
        .str.strip()
        .str.casefold()
        == nombre.casefold()
    ]

    if encontrados.empty:
        print("❌ NO EXISTE")
        continue

    print(
        encontrados.to_string(index=False)
    )