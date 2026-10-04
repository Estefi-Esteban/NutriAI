from backend.utils.nutrition_calculator import calcular_todo
from backend.database.connection import SessionLocal
from backend.database.repositories.user_repository import obtener_perfil
import os

def test_con_marta():
    """
    Recupera el perfil de Marta desde Supabase
    y calcula sus necesidades nutricionales.
    """
    db = SessionLocal()

    try:
        # Marta se guardó con user_id=4
        perfil = obtener_perfil(db, user_id=4)

        assert perfil is not None, "No se encontró el perfil. Comprueba el user_id."

        print("✅ Perfil cargado desde Supabase")
        print(f"   Peso:      {perfil.peso_kg} kg")
        print(f"   Altura:    {perfil.altura_cm} cm")
        print(f"   Edad:      {perfil.edad} años")
        print(f"   Sexo:      {perfil.sexo}")
        print(f"   Objetivo:  {perfil.objetivo_principal.value}")
        print(f"   Actividad: {perfil.nivel_actividad.value}")

        print("\n🧮 Calculando...")
        resultado = calcular_todo(perfil).to_dict()

        assert resultado["tmb"] > 0
        assert resultado["tdee"] > 0
        assert resultado["calorias_objetivo"] > 0
        assert resultado["macros"]["proteinas_g"] > 0
        assert resultado["macros"]["carbos_g"] > 0
        assert resultado["macros"]["grasas_g"] > 0
        assert resultado["hidratacion_ml"] > 0

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