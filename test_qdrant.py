from backend.rag.food_search import buscar_alimento


consultas = [
    "platano",
    "banana",
    "manzana",
    "naranja",
    "aguacate",
    "batata",
    "brocoli",
    "arroz integral",
    "pollo",
    "atun",
    "merluza",
    "huevo",
    "lentejas",
    "garbanzos",
    "almendras",
    "nueces",
]


for consulta in consultas:
    print(f"\n### {consulta}")

    resultados = buscar_alimento(
        consulta,
        n_resultados=10
    )

    for resultado in resultados:
        print(
            f"{resultado['nombre']} | "
            f"kcal={resultado['kcal_100g']} | "
            f"prot={resultado['proteinas_100g']} | "
            f"carbos={resultado['carbos_100g']} | "
            f"grasas={resultado['grasas_100g']} | "
            f"sim={resultado['similitud']}"
        )