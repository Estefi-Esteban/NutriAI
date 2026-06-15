from backend.database.connection import engine
from sqlalchemy import text

try:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("✅ Conexión a Supabase correcta")
except Exception as e:
    print(f"❌ Error: {e}")