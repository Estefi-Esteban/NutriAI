"""
test_api.py
------------
Tests de los endpoints de la API usando el TestClient de FastAPI.
No hacen llamadas reales a Groq ni a Supabase — usan mocks para
ser rápidos y no depender de servicios externos.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.api.dependencies import get_current_user, get_db
from backend.database.models import User

client = TestClient(app)

# Crear un usuario de prueba dummy
dummy_user = User(id=999, nombre="Usuario Test", email="test@example.com")


# ── Tests del endpoint raíz ───────────────────────────────────────────────────

def test_root_ok():
    """El endpoint raíz debe responder 200 con estado ok."""
    respuesta = client.get("/")
    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "ok"


# ── Tests de autenticación ────────────────────────────────────────────────────

def test_login_credenciales_invalidas():
    """Login con credenciales incorrectas debe devolver 400."""
    # Mockear la base de datos para retornar None (usuario no existe)
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        respuesta = client.post("/auth/login", json={
            "email": "noexiste@test.com",
            "password": "contrasenawrong"
        })
        # El endpoint de la API devuelve 400 en credenciales incorrectas
        assert respuesta.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_registro_email_invalido():
    """Registro con email inválido debe devolver 422 (validación Pydantic)."""
    respuesta = client.post("/auth/registro", json={
        "nombre": "Test",
        "email": "esto-no-es-un-email",
        "password": "password123"
    })
    assert respuesta.status_code == 422


# ── Tests del chat ────────────────────────────────────────────────────────────

def test_chat_mensaje_sin_sesion():
    """Enviar mensaje con session_id inválido debe devolver 404."""
    # Simular usuario autenticado
    app.dependency_overrides[get_current_user] = lambda: dummy_user
    try:
        respuesta = client.post("/chat/mensaje", json={
            "session_id": "sesion-que-no-existe-123",
            "mensaje": "Hola"
        })
        assert respuesta.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_chat_iniciar_devuelve_session_id():
    """Iniciar chat debe devolver un session_id y una respuesta de texto."""
    app.dependency_overrides[get_current_user] = lambda: dummy_user
    try:
        with patch("backend.agents.profile_agent.ProfileAgent.chat") as mock_chat:
            mock_chat.return_value = {
                "respuesta": "¡Hola! ¿Cómo te llamas?",
                "perfil_completo": False,
                "datos": None,
            }
            respuesta = client.post("/chat/iniciar")
            assert respuesta.status_code == 200
            datos = respuesta.json()
            assert "session_id" in datos
            assert len(datos["session_id"]) > 0
            assert "respuesta" in datos
    finally:
        app.dependency_overrides.clear()


# ── Tests de planes ───────────────────────────────────────────────────────────

def test_plan_activo_usuario_inexistente():
    """Pedir plan activo de usuario inexistente con token inválido debe devolver 401."""
    respuesta = client.get(
        "/planes/activo",
        headers={"Authorization": "Bearer token-invalido"}
    )
    # Sin token válido debe dar 401
    assert respuesta.status_code == 401


def test_estado_tarea_inexistente():
    """Consultar estado de tarea inexistente debe devolver 404."""
    respuesta = client.get("/planes/estado/tarea-que-no-existe-xyz")
    assert respuesta.status_code == 404
