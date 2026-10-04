import uuid
import time
import os
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.api.dependencies import tareas_planes

# Mock de NutritionAgent.analizar
def mock_nutrition_analizar(self, perfil, calculos):
    return {
        "resumen_perfil": "Perfil completo Marta",
        "justificacion_calorias": "Mantenimiento energético",
        "justificacion_macros": {
            "proteinas": "120g para preservar masa",
            "carbos": "200g para energía",
            "grasas": "50g para equilibrio hormonal"
        },
        "recomendaciones": ["Entrenar 3 días", "Hidratarse bien"],
        "alertas": [],
        "distribucion_comidas": {
            "desayuno_pct": 20,
            "media_manana_pct": 10,
            "comida_pct": 35,
            "merienda_pct": 15,
            "cena_pct": 20
        },
        "notas_para_dietista": "Dieta variada"
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
                "carbos_g": 35,
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
            "carbos_g": 35,
            "grasas_g": 10
        }
    }

# Perfil para la prueba de planes
PERFIL_TEST = {
    "nombre": "Marta Completa",
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
    "presupuesto_semanal": 60,
    "patologias": [],
    "medicacion": "",
    "tiene_analitica": False,
    "nivel_actividad": "sedentario",
}

# Mock de ProfileAgent.chat
def mock_profile_agent_chat(self, mensaje):
    if mensaje == "Hola":
        return {
            "respuesta": "Hola, soy tu asistente de perfil de NutriAI. ¿Cuál es tu peso?",
            "perfil_completo": False,
            "datos": None
        }
    else:
        return {
            "respuesta": "¡Gracias! Tu perfil está completo.",
            "perfil_completo": True,
            "datos": PERFIL_TEST
        }

@patch("backend.api.services.plan_service.time.sleep", return_value=None)
@patch("backend.agents.profile_agent.ProfileAgent.chat", mock_profile_agent_chat)
@patch("backend.agents.nutrition_agent.NutritionAgent.analizar", mock_nutrition_analizar)
@patch("backend.agents.dietist_agent.DietistAgent.generar_dia", mock_dietist_generar_dia)
def test_full_system(mock_sleep):
    client = TestClient(app)
    
    # 1. Registrar usuario
    print("\n🚀 [1/8] POST /auth/registro...")
    email = f"e2e.{uuid.uuid4().hex[:6]}@nutriai.com"
    payload_reg = {
        "nombre": "Marta Autenticada",
        "email": email,
        "password": "PasswordSegura123!"
    }
    response = client.post("/auth/registro", json=payload_reg)
    assert response.status_code == 200, f"Error: {response.text}"
    auth_data = response.json()
    token = auth_data["access_token"]
    user_id = auth_data["user_id"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"   ✅ Registro exitoso. user_id={user_id}, token={token[:20]}...")
    
    # 2. Iniciar Chat (Autenticado)
    print("🚀 [2/8] POST /chat/iniciar...")
    response = client.post("/chat/iniciar", headers=headers)
    assert response.status_code == 200, f"Error: {response.text}"
    chat_start = response.json()
    print(f"   ✅ Chat iniciado con éxito. Saludo: '{chat_start['respuesta']}'")
    
    # 3. Enviar mensaje de Chat (Autenticado)
    print("🚀 [3/8] POST /chat/mensaje...")
    payload_msg = {
        "session_id": str(user_id), # Pasamos el session_id aunque se ignore en favor de la sesión por user_id
        "mensaje": "Quiero ganar músculo"
    }
    response = client.post("/chat/mensaje", json=payload_msg, headers=headers)
    assert response.status_code == 200, f"Error: {response.text}"
    chat_msg = response.json()
    print(f"   ✅ Mensaje enviado con éxito. Respuesta: '{chat_msg['respuesta'][:40]}...'")
    
    # 4. Generar plan en background (Autenticado)
    print("🚀 [4/8] POST /planes/generar...")
    response = client.post("/planes/generar", json={}, headers=headers)
    assert response.status_code == 200, f"Error: {response.text}"
    gen_data = response.json()
    tarea_id = gen_data["tarea_id"]
    print(f"   ✅ Tarea de generación lanzada. tarea_id={tarea_id}, estado={gen_data['estado']}")
    
    # 5. Polling de la tarea (Público)
    print("🚀 [5/8] GET /planes/estado/{tarea_id}...")
    response = client.get(f"/planes/estado/{tarea_id}")
    assert response.status_code == 200, f"Error: {response.text}"
    state_data = response.json()
    print(f"   ✅ Estado de la tarea: {state_data}")
    assert state_data["estado"] == "completado"
    assert state_data["progreso"] == 100
    
    # 6. Obtener Plan Activo (Autenticado)
    print("🚀 [6/8] GET /planes/activo...")
    response = client.get("/planes/activo", headers=headers)
    assert response.status_code == 200, f"Error: {response.text}"
    plan_data = response.json()
    print(f"   ✅ Plan activo recuperado. plan_id={plan_data['plan_id']}")
    print(f"      Calorías objetivo: {plan_data['calorias_objetivo']}")
    print(f"      Días de menú: {list(plan_data['plan_semanal'].keys())}")
    
    # 7. Obtener Lista de la Compra (Autenticado)
    print("🚀 [7/8] GET /lista-compra...")
    response = client.get("/lista-compra", headers=headers)
    assert response.status_code == 200, f"Error: {response.text}"
    list_data = response.json()
    print(f"   ✅ Lista de la compra generada.")
    print(f"      Total items: {list_data['total_items']}")
    print(f"      Categorías:  {list(list_data['categorias'].keys())}")
    
    # 8. Obtener Datos de Usuario y Perfil (Autenticado)
    print("🚀 [8/8] GET /usuarios/me y /usuarios/me/perfil...")
    response_me = client.get("/usuarios/me", headers=headers)
    assert response_me.status_code == 200, f"Error: {response_me.text}"
    me_data = response_me.json()
    print(f"   ✅ Datos /me obtenidos. Nombre: {me_data['nombre']}")
    
    response_profile = client.get("/usuarios/me/perfil", headers=headers)
    assert response_profile.status_code == 200, f"Error: {response_profile.text}"
    profile_data = response_profile.json()
    print(f"   ✅ Datos /me/perfil obtenidos. Edad: {profile_data['edad']}, Objetivo: {profile_data['objetivo_principal']}")

    # 9. Verificar rechazo de rutas protegidas sin token
    print("🚀 [*] Verificando protección de rutas (sin token)...")
    response_unauth = client.get("/planes/activo")
    assert response_unauth.status_code == 401
    print("   ✅ Acceso sin token rechazado correctamente con HTTP 401.")

    print("\n🎉 INTEGRACIÓN COMPLETADA: ¡Todo el sistema con autenticación JWT funciona al 100%!")

if __name__ == "__main__":
    test_full_system()
