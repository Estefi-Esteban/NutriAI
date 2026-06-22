import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime

from backend.api.main import app
from backend.api.dependencies import get_current_user
from backend.database.models import (
    User, UserProfile, NutritionPlan, ProtocoloNutricional, ChatMessage,
    ObjetivoPrincipal, NivelActividad, TipoEntrenamiento, DietaTipo
)
from backend.agents.assistant_agent import AssistantAgent

client = TestClient(app)

dummy_user = User(id=999, nombre="Usuario Test", email="test@example.com")


def test_construir_system_prompt():
    """Prueba que el prompt se construya correctamente con los datos del usuario."""
    agent = AssistantAgent()

    perfil = {
        "nombre": "Usuario Test",
        "edad": 30,
        "sexo": "hombre",
        "peso_kg": 80.0,
        "altura_cm": 180.0,
        "objetivo_principal": "perder_grasa",
        "nivel_actividad": "moderado",
        "tipo_entrenamiento": "fuerza",
        "dias_entrenamiento": 4,
        "dieta_tipo": "omnivoro",
        "alergias": ["maní"],
        "patologias": ["hipertension"],
    }

    plan_activo = {
        "calorias_objetivo": 2000.0,
        "proteinas_g": 150.0,
        "carbos_g": 200.0,
        "grasas_g": 70.0,
    }

    protocolo = {
        "notas_dietista": "Reducir sodio.",
    }

    prompt = agent._construir_system_prompt(perfil, plan_activo, protocolo)

    assert "Usuario Test" in prompt
    assert "30 años" in prompt
    assert "80.0 kg" in prompt
    assert "perder_grasa" in prompt
    assert "maní" in prompt
    assert "hipertension" in prompt
    assert "2000.0 kcal/día" in prompt
    assert "Reducir sodio." in prompt


def test_construir_mensajes():
    """Prueba que se construya la lista de mensajes alternando roles."""
    agent = AssistantAgent()

    system_prompt = "System instructions"
    historial = [
        {"rol": "user", "contenido": "Hola"},
        {"rol": "assistant", "contenido": "Hola, ¿en qué te ayudo?"},
    ]
    mensaje_actual = "¿Cómo reduzco sodio?"

    mensajes = agent._construir_mensajes(system_prompt, historial, mensaje_actual)

    assert len(mensajes) == 4
    assert mensajes[0].content == system_prompt
    assert mensajes[1].content == "Hola"
    assert mensajes[2].content == "Hola, ¿en qué te ayudo?"
    assert mensajes[3].content == "¿Cómo reduzco sodio?"


@patch("backend.api.routers.assistant.SessionLocal")
@patch("backend.agents.assistant_agent.AssistantAgent.responder")
def test_enviar_mensaje_ok(mock_responder, mock_session_local):
    """Prueba que enviar un mensaje válido al asistente funciona y retorna 200."""
    try:
        app.dependency_overrides[get_current_user] = lambda: dummy_user

        mock_db = MagicMock()
        mock_session_local.return_value.__enter__.return_value = mock_db

        # Mock del perfil
        mock_user_rel = User(nombre="Usuario Test")
        mock_profile = UserProfile(
            user_id=999,
            sexo="hombre",
            edad=30,
            peso_kg=80.0,
            altura_cm=180.0,
            objetivo_principal=ObjetivoPrincipal.perder_grasa,
            nivel_actividad=NivelActividad.moderado,
            tipo_entrenamiento=TipoEntrenamiento.fuerza,
            dias_entrenamiento=4,
            dieta_tipo=DietaTipo.omnivoro,
            alergias=["maní"],
            patologias=["hipertension"],
            usuario=mock_user_rel
        )

        mock_plan = NutritionPlan(
            user_id=999,
            calorias_objetivo=2000.0,
            proteinas_g=150.0,
            carbos_g=200.0,
            grasas_g=70.0
        )

        mock_protocol = ProtocoloNutricional(
            user_id=999,
            notas_dietista="Reducir sodio."
        )

        mock_historial = [
            ChatMessage(rol="user", contenido="Hola"),
            ChatMessage(rol="assistant", contenido="Hola, Usuario Test")
        ]

        # Simular repositorios
        with patch("backend.api.routers.assistant.obtener_perfil", return_value=mock_profile), \
             patch("backend.api.routers.assistant.obtener_plan_activo", return_value=mock_plan), \
             patch("backend.api.routers.assistant.obtener_protocolo", return_value=mock_protocol), \
             patch("backend.api.routers.assistant.obtener_historial_reciente", return_value=mock_historial), \
             patch("backend.api.routers.assistant.guardar_mensaje") as mock_guardar:

            mock_responder.return_value = "¡Hola! ¿Cómo estás hoy?"

            respuesta = client.post("/asistente/mensaje", json={"mensaje": "Hola de nuevo"})

            assert respuesta.status_code == 200
            data = respuesta.json()
            assert data["respuesta"] == "¡Hola! ¿Cómo estás hoy?"
            assert data["user_id"] == 999
            
            # Verificar que se guardan los mensajes del usuario y del asistente
            assert mock_guardar.call_count == 2
            mock_guardar.assert_any_call(mock_db, user_id=999, rol="user", contenido="Hola de nuevo")
            mock_guardar.assert_any_call(mock_db, user_id=999, rol="assistant", contenido="¡Hola! ¿Cómo estás hoy?")

    finally:
        app.dependency_overrides.clear()


