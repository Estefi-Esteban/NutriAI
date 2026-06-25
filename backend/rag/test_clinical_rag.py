import os
import sys
import io
from dotenv import load_dotenv

# Asegurar encoding UTF-8 en Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

load_dotenv()

from backend.rag.clinical_knowledge_search import buscar_evidencia

def test():
    print("=" * 60)
    print("  TEST — Búsqueda Semántica en Qdrant (Conocimiento Clínico)")
    print("=" * 60)
    
    terminos = ["anemia", "diabetes tipo 2", "hipertiroidismo", "fasting"]
    
    for term in terminos:
        print(f"\n🔍 Buscando: '{term}'...")
        resultados = buscar_evidencia(term, n_resultados=2)
        print(f"Resultados encontrados: {len(resultados)}")
        for idx, res in enumerate(resultados):
            print(f"  [{idx + 1}] {res['titulo']} ({res['año']})")
            print(f"      Fuente: {res['fuente']} | Similitud: {res['similitud']}")
            print(f"      Texto: {res['texto'][:150]}...")
            print("-" * 40)

if __name__ == "__main__":
    test()
