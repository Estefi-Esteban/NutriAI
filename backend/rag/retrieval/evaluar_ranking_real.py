
"""
Evaluación del ranking unificado con candidatos reales de Qdrant.

Compara:
1. Orden original de la fusión RRF.
2. Orden después de aplicar el ranking unificado.

No modifica Qdrant ni los datos de producción.
"""

import logging
from typing import Any
import json 

from backend.rag.retrieval.search_pipeline import recuperar_candidatos
from backend.rag.retrieval.ranking import ordenar_por_ranking
from backend.rag.retrieval.text_search import (
    normalizar_texto,
    obtener_tokens,
)

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


def numero_seguro(valor: Any, decimales: int = 2) -> str:
    """Formatea números sin interrumpir la evaluación."""
    try:
        if valor is None:
            return "N/A"
        return f"{float(valor):.{decimales}f}"
    except (TypeError, ValueError):
        return "N/A"


def mostrar_resultados(
    titulo: str,
    resultados: list[dict],
    limite: int = 10,
) -> None:
    print(f"\n{titulo}")
    print("-" * 90)

    for posicion, alimento in enumerate(resultados[:limite], start=1):
        nombre = alimento.get("nombre", "Sin nombre")
        fuentes = alimento.get("fuentes_recuperacion", [])

        print(f"{posicion:02d}. {nombre}")
        print(
            f"    Ranking: "
            f"{numero_seguro(alimento.get('score_ranking'))}"
        )
        print(
            f"    RRF: "
            f"{numero_seguro(alimento.get('score_rrf'), 6)}"
        )
        print(
            f"    Similitud vectorial: "
            f"{numero_seguro(alimento.get('similitud'), 4)}"
        )
        print(f"    Fuentes: {fuentes}")
        print()


def evaluar_consulta(query: str) -> None:
    print("\n" + "=" * 100)
    print(f"CONSULTA: {query}")
    print("=" * 100)

    # 1. Recuperación híbrida y fusión RRF.
    candidatos = recuperar_candidatos(
        query=query,
        limite_textual=30,
        limite_vectorial=30,
        limite_final=50,
        rrf_k=60,
    )

    if not candidatos:
        print("No se han recuperado candidatos.")
        return

    print(f"Candidatos recuperados: {len(candidatos)}")

    # 2. Conservamos una copia del orden RRF original.
    resultados_rrf = [dict(c) for c in candidatos]

    # 3. Aplicamos el ranking unificado sobre los mismos candidatos.
    resultados_ranking = ordenar_por_ranking(
        [dict(c) for c in candidatos],
        query,
        normalizar_texto=normalizar_texto,
        obtener_tokens=obtener_tokens,
    )

    # 4. Comparamos ambos rankings.
    mostrar_resultados(
        "RANKING ORIGINAL: RRF",
        resultados_rrf,
    )

    mostrar_resultados(
        "RANKING UNIFICADO",
        resultados_ranking,
    )

    if query == "yogur natural sin azúcar":
        print("\n" + "=" * 100)
        print("INSPECCIÓN DE PAYLOADS: YOGURES")
        print("=" * 100)

        for alimento in resultados_ranking[:5]:
            print(json.dumps(
                alimento,
                ensure_ascii=False,
                indent=2,
                default=str,
            ))
            print("-" * 80)


def main() -> None:
    for query in CONSULTAS:
        try:
            evaluar_consulta(query)
        except Exception:
            logging.exception(
                "Error evaluando la consulta '%s'",
                query,
            )


if __name__ == "__main__":
    main()
