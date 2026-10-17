from backend.rag.food_search import buscar_alimento, buscar_mejor_match


ALIMENTOS = [
    "Aguacate",
    "Yogur griego bajo en grasa",
    "Proteína whey sabor neutro",
    "Granola sin azúcar",
    "Verduras mixtas",
    "Frijoles negros cocidos",
    "Mantequilla de cacahuete sin azúcar",
    "Jugo de limón",
]


for alimento in ALIMENTOS:
    print("\n" + "=" * 80)
    print(f"CONSULTA: {alimento}")

    mejor = buscar_mejor_match(alimento)

    if mejor:
        print("\n>>> MEJOR MATCH:")
        print(mejor)
    else:
        print("\n>>> SIN MATCH")

    print("\n>>> TOP CANDIDATOS:")
    resultados = buscar_alimento(alimento, n_resultados=5)

    for i, resultado in enumerate(resultados, 1):
        print(
            f"{i}. {resultado['nombre']} "
            f"| similitud={resultado['similitud']} "
            f"| kcal={resultado['kcal_100g']} "
            f"| prot={resultado['proteinas_100g']} "
            f"| carbos={resultado['carbos_100g']} "
            f"| grasas={resultado['grasas_100g']}"
        )

print("\n" + "=" * 80)
print("BUSCANDO TODOS LOS AGUACATES EN QDRANT")

from backend.rag.food_search import _cliente, COLECCION

if _cliente is not None:
    resultados_qdrant, _ = _cliente.scroll(
        collection_name=COLECCION,
        limit=1000,
        with_payload=True,
        with_vectors=False,
    )

    encontrados = 0

    for punto in resultados_qdrant:
        payload = punto.payload or {}
        nombre = str(payload.get("nombre", "")).lower()

        if "aguacat" in nombre:
            encontrados += 1

            print("\n--- RESULTADO", encontrados, "---")
            print("ID:", punto.id)
            print("Nombre:", payload.get("nombre"))
            print("kcal:", payload.get("kcal_100g"))
            print("proteínas:", payload.get("proteinas_100g"))
            print("carbos:", payload.get("carbos_100g"))
            print("grasas:", payload.get("grasas_100g"))
            print("calidad_nutricional:", payload.get("calidad_nutricional"))
            print("score_calidad:", payload.get("score_calidad"))
            print("outlier_nutricional:", payload.get("outlier_nutricional"))
            print("estado_alimento:", payload.get("estado_alimento"))

    print("\nTOTAL ENCONTRADOS:", encontrados)