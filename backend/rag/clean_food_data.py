from pathlib import Path
import csv
import re
import sys
import unicodedata

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_FILE = BASE_DIR / "data" / "food_db" / "openfoodfacts_es.csv"
OUTPUT_FILE = BASE_DIR / "data" / "food_db" / "alimentos_limpios.csv"

INVALID_ROWS_FILE = (
    BASE_DIR / "data" / "food_db" / "filas_invalidas_openfoodfacts.csv"
)

# Límites nutricionales físicos.
MIN_CALORIES = 0
MAX_CALORIES = 900

MIN_MACRO = 0
MAX_MACRO = 100

# Clasificación de calidad según consistencia
# entre kcal declaradas y kcal calculadas desde macros.
QUALITY_PRIORITY = {
    "alta": 3,
    "media": 2,
    "baja": 1,
}


# ============================================================
# LECTURA ROBUSTA DE OPENFOODFACTS
# ============================================================

def aumentar_limite_csv():
    """
    OpenFoodFacts puede contener campos de texto muy grandes.

    El módulo csv de Python tiene un límite relativamente pequeño
    por defecto. Lo aumentamos para evitar errores del tipo:

        field larger than field limit
    """

    limite = sys.maxsize

    while True:
        try:
            csv.field_size_limit(limite)
            break
        except OverflowError:
            limite //= 10


def cargar_openfoodfacts(path):
    """
    Lee el TSV de OpenFoodFacts de forma tolerante.

    No utiliza pandas.read_csv porque el archivo puede contener:

    - campos extremadamente grandes
    - comillas malformadas
    - filas con distinto número de columnas

    Las filas cuya estructura no coincide con el encabezado
    se descartan y se registran en un CSV independiente.

    Esto permite saber exactamente cuántas filas se han perdido.
    """

    aumentar_limite_csv()

    filas_validas = []
    filas_invalidas = []

    with open(
        path,
        "r",
        encoding="utf-8",
        errors="replace",
        newline=""
    ) as archivo:

        lector = csv.reader(
            archivo,
            delimiter="\t",
            quoting=csv.QUOTE_NONE,
            escapechar="\\",
        )

        try:
            encabezado = next(lector)
        except StopIteration:
            raise ValueError(
                f"El archivo está vacío: {path}"
            )

        numero_columnas = len(encabezado)

        print(
            f"Columnas detectadas: {numero_columnas}"
        )

        for numero_linea, fila in enumerate(
            lector,
            start=2
        ):

            if len(fila) != numero_columnas:
                filas_invalidas.append({
                    "linea": numero_linea,
                    "columnas_detectadas": len(fila),
                    "columnas_esperadas": numero_columnas,
                })
                continue

            filas_validas.append(fila)

    print(
        f"Filas válidas: {len(filas_validas):,}"
    )

    print(
        f"Filas descartadas por estructura: "
        f"{len(filas_invalidas):,}"
    )

    # Guardar informe de filas inválidas.
    if filas_invalidas:

        pd.DataFrame(
            filas_invalidas
        ).to_csv(
            INVALID_ROWS_FILE,
            index=False,
            encoding="utf-8-sig"
        )

        print(
            f"Informe de filas inválidas: "
            f"{INVALID_ROWS_FILE}"
        )

    return pd.DataFrame(
        filas_validas,
        columns=encabezado
    )


# ============================================================
# NORMALIZACIÓN DE TEXTO
# ============================================================

def normalizar_texto(texto):
    """
    Normaliza texto para facilitar búsquedas y deduplicación.

    Ejemplo:

        "Pechuga de Pollo"
        "pechuga-de-pollo"
        "PECHUGA DE POLLO"

    terminan representándose de forma equivalente.
    """

    if pd.isna(texto):
        return ""

    texto = str(texto).lower().strip()

    # Eliminar acentos.
    texto = unicodedata.normalize(
        "NFKD",
        texto
    )

    texto = "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(caracter)
    )

    # Separadores → espacios.
    texto = re.sub(
        r"[-_/,:;|]+",
        " ",
        texto
    )

    # Eliminar caracteres especiales.
    texto = re.sub(
        r"[^\w\s]",
        " ",
        texto
    )

    # Eliminar espacios repetidos.
    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


