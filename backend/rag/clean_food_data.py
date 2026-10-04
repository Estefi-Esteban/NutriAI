"""
clean_food_data.py
-------------------
Limpia y valida el dataset de Open Food Facts para NutriAI.

Objetivos:
- Mantener alimentos con nombre.
- Mantener alimentos con kcal y macronutrientes útiles.
- Eliminar registros sin ningún macronutriente.
- Eliminar valores nutricionales claramente imposibles.
- Clasificar la coherencia kcal/macros.
- Reducir duplicados por nombre normalizado.
- Mantener el dataset conservador: una discrepancia alta NO implica
  automáticamente que el alimento sea incorrecto.
"""

import re
import unicodedata
from pathlib import Path

import pandas as pd


RUTA_ENTRADA = Path("data/food_db/openfoodfacts_es.csv")
RUTA_SALIDA = Path("data/food_db/alimentos_limpios.csv")


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


def normalizar_nombre(nombre):
    """
    Normaliza el nombre para detectar duplicados superficiales.

    Ejemplo:
        " PECHUGA  DE Pollo " -> "pechuga de pollo"
    """
    if pd.isna(nombre):
        return ""

    texto = str(nombre).strip().lower()

    # Eliminar tildes.
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )

    # Normalizar espacios.
    texto = re.sub(r"\s+", " ", texto)

    return texto


def calcular_calidad(df):
    """
    Clasifica la coherencia entre kcal declaradas y kcal estimadas
    a partir de proteínas, carbohidratos y grasas.

    No elimina automáticamente alimentos por discrepancia.
    """

    kcal_estimadas = (
        df["proteins_100g"] * 4
        + df["carbohydrates_100g"] * 4
        + df["fat_100g"] * 9
    )

    # Evitamos división por cero.
    denominador = kcal_estimadas.clip(lower=1)

    diferencia = (
        (df["energy-kcal_100g"] - kcal_estimadas).abs()
        / denominador
    )

    df["kcal_estimadas_100g"] = kcal_estimadas
    df["diferencia_kcal_relativa"] = diferencia

    df["calidad_nutricional"] = "baja"

    df.loc[diferencia <= 1.00, "calidad_nutricional"] = "media"
    df.loc[diferencia <= 0.50, "calidad_nutricional"] = "media"
    df.loc[diferencia <= 0.20, "calidad_nutricional"] = "alta"

    return df


