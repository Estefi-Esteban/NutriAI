import pandas as pd

RUTA_CSV = "data/food_db/alimentos_limpios.csv"

df = pd.read_csv(RUTA_CSV, low_memory=False)

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
        print("❌ NO EXISTE CON ESE NOMBRE EXACTO")
        continue

    print(
        encontrados[
            [
                "product_name",
                "energy-kcal_100g",
                "kcal_estimadas_100g",
                "proteins_100g",
                "carbohydrates_100g",
                "fat_100g",
            ]
        ].to_string(index=False)
    )