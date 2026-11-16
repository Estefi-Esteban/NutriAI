
"""
Evaluación funcional del pipeline híbrido con Qdrant real.

No modifica la colección ni sus datos.
Muestra los candidatos recuperados por texto y vector,
fusionados mediante RRF.
"""

import logging

from backend.rag.retrieval.search_pipeline import recuperar_candidatos


logging.basicConfig(level=logging.WARNING)

CONSULTAS = [
    "pechuga de pollo",
    "pollo",
    "yogur natural",
    "yogur natural sin azúcar",
    "arroz integral",
    "banana",
    "leche sin lactosa",
]


def evaluar_consulta(query: str) -> None:
    print("\n" + "=" * 90)
    print(f"CONSULTA: {query}")
    print("=" * 90)

    resultados = recuperar_candidatos(
        query=query,
        limite_textual=30,
        limite_vectorial=30,
        limite_final=20,
        rrf_k=60,
    )

    if not resultados:
        print("No se han encontrado candidatos.")
        return

    print(f"Candidatos recuperados: {len(resultados)}\n")

    for posicion, alimento in enumerate(resultados, start=1):
        nombre = alimento.get("nombre", "Sin nombre")
        identificador = alimento.get("id", "Sin ID")
        fuentes = alimento.get("fuentes_recuperacion", [])

        score_rrf = alimento.get("score_rrf", 0.0)
        score_normalizado = alimento.get(
            "score_rrf_normalizado", 0.0
        )

        similitud = alimento.get("similitud")
        score_textual = alimento.get("score_textual")

        print(f"{posicion}. {nombre}")
        print(f"   ID: {identificador}")
        print(f"   Fuentes: {fuentes}")
        print(f"   RRF: {score_rrf:.6f}")
        print(f"   RRF normalizado: {score_normalizado:.4f}")

        if similitud is not None:
            print(f"   Similitud vectorial: {similitud}")

        if score_textual is not None:
            print(f"   Score textual: {score_textual}")

        print()


def main():
    for query in CONSULTAS:
        try:
            evaluar_consulta(query)
        except Exception:
            logging.exception(
                "Error evaluando la consulta: %s", query
            )


if __name__ == "__main__":
    main()
