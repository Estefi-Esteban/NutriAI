
import pandas as pd
from pathlib import Path

ruta = Path("data/food_db/alimentos_limpios.csv")
df = pd.read_csv(ruta, low_memory=False)

columnas = [
    "nombre",
    "nombre_normalizado",
    "energy-kcal_100g",
    "proteins_100g",
    "carbohydrates_100g",
    "sugars_100g",
    "fat_100g",
    "score_calidad",
    "outlier_nutricional",
]

columnas = [c for c in columnas if c in df.columns]

busquedas = {
    "GRANOLA INTEGRAL": ["granola integral"],
    "GRANOLA SIN AZUCAR": ["granola"],
    "MANTEQUILLA CACAHUETE": [
        "mantequilla de cacahuete",
        "mantequilla de mani",
        "crema de cacahuete",
        "crema de mani",
        "100% crema cacahuete",
    ],
    "MEZCLAS DE LECHUGAS": [
        "mezcla de lechugas",
        "mezcla de hojas",
        "ensalada de lechugas",
        "brotes tiernos",
    ],
    "VERDURAS MIXTAS": [
        "verduras mixtas",
        "verduras variadas",
        "menestra de verduras",
        "verduras congeladas",
    ],
}

for titulo, terminos in busquedas.items():
    mascara = pd.Series(False, index=df.index)

    for termino in terminos:
        mascara |= df["nombre"].astype(str).str.contains(
            termino, case=False, na=False, regex=False
        )

    resultados = df.loc[mascara, columnas].drop_duplicates()

    print(f"\n{'=' * 70}")
    print(f"{titulo}: {len(resultados)} candidatos")

    if resultados.empty:
        print("No se encontraron coincidencias.")
    else:
        print(resultados.head(25).to_string(index=False))
