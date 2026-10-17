from pathlib import Path
import pandas as pd
import unicodedata
import re


BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = (
    BASE_DIR
    / "data"
    / "food_db"
    / "openfoodfacts_es.csv"
)


ALIMENTOS = [
    "Aguacate",
    "Plátano",
    "Yogur griego",
    "Frijoles negros",
    "Granola",
    "Mantequilla de cacahuete",
]


def normalizar_texto(texto):
    if pd.isna(texto):
        return ""

    texto = str(texto).lower().strip()

    texto = unicodedata.normalize(
        "NFKD",
        texto,
    )

    texto = "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(caracter)
    )

    texto = re.sub(
        r"[-_/,:;|]+",
        " ",
        texto,
    )

    texto = re.sub(
        r"[^\w\s]",
        " ",
        texto,
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto,
    )

    return texto.strip()


def analizar_alimento(df, alimento):
    objetivo = normalizar_texto(alimento)

    nombres = (
        df["product_name"]
        .fillna("")
        .astype(str)
        .apply(normalizar_texto)
    )

    # Primero buscamos coincidencia exacta del nombre.
    mask_exacta = nombres == objetivo

    grupo = df.loc[
        mask_exacta,
        [
            "product_name",
            "energy-kcal_100g",
            "proteins_100g",
            "carbohydrates_100g",
            "fat_100g",
        ],
    ].copy()

    print()
    print("=" * 80)
    print(f"ALIMENTO: {alimento}")
    print("=" * 80)

    print(
        f"Registros con nombre exacto: {len(grupo):,}"
    )

    if grupo.empty:
        print("No se encontraron registros exactos.")
        return

    columnas_nutricionales = [
        "energy-kcal_100g",
        "proteins_100g",
        "carbohydrates_100g",
        "fat_100g",
    ]

    for columna in columnas_nutricionales:
        grupo[columna] = pd.to_numeric(
            grupo[columna],
            errors="coerce",
        )

    grupo = grupo.dropna(
        subset=columnas_nutricionales
    ).copy()

    if grupo.empty:
        print("No hay registros con datos nutricionales completos.")
        return

    print(
        f"Registros con macros completos: {len(grupo):,}"
    )

    print()
    print("ESTADÍSTICAS")
    print("-" * 80)

    for columna in columnas_nutricionales:
        serie = grupo[columna]

        print(
            f"{columna:25} "
            f"min={serie.min():8.2f} | "
            f"P25={serie.quantile(0.25):8.2f} | "
            f"mediana={serie.median():8.2f} | "
            f"P75={serie.quantile(0.75):8.2f} | "
            f"max={serie.max():8.2f}"
        )

    # --------------------------------------------------------
    # Consistencia kcal/macros
    # --------------------------------------------------------

    grupo["kcal_estimadas"] = (
        grupo["proteins_100g"] * 4
        + grupo["carbohydrates_100g"] * 4
        + grupo["fat_100g"] * 9
    )

    grupo["diferencia_relativa"] = (
        (
            grupo["energy-kcal_100g"]
            - grupo["kcal_estimadas"]
        ).abs()
        / grupo["kcal_estimadas"].clip(lower=1)
    )

    print()
    print("CONSISTENCIA ENERGÉTICA")
    print("-" * 80)

    print(
        f"Diferencia mediana: "
        f"{grupo['diferencia_relativa'].median():.3f}"
    )

    print(
        f"Diferencia P75:     "
        f"{grupo['diferencia_relativa'].quantile(0.75):.3f}"
    )

    print(
        f"Diferencia máxima:   "
        f"{grupo['diferencia_relativa'].max():.3f}"
    )

    # --------------------------------------------------------
    # Registros más cercanos a la mediana de kcal
    # --------------------------------------------------------

    mediana_kcal = grupo["energy-kcal_100g"].median()

    grupo["distancia_mediana"] = (
        grupo["energy-kcal_100g"]
        - mediana_kcal
    ).abs()

    print()
    print(
        "5 REGISTROS MÁS REPRESENTATIVOS "
        "(más cercanos a la mediana)"
    )
    print("-" * 80)

    columnas_mostrar = [
        "product_name",
        "energy-kcal_100g",
        "proteins_100g",
        "carbohydrates_100g",
        "fat_100g",
        "diferencia_relativa",
    ]

    print(
        grupo
        .sort_values("distancia_mediana")
        .head(5)[columnas_mostrar]
        .to_string(index=False)
    )

    # --------------------------------------------------------
    # Registros extremos
    # --------------------------------------------------------

    print()
    print("5 REGISTROS CON MÁS KCAL")
    print("-" * 80)

    print(
        grupo
        .sort_values(
            "energy-kcal_100g",
            ascending=False,
        )
        .head(5)[columnas_mostrar]
        .to_string(index=False)
    )

    print()
    print("5 REGISTROS CON MENOS KCAL")
    print("-" * 80)

    print(
        grupo
        .sort_values(
            "energy-kcal_100g",
            ascending=True,
        )
        .head(5)[columnas_mostrar]
        .to_string(index=False)
    )


def main():
    print("=" * 80)
    print("DIAGNÓSTICO DE VALORES NUTRICIONALES")
    print("=" * 80)

    print()
    print(f"Archivo: {INPUT_FILE}")

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"No se encontró:\n{INPUT_FILE}"
        )

    print()
    print("Cargando dataset...")

    # Solo necesitamos estas columnas.
    df = pd.read_csv(
        INPUT_FILE,
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

    print(
        f"Registros cargados: {len(df):,}"
    )

    for alimento in ALIMENTOS:
        analizar_alimento(
            df,
            alimento,
        )

    print()
    print("=" * 80)
    print("DIAGNÓSTICO TERMINADO")
    print("=" * 80)


if __name__ == "__main__":
    main()