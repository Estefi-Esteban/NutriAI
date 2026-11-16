from backend.rag.core.qdrant_service import (
    check_collection,
    check_text_index,
    get_collection_info,
)

from backend.rag.retrieval.text_search import (
    buscar_por_texto,
)


def main():
    print("\n========== ESTADO QDRANT ==========")

    assert check_collection("alimentos"), (
        "No se encuentra la colección alimentos"
    )

    assert check_text_index(), (
        "No se encuentra el campo textual esperado"
    )

    info = get_collection_info("alimentos")

    print("Colección: alimentos")
    print("Puntos:", info.points_count)
    print("Índice textual: disponible")

    consultas = [
        "platano",
        "banana",
        "arroz integral",
        "yogurt sin azúcar",
        "pollo cocido",
        "leche desnatada",
    ]

    print("\n========== PRUEBAS ==========")

    for query in consultas:
        print(f"\nConsulta: {query}")

        resultados = buscar_por_texto(
            query=query,
            limite=30,
        )

        print("Candidatos:", len(resultados))

        for resultado in resultados[:5]:
            print(
                f"  {resultado['score_textual']:>8.2f}"
                f" | {resultado['nombre']}"
            )


if __name__ == "__main__":
    main()
