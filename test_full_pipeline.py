"""
test_full_pipeline.py
=====================
Script orquestador que ejecuta el flujo completo de NutriAI de principio a fin:

    Perfil de Marta (hardcoded)
           ↓
    Motor de cálculo nutricional
           ↓
    Agente Nutricionista  (1 llamada Groq)
           ↓
    Agente Dietista       (7 llamadas Groq, una por día)
           ↓
    Guardar plan en Supabase
           ↓
    Verificación del plan guardado

Uso:
    .\\venv\\Scripts\\python.exe test_full_pipeline.py
    o con el venv activado:
    python test_full_pipeline.py
"""

from __future__ import annotations

import sys
import io
import json
import time
import logging

# Forzar UTF-8 en la consola de Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Logging básico para ver el progreso en consola
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pipeline")


def separador(titulo: str):
    print(f"\n{'=' * 60}")
    print(f"  {titulo}")
    print(f"{'=' * 60}")


# ---------------------------------------------------------------------------
# Perfil de prueba — Marta
# ---------------------------------------------------------------------------

PERFIL_MARTA = {
    "nombre": "Marta",
    "edad": 21,
    "sexo": "mujer",
    "peso_kg": 68.0,
    "altura_cm": 163,
    "porcentaje_grasa": None,
    "objetivo_principal": "recomposicion_corporal",
    "objetivo_secundario": "ganar energía",
    "dias_entrenamiento": 3,
    "tipo_entrenamiento": "fuerza",
    "minutos_sesion": 60,
    "dieta_tipo": "omnivora",
    "alergias": [],
    "intolerancias": [],
    "tiempo_cocina_min": 30,
    "personas_en_casa": 1,
    "presupuesto_semanal_eur": 60,
    "patologias": [],
    "medicacion": "",
    "tiene_analitica": False,
    "nivel_actividad": "sedentario",
}

# ---------------------------------------------------------------------------
# PASO 0 — Imports de los módulos del proyecto
# ---------------------------------------------------------------------------

separador("PASO 0 — Importando módulos")

from backend.utils.nutrition_calculator import calcular_todo
from backend.agents.nutrition_agent import NutritionAgent
from backend.agents.dietist_agent import DietistAgent, DIAS_SEMANA
from backend.database.connection import SessionLocal
from backend.database.repositories.user_repository import (
    crear_usuario,
    guardar_perfil,
    obtener_perfil,
)
from backend.database.repositories.plan_repository import (
    guardar_plan,
    obtener_plan_activo,
)

print("✅ Todos los módulos importados correctamente.")

# ---------------------------------------------------------------------------
# PASO 1 — Motor de cálculo
# ---------------------------------------------------------------------------

separador("PASO 1 — Motor de cálculo nutricional")

calculos = calcular_todo(PERFIL_MARTA).to_dict()

print(f"  TMB:               {calculos['tmb']:.1f} kcal")
print(f"  TDEE:              {calculos['tdee']:.1f} kcal")
print(f"  Calorías objetivo: {calculos['calorias_objetivo']:.1f} kcal")
print(f"  Proteínas:         {calculos['macros']['proteinas_g']:.1f} g")
print(f"  Carbos:            {calculos['macros']['carbos_g']:.1f} g")
print(f"  Grasas:            {calculos['macros']['grasas_g']:.1f} g")
print(f"  Hidratación:       {calculos['hidratacion_ml']} ml")

# ---------------------------------------------------------------------------
# PASO 2 — Agente Nutricionista
# ---------------------------------------------------------------------------

separador("PASO 2 — Agente Nutricionista (análisis clínico)")

nutrition_agente = NutritionAgent()
print("🤖 Llamando a Groq (NutritionAgent)...")
analisis = nutrition_agente.analizar(perfil=PERFIL_MARTA, calculos=calculos)

dist = analisis.get("distribucion_comidas", {})
print(f"✅ Análisis clínico completado.")
print(f"   Distribución: {dist}")
print(f"   Alertas: {analisis.get('alertas', [])}")

# ---------------------------------------------------------------------------
# PASO 3 — Agente Dietista (7 días con anti-rate-limit)
# ---------------------------------------------------------------------------

separador("PASO 3 — Agente Dietista (generando 7 días)")

dietist_agente = DietistAgent()
menu_semana: dict = {}
comidas_previas: list[str] = []

PAUSA_ENTRE_DIAS_SEG = 15  # pausa entre días para respetar el rate-limit de Groq (plan gratuito)

