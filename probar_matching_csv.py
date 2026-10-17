from backend.rag.food_search import buscar_mejor_match


CONSULTAS = [
    "Aguacate",
    "Yogur griego bajo en grasa",
    "Proteína whey sabor neutro",
    "Granola sin azúcar",
    "Verduras mixtas",
    "Frijoles negros cocidos",
    "Mantequilla de cacahuete sin azúcar",
    "Jugo de limón",
    "Granola integral",
    "Granola sin azúcar",
    "Mantequilla de cacahuete sin azúcares añadidos",
    "Mezcla de lechugas",
    "Lechuga",
    "Verduras mixtas (pimiento, calabacín, zanahoria)",
]


def main():
    print("=" * 100)
    print("PRUEBA DEL MATCHER REAL DE FOOD_SEARCH")
    print("=" * 100)

    for consulta in CONSULTAS:
        print("\n" + "-" * 100)
        print(f"CONSULTA: {consulta}")
        print("-" * 100)

        try:
            resultado = buscar_mejor_match(consulta)

            if not resultado:
                print("❌ SIN MATCH")
                continue

            print(f"✅ MATCH: {resultado.get('nombre')}")
            print(f"Score: {resultado.get('similitud')}")
            print(f"Kcal: {resultado.get('kcal_100g')}")
            print(f"Proteínas: {resultado.get('proteinas_100g')} g")
            print(f"Carbohidratos: {resultado.get('carbos_100g')} g")
            print(f"Grasas: {resultado.get('grasas_100g')} g")

        except Exception as e:
            print(f"❌ ERROR: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()