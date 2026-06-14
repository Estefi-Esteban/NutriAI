import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from backend.agents.profile_agent import ProfileAgent

def main():
    agente = ProfileAgent()
    print("\n🥗 NutriAI - Test del Agente Perfil")
    print("=" * 40)
    print("Escribe 'salir' para terminar\n")

    # Mensaje inicial — el agente saluda primero
    inicio = agente.chat("Hola")
    print(f"NutriAI: {inicio['respuesta']}\n")

    while True:
        entrada = input("Tú: ").strip()

        if entrada.lower() == "salir":
            break

        if not entrada:
            continue

        resultado = agente.chat(entrada)
        print(f"\nNutriAI: {resultado['respuesta']}\n")

        if resultado["perfil_completo"]:
            print("\n✅ PERFIL COMPLETADO")
            print("=" * 40)
            import json
            print(json.dumps(resultado["datos"], indent=2, ensure_ascii=False))
            break

if __name__ == "__main__":
    main()