
import pandas as pd
from pathlib import Path

RUTA_CSV = Path("data/food_db/alimentos_limpios.csv")

COLUMNAS_NECESARIAS = [
    "nombre",
    "energy-kcal_100g",
    "kcal_estimadas_100g",
    "proteins_100g",
    "carbohydrates_100g",
    "fat_100g",
]


def cargar_csv():
    assert RUTA_CSV.exists(), f"No existe el archivo: {RUTA_CSV}"
    df = pd.read_csv(RUTA_CSV, low_memory=False)
    faltantes = [col for col in COLUMNAS_NECESARIAS if col not in df.columns]
    assert not faltantes, f"Faltan columnas: {faltantes}"
    return df


def test_estructura_csv():
    df = cargar_csv()
    assert not df.empty, "El CSV está vacío"


def test_valores_nutricionales_no_negativos():
    df = cargar_csv()
    columnas = [
        "energy-kcal_100g",
        "kcal_estimadas_100g",
        "proteins_100g",
        "carbohydrates_100g",
        "fat_100g",
    ]

    for columna in columnas:
        valores = pd.to_numeric(df[columna], errors="coerce").dropna()
        assert (valores >= 0).all(), f"Hay valores negativos en {columna}"


def test_busqueda_de_alimentos_conocidos():
    df = cargar_csv()
    nombres = df["nombre"].astype(str).str.strip().str.casefold()

    # Comprobamos que hay alimentos con nombres no vacíos.
    assert nombres.ne("").any(), "No hay nombres de alimentos"

    for buscado in ["Banana", "Tomate", "Salmon fresco", "Pechuga de pollo"]:
        encontrados = nombres.eq(buscado.casefold())
        print(f"{buscado}: {'encontrado' if encontrados.any() else 'sin coincidencia exacta'}")
