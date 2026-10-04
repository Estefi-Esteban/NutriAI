import uuid
from datetime import datetime, timedelta

from unittest.mock import patch

from fastapi.testclient import TestClient
from jose import jwt

from backend.api.main import app
from backend.config import jwt_secret_key, jwt_algorithm
from backend.database.connection import SessionLocal
from backend.database.models import User


def mock_verificar_google_token(token):
    if token == "valid-mock-token":
        return {
            "sub": f"google-mock-{uuid.uuid4().hex[:8]}",
            "email": f"marta.google.{uuid.uuid4().hex[:4]}@gmail.com",
            "name": "Marta Google Test"
        }
    return None


def crear_usuario_test(client: TestClient):
    email = f"user.{uuid.uuid4().hex[:8]}@nutriai.com"
    password = "SuperPassword123!"

    response = client.post(
        "/auth/registro",
        json={
            "nombre": "Usuario Test",
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 200, response.text

    return {
        "email": email,
        "password": password,
        "data": response.json(),
    }


@patch("backend.api.routers.auth.verificar_google_token", mock_verificar_google_token)
def test_auth_flow():
    """
    Flujo principal de autenticación:
    registro → login → usuario autenticado → Google OAuth.
    """
    client = TestClient(app)

    email = f"user.{uuid.uuid4().hex[:8]}@nutriai.com"
    password = "SuperPassword123!"
    nombre = "Esteban Test"

    # 1. Registro
    response = client.post(
        "/auth/registro",
        json={
            "nombre": nombre,
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert "access_token" in data
    assert "refresh_token" in data
    assert data["nombre"] == nombre
    assert data["email"] == email

    access_token = data["access_token"]

    # 2. Login
    response_login = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    assert response_login.status_code == 200

    login_data = response_login.json()

    assert "access_token" in login_data
    assert "refresh_token" in login_data

    # 3. Usuario autenticado
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response_user = client.get(
        "/usuarios/me",
        headers=headers,
    )

    assert response_user.status_code == 200

    user_data = response_user.json()

    assert user_data["nombre"] == nombre
    assert user_data["email"] == email

    # 4. Google OAuth
    response_google = client.post(
        "/auth/google",
        json={
            "token": "valid-mock-token"
        },
    )

    assert response_google.status_code == 200

    google_data = response_google.json()

    assert "access_token" in google_data
    assert "refresh_token" in google_data

    # 5. Google token inválido
    response_bad_google = client.post(
        "/auth/google",
        json={
            "token": "invalid-token"
        },
    )

    assert response_bad_google.status_code == 400


def test_registro_email_duplicado():
    client = TestClient(app)

    usuario = crear_usuario_test(client)

    response = client.post(
        "/auth/registro",
        json={
            "nombre": "Otro Usuario",
            "email": usuario["email"],
            "password": "OtraPassword123!",
        },
    )

    assert response.status_code == 400


def test_login_password_incorrecta():
    client = TestClient(app)

    usuario = crear_usuario_test(client)

    response = client.post(
        "/auth/login",
        json={
            "email": usuario["email"],
            "password": "PasswordIncorrecta123!",
        },
    )

    assert response.status_code == 400


def test_login_usuario_inexistente():
    client = TestClient(app)

    response = client.post(
        "/auth/login",
        json={
            "email": f"noexiste.{uuid.uuid4().hex[:8]}@nutriai.com",
            "password": "SuperPassword123!",
        },
    )

    assert response.status_code == 400


def test_endpoint_protegido_sin_token():
    client = TestClient(app)

    response = client.get("/usuarios/me")

    assert response.status_code == 401


def test_endpoint_protegido_con_token_invalido():
    client = TestClient(app)

    response = client.get(
        "/usuarios/me",
        headers={
            "Authorization": "Bearer token-totalmente-invalido"
        },
    )

    assert response.status_code == 401


def test_endpoint_protegido_con_token_manipulado():
    client = TestClient(app)

    usuario = crear_usuario_test(client)

    token = usuario["data"]["access_token"]

    # Modificamos el último carácter del JWT.
    token_manipulado = token[:-1] + (
        "a" if token[-1] != "a" else "b"
    )

    response = client.get(
        "/usuarios/me",
        headers={
            "Authorization": f"Bearer {token_manipulado}"
        },
    )

    assert response.status_code == 401


def test_endpoint_protegido_con_jwt_sin_sub():
    client = TestClient(app)

    payload = {
        "exp": datetime.utcnow() + timedelta(minutes=10)
    }

    token = jwt.encode(
        payload,
        jwt_secret_key,
        algorithm=jwt_algorithm,
    )

    response = client.get(
        "/usuarios/me",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 401


def test_endpoint_protegido_con_sub_invalido():
    client = TestClient(app)

    payload = {
        "sub": "esto-no-es-un-id",
        "exp": datetime.utcnow() + timedelta(minutes=10),
    }

    token = jwt.encode(
        payload,
        jwt_secret_key,
        algorithm=jwt_algorithm,
    )

    response = client.get(
        "/usuarios/me",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 401


def test_endpoint_protegido_con_usuario_inexistente():
    client = TestClient(app)

    payload = {
        "sub": "999999999",
        "exp": datetime.utcnow() + timedelta(minutes=10),
    }

    token = jwt.encode(
        payload,
        jwt_secret_key,
        algorithm=jwt_algorithm,
    )

    response = client.get(
        "/usuarios/me",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 401


def test_refresh_token_rotation():
    client = TestClient(app)

    usuario = crear_usuario_test(client)

    refresh_token_original = usuario["data"]["refresh_token"]

    response = client.post(
        "/auth/refresh",
        json={
            "refresh_token": refresh_token_original
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data
    assert "refresh_token" in data

    nuevo_refresh = data["refresh_token"]

    assert nuevo_refresh != refresh_token_original

    # El refresh token original debe haber sido revocado.
    response_reutilizacion = client.post(
        "/auth/refresh",
        json={
            "refresh_token": refresh_token_original
        },
    )

    assert response_reutilizacion.status_code == 401


def test_refresh_token_invalido():
    client = TestClient(app)

    response = client.post(
        "/auth/refresh",
        json={
            "refresh_token": "refresh-token-inexistente"
        },
    )

    assert response.status_code == 401


def test_logout_revoca_refresh_token():
    client = TestClient(app)

    usuario = crear_usuario_test(client)

    refresh_token = usuario["data"]["refresh_token"]

    response = client.post(
        "/auth/logout",
        json={
            "refresh_token": refresh_token
        },
    )

    assert response.status_code == 200

    # Después del logout no debe poder reutilizarse.
    response_refresh = client.post(
        "/auth/refresh",
        json={
            "refresh_token": refresh_token
        },
    )

    assert response_refresh.status_code == 401


def test_usuario_google_no_puede_hacer_login_tradicional():
    client = TestClient(app)

    with patch(
        "backend.api.routers.auth.verificar_google_token",
        mock_verificar_google_token,
    ):
        response_google = client.post(
            "/auth/google",
            json={
                "token": "valid-mock-token"
            },
        )

    assert response_google.status_code == 200

    email_google = response_google.json()["email"]

    response_login = client.post(
        "/auth/login",
        json={
            "email": email_google,
            "password": "SuperPassword123!",
        },
    )

    assert response_login.status_code == 400