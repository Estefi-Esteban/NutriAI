import sys
import io
import os
from pathlib import Path
from fastapi.testclient import TestClient

# Forzar codificación UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from backend.api.main import app

def test_error_handlers_and_logging():
    client = TestClient(app)
    
    print("\n🚀 [1/3] Verificando RecursoNoEncontradoError -> HTTP 404...")
    # Buscamos una tarea de plan inexistente
    response = client.get("/planes/estado/inexistente-123")
    assert response.status_code == 404, f"Se esperaba 404, se obtuvo {response.status_code}"
    data = response.json()
    assert data["error"] == "recurso_no_encontrado"
    assert "inexistente-123" in data["detail"]
    print("   ✅ RecursoNoEncontradoError capturado correctamente.")

    # Registramos un usuario de prueba para poder autenticarnos y probar las dependencias de chat
    import uuid
    email = f"error.test.{uuid.uuid4().hex[:6]}@nutriai.com"
    password = "SuperPassword123!"
    
    # Registro
    reg_response = client.post("/auth/registro", json={
        "nombre": "Test Errores",
        "email": email,
        "password": password
    })
    assert reg_response.status_code == 200
    token = reg_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    print("🚀 [2/3] Verificando SesionNoEncontradaError -> HTTP 404...")
    # Enviamos un mensaje de chat directamente sin llamar a /chat/iniciar primero
    chat_response = client.post("/chat/mensaje", json={"mensaje": "Hola de prueba"}, headers=headers)
    assert chat_response.status_code == 404, f"Se esperaba 404, se obtuvo {chat_response.status_code}"
    chat_data = chat_response.json()
    assert chat_data["error"] == "sesion_no_encontrada"
    assert "no encontrada o expirada" in chat_data["detail"]
    print("   ✅ SesionNoEncontradaError capturado correctamente al no iniciar sesión.")

    # Probamos iniciar chat y enviar mensaje (debería funcionar)
    print("🚀 [*] Verificando flujo feliz del chat (iniciar -> mensaje)...")
    init_response = client.post("/chat/iniciar", headers=headers)
    assert init_response.status_code == 200
    init_data = init_response.json()
    assert "session_id" in init_data
    
    msg_response = client.post("/chat/mensaje", json={"mensaje": "Me llamo Esteban"}, headers=headers)
    assert msg_response.status_code == 200
    print("   ✅ Flujo feliz funciona correctamente tras inicializar sesión.")

    print("🚀 [3/3] Verificando la creación del archivo de logs...")
    # Verificamos que existe la ruta de logs y el archivo nutriai.log
    ruta_log = Path("logs/nutriai.log")
    assert ruta_log.exists(), "El archivo de logs logs/nutriai.log no fue creado"
    assert ruta_log.stat().st_size > 0, "El archivo de logs está vacío"
    print(f"   ✅ Archivo de logs encontrado en {ruta_log.absolute()} con tamaño {ruta_log.stat().st_size} bytes.")

    print("\n🎉 TODO OK: ¡El sistema de manejo de errores y logging robusto funciona a la perfección!")

if __name__ == "__main__":
    test_error_handlers_and_logging()