for i, dia in enumerate(DIAS_SEMANA):
    print(f"\n🍽️  Generando {dia}... ({i+1}/7)", end=" ", flush=True)

    try:
        menu_dia = dietist_agente.generar_dia(
            perfil=PERFIL_MARTA,
            calculos=calculos,
            analisis=analisis,
            dia_semana=dia,
            comidas_previas=comidas_previas,
        )
        menu_semana[dia] = menu_dia

        # Acumular nombres para garantizar variedad en los días siguientes
        comidas = menu_dia.get("comidas", {})
        nuevos = [v["nombre"] for v in comidas.values() if isinstance(v, dict) and "nombre" in v]
        comidas_previas.extend(nuevos)

        totales = menu_dia.get("totales_dia", {})
        print(
            f"✅  {totales.get('calorias', '?')} kcal | "
            f"P:{totales.get('proteinas_g', '?')}g | "
            f"C:{totales.get('carbos_g', '?')}g | "
            f"G:{totales.get('grasas_g', '?')}g"
        )

    except RuntimeError as exc:
        # Rate-limit o error de red: reintentamos una vez tras 15s
        if "429" in str(exc) or "rate" in str(exc).lower():
            print(f"⏳ Rate-limit detectado. Esperando 15s...", end=" ", flush=True)
            time.sleep(15)
            menu_dia = dietist_agente.generar_dia(
                perfil=PERFIL_MARTA,
                calculos=calculos,
                analisis=analisis,
                dia_semana=dia,
                comidas_previas=comidas_previas,
            )
            menu_semana[dia] = menu_dia
            comidas = menu_dia.get("comidas", {})
            nuevos = [v["nombre"] for v in comidas.values() if isinstance(v, dict) and "nombre" in v]
            comidas_previas.extend(nuevos)
            print("✅ Reintento exitoso.")
        else:
            raise

    # Pausa cortés entre días para no saturar la API
    if i < len(DIAS_SEMANA) - 1:
        time.sleep(PAUSA_ENTRE_DIAS_SEG)

print(f"\n✅ Semana completa generada — {len(menu_semana)} días.")

# ---------------------------------------------------------------------------
# PASO 4 — Guardar en Supabase
# ---------------------------------------------------------------------------

separador("PASO 4 — Guardando plan en Supabase")

# Guardamos user_id como int puro ANTES de cerrar la sesión para evitar
# DetachedInstanceError al usarlo fuera del bloque 'with'.
user_id: int

with SessionLocal() as db:
    # Crear usuario de prueba (o recuperar si ya existe)
    from sqlalchemy.exc import IntegrityError
    try:
        usuario = crear_usuario(db, nombre="Marta Test", email="marta.test@nutriai.com")
        user_id = int(usuario.id)          # ← int plano, independiente de la sesión
        print(f"✅ Usuario creado: id={user_id}")
    except IntegrityError:
        db.rollback()
        from backend.database.models import User
        usuario = db.query(User).filter(User.email == "marta.test@nutriai.com").first()
        user_id = int(usuario.id)          # ← id antes de que la sesión cierre
        print(f"ℹ️  Usuario ya existe: id={user_id}")

    # Guardar el perfil (reemplaza el anterior si lo hay)
    perfil_db = guardar_perfil(db, user_id=user_id, datos={
        **PERFIL_MARTA,
        "presupuesto_semanal": PERFIL_MARTA["presupuesto_semanal_eur"],
    })
    print(f"✅ Perfil guardado: id={perfil_db.id}")

    # Guardar el plan semanal (desactiva automáticamente los anteriores)
    plan = guardar_plan(
        db=db,
        user_id=user_id,
        calculos=calculos,
        menu_semana=menu_semana,
    )
    print(f"✅ Plan guardado:   id={plan.id} | activo={plan.activo}")

# ---------------------------------------------------------------------------
# PASO 5 — Verificación: leer el plan desde Supabase
# ---------------------------------------------------------------------------

separador("PASO 5 — Verificación: recuperando plan desde Supabase")

with SessionLocal() as db:
    plan_recuperado = obtener_plan_activo(db, user_id=user_id)  # int plano, sin ORM

    if plan_recuperado is None:
        print("❌ ERROR: no se encontró el plan activo en la BD.")
        sys.exit(1)

    print(f"✅ Plan activo encontrado: id={plan_recuperado.id}")
    print(f"   Calorías:  {plan_recuperado.calorias_objetivo:.0f} kcal")
    print(f"   Proteínas: {plan_recuperado.proteinas_g:.1f} g")
    print(f"   Carbos:    {plan_recuperado.carbos_g:.1f} g")
    print(f"   Grasas:    {plan_recuperado.grasas_g:.1f} g")
    print(f"   Generado:  {plan_recuperado.fecha_generacion}")

    dias_guardados = list(plan_recuperado.plan_semanal.keys())
    print(f"   Días en plan_semanal: {dias_guardados}")

    # Mostrar resumen de cada día
    print("\n📋 Resumen del menú semanal guardado:")
    for dia, menu_dia in plan_recuperado.plan_semanal.items():
        totales = menu_dia.get("totales_dia", {})
        print(
            f"   {dia:12s}: "
            f"{totales.get('calorias', '?'):4} kcal | "
            f"P:{totales.get('proteinas_g', '?')}g | "
            f"C:{totales.get('carbos_g', '?')}g | "
            f"G:{totales.get('grasas_g', '?')}g"
        )

# ---------------------------------------------------------------------------
# FIN
# ---------------------------------------------------------------------------

separador("🎉 PIPELINE COMPLETO — TODO OK")
print("""
Puedes verificar el plan en Supabase Table Editor:
  → Tabla: nutrition_plans
  → Columna plan_semanal: JSON con los 7 días
""")
