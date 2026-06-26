import sys
from dotenv import load_dotenv
load_dotenv()

# Safe encoding for Windows console output
sys.stdout.reconfigure(encoding='utf-8')

from backend.rag.food_search import buscar_alimento, UMBRAL_SIMILITUD
from typing import Optional

def buscar_mejor_match_hibrido(query: str) -> Optional[dict]:
    # Pull 40 results from Qdrant
    resultados = buscar_alimento(query, n_resultados=40)
    if not resultados:
        return None

    query_words = set(query.lower().replace(",", " ").replace(".", " ").split())
    stop_words = {"de", "la", "a", "con", "en", "para", "un", "una", "el", "los", "las", "y", "plana"} # 'plana' can be a typo for plancha
    query_keywords = {w for w in query_words if w not in stop_words and len(w) > 2}

    best_item = None
    best_score = -1.0

    print(f"\n[Re-ranking para: '{query}']")
    for r in resultados:
        nombre_words = set(r["nombre"].lower().replace(",", " ").replace(".", " ").split())
        nombre_keywords = {w for w in nombre_words if w not in stop_words and len(w) > 2}
        
        # Calculate keyword match using 4-character prefix
        overlap = 0
        coincidencias = []
        for qw in query_keywords:
            for nw in nombre_keywords:
                # Direct check, substring check, or prefix check
                if qw in nw or nw in qw or (len(qw) > 3 and len(nw) > 3 and qw[:4] == nw[:4]):
                    overlap += 1
                    coincidencias.append(f"{qw}~{nw}")
                    break
        
        # Combined score: base similarity + 0.15 per matched keyword
        bonus = overlap * 0.15
        score = r["similitud"] + bonus
        
        # Only print top candidates or items with overlap to keep logs clear
        if overlap > 0:
            print(f"   - {r['nombre'][:40]:40s} | Sim base: {r['similitud']:.3f} | Bonus: {bonus:.2f} (Coincide: {coincidencias}) | Score final: {score:.3f}")
        
        if score > best_score:
            best_score = score
            best_item = r

    if best_item and best_item["similitud"] < UMBRAL_SIMILITUD:
        print(f"   [x] Match '{best_item['nombre']}' descartado por similitud base {best_item['similitud']} < {UMBRAL_SIMILITUD}")
        return None

    return best_item

if __name__ == "__main__":
    test_queries = [
        "filete de ternera a la plana",
        "mantequeilla",
        "pechuga de pollo",
        "lentejas estofadas"
    ]
    
    for q in test_queries:
        match = buscar_mejor_match_hibrido(q)
        if match:
            print(f"MEJOR MATCH SELECCIONADO: '{match['nombre']}' (similitud base: {match['similitud']}, macros: kcal={match['kcal_100g']}, prot={match['proteinas_100g']}, carb={match['carbos_100g']}, fat={match['grasas_100g']})")
        else:
            print("SIN MATCH")
