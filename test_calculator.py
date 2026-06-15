import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from backend.utils.nutrition_calculator import calcular_todo
from backend.database.connection import SessionLocal
from backend.database.repositories.user_repository import obtener_perfil

def test_con_marta():
    """
    Recupera el perfil de Marta desde Supabase
    y calcula sus necesidades nutricionales.
    """
    db = SessionLocal()

    try:
        # Marta se guardó con user_id=4
        perfil = obtener_perfil(db, user_id=4)

        if perfil is None:
            print("❌ No se encontró el perfil. Comprueba el user_id.")
            return

        print("✅ Perfil cargado desde Supabase")
        print(f"   Peso:      {perfil.peso_kg} kg")
        print(f"   Altura:    {perfil.altura_cm} cm")
        print(f"   Edad:      {perfil.edad} años")
        print(f"   Sexo:      {perfil.sexo}")
        print(f"   Objetivo:  {perfil.objetivo_principal.value}")
        print(f"   Actividad: {perfil.nivel_actividad.value}")

        print("\n🧮 Calculando...")
        resultado = calcular_todo(perfil).to_dict()

        print("\n📊 RESULTADO:")
        print(f"   TMB:                {resultado['tmb']} kcal")
        print(f"   TDEE:               {resultado['tdee']} kcal")
        print(f"   Calorías objetivo:  {resultado['calorias_objetivo']} kcal")
        print(f"   Proteínas:          {resultado['macros']['proteinas_g']} g")
        print(f"   Carbohidratos:      {resultado['macros']['carbos_g']} g")
        print(f"   Grasas:             {resultado['macros']['grasas_g']} g")
        print(f"   Hidratación:        {resultado['hidratacion_ml']} ml")

    finally:
        db.close()

if __name__ == "__main__":
    test_con_marta()