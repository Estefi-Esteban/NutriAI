import logging
from backend.agents.dietist_agent import DietistAgent

# Configuramos el log para ver qué hace el agente por dentro
logging.basicConfig(level=logging.INFO)

def probar_lunes():
    print("🔥 Iniciando prueba AISLADA de DietistAgent para el Lunes...")

    # Datos simulados para no tener que usar la base de datos
    perfil_prueba = {
        "nombre": "Usuario de Prueba",
        "edad": 30,
        "sexo": "masculino",
        "peso_kg": 80,
        "altura_cm": 180,
        "objetivo_principal": "perder_grasa",
        "nivel_actividad": "moderado",
        "alergias": [],
        "patologias": []
    }

    calculos_prueba = {
        "calorias_objetivo": 2000,
        "macros": {"proteinas": 150, "grasas": 65, "carbos": 200}
    }

    analisis_prueba = {"recomendaciones": "Priorizar saciedad y proteína."}

    agente = DietistAgent()

    try:
        resultado = agente.generar_dia(
            perfil=perfil_prueba,
            calculos=calculos_prueba,
            analisis=analisis_prueba,
            dia_semana="Lunes",
            comidas_previas=[]
        )
        print("\n✅ ¡ÉXITO! El Lunes se ha generado correctamente.")
        print("\n=== RESULTADO JSON ===")
        print(resultado)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

if __name__ == "__main__":
    probar_lunes()