from backend.rag.food_search import buscar_mejor_match


alimentos = [
    "plátano",
    "manzana",
    "tomate",
    "aceite de oliva",
    "salmón fresco",
    "pechuga de pollo",
    "quinoa cocida",
    "pan integral",
    "claras de huevo",
]


for nombre in alimentos:
    print("\n" + "=" * 70)
    print(nombre)

    resultado = buscar_mejor_match(nombre)

    if resultado is None:
        print("❌ SIN MATCH")
        continue

    print("Match:", resultado["nombre"])
    print("Similitud:", resultado["similitud"])
    print("kcal/100g:", resultado["kcal_100g"])
    print("proteínas/100g:", resultado["proteinas_100g"])
    print("carbos/100g:", resultado["carbos_100g"])
    print("grasas/100g:", resultado["grasas_100g"])