def crear_nombre_normalizado(df):
    """
    Crea las columnas nombre y nombre_normalizado.
    """

    if "product_name" not in df.columns:
        raise ValueError(
            "El dataset no contiene la columna "
            "'product_name'."
        )

    df["nombre"] = (
        df["product_name"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df["nombre_normalizado"] = (
        df["nombre"]
        .apply(normalizar_texto)
    )

    return df


# ============================================================
# CONVERSIÓN NUMÉRICA
# ============================================================

def convertir_numericos(df):
    """
    Convierte las columnas nutricionales a números.

    Los valores no convertibles pasan a NaN.
    """

    columnas = [
        "energy-kcal_100g",
        "proteins_100g",
        "carbohydrates_100g",
        "sugars_100g",
        "fat_100g",
        "saturated-fat_100g",
        "fiber_100g",
        "salt_100g",
    ]

    for columna in columnas:

        if columna in df.columns:

            df[columna] = pd.to_numeric(
                df[columna],
                errors="coerce"
            )

    return df


# ============================================================
# VALIDACIÓN BÁSICA
# ============================================================

def filtrar_datos_invalidos(df):
    """
    Elimina registros nutricionalmente inutilizables.

    No intenta decidir si una manzana debe tener 50 kcal,
    ni si una patata debe tener 80 kcal.

    Solo elimina datos físicamente imposibles o incompletos.
    """

    columnas_nutricionales = [
        "energy-kcal_100g",
        "proteins_100g",
        "carbohydrates_100g",
        "fat_100g",
    ]

    # --------------------------------------------------------
    # Nombre obligatorio
    # --------------------------------------------------------

    df = df[
        df["nombre_normalizado"].str.len() > 0
    ].copy()

    # --------------------------------------------------------
    # Datos nutricionales obligatorios
    # --------------------------------------------------------

    df = df.dropna(
        subset=columnas_nutricionales
    ).copy()

    # --------------------------------------------------------
    # Kcal
    # --------------------------------------------------------

    df = df[
        df["energy-kcal_100g"].between(
            MIN_CALORIES,
            MAX_CALORIES
        )
    ].copy()

    # --------------------------------------------------------
    # Macronutrientes
    # --------------------------------------------------------

    for columna in [
        "proteins_100g",
        "carbohydrates_100g",
        "fat_100g",
    ]:

        df = df[
            df[columna].between(
                MIN_MACRO,
                MAX_MACRO
            )
        ].copy()

    # --------------------------------------------------------
    # Evitar alimentos sin macros
    # --------------------------------------------------------

    suma_macros = (
        df["proteins_100g"]
        + df["carbohydrates_100g"]
        + df["fat_100g"]
    )

    df = df[
        suma_macros > 0
    ].copy()

    return df


# ============================================================
# CONSISTENCIA ENERGÉTICA
# ============================================================

def calcular_consistencia_energetica(df):
    """
    Calcula las kcal teóricas usando:

        proteínas × 4
        carbohidratos × 4
        grasas × 9

    Esto NO determina las kcal reales del alimento.

    Sirve para detectar registros nutricionales internamente
    inconsistentes.
    """

    proteinas = df["proteins_100g"]
    carbohidratos = df["carbohydrates_100g"]
    grasas = df["fat_100g"]

    kcal_estimadas = (
        proteinas * 4
        + carbohidratos * 4
        + grasas * 9
    )

    df["kcal_estimadas_100g"] = (
        kcal_estimadas
    )

    denominador = kcal_estimadas.clip(
        lower=1
    )

    df["diferencia_kcal_relativa"] = (
        (
            df["energy-kcal_100g"]
            - kcal_estimadas
        ).abs()
        / denominador
    )

    # --------------------------------------------------------
    # Calidad automática
    # --------------------------------------------------------

    df["calidad_nutricional"] = "baja"

    df.loc[
        df["diferencia_kcal_relativa"] <= 1.00,
        "calidad_nutricional"
    ] = "media"

    df.loc[
        df["diferencia_kcal_relativa"] <= 0.20,
        "calidad_nutricional"
    ] = "alta"

    return df


# ============================================================
# DETECCIÓN GENÉRICA DEL ESTADO
# ============================================================

ESTADOS = {
    "cocido": "cocido",
    "cocida": "cocido",
    "cooked": "cocido",

    "hervido": "cocido",
    "hervida": "cocido",

    "asado": "asado",
    "asada": "asado",

    "horneado": "horneado",
    "horneada": "horneado",

    "frito": "frito",
    "frita": "frito",

    "seco": "seco",
    "seca": "seco",
    "dry": "seco",

    "crudo": "crudo",
    "cruda": "crudo",
    "raw": "crudo",

    "congelado": "congelado",
    "congelada": "congelado",
    "frozen": "congelado",
}


def detectar_estado(nombre):
    """
    Detecta automáticamente el estado/preparación
    a partir del nombre.
    """

    texto = normalizar_texto(
        nombre
    )

    palabras = set(
        texto.split()
    )

    for palabra, estado in ESTADOS.items():

        if palabra in palabras:
            return estado

    return "desconocido"


# ============================================================
# DETECCIÓN GENÉRICA DE PROCESAMIENTO
# ============================================================

PALABRAS_PROCESADO = {
    "galleta",
    "galletas",
    "bizcocho",
    "tarta",
    "pastel",
    "chocolate",
    "barrita",
    "snack",
    "pizza",
    "salsa",
    "mayonesa",
    "ketchup",
    "cereal",
    "cereales",
    "helado",
    "dulce",
    "caramelo",
    "chuches",
    "patatas fritas",
    "hamburguesa",
    "nugget",
    "nuggets",
    "embutido",
    "salchicha",
    "salchichas",
    "croqueta",
    "croquetas",
    "pan",
}


def calcular_indice_procesamiento(texto):
    """
    Genera una señal genérica de procesamiento.

    No pretende saber si un alimento es saludable.

    Solo ayuda a diferenciar productos básicos de productos
    claramente procesados durante la selección automática.
    """

    texto = normalizar_texto(
        texto
    )

    puntuacion = 0

    for termino in PALABRAS_PROCESADO:

        if termino in texto:
            puntuacion += 1

    return puntuacion


# ============================================================
# INFORMACIÓN SEMÁNTICA
# ============================================================

def preparar_informacion_semantica(df):
    """
    Añade información auxiliar para el futuro matching
    nutricional y la búsqueda en Qdrant.
    """

    categorias = (
        df.get(
            "categories",
            pd.Series(
                "",
                index=df.index
            )
        )
        .fillna("")
        .astype(str)
    )

    df["categorias_normalizadas"] = (
        categorias.apply(
            normalizar_texto
        )
    )

    df["estado_alimento"] = (
        df["nombre"].apply(
            detectar_estado
        )
    )

    texto_semantico = (
        df["nombre_normalizado"]
        + " "
        + df["categorias_normalizadas"]
    )

    df["indice_procesamiento"] = (
        texto_semantico.apply(
            calcular_indice_procesamiento
        )
    )

    return df


# ============================================================
# OUTLIERS
# ============================================================

def detectar_outliers_por_alimento(df):
    """
    Detecta valores nutricionales anómalos dentro del mismo
    alimento y estado utilizando una desviación robusta basada
    en la mediana y el MAD.

    Se evalúan conjuntamente:
        - kcal
        - proteínas
        - carbohidratos
        - grasas

    No se elimina ningún registro aquí.
    Solo se marca como outlier_nutricional=True.

    Con pocos registros no se fuerza una decisión estadística.
    """

    df["outlier_nutricional"] = False

    columnas = [
        "energy-kcal_100g",
        "proteins_100g",
        "carbohydrates_100g",
        "fat_100g",
    ]

    grupos = df.groupby(
        [
            "nombre_normalizado",
            "estado_alimento",
        ],
        dropna=False,
    )

    for _, indices in grupos.groups.items():

        # ----------------------------------------------------
        # Necesitamos suficientes registros.
        # ----------------------------------------------------

        if len(indices) < 5:
            continue

        grupo = df.loc[
            indices,
            columnas,
        ].copy()

        # ----------------------------------------------------
        # Calculamos una puntuación de anomalía por columna.
        # ----------------------------------------------------

        puntuaciones = pd.DataFrame(
            0.0,
            index=grupo.index,
            columns=columnas,
        )

        for columna in columnas:

            valores = grupo[columna]

            mediana = valores.median()

            mad = np.median(
                np.abs(
                    valores - mediana
                )
            )

            # ------------------------------------------------
            # Si todos los valores son iguales, esa variable
            # no aporta información para detectar anomalías.
            # ------------------------------------------------

            if mad == 0 or pd.isna(mad):
                continue

            z = (
                0.6745
                * (valores - mediana)
                / mad
            ).abs()

            puntuaciones[columna] = z

        # ----------------------------------------------------
        # Número de variables que consideran anómalo
        # al mismo registro.
        # ----------------------------------------------------

        variables_anomalas = (
            puntuaciones >= 3.5
        ).sum(axis=1)

        # ----------------------------------------------------
        # Un registro se marca como outlier si:
        #
        # 1. Es extremo en al menos 2 variables
        #
        # O:
        #
        # 2. Es extremadamente extremo en una sola variable.
        # ----------------------------------------------------

        outlier = (
            (variables_anomalas >= 3)
            | (
                puntuaciones.max(axis=1)
                >= 8.0
            )
        )

        df.loc[
            outlier.index[outlier],
            "outlier_nutricional",
        ] = True

    return df


# ============================================================
# SCORE DE CALIDAD
# ============================================================

def calcular_score_calidad(df):
    """
    Genera una puntuación automática para seleccionar
    el mejor registro disponible de cada alimento/estado.

    La selección prioriza:

        1. consistencia energética
        2. ausencia de anomalías nutricionales
        3. calidad energética
        4. menor procesamiento

    Los registros marcados como outliers reciben una
    penalización fuerte para evitar que datos extremos
    terminen representando al alimento.
    """

    score = pd.Series(
        0.0,
        index=df.index,
    )

    # --------------------------------------------------------
    # 1. Calidad energética
    # --------------------------------------------------------

    score += (
        df["calidad_nutricional"]
        .map(QUALITY_PRIORITY)
        .fillna(0)
        * 10
    )

    # --------------------------------------------------------
    # 2. Consistencia energética
    #
    # Cuanto menor sea la diferencia entre las kcal
    # declaradas y las kcal calculadas desde macros,
    # mejor.
    # --------------------------------------------------------

    score += (
        1
        / (
            1
            + df["diferencia_kcal_relativa"]
        )
    ) * 10

    # --------------------------------------------------------
    # 3. Penalización fuerte de anomalías nutricionales
    # --------------------------------------------------------

    score -= (
        df["outlier_nutricional"]
        .astype(int)
        * 40
    )

    # --------------------------------------------------------
    # 4. Penalización suave de productos procesados
    # --------------------------------------------------------

    score -= (
        df["indice_procesamiento"]
        .clip(upper=3)
        * 1.5
    )

    df["score_calidad"] = score

    return df


# ============================================================
# DEDUPLICACIÓN
# ============================================================

def deduplicar(df):
    """
    Elimina duplicados del dataset en dos fases:

    1. Elimina registros nutricionalmente idénticos dentro del mismo
       alimento/estado, conservando el de mayor calidad.

    2. Para cada nombre_normalizado + estado_alimento, conserva
       únicamente el registro con mejor score_calidad.

    IMPORTANTE:
    - No mezcla variantes diferentes.
      Ej.: yogur griego, yogur griego natural, yogur griego fresa
      siguen siendo alimentos distintos.
    - Los outliers ya penalizados por score_calidad tienen menos
      posibilidades de ser seleccionados.
    """

    df = df.copy()

    columnas_identidad_nutricional = [
        "nombre_normalizado",
        "energy-kcal_100g",
        "proteins_100g",
        "carbohydrates_100g",
        "fat_100g",
        "estado_alimento",
    ]

    columnas_alimento = [
        "nombre_normalizado",
        "estado_alimento",
    ]

    registros_iniciales = len(df)

    # ------------------------------------------------------------------
    # PASO 1: eliminar duplicados nutricionalmente idénticos
    # ------------------------------------------------------------------

    # Ordenamos por score para que, cuando haya duplicados exactos,
    # conservemos el registro de mayor calidad.
    df = df.sort_values(
        by="score_calidad",
        ascending=False,
        kind="stable",
    )

    duplicados_nutricionales = df.duplicated(
        subset=columnas_identidad_nutricional,
        keep="first",
    )

    eliminados_nutricionales = int(duplicados_nutricionales.sum())

    df = df.loc[~duplicados_nutricionales].copy()

    # ------------------------------------------------------------------
    # PASO 2: seleccionar el mejor registro de cada alimento/variante
    # ------------------------------------------------------------------

    df = df.sort_values(
        by=[
            "nombre_normalizado",
            "estado_alimento",
            "score_calidad",
        ],
        ascending=[
            True,
            True,
            False,
        ],
        kind="stable",
    )

    duplicados_alimento = df.duplicated(
        subset=columnas_alimento,
        keep="first",
    )

    eliminados_por_variante = int(duplicados_alimento.sum())

    df = df.loc[~duplicados_alimento].copy()

    # ------------------------------------------------------------------
    # RESULTADO
    # ------------------------------------------------------------------

    df = df.reset_index(drop=True)

    registros_finales = len(df)
    eliminados_totales = registros_iniciales - registros_finales

    print("\n" + "=" * 80)
    print("DEDUPLICACIÓN")
    print("=" * 80)

    print(f"Registros antes: {registros_iniciales:,}")
    print(
        f"Duplicados nutricionalmente idénticos eliminados: "
        f"{eliminados_nutricionales:,}"
    )
    print(
        f"Registros adicionales eliminados por variante: "
        f"{eliminados_por_variante:,}"
    )
    print(f"Total eliminados: {eliminados_totales:,}")
    print(f"Registros finales: {registros_finales:,}")

    if registros_iniciales > 0:
        porcentaje = (
            eliminados_totales / registros_iniciales
        ) * 100

        print(
            f"Reducción del dataset: {porcentaje:.2f}%"
        )

    print("=" * 80)

    return df


# ============================================================
# SALIDA
# ============================================================

def preparar_salida(df):
    """
    Deja las columnas necesarias para NutriAI/Qdrant.
    """

    columnas_salida = [
        "nombre",
        "nombre_normalizado",

        "categories",
        "categorias_normalizadas",

        "estado_alimento",

        "energy-kcal_100g",
        "proteins_100g",
        "carbohydrates_100g",
        "sugars_100g",
        "fat_100g",
        "saturated-fat_100g",
        "fiber_100g",
        "salt_100g",

        "kcal_estimadas_100g",
        "diferencia_kcal_relativa",
        "calidad_nutricional",

        "indice_procesamiento",
        "score_calidad",
        "outlier_nutricional",

        "allergens",
    ]

    columnas_existentes = [
        columna
        for columna in columnas_salida
        if columna in df.columns
    ]

    df = df[
        columnas_existentes
    ].copy()

    df = (
        df
        .sort_values(
            "nombre_normalizado"
        )
        .reset_index(
            drop=True
        )
    )

    return df


# ============================================================
# RESUMEN
# ============================================================

def mostrar_resumen(df, inicial):
    """
    Muestra un resumen final del proceso.
    """

    print()
    print("=" * 60)
    print("LIMPIEZA COMPLETADA")
    print("=" * 60)

    print(
        f"Registros originales: "
        f"{inicial:,}"
    )

    print(
        f"Registros finales:    "
        f"{len(df):,}"
    )

    reduccion = (
        1
        - len(df) / inicial
    ) * 100

    print(
        f"Reducción:             "
        f"{reduccion:.2f}%"
    )

    print()

    if "calidad_nutricional" in df.columns:

        print("Calidad nutricional:")

        print(
            df[
                "calidad_nutricional"
            ]
            .value_counts()
            .to_string()
        )

    print()

    if "estado_alimento" in df.columns:

        print("Estados:")

        print(
            df[
                "estado_alimento"
            ]
            .value_counts()
            .to_string()
        )

    print()

    if "outlier_nutricional" in df.columns:

        print(
            "Outliers conservados en el dataset:"
            f" {int(df['outlier_nutricional'].sum()):,}"
        )

    print()

    print(
        "Archivo generado:"
    )

    print(
        OUTPUT_FILE
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("LIMPIEZA DE OPENFOODFACTS")
    print("=" * 60)

    # --------------------------------------------------------
    # Comprobar archivos
    # --------------------------------------------------------

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"No se encontró el dataset:\n"
            f"{INPUT_FILE}"
        )

    print(
        f"\nEntrada:\n{INPUT_FILE}"
    )

    print(
        f"\nSalida:\n{OUTPUT_FILE}"
    )

    # --------------------------------------------------------
    # 1. Cargar
    # --------------------------------------------------------

    print(
        "\n[1/9] Cargando dataset..."
    )

    df = cargar_openfoodfacts(
        INPUT_FILE
    )

    inicial = len(df)

    # --------------------------------------------------------
    # 2. Normalización
    # --------------------------------------------------------

    print(
        "\n[2/9] Normalizando nombres..."
    )

    df = crear_nombre_normalizado(
        df
    )

    # --------------------------------------------------------
    # 3. Numéricos
    # --------------------------------------------------------

    print(
        "\n[3/9] Convirtiendo datos nutricionales..."
    )

    df = convertir_numericos(
        df
    )

    # --------------------------------------------------------
    # 4. Validación
    # --------------------------------------------------------

    print(
        "\n[4/9] Eliminando datos inválidos..."
    )

    antes = len(df)

    df = filtrar_datos_invalidos(
        df
    )

    print(
        f"Eliminados: "
        f"{antes - len(df):,}"
    )

    # --------------------------------------------------------
    # 5. Consistencia energética
    # --------------------------------------------------------

    print(
        "\n[5/9] Calculando consistencia energética..."
    )

    df = calcular_consistencia_energetica(
        df
    )

    # --------------------------------------------------------
    # 6. Estado y procesamiento
    # --------------------------------------------------------

    print(
        "\n[6/9] Detectando estado y procesamiento..."
    )

    df = preparar_informacion_semantica(
        df
    )

    # --------------------------------------------------------
    # 7. Outliers
    # --------------------------------------------------------

    print(
        "\n[7/9] Detectando valores anómalos..."
    )

    df = detectar_outliers_por_alimento(
        df
    )

    print(
        "Outliers detectados:",
        int(
            df[
                "outlier_nutricional"
            ].sum()
        )
    )

    # --------------------------------------------------------
    # 8. Score + deduplicación
    # --------------------------------------------------------

    print(
        "\n[8/9] Seleccionando mejores registros..."
    )

    df = calcular_score_calidad(
        df
    )

    antes = len(df)

    df = deduplicar(
        df
    )

    print(
        f"Duplicados eliminados: "
        f"{antes - len(df):,}"
    )

    # --------------------------------------------------------
    # 9. Guardar
    # --------------------------------------------------------

    print(
        "\n[9/9] Guardando dataset limpio..."
    )

    df = preparar_salida(
        df
    )

    df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    mostrar_resumen(
        df,
        inicial
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()