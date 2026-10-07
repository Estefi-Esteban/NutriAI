from backend.rag.food_search import buscar_alimento


def main():
    consultas = [
        "plátano",
        "batata",
        "mantequilla de cacahuete",
        "brócoli y zanahoria",
        "pechuga de pollo",
        "salmón",
        "arroz integral",
    ]

    print("\n========== TOP 10 RAG ==========\n")

    for consulta in consultas:
        print(f"\n🔎 {consulta}")

        resultados = buscar_alimento(
            consulta,
            n_resultados=10
        )

        for i, r in enumerate(resultados, 1):
            print(
                f"  {i:02d}. {r['nombre']}"
                f" | similitud={r['similitud']}"
            )


if __name__ == "__main__":
    main()