"""
test_verify_plan.py
===================
Verificación rápida del PASO 5 sin llamar a Groq.
Lee el plan activo de un user_id ya guardado en Supabase y muestra
el resumen de los 7 días.

Uso:
    python test_verify_plan.py
"""

import json
from backend.database.connection import SessionLocal
from backend.database.repositories.plan_repository import obtener_plan_activo
import os
# ← Marta Test ya guardada en una ejecución anterior
USER_ID = 5

print(f"\n🔍 Buscando plan activo para user_id={USER_ID}...\n")

with SessionLocal() as db:
    plan = obtener_plan_activo(db, user_id=USER_ID)

    if plan is None:
        print("❌ No se encontró ningún plan activo.")
        sys.exit(1)

    print(f"✅ Plan activo encontrado")
    print(f"   id:        {plan.id}")
    print(f"   Calorías:  {plan.calorias_objetivo:.0f} kcal")
    print(f"   Proteínas: {plan.proteinas_g:.1f} g")
    print(f"   Carbos:    {plan.carbos_g:.1f} g")
    print(f"   Grasas:    {plan.grasas_g:.1f} g")
    print(f"   Generado:  {plan.fecha_generacion}")
    print(f"   Activo:    {plan.activo}")

    dias = list(plan.plan_semanal.keys())
    print(f"\n📋 Días guardados en plan_semanal: {dias}")

    print("\n─── Resumen nutricional por día ───────────────────────────")
    for dia, menu_dia in plan.plan_semanal.items():
        totales = menu_dia.get("totales_dia", {})
        print(
            f"  {dia:12s}: "
            f"{str(totales.get('calorias', '?')):4} kcal | "
            f"P:{totales.get('proteinas_g', '?')}g | "
            f"C:{totales.get('carbos_g', '?')}g | "
            f"G:{totales.get('grasas_g', '?')}g"
        )

    print("\n─── Detalle del Lunes (muestra) ───────────────────────────")
    lunes = plan.plan_semanal.get("Lunes", {})
    for toma, datos in lunes.get("comidas", {}).items():
        if isinstance(datos, dict):
            print(f"  {toma:14s}: {datos.get('nombre', '?')}  ({datos.get('calorias', '?')} kcal)")

print("\n✅ Verificación completada — el plan se lee correctamente desde Supabase.\n")
