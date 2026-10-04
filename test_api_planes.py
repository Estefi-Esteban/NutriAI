import time
import os
import uuid

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.dependencies import tareas_planes
from backend.database.connection import SessionLocal
from backend.database.repositories.user_repository import guardar_perfil


# ============================================================
# MOCK DE NUTRITION AGENT
# ============================================================

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


# ============================================================
# MOCK DE DIETIST AGENT
# ============================================================

def mock_dietist_generar_dia(
    self,
    perfil,
    calculos,
    analisis,
    dia_semana,
    comidas_previas
):
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
                    {
                        "nombre": "Avena",
                        "cantidad": 50,
                        "unidad": "g"
                    },
                    {
                        "nombre": "Leche",
                        "cantidad": 200,
                        "unidad": "ml"
                    }
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


# ============================================================
# PERFIL DE MARTA PARA LAS PRUEBAS
# ============================================================

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


# ============================================================
# TEST COMPLETO DEL PIPELINE
# ============================================================

@patch(
    "backend.api.services.plan_service.time.sleep",
    return_value=None
)
@patch(
    "backend.agents.nutrition_agent.NutritionAgent.analizar",
    mock_nutrition_analizar
)
@patch(
    "backend.agents.dietist_agent.DietistAgent.generar_dia",
    mock_dietist_generar_dia
)
def test_pipeline(mock_sleep):

    client = TestClient(app)

    # ========================================================
    # 0. REGISTRAR USUARIO Y OBTENER JWT
    # ========================================================

    print("\n🚀 [0/7] POST /auth/registro...")

    email = f"planes.test.{uuid.uuid4().hex[:8]}@nutriai.com"
    password = "SuperPassword123!"

    response_registro = client.post(
        "/auth/registro",
        json={
            "nombre": "Marta Test API",
            "email": email,
            "password": password
        }
    )

    assert response_registro.status_code == 200, (
        f"Error registrando usuario: {response_registro.text}"
    )

    auth_data = response_registro.json()

    assert "access_token" in auth_data
    assert "user_id" in auth_data

    token = auth_data["access_token"]
    user_id = auth_data["user_id"]

    headers = {
        "Authorization": f"Bearer {token}"
    }

    print(f"✅ Usuario registrado. user_id={user_id}")
    print("✅ JWT obtenido correctamente.")

    # ========================================================
    # 1. CREAR PERFIL NUTRICIONAL
    # ========================================================

    print("\n🚀 [1/7] Guardando perfil nutricional...")

    with SessionLocal() as db:
        guardar_perfil(
            db,
            user_id=user_id,
            datos=PERFIL_TEST
        )

    print("✅ Perfil nutricional creado correctamente.")

    # ========================================================
    # 2. GENERAR PLAN
    # ========================================================

    print("\n🚀 [2/7] POST /planes/generar...")

    response = client.post(
        "/planes/generar",
        json={"perfil": PERFIL_TEST},
        headers=headers
    )

    assert response.status_code == 200, (
        f"Error generando plan: {response.text}"
    )

    data = response.json()

    assert "tarea_id" in data

    tarea_id = data["tarea_id"]

    print(
        f"✅ Tarea iniciada: "
        f"tarea_id={tarea_id}, "
        f"estado={data['estado']}"
    )

    # ========================================================
    # 3. COMPROBAR ESTADO DE LA TAREA
    # ========================================================

    print("\n🚀 [3/7] GET /planes/estado/{tarea_id}...")

    response_estado = client.get(
        f"/planes/estado/{tarea_id}",
        headers=headers
    )

    assert response_estado.status_code == 200, (
        f"Error consultando estado: {response_estado.text}"
    )

    estado_data = response_estado.json()

    print(f"✅ Estado tarea: {estado_data}")

    assert estado_data["estado"] == "completado"
    assert estado_data["progreso"] == 100

    user_id = estado_data["user_id"]
    plan_id = estado_data["plan_id"]

    assert user_id is not None
    assert plan_id is not None

    # ========================================================
    # 4. OBTENER PLAN ACTIVO
    # ========================================================

    print("\n🚀 [4/7] GET /planes/activo...")

    response_plan = client.get(
        "/planes/activo",
        headers=headers
    )

    assert response_plan.status_code == 200, (
        f"Error obteniendo plan activo: {response_plan.text}"
    )

    plan_data = response_plan.json()

    print("✅ Plan recuperado con éxito!")
    print(f"   plan_id:           {plan_data['plan_id']}")
    print(f"   user_id:           {plan_data['user_id']}")
    print(f"   calorías objetivo: {plan_data['calorias_objetivo']}")
    print(f"   plan_semanal keys: {list(plan_data['plan_semanal'].keys())}")

    assert plan_data["plan_id"] == plan_id
    assert plan_data["user_id"] == user_id
    assert plan_data["activo"] is True

    # ========================================================
    # 5. LISTA DE LA COMPRA
    # ========================================================

    print("\n🚀 [5/7] GET /lista-compra...")    

    response_list = client.get(
        "/lista-compra",
        headers=headers
    )

    assert response_list.status_code == 200, (
        f"Error obteniendo lista de compra: {response_list.text}"
    )

    list_data = response_list.json()

    print("✅ Lista de la compra generada con éxito!")
    print(f"   plan_id:     {list_data['plan_id']}")
    print(f"   user_id:     {list_data['user_id']}")
    print(f"   total_items: {list_data['total_items']}")
    print(f"   categorías:  {list(list_data['categorias'].keys())}")

    assert list_data["plan_id"] == plan_id
    assert list_data["user_id"] == user_id
    assert list_data["total_items"] >= 0
    assert isinstance(list_data["categorias"], dict)

    # ========================================================
    # 6. DATOS DEL USUARIO
    # ========================================================

    print("\n🚀 [6/7] GET /usuarios/me...")

    response_user = client.get(
        f"/usuarios/me",
        headers=headers
    )

    assert response_user.status_code == 200, (
        f"Error obteniendo usuario: {response_user.text}"
    )

    user_data = response_user.json()

    print("✅ Datos del usuario recuperados con éxito!")
    print(f"   id:     {user_data['id']}")
    print(f"   nombre: {user_data['nombre']}")
    print(f"   email:  {user_data['email']}")

    assert user_data["id"] == user_id
    assert user_data["nombre"] == "Marta Test API"
    assert user_data["email"] == email

    # ========================================================
    # 7. PERFIL NUTRICIONAL
    # ========================================================

    print("\n🚀 [7/7] GET /usuarios/me/perfil...")

    response_profile = client.get(
        f"/usuarios/me/perfil",
        headers=headers
    )

    assert response_profile.status_code == 200, (
        f"Error obteniendo perfil: {response_profile.text}"
    )

    profile_data = response_profile.json()

    print("✅ Perfil del usuario recuperado con éxito!")
    print(f"   user_id:            {profile_data['user_id']}")
    print(f"   peso_kg:            {profile_data['peso_kg']}")
    print(f"   objetivo_principal: {profile_data['objetivo_principal']}")

    assert profile_data["user_id"] == user_id
    assert profile_data["peso_kg"] == PERFIL_TEST["peso_kg"]
    assert profile_data["objetivo_principal"] == PERFIL_TEST["objetivo_principal"]
    

    print("\n🎉 TODO OK: ¡Test completado con éxito!")


if __name__ == "__main__":
    test_pipeline()
