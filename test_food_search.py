from backend.rag.food_search import buscar_alimento, buscar_mejor_match


def probar(query: str):
    print(f"\n[*] Buscando: '{query}'")
    resultados = buscar_alimento(query, n_resultados=3)

    if not resultados:
        print("   [x] Sin resultados")
        return

    for i, r in enumerate(resultados, 1):
        print(
            f"   {i}. {r['nombre'][:50]:50s} "
            f"| {r['kcal_100g']:.0f} kcal "
            f"| P:{r['proteinas_100g']:.1f}g "
            f"C:{r['carbos_100g']:.1f}g "
            f"G:{r['grasas_100g']:.1f}g "
            f"| similitud: {r['similitud']}"
        )


if __name__ == "__main__":
    print("=" * 70)
    print("  TEST - Busqueda semantica de alimentos")
    print("=" * 70)

    consultas = [
        "pechuga de pollo",
        "lentejas estofadas",
        "yogur griego natural",
        "arroz integral cocido",
        "salmón a la plancha",
    ]

    for q in consultas:
        probar(q)
