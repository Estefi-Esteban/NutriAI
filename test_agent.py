import json
from backend.agents.profile_agent import ProfileAgent
from backend.database.connection import SessionLocal
from backend.database.repositories.user_repository import (
    crear_usuario,
    guardar_perfil,
    obtener_perfil,
)
from datetime import datetime


def guardar_en_supabase(datos: dict) -> None:
    """
    Recibe los datos del agente y los guarda en Supabase.
    """
    db = SessionLocal()

    try:
        # 1. Creamos el usuario base
        print("\n💾 Guardando en Supabase...")
        usuario = crear_usuario(
            db=db,
            nombre=datos["nombre"],
email=f"{datos['nombre'].lower().replace(' ', '_')}_{datetime.now().strftime('%H%M%S')}@nutriai.local"
        )
        print(f"✅ Usuario creado — ID: {usuario.id}")

        # 2. Guardamos el perfil completo
        perfil = guardar_perfil(
            db=db,
            user_id=usuario.id,
            datos=datos
        )
        print(f"✅ Perfil guardado — ID: {perfil.id}")

        # 3. Verificamos que se guardó correctamente
        perfil_verificado = obtener_perfil(db, usuario.id)
        print(f"\n📋 Verificación:")
        print(f"   Nombre:     {usuario.nombre}")
        print(f"   Objetivo:   {perfil_verificado.objetivo_principal.value}")
        print(f"   Peso:       {perfil_verificado.peso_kg} kg")
        print(f"   Altura:     {perfil_verificado.altura_cm} cm")
        print(f"   Actividad:  {perfil_verificado.nivel_actividad.value}")
        print(f"   Dieta:      {perfil_verificado.dieta_tipo.value}")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Error al guardar: {e}")
        raise

    finally:
        db.close()


def main():
    agente = ProfileAgent()
    print("\n🥗 NutriAI - Test del Agente Perfil")
    print("=" * 40)
    print("Escribe 'salir' para terminar\n")

    # El agente saluda primero
    inicio = agente.chat("Hola")
    print(f"NutriAI: {inicio['respuesta']}\n")

    while True:
        entrada = input("Tú: ").strip()

        if entrada.lower() == "salir":
            break

        if not entrada:
            continue

        resultado = agente.chat(entrada)
        print(f"\nNutriAI: {resultado['respuesta']}\n")

        # Cuando el perfil está completo, guardamos en Supabase
        if resultado["perfil_completo"]:
            print("\n✅ PERFIL COMPLETADO POR EL AGENTE")
            print("=" * 40)
            print(json.dumps(resultado["datos"], indent=2, ensure_ascii=False))

            # Guardamos en la base de datos
            guardar_en_supabase(resultado["datos"])

            print("\n🎉 Todo guardado correctamente en Supabase.")
            print("Puedes verificarlo en el Table Editor de Supabase.")
            break


if __name__ == "__main__":
    main()