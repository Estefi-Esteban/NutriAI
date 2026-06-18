import sys
import io
import uuid
import time
from unittest.mock import patch
from fastapi.testclient import TestClient

# Forzar codificación UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from backend.api.main import app
from backend.database.connection import SessionLocal
from backend.database.repositories.user_repository import obtener_perfil
from backend.database.repositories.plan_repository import obtener_plan_activo

# Mock de respuestas del agente de seguimiento
respuestas_mock = []
mock_indice = 0

def mock_followup_agent_chat(self, mensaje):
    global mock_indice
    res = respuestas_mock[mock_indice]
    mock_indice += 1
    return res

# Estructura del plan semanal inicial para insertar
MENU_TEST_INICIAL = {
    "Lunes": {
        "comidas": {
            "desayuno": {
                "nombre": "Avena con leche",
                "calorias": 300,
                "proteinas_g": 12.0,
                "carbos_g": 48.0,
                "grasas_g": 6.0,
                "tiempo_preparacion_min": 5,
                "dificultad": "facil",
                "ingredientes": [{"nombre": "Avena", "cantidad": 50, "unidad": "g"}],
                "pasos": ["Mezclar"],
                "sustituciones": {}
            }
        },
        "totales_dia": {
            "calorias": 300.0,
            "proteinas_g": 12.0,
            "carbos_g": 48.0,
            "grasas_g": 6.0
        }
    },
    "Martes": {
        "comidas": {
            "desayuno": {
                "nombre": "Yogur con avena",
                "calorias": 280,
                "proteinas_g": 15.0,
                "carbos_g": 40.0,
                "grasas_g": 5.0,
                "ingredientes": [],
                "pasos": [],
                "sustituciones": {}
            }
        },
        "totales_dia": {
            "calorias": 280.0,
            "proteinas_g": 15.0,
            "carbos_g": 40.0,
            "grasas_g": 5.0
        }
    }
}

@patch("backend.agents.followup_agent.FollowupAgent.chat", mock_followup_agent_chat)
@patch("backend.api.routers.seguimiento.generar_plan_background") # Evitar que corra Groq real al regenerar
def test_followup_flow(mock_gen_bg):
    global mock_indice, respuestas_mock
    mock_indice = 0
    respuestas_mock = [
        # 1. Saludo inicial al conectar (/iniciar)
        {
            "respuesta": "Hola Marta, soy tu asistente de seguimiento. ¿Cómo te ha ido esta semana?",
            "accion": None,
            "datos": None
        },
        # 2. Respuesta a reportar peso
        {
            "respuesta": "¡Felicidades por bajar a 66kg! He actualizado tu perfil.",
            "accion": "actualizar_perfil",
            "datos": {"peso_kg": 66.0}
        },
        # 3. Respuesta a modificar desayuno del Lunes
        {
            "respuesta": "He cambiado tu desayuno del Lunes por huevos revueltos.",
            "accion": "modificar_comida",
            "datos": {
                "dia": "Lunes",
                "comida": "desayuno",
                "nueva_comida": {
                    "nombre": "Huevos Revueltos",
                    "calorias": 250,
                    "proteinas_g": 18.0,
                    "carbos_g": 2.0,
                    "grasas_g": 17.0,
                    "tiempo_preparacion_min": 5,
                    "dificultad": "facil",
                    "ingredientes": [],
                    "pasos": [],
                    "sustituciones": {}
                }
            }
        },
        # 4. Respuesta a regenerar plan
        {
            "respuesta": "Entendido. Recalculando tu plan semanal completo.",
            "accion": "regenerar_plan",
            "datos": {}
        }
    ]

    client = TestClient(app)

    # ── [Paso 1] Registro y Login de usuario
    print("\n🚀 [1/5] Registrar usuario e iniciar sesión...")
    email = f"followup.{uuid.uuid4().hex[:6]}@nutriai.com"
    reg_payload = {
        "nombre": "Marta Seguimiento",
        "email": email,
        "password": "Password123!"
    }
    res_reg = client.post("/auth/registro", json=reg_payload)
    assert res_reg.status_code == 200, f"Error registro: {res_reg.text}"
    token = res_reg.json()["access_token"]
    user_id = res_reg.json()["user_id"]
    headers = {"Authorization": f"Bearer {token}"}

    # ── [Paso 2] Insertar perfil y plan activo en la DB directamente para el test
    print("🚀 [2/5] Creando perfil y plan activo de test en base de datos...")
    with SessionLocal() as db:
        from backend.database.repositories.user_repository import guardar_perfil
        from backend.database.repositories.plan_repository import guardar_plan
        
        perfil_test = {
            "nombre": "Marta Seguimiento",
            "edad": 22,
            "sexo": "mujer",
            "peso_kg": 68.0,
            "altura_cm": 163,
            "objetivo_principal": "perder_grasa",
            "nivel_actividad": "sedentario",
            "dias_entrenamiento": 3,
            "tipo_entrenamiento": "cardio",
            "dieta_tipo": "omnivora",
            "alergias": [],
            "intolerancias": [],
            "tiempo_cocina_min": 30,
            "personas_en_casa": 1,
        }
        guardar_perfil(db, user_id=user_id, datos=perfil_test)
        
        calculos_test = {
            "calorias_objetivo": 1500.0,
            "macros": {"proteinas_g": 120.0, "carbos_g": 150.0, "grasas_g": 44.0}
        }
        guardar_plan(db, user_id=user_id, calculos=calculos_test, menu_semana=MENU_TEST_INICIAL)

    # ── [Paso 3] Iniciar conversación de seguimiento
    print("🚀 [3/5] POST /chat/seguimiento/iniciar...")
    res_init = client.post("/chat/seguimiento/iniciar", headers=headers)
    assert res_init.status_code == 200, f"Error iniciar: {res_init.text}"
    init_data = res_init.json()
    print(f"   ✅ Saludo del agente: '{init_data['respuesta']}'")
    assert init_data["accion"] is None

    # ── [Paso 4] Enviar peso nuevo (Acción: actualizar_perfil)
    print("🚀 [4/5] POST /chat/seguimiento/mensaje -> Reportar peso nuevo (66kg)...")
    res_peso = client.post("/chat/seguimiento/mensaje", json={"mensaje": "He bajado de peso a 66kg"}, headers=headers)
    assert res_peso.status_code == 200, f"Error peso: {res_peso.text}"
    peso_data = res_peso.json()
    print(f"   ✅ Respuesta del agente: '{peso_data['respuesta']}'")
    assert peso_data["accion"] == "actualizar_perfil"
    assert peso_data["datos"]["peso_kg"] == 66.0
    
    # Validar cambio en base de datos
    with SessionLocal() as db:
        perfil_db = obtener_perfil(db, user_id=user_id)
        print(f"   ✅ Peso verificado en base de datos: {perfil_db.peso_kg} kg (esperado: 66.0)")
        assert perfil_db.peso_kg == 66.0

    # ── [Paso 5] Modificar comida (Acción: modificar_comida)
    print("🚀 [5/5] POST /chat/seguimiento/mensaje -> Cambiar desayuno lunes por huevos...")
    res_comida = client.post(
        "/chat/seguimiento/mensaje", 
        json={"mensaje": "Cambia el desayuno del lunes por huevos revueltos"}, 
        headers=headers
    )
    assert res_comida.status_code == 200, f"Error comida: {res_comida.text}"
    comida_data = res_comida.json()
    print(f"   ✅ Respuesta del agente: '{comida_data['respuesta']}'")
    assert comida_data["accion"] == "modificar_comida"
    assert comida_data["datos"]["dia"] == "Lunes"
    
    # Validar modificación del plan en base de datos
    with SessionLocal() as db:
        plan_db = obtener_plan_activo(db, user_id=user_id)
        desayuno_lunes = plan_db.plan_semanal["Lunes"]["comidas"]["desayuno"]
        print(f"   ✅ Desayuno modificado en base de datos: '{desayuno_lunes['nombre']}' (esperado: 'Huevos Revueltos')")
        assert desayuno_lunes["nombre"] == "Huevos Revueltos"
        print(f"   ✅ Calorías en BD: {desayuno_lunes['calorias']} kcal")
        # Verificar totales recalculados
        totales_lunes = plan_db.plan_semanal["Lunes"]["totales_dia"]
        print(f"   ✅ Totales Lunes recalculados: {totales_lunes}")
        assert totales_lunes["calorias"] == 250.0 # como solo hay desayuno, el total es el del nuevo desayuno

    # ── [Paso Extra] Solicitar regeneración (Acción: regenerar_plan)
    print("🚀 [*] POST /chat/seguimiento/mensaje -> Solicitar nuevo plan...")
    res_regen = client.post(
        "/chat/seguimiento/mensaje",
        json={"mensaje": "Quiero un plan nuevo completo"},
        headers=headers
    )
    assert res_regen.status_code == 200, f"Error regen: {res_regen.text}"
    regen_data = res_regen.json()
    print(f"   ✅ Respuesta del agente: '{regen_data['respuesta']}'")
    assert regen_data["accion"] == "regenerar_plan"
    assert regen_data["tarea_id"] is not None
    print(f"   ✅ Tarea de regeneración iniciada en background: {regen_data['tarea_id']}")

    print("\n🎉 VERIFICACIÓN DE SEGUIMIENTO COMPLETADA: ¡Todos los flujos del agente funcionan al 100%!")

if __name__ == "__main__":
    test_followup_flow()
