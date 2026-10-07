import pandas as pd
import unicodedata
import re


CSV_PATH = "data/food_db/alimentos_limpios.csv"


ALIMENTOS_PRUEBA = [
    "banana",
    "tomate",
    "manzana",
    "naranja",
    "aguacate",
    "patata",
    "batata",
    "zanahoria",
    "brócoli",
    "espinacas",
    "arroz integral",
    "arroz",
    "quinoa",
    "quinoa cocida",
    "avena",
    "pasta",
    "pan",
    "pechuga de pollo",
    "pollo",
    "pavo",
    "carne de vacuno",
    "salmón",
    "salmón fresco",
    "atún",
    "merluza",
    "huevo",
    "leche",
    "yogur",
    "queso",
    "lentejas",
    "garbanzos",
    "almendras",
    "nueces",
    "mantequilla de cacahuete",
]


def normalizar(texto):
    texto = str(texto).lower().strip()

    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(
        c for c in texto
        if unicodedata.category(c) != "Mn"
    )

    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


def buscar(df, nombre):
    objetivo = normalizar(nombre)

    resultados = df[
        df["nombre_normalizado"].astype(str).map(normalizar) == objetivo
    ]

    return resultados


def main():

    print("[*] Cargando dataset limpio...")

    df = pd.read_csv(CSV_PATH)

    print(f"[+] Registros: {len(df):,}")
    print()

    columnas = [
        "nombre_normalizado",
        "product_name",
        "energy-kcal_100g",
        "proteins_100g",
        "carbohydrates_100g",
        "fat_100g",
        "categories",
    ]

    encontrados = 0
    no_encontrados = 0

    print("=" * 100)
    print("PRUEBA AUTOMÁTICA DEL DATASET")
    print("=" * 100)

    for alimento in ALIMENTOS_PRUEBA:

        resultados = buscar(df, alimento)

        if resultados.empty:
            print(f"❌ {alimento:25} -> NO ENCONTRADO")
            no_encontrados += 1
            continue

        fila = resultados.iloc[0]

        kcal = fila["energy-kcal_100g"]
        proteinas = fila["proteins_100g"]
        carbos = fila["carbohydrates_100g"]
        grasas = fila["fat_100g"]

        print(
            f"✅ {alimento:25} -> "
            f"{str(fila['product_name'])[:35]:35} | "
            f"{kcal:6.1f} kcal | "
            f"P {proteinas:5.1f} | "
            f"C {carbos:5.1f} | "
            f"G {grasas:5.1f}"
        )

        encontrados += 1

    print()
    print("=" * 100)
    print("RESUMEN")
    print("=" * 100)

    print(f"Encontrados    : {encontrados}/{len(ALIMENTOS_PRUEBA)}")
    print(f"No encontrados: {no_encontrados}/{len(ALIMENTOS_PRUEBA)}")

    print()
    print("⚠️ IMPORTANTE:")
    print("Este test comprueba que existan registros.")
    print("Después revisaremos específicamente si representan")
    print("el alimento correcto (crudo/cocido/procesado).")


if __name__ == "__main__":
    main()