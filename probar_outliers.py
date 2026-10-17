from pathlib import Path
import pandas as pd

from backend.rag.clean_food_data import (
    crear_nombre_normalizado,
    convertir_numericos,
    filtrar_datos_invalidos,
    calcular_consistencia_energetica,
    preparar_informacion_semantica,
    detectar_outliers_por_alimento,
    calcular_score_calidad,
    deduplicar,
)


BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = (
    BASE_DIR
    / "data"
    / "food_db"
    / "openfoodfacts_es.csv"
)


def main():

    print("=" * 80)
    print("PRUEBA CONTROLADA DE OUTLIERS")
    print("=" * 80)

    print("\nCargando dataset...")

    df = pd.read_csv(
        INPUT_FILE,
        sep="\t",
        usecols=[
            "product_name",
            "categories",
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

    # --------------------------------------------------------
    # MISMO FLUJO QUE EL LIMPIADOR
    # --------------------------------------------------------

    df = crear_nombre_normalizado(df)
    df = convertir_numericos(df)
    df = filtrar_datos_invalidos(df)
    df = calcular_consistencia_energetica(df)
    df = preparar_informacion_semantica(df)

    print(
        f"Registros después de validación: {len(df):,}"
    )

    # --------------------------------------------------------
    # DETECCIÓN DE OUTLIERS
    # --------------------------------------------------------

    df = detectar_outliers_por_alimento(df)

    # Guardamos una copia antes de eliminar duplicados.
    # Aquí todavía están TODOS los registros.
    df_antes_deduplicar = df.copy()

    # --------------------------------------------------------
    # SCORE DE CALIDAD
    # --------------------------------------------------------

    df = calcular_score_calidad(df)

    # --------------------------------------------------------
    # DEDUPLICACIÓN
    # --------------------------------------------------------

    df = deduplicar(df)
    df_despues_deduplicar = df.copy()
    print("\n" + "=" * 80)
    print("COMPROBACIÓN DEL DATASET FINAL")
    print("=" * 80)

    print(f"Registros finales: {len(df):,}")

    # Comprobar duplicados por alimento/variante
    duplicados_variantes = df[
        df.duplicated(
            subset=["nombre_normalizado", "estado_alimento"],
            keep=False
        )
    ]

    print(
        f"Duplicados por nombre_normalizado + estado: "
        f"{len(duplicados_variantes):,}"
    )

    # Comprobar duplicados nutricionales exactos
    duplicados_nutricionales_final = df[
        df.duplicated(
            subset=[
                "nombre_normalizado",
                "energy-kcal_100g",
                "proteins_100g",
                "carbohydrates_100g",
                "fat_100g",
                "estado_alimento",
            ],
            keep=False
        )
    ]

    print(
        f"Duplicados nutricionales en dataset final: "
        f"{len(duplicados_nutricionales_final):,}"
    )

    print("\nALIMENTOS DE CONTROL:")

    for alimento in [
        "aguacate",
        "platano",
        "frijoles negros",
        "yogur griego",
        "yogur griego natural",
        "yogur griego fresa",
        "yogur griego ligero",
        "granola",
        "mantequilla de cacahuete",
    ]:
        encontrados = df[
            df["nombre_normalizado"] == alimento
        ]

        print(
            f"  {alimento}: {len(encontrados)} registro(s)"
        )   

    print("=" * 80)

    print()

    print(
        "Total de outliers detectados:",
        int(df_antes_deduplicar["outlier_nutricional"].sum()),
    )

    # --------------------------------------------------------
    # REVISAR ALIMENTOS CONCRETOS
    # --------------------------------------------------------

    alimentos = [
        "aguacate",
        "platano",
        "frijoles negros",
        "yogur griego",
        "granola",
        "mantequilla de cacahuete",
    ]

    for alimento in alimentos:

        grupo = df[
            df["nombre_normalizado"] == alimento
        ].copy()

        if grupo.empty:
            print()
            print(f"{alimento}: sin registros")
            continue

        seleccionado = df_despues_deduplicar[
            df_despues_deduplicar["nombre_normalizado"] == alimento
        ].copy()

        print()
        print("=" * 80)
        print(alimento.upper())
        print("=" * 80)

        print(
            f"Registros originales válidos: {len(grupo)}"
        )

        print(
            f"Outliers: "
            f"{int(grupo['outlier_nutricional'].sum())}"
        )

        print()
        print("REGISTRO QUE SELECCIONARÍA:")
        print("-" * 80)

        columnas = [
            "nombre",
            "energy-kcal_100g",
            "proteins_100g",
            "carbohydrates_100g",
            "fat_100g",
            "diferencia_kcal_relativa",
            "calidad_nutricional",
            "outlier_nutricional",
            "indice_procesamiento",
            "score_calidad",
        ]

        print(
            seleccionado[columnas]
            .to_string(index=False)
        )

        # --------------------------------------------------------
    # REVISION DETALLADA: VARIANTES DE YOGUR GRIEGO
    # --------------------------------------------------------

    print()
    print("=" * 100)
    print("REVISION DE VARIANTES: YOGUR GRIEGO")
    print("=" * 100)

    yogur = df[
        df["nombre_normalizado"].str.contains(
            "yogur griego",
            na=False
        )
    ].copy()

    if yogur.empty:
        print("No se encontraron registros.")
    else:

        columnas = [
            "nombre",
            "nombre_normalizado",
            "estado_alimento",
            "energy-kcal_100g",
            "proteins_100g",
            "carbohydrates_100g",
            "fat_100g",
            "diferencia_kcal_relativa",
            "calidad_nutricional",
            "outlier_nutricional",
            "score_calidad",
        ]

        print(
            yogur[columnas]
            .sort_values(
                [
                    "nombre_normalizado",
                    "score_calidad"
                ],
                ascending=[True, False]
            )
            .to_string(index=False)
        )

        print()
        print("-" * 100)
        print("RESUMEN DE NOMBRES NORMALIZADOS")
        print("-" * 100)

        resumen = (
            yogur
            .groupby("nombre_normalizado")
            .agg(
                registros=("nombre", "count"),
                kcal_min=("energy-kcal_100g", "min"),
                kcal_max=("energy-kcal_100g", "max"),
                outliers=("outlier_nutricional", "sum"),
            )
            .sort_values("registros", ascending=False)
        )

        print(resumen.to_string())

        print()
        print("-" * 100)
        print("TOTAL DE VARIANTES NORMALIZADAS")
        print("-" * 100)

        print(
            "Nombres normalizados distintos:",
            yogur["nombre_normalizado"].nunique()
        )

        print(
            "Registros totales:",
            len(yogur)
        )

            # --------------------------------------------------------
    # PRUEBA DE DUPLICADOS NUTRICIONALES
    # --------------------------------------------------------

    print()
    print("=" * 100)
    print("PRUEBA DE DUPLICADOS NUTRICIONALES")
    print("=" * 100)

    columnas_nutricionales = [
        "nombre_normalizado",
        "energy-kcal_100g",
        "proteins_100g",
        "carbohydrates_100g",
        "fat_100g",
        "estado_alimento",
    ]

    duplicados_nutricionales = df[
        df.duplicated(
            subset=columnas_nutricionales,
            keep=False,
        )
    ].copy()

    print(
        "Registros que tienen duplicados nutricionalmente idénticos:",
        len(duplicados_nutricionales),
    )

    print(
        "Grupos duplicados:",
        duplicados_nutricionales[
            columnas_nutricionales
        ]
        .drop_duplicates()
        .shape[0],
    )

    print()
    print("Ejemplos:")
    print("-" * 100)

    if duplicados_nutricionales.empty:
        print("No se encontraron duplicados.")
    else:
        print(
            duplicados_nutricionales[
                [
                    "nombre",
                    "nombre_normalizado",
                    "energy-kcal_100g",
                    "proteins_100g",
                    "carbohydrates_100g",
                    "fat_100g",
                    "estado_alimento",
                    "outlier_nutricional",
                    "score_calidad",
                ]
            ]
            .sort_values(
                [
                    "nombre_normalizado",
                    "energy-kcal_100g",
                ]
            )
            .head(50)
            .to_string(index=False)
        )


if __name__ == "__main__":
    main()

