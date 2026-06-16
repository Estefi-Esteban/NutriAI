import sys
import io

# Forzar codificación UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

print("🔍 Iniciando pruebas de verificación de la configuración de Autenticación...")

# 1. Verificar importaciones
print("   [1/2] Verificando importaciones de dependencias...")
try:
    import jose
    import passlib
    import google.auth
    print("   ✅ Dependencias importadas correctamente.")
except Exception as e:
    print(f"   ❌ Error de importación: {e}")
    sys.exit(1)

# 2. Verificar columnas en base de datos
print("   [2/2] Verificando estructura de la base de datos...")
try:
    from backend.database.connection import SessionLocal
    from backend.database.models import User
    
    with SessionLocal() as db:
        from sqlalchemy import inspect
        inspector = inspect(db.bind)
        columns = {col["name"]: col for col in inspector.get_columns("users")}
        
        # Verificar password_hash
        assert "password_hash" in columns, "Columna password_hash no existe"
        assert columns["password_hash"]["nullable"] is True, "password_hash debe ser nullable"
        
        # Verificar google_id
        assert "google_id" in columns, "Columna google_id no existe"
        assert columns["google_id"]["nullable"] is True, "google_id debe ser nullable"
        
        # Verificar auth_provider
        assert "auth_provider" in columns, "Columna auth_provider no existe"
        
        print("   ✅ Estructura de base de datos verificada con éxito.")
except Exception as e:
    print(f"   ❌ Error en verificación de base de datos: {e}")
    sys.exit(1)

print("\n🎉 TODO OK: Configuración de infraestructura completada y validada con éxito.")
