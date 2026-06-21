"""
migrate_enums.py
----------------
Añade valores faltantes a los ENUMs nativos de PostgreSQL en Supabase.

Uso:
    python -m backend.database.migrate_enums

Solo necesita ejecutarse UNA VEZ. PostgreSQL ignora valores que ya existen
si usas la cláusula IF NOT EXISTS (disponible desde PG 9.6).
"""

from sqlalchemy import text
from backend.database.connection import engine


MIGRATIONS = [
    # ObjetivoPrincipal — añadimos recomposicion_corporal
    "ALTER TYPE objetivoprincipal ADD VALUE IF NOT EXISTS 'recomposicion_corporal'",

    # Por si acaso faltan otros valores futuros, los añadimos también
    "ALTER TYPE objetivoprincipal ADD VALUE IF NOT EXISTS 'perder_grasa'",
    "ALTER TYPE objetivoprincipal ADD VALUE IF NOT EXISTS 'ganar_musculo'",
    "ALTER TYPE objetivoprincipal ADD VALUE IF NOT EXISTS 'mantenimiento'",
    "ALTER TYPE objetivoprincipal ADD VALUE IF NOT EXISTS 'volumen'",
]


def run_migrations():
    print("[*] Ejecutando migraciones de ENUMs en Supabase...\n")

    for sql in MIGRATIONS:
        # Cada ALTER TYPE necesita su propia conexion en AUTOCOMMIT
        # (PostgreSQL no permite ADD VALUE dentro de una transaccion)
        try:
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                conn.execute(text(sql))
            valor = sql.split("'")[1]
            print(f"  [OK] '{valor}'")
        except Exception as e:
            print(f"  [ERR] {sql}\n        {e}")

    print("\n[DONE] Migraciones completadas. Ya puedes ejecutar test_agent.py.")


if __name__ == "__main__":
    run_migrations()
