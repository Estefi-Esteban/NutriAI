
from backend.rag.retrieval.text_search import buscar_por_texto

consultas = [
    "manzana",
    "pollo",
    "tomate",
    "leche",
    "arroz",
]

for consulta in consultas:
    print("\n" + "=" * 100)
    print(f"CONSULTA: {consulta}")
    print("=" * 100)

    resultados = buscar_por_texto(consulta, limite=10)

    for i, r in enumerate(resultados, start=1):
        print(f"\n{i}. {r.get('nombre')}")
        print(f"   Score textual: {r.get('score_textual')}")
        print(f"   Score ranking: {r.get('score_ranking')}")
        print(f"   Categorías: {r.get('categorias')}")
        print(f"   Desglose: {r.get('desglose_ranking')}")
        print(f"   Señales: {r.get('senales_ranking')}")
        print(f"   Métricas: {r.get('metricas_ranking')}")
