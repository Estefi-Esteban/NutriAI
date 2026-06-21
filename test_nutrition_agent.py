"""
Test del Agente Nutricionista — NutriAI
========================================
Ejecutar con:
    python test_nutrition_agent.py

Verifica:
  1. El agente se inicializa correctamente (carga el prompt).
  2. Llama a Groq y obtiene una respuesta.
  3. El JSON de salida tiene todas las claves esperadas.
  4. El razonamiento clínico es coherente con los datos de Marta.
"""

import sys
import io
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from backend.agents.nutrition_agent import NutritionAgent
from backend.utils.nutrition_calculator import calcular_todo


# ── Perfil de prueba: Marta ──────────────────────────────────────────────────

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

# Claves que DEBEN estar en el JSON de salida
CLAVES_ESPERADAS = {
    "resumen_perfil",
    "justificacion_calorias",
    "justificacion_macros",
    "recomendaciones",
    "alertas",
    "distribucion_comidas",
    "notas_para_dietista",
}

CLAVES_MACROS = {"proteinas", "carbos", "grasas"}

CLAVES_DISTRIBUCION = {
    "desayuno_pct",
    "media_manana_pct",
    "comida_pct",
    "merienda_pct",
    "cena_pct",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def ok(msg: str):
    print(f"  ✅  {msg}")

def fallo(msg: str):
    print(f"  ❌  {msg}")
    raise AssertionError(msg)

def separador(titulo: str):
    print(f"\n{'─' * 55}")
    print(f"  {titulo}")
    print(f"{'─' * 55}")


# ── Tests ────────────────────────────────────────────────────────────────────

def test_calculos_base():
    separador("1 · Cálculos nutricionales de Marta")
    calculos = calcular_todo(PERFIL_MARTA).to_dict()

    assert abs(calculos["tmb"] - 1432.75) < 1, f"TMB inesperada: {calculos['tmb']}"
    ok(f"TMB:     {calculos['tmb']:.1f} kcal  (esperado ≈ 1432.75)")

    assert abs(calculos["tdee"] - 1719.3) < 2, f"TDEE inesperado: {calculos['tdee']}"
    ok(f"TDEE:    {calculos['tdee']:.1f} kcal  (esperado ≈ 1719.3)")

    assert abs(calculos["calorias_objetivo"] - 1519.3) < 2
    ok(f"Obj:     {calculos['calorias_objetivo']:.1f} kcal  (esperado ≈ 1519.3)")

    assert abs(calculos["macros"]["proteinas_g"] - 136.0) < 2
    ok(f"Prot:    {calculos['macros']['proteinas_g']:.0f} g")

    return calculos


def test_estructura_json(resultado: dict):
    separador("2 · Estructura del JSON de salida")

    faltantes = CLAVES_ESPERADAS - resultado.keys()
    if faltantes:
        fallo(f"Claves faltantes en el JSON: {faltantes}")
    ok("Todas las claves principales presentes")

    # justificacion_macros
    macros_faltantes = CLAVES_MACROS - resultado["justificacion_macros"].keys()
    if macros_faltantes:
        fallo(f"Claves faltantes en justificacion_macros: {macros_faltantes}")
    ok("justificacion_macros completo")

    # distribucion_comidas
    dist_faltantes = CLAVES_DISTRIBUCION - resultado["distribucion_comidas"].keys()
    if dist_faltantes:
        fallo(f"Claves faltantes en distribucion_comidas: {dist_faltantes}")
    ok("distribucion_comidas completo")

    # Porcentajes suman ~100
    total_pct = sum(resultado["distribucion_comidas"].values())
    if not (95 <= total_pct <= 105):
        fallo(f"Los porcentajes de comidas no suman ~100 (suman {total_pct})")
    ok(f"Porcentajes de comidas suman {total_pct}%")

    # recomendaciones es lista no vacía
    if not isinstance(resultado["recomendaciones"], list) or len(resultado["recomendaciones"]) == 0:
        fallo("recomendaciones debe ser una lista no vacía")
    ok(f"recomendaciones: {len(resultado['recomendaciones'])} elementos")

    # alertas es lista (puede estar vacía para Marta)
    if not isinstance(resultado["alertas"], list):
        fallo("alertas debe ser una lista")
    ok(f"alertas: {len(resultado['alertas'])} alertas")


def test_coherencia_clinica(resultado: dict):
    separador("3 · Coherencia clínica del análisis")

    resumen = resultado["resumen_perfil"].lower()
    if "marta" not in resumen and "recomposic" not in resumen:
        fallo("El resumen no menciona a Marta ni su objetivo de recomposición")
    ok("Resumen menciona el perfil de Marta")

    justif = resultado["justificacion_calorias"].lower()
    if "déficit" not in justif and "deficit" not in justif and "200" not in justif:
        fallo("La justificación de calorías no menciona el déficit aplicado")
    ok("Justificación de calorías menciona el déficit")

    prot_texto = resultado["justificacion_macros"]["proteinas"].lower()
    if "136" not in prot_texto and "2" not in prot_texto and "g/kg" not in prot_texto:
        fallo("Justificación de proteínas no menciona el ratio aplicado")
    ok("Justificación de proteínas referencia el ratio g/kg")

    notas = resultado["notas_para_dietista"]
    if len(notas) < 50:
        fallo("notas_para_dietista demasiado corto — debe ser instrucciones detalladas")
    ok(f"notas_para_dietista con {len(notas)} caracteres")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  NutritionAgent — Test con perfil de Marta")
    print("=" * 55)

    # Test 1: cálculos base
    calculos = test_calculos_base()

    # Inicializar agente
    separador("Inicializando NutritionAgent...")
    agente = NutritionAgent()
    ok("Agente inicializado (prompt cargado)")

    # Llamar al agente
    separador("Llamando a Groq...")
    print("  ⏳ Esto puede tardar unos segundos...")
    resultado = agente.analizar(perfil=PERFIL_MARTA, calculos=calculos)
    ok("Respuesta recibida y JSON parseado correctamente")

    # Test 2: estructura
    test_estructura_json(resultado)

    # Test 3: coherencia clínica
    test_coherencia_clinica(resultado)

    # Resultado completo
    separador("📋 Análisis clínico completo")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))

    print("\n")
    print("=" * 55)
    print("  ✅  TODOS LOS TESTS PASARON")
    print("=" * 55)


if __name__ == "__main__":
    main()