def test_enviar_mensaje_vacio():
    """Prueba que mandar un mensaje vacío retorna error 400."""
    try:
        app.dependency_overrides[get_current_user] = lambda: dummy_user

        respuesta = client.post("/asistente/mensaje", json={"mensaje": "   "})
        assert respuesta.status_code == 400
        assert "no puede estar vacío" in respuesta.json()["detail"]

    finally:
        app.dependency_overrides.clear()


@patch("backend.api.routers.assistant.SessionLocal")
def test_enviar_mensaje_sin_perfil(mock_session_local):
    """Prueba que si el usuario no tiene perfil retorna error 404."""
    try:
        app.dependency_overrides[get_current_user] = lambda: dummy_user

        mock_db = MagicMock()
        mock_session_local.return_value.__enter__.return_value = mock_db

        with patch("backend.api.routers.assistant.obtener_perfil", return_value=None):
            respuesta = client.post("/asistente/mensaje", json={"mensaje": "Hola"})
            assert respuesta.status_code == 404
            assert "Completa tu perfil" in respuesta.json()["detail"]

    finally:
        app.dependency_overrides.clear()


@patch("backend.api.routers.assistant.SessionLocal")
def test_obtener_historial(mock_session_local):
    """Prueba que obtener el historial devuelve los mensajes serializados."""
    try:
        app.dependency_overrides[get_current_user] = lambda: dummy_user

        mock_db = MagicMock()
        mock_session_local.return_value.__enter__.return_value = mock_db

        mock_historial = [
            ChatMessage(rol="user", contenido="Hola", fecha=datetime(2026, 6, 22, 10, 0, 0)),
            ChatMessage(rol="assistant", contenido="Hola, Usuario Test", fecha=datetime(2026, 6, 22, 10, 0, 5))
        ]

        with patch("backend.api.routers.assistant.obtener_historial_reciente", return_value=mock_historial):
            respuesta = client.get("/asistente/historial")
            assert respuesta.status_code == 200
            data = respuesta.json()
            assert data["total"] == 2
            assert data["mensajes"][0]["rol"] == "user"
            assert data["mensajes"][0]["contenido"] == "Hola"
            assert data["mensajes"][1]["rol"] == "assistant"

    finally:
        app.dependency_overrides.clear()


@patch("backend.api.routers.assistant.SessionLocal")
def test_borrar_historial(mock_session_local):
    """Prueba que borrar el historial limpia los mensajes y retorna el conteo."""
    try:
        app.dependency_overrides[get_current_user] = lambda: dummy_user

        mock_db = MagicMock()
        mock_session_local.return_value.__enter__.return_value = mock_db

        with patch("backend.api.routers.assistant.limpiar_historial", return_value=4) as mock_limpiar:
            respuesta = client.delete("/asistente/historial")
            assert respuesta.status_code == 200
            data = respuesta.json()
            assert "4 mensajes eliminados" in data["mensaje"]
            mock_limpiar.assert_called_once_with(mock_db, user_id=999)

    finally:
        app.dependency_overrides.clear()
