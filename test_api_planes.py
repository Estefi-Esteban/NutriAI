import sys
import io
import time
from unittest.mock import patch
from fastapi.testclient import TestClient

# Forzar codificación UTF-8 para evitar errores en la consola de Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from backend.api.main import app
from backend.api.dependencies import tareas_planes

# Mock de NutritionAgent.analizar
def mock_nutrition_analizar(self, perfil, calculos):
    return {
        "resumen_perfil": "Test de perfil",
        "justificacion_calorias": "Test de calorias",
        "justificacion_macros": {
            "proteinas": "Test proteinas",
            "carbos": "Test carbos",
            "grasas": "Test grasas"
        },
        "recomendaciones": ["Test rec 1"],
        "alertas": ["Test alerta 1"],
        "distribucion_comidas": {
            "desayuno_pct": 20,
            "media_manana_pct": 10,
            "comida_pct": 35,
            "merienda_pct": 15,
            "cena_pct": 20
        },
        "notas_para_dietista": "Test notas"
    }

# Mock de DietistAgent.generar_dia
def mock_dietist_generar_dia(self, perfil, calculos, analisis, dia_semana, comidas_previas):
    return {
        "dia": dia_semana,
        "comidas": {
            "desayuno": {
                "nombre": f"Desayuno del {dia_semana}",
                "calorias": 300,
                "proteinas_g": 20,
                "carbos_g": 30,
                "grasas_g": 10,
                "tiempo_preparacion_min": 10,
                "dificultad": "facil",
                "ingredientes": [
                    {"nombre": "Avena", "cantidad": 50, "unidad": "g"},
                    {"nombre": "Leche", "cantidad": 200, "unidad": "ml"}
                ],
                "pasos": ["paso1"],
                "sustituciones": ["sus1"]
            }
        },
        "totales_dia": {
            "calorias": 300,
            "proteinas_g": 20,
            "carbos_g": 30,
            "grasas_g": 10
        }
    }

# Perfil de Marta para las pruebas
PERFIL_TEST = {
    "nombre": "Marta Test API",
    "edad": 21,
    "sexo": "mujer",
    "peso_kg": 68.0,
    "altura_cm": 163,
    "porcentaje_grasa": None,
    "objetivo_principal": "recomposicion_corporal",
    "objetivo_secundario": "ganar energía",
    "dias_entrenamiento": 3,
    "tipo_entrenamiento": "fuerza",
    "minutos_sesion": 60,
    "dieta_tipo": "omnivora",
    "alergias": [],
    "intolerancias": [],
    "tiempo_cocina_min": 30,
    "personas_en_casa": 1,
    "presupuesto_semanal_eur": 60,
    "patologias": [],
    "medicacion": "",
    "tiene_analitica": False,
    "nivel_actividad": "sedentario",
}

@patch("backend.api.services.plan_service.time.sleep", return_value=None)
@patch("backend.agents.nutrition_agent.NutritionAgent.analizar", mock_nutrition_analizar)
@patch("backend.agents.dietist_agent.DietistAgent.generar_dia", mock_dietist_generar_dia)
def test_pipeline(mock_sleep):
    client = TestClient(app)
    
    print("\n🚀 [1/3] POST /planes/generar...")
    response = client.post("/planes/generar", json={"perfil": PERFIL_TEST})
    assert response.status_code == 200, f"Error: {response.text}"
    data = response.json()
    tarea_id = data["tarea_id"]
    print(f"✅ Tarea iniciada: tarea_id={tarea_id}, estado={data['estado']}")
    
    # En FastAPI TestClient, las BackgroundTasks se ejecutan síncronamente antes de retornar la respuesta.
    # Por lo tanto, el estado ya debería estar completado al consultar.
    print("🚀 [2/3] GET /planes/estado/{tarea_id}...")
    response_estado = client.get(f"/planes/estado/{tarea_id}")
    assert response_estado.status_code == 200, f"Error: {response_estado.text}"
    estado_data = response_estado.json()
    print(f"✅ Estado tarea: {estado_data}")
    assert estado_data["estado"] == "completado"
    assert estado_data["progreso"] == 100
    user_id = estado_data["user_id"]
    plan_id = estado_data["plan_id"]
    
    print("🚀 [3/4] GET /planes/activo/{user_id}...")
    response_plan = client.get(f"/planes/activo/{user_id}")
    assert response_plan.status_code == 200, f"Error: {response_plan.text}"
    plan_data = response_plan.json()
    print("✅ Plan recuperado con éxito!")
    print(f"   plan_id:           {plan_data['plan_id']}")
    print(f"   user_id:           {plan_data['user_id']}")
    print(f"   calorías objetivo: {plan_data['calorias_objetivo']}")
    print(f"   plan_semanal keys: {list(plan_data['plan_semanal'].keys())}")

    print("🚀 [4/6] GET /lista-compra/{user_id}...")
    response_list = client.get(f"/lista-compra/{user_id}")
    assert response_list.status_code == 200, f"Error: {response_list.text}"
    list_data = response_list.json()
    print("✅ Lista de la compra generada con éxito!")
    print(f"   plan_id:     {list_data['plan_id']}")
    print(f"   total_items: {list_data['total_items']}")
    print(f"   categorías:  {list(list_data['categorias'].keys())}")

    print("🚀 [5/6] GET /usuarios/{user_id}...")
    response_user = client.get(f"/usuarios/{user_id}")
    assert response_user.status_code == 200, f"Error: {response_user.text}"
    user_data = response_user.json()
    print("✅ Datos del usuario recuperados con éxito!")
    print(f"   id:     {user_data['id']}")
    print(f"   nombre: {user_data['nombre']}")
    print(f"   email:  {user_data['email']}")

    print("🚀 [6/6] GET /usuarios/{user_id}/perfil...")
    response_profile = client.get(f"/usuarios/{user_id}/perfil")
    assert response_profile.status_code == 200, f"Error: {response_profile.text}"
    profile_data = response_profile.json()
    print("✅ Perfil del usuario recuperado con éxito!")
    print(f"   user_id:            {profile_data['user_id']}")
    print(f"   peso_kg:            {profile_data['peso_kg']}")
    print(f"   objetivo_principal: {profile_data['objetivo_principal']}")
    
    print("\n🎉 TODO OK: ¡Test completado con éxito!")

if __name__ == "__main__":
    test_pipeline()
