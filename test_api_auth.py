import sys
import io
import uuid
from unittest.mock import patch
from fastapi.testclient import TestClient

# Forzar codificación UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from backend.api.main import app
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

@patch("backend.api.routers.auth.verificar_google_token", mock_verificar_google_token)
def test_auth_flow():
    client = TestClient(app)
    
    # Generar credenciales únicas para la prueba
    email = f"user.{uuid.uuid4().hex[:6]}@nutriai.com"
    password = "SuperPassword123!"
    nombre = "Esteban Test"
    
    print("\n🚀 [1/4] POST /auth/registro (Registro tradicional)...")
    payload_reg = {
        "nombre": nombre,
        "email": email,
        "password": password
    }
    response = client.post("/auth/registro", json=payload_reg)
    assert response.status_code == 200, f"Error: {response.text}"
    data = response.json()
    assert "access_token" in data
    assert data["nombre"] == nombre
    assert data["email"] == email
    token_tradicional = data["access_token"]
    user_id = data["user_id"]
    print(f"   ✅ Usuario registrado con ID: {user_id}")
    print(f"   ✅ JWT obtenido con éxito.")
    
    print("🚀 [2/4] POST /auth/login (Login tradicional)...")
    payload_login = {
        "email": email,
        "password": password
    }
    response_login = client.post("/auth/login", json=payload_login)
    assert response_login.status_code == 200, f"Error: {response_login.text}"
    data_login = response_login.json()
    assert "access_token" in data_login
    print(f"   ✅ Login exitoso. JWT obtenido con éxito.")
    
    print("🚀 [3/4] GET /usuarios/{user_id} (Recuperar datos básicos)...")
    response_user = client.get(f"/usuarios/{user_id}")
    assert response_user.status_code == 200, f"Error: {response_user.text}"
    user_data = response_user.json()
    assert user_data["nombre"] == nombre
    assert user_data["email"] == email
    print(f"   ✅ Datos recuperados. Nombre: {user_data['nombre']}")
    
    print("🚀 [4/4] POST /auth/google (Registro/Login con Google)...")
    payload_google = {
        "token": "valid-mock-token"
    }
    response_google = client.post("/auth/google", json=payload_google)
    assert response_google.status_code == 200, f"Error: {response_google.text}"
    data_google = response_google.json()
    assert "access_token" in data_google
    print(f"   ✅ Registro/Login de Google exitoso.")
    print(f"   ✅ Usuario Google ID: {data_google['user_id']}, Email: {data_google['email']}")
    
    # Intentar login con token inválido
    print("🚀 [*] Verificando rechazo de token Google inválido...")
    response_bad_google = client.post("/auth/google", json={"token": "invalid-token"})
    assert response_bad_google.status_code == 400
    print("   ✅ Rechazado correctamente con HTTP 400.")

    print("\n🎉 TODO OK: ¡Todos los flujos de autenticación funcionan a la perfección!")

if __name__ == "__main__":
    test_auth_flow()