def limpiar_dataset():
    print("[*] Cargando CSV de Open Food Facts...")
    print("    Esto puede tardar unos minutos.")

    df = pd.read_csv(
        RUTA_ENTRADA,
        sep="\t",
        usecols=lambda col: col in COLUMNAS_NECESARIAS,
        low_memory=False,
        on_bad_lines="skip",
    )

    print(f"[+] Cargado: {len(df):,} productos totales")

    # ---------------------------------------------------------
    # 1. Nombre obligatorio
    # ---------------------------------------------------------

    df = df.dropna(subset=["product_name"])

    df["product_name"] = df["product_name"].astype(str).str.strip()

    df = df[df["product_name"] != ""]

    print(f"[+] Con nombre: {len(df):,}")

    # ---------------------------------------------------------
    # 2. Macronutrientes básicos obligatorios
    # ---------------------------------------------------------

    columnas_macro = [
        "energy-kcal_100g",
        "proteins_100g",
        "carbohydrates_100g",
        "fat_100g",
    ]

    df = df.dropna(subset=columnas_macro)

    print(f"[+] Con kcal + macros: {len(df):,}")

    # ---------------------------------------------------------
    # 3. Valores numéricos
    # ---------------------------------------------------------

    for columna in columnas_macro:
        df[columna] = pd.to_numeric(
            df[columna],
            errors="coerce",
        )

    df = df.dropna(subset=columnas_macro)

    # ---------------------------------------------------------
    # 4. Valores básicos razonables
    # ---------------------------------------------------------

    df = df[
        (df["energy-kcal_100g"] > 0)
        & (df["energy-kcal_100g"] <= 900)
        & (df["proteins_100g"] >= 0)
        & (df["proteins_100g"] <= 100)
        & (df["carbohydrates_100g"] >= 0)
        & (df["carbohydrates_100g"] <= 100)
        & (df["fat_100g"] >= 0)
        & (df["fat_100g"] <= 100)
    ]

    print(f"[+] Valores básicos válidos: {len(df):,}")

    # ---------------------------------------------------------
    # 5. Eliminar alimentos sin ningún macronutriente
    # ---------------------------------------------------------

    sin_macros = (
        (df["proteins_100g"] == 0)
        & (df["carbohydrates_100g"] == 0)
        & (df["fat_100g"] == 0)
    )

    eliminados_sin_macros = int(sin_macros.sum())

    df = df[~sin_macros].copy()

    print(
        f"[+] Eliminados sin macros útiles: "
        f"{eliminados_sin_macros:,}"
    )

    # ---------------------------------------------------------
    # 6. Clasificación de calidad nutricional
    # ---------------------------------------------------------

    df = calcular_calidad(df)

    print("\n[*] Calidad nutricional:")

    conteo_calidad = (
        df["calidad_nutricional"]
        .value_counts()
    )

    for calidad in ["alta", "media", "baja"]:
        print(
            f"    {calidad.capitalize():<8}: "
            f"{conteo_calidad.get(calidad, 0):,}"
        )

    # ---------------------------------------------------------
    # 7. Normalización de nombres
    # ---------------------------------------------------------

    df["nombre_normalizado"] = (
        df["product_name"]
        .apply(normalizar_nombre)
    )

    # ---------------------------------------------------------
    # 8. Eliminar duplicados superficiales
    # ---------------------------------------------------------

    antes_duplicados = len(df)

    df = df.drop_duplicates(
        subset=["nombre_normalizado"],
        keep="first",
    ).copy()

    eliminados_duplicados = (
        antes_duplicados - len(df)
    )

    print(
        f"[+] Duplicados por nombre normalizado eliminados: "
        f"{eliminados_duplicados:,}"
    )

    # ---------------------------------------------------------
    # 9. Columnas opcionales
    # ---------------------------------------------------------

    for columna in [
        "sugars_100g",
        "saturated-fat_100g",
        "fiber_100g",
        "salt_100g",
    ]:
        if columna not in df.columns:
            df[columna] = None

    if "allergens" not in df.columns:
        df["allergens"] = ""

    if "categories" not in df.columns:
        df["categories"] = ""

    df["allergens"] = df["allergens"].fillna("")
    df["categories"] = df["categories"].fillna("")

    # ---------------------------------------------------------
    # 10. Ordenar columnas
    # ---------------------------------------------------------

    columnas_finales = [
        "product_name",
        "nombre_normalizado",
        "categories",
        "allergens",
        "energy-kcal_100g",
        "kcal_estimadas_100g",
        "diferencia_kcal_relativa",
        "calidad_nutricional",
        "proteins_100g",
        "carbohydrates_100g",
        "sugars_100g",
        "fat_100g",
        "saturated-fat_100g",
        "fiber_100g",
        "salt_100g",
    ]

    columnas_finales = [
        columna
        for columna in columnas_finales
        if columna in df.columns
    ]

    df = df[columnas_finales]

    # ---------------------------------------------------------
    # 11. Guardar
    # ---------------------------------------------------------

    RUTA_SALIDA.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        RUTA_SALIDA,
        index=False,
    )

    print("\n" + "=" * 60)
    print("✅ DATASET LIMPIO")
    print("=" * 60)
    print(
        f"Alimentos finales: {len(df):,}"
    )
    print(
        f"Archivo: {RUTA_SALIDA}"
    )
    print(
        f"Tamaño: "
        f"{RUTA_SALIDA.stat().st_size / (1024 * 1024):.2f} MB"
    )
    print("=" * 60)


if __name__ == "__main__":
    limpiar_dataset()