import sys
import io
from sqlalchemy import text
from backend.database.connection import engine

# Forzar codificación UTF-8 para evitar errores de codificación en consola Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

print("🔍 Iniciando migración de base de datos...")

sql_statements = [
    "ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id VARCHAR UNIQUE;",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider VARCHAR DEFAULT 'email';"
]

try:
    with engine.connect() as conn:
        with conn.begin():
            for statement in sql_statements:
                print(f"   Ejecutando: {statement}")
                conn.execute(text(statement))
    print("✅ Migración de base de datos completada con éxito.")
except Exception as e:
    print(f"❌ Error al ejecutar la migración: {e}")
    sys.exit(1)
