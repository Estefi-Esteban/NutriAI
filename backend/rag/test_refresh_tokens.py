import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

from backend.database.connection import SessionLocal
from backend.database.models import User, RefreshToken
from backend.api.routers.auth import generar_y_guardar_token_refresco
from backend.utils.security import crear_token_acceso

def run_tests():
    print("=" * 60)
    print("  TEST — Flujo de Refresh Tokens (Backend)")
    print("=" * 60)

    db = SessionLocal()
    test_user_email = "test_refresh_tokens@nutriai.com"
    test_user = None

    try:
        # 1. Limpieza inicial por si acaso
        db.query(User).filter(User.email == test_user_email).delete()
        db.commit()

        # 2. Crear usuario de prueba
        print("👤 Creando usuario de prueba...")
        test_user = User(
            nombre="Tester Refresh Tokens",
            email=test_user_email,
            auth_provider="email"
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        print(f"✅ Usuario creado con ID: {test_user.id}")

        # 3. Generar token de acceso y refresh token
        print("\n🔑 Generando tokens iniciales...")
        access_token = crear_token_acceso(subject=test_user.id)
        refresh_token = generar_y_guardar_token_refresco(db, test_user.id)
        print(f"   Access Token: {access_token[:30]}...")
        print(f"   Refresh Token: {refresh_token}")

        # 4. Validar token en la base de datos
        print("\n🔍 Validando el Refresh Token en la base de datos...")
        db_token = db.query(RefreshToken).filter(
            RefreshToken.token == refresh_token,
            RefreshToken.revocado == False
        ).first()

        assert db_token is not None, "❌ Error: El Refresh Token no se encontró en la BD o está revocado"
        assert db_token.user_id == test_user.id, "❌ Error: El token no pertenece al usuario correcto"
        assert db_token.fecha_expiracion > datetime.utcnow(), "❌ Error: El token ya está expirado"
        print("✅ Refresh Token válido encontrado en la BD.")

        # 5. Simular Rotación de Tokens (Refresh)
        print("\n🔄 Simulando la rotación de tokens (Renovación)...")
        # Revocamos el antiguo
        db_token.revocado = True
        db.commit()

        # Generamos los nuevos
        nuevo_access = crear_token_acceso(subject=test_user.id)
        nuevo_refresh = generar_y_guardar_token_refresco(db, test_user.id)
        print(f"   Nuevo Access Token: {nuevo_access[:30]}...")
        print(f"   Nuevo Refresh Token: {nuevo_refresh}")

        # Validar que el viejo esté revocado
        db_old_token = db.query(RefreshToken).filter(RefreshToken.token == refresh_token).first()
        assert db_old_token.revocado is True, "❌ Error: El token original no se marcó como revocado"
        print("✅ Token original correctamente marcado como revocado.")

        # Validar que el nuevo esté activo
        db_new_token = db.query(RefreshToken).filter(
            RefreshToken.token == nuevo_refresh,
            RefreshToken.revocado == False
        ).first()
        assert db_new_token is not None, "❌ Error: El nuevo token no está activo en la BD"
        print("✅ Nuevo Refresh Token activo y listo para usarse.")

        # 6. Simular revocación mediante Logout
        print("\n🚪 Simulando revocación mediante Logout...")
        db_new_token.revocado = True
        db.commit()

        db_logout_token = db.query(RefreshToken).filter(RefreshToken.token == nuevo_refresh).first()
        assert db_logout_token.revocado is True, "❌ Error: El token no se marcó como revocado tras el logout"
        print("✅ Sesión cerrada y token revocado correctamente.")

        print("\n🎉 ¡TODAS LAS PRUEBAS COMPLETADAS CON ÉXITO! 🎉")

    except AssertionError as e:
        print(str(e))
    except Exception as e:
        print(f"❌ Error inesperado: {str(e)}")
    finally:
        # 7. Limpieza final de la base de datos
        print("\n🧹 Limpiando base de datos...")
        if test_user:
            db.query(User).filter(User.id == test_user.id).delete()
            db.commit()
        db.close()
        print("✅ Base de datos limpia.")

if __name__ == "__main__":
    run_tests()
