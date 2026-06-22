"""
test_calculator.py
-------------------
Tests unitarios del motor de cálculo nutricional.
Verifican que las fórmulas de TMB, TDEE y macros producen
resultados correctos y dentro de rangos clínicamente válidos.
"""

import pytest
from backend.utils.nutrition_calculator import calcular_todo


# ── Perfil base de prueba ─────────────────────────────────────────────────────
PERFIL_MUJER_SEDENTARIA = {
    "nombre": "Test",
    "edad": 21,
    "sexo": "mujer",
    "peso_kg": 68.0,
    "altura_cm": 163,
    "porcentaje_grasa": None,
    "objetivo_principal": "recomposicion_corporal",
    "nivel_actividad": "sedentario",
    "dias_entrenamiento": 0,
    "tipo_entrenamiento": "ninguno",
    "dieta_tipo": "omnivora",
    "alergias": [],
    "intolerancias": [],
    "tiempo_cocina_min": 30,
    "personas_en_casa": 1,
    "presupuesto_semanal_eur": 60,
}

PERFIL_HOMBRE_ACTIVO = {
    **PERFIL_MUJER_SEDENTARIA,
    "sexo": "hombre",
    "edad": 30,
    "peso_kg": 80.0,
    "altura_cm": 180,
    "objetivo_principal": "ganar_musculo",
    "nivel_actividad": "activo",
    "dias_entrenamiento": 5,
    "tipo_entrenamiento": "fuerza",
}


# ── Tests de TMB ──────────────────────────────────────────────────────────────

def test_tmb_mujer_resultado_conocido():
    """La TMB de Marta debe ser aproximadamente 1432 kcal (Mifflin-St Jeor)."""
    resultado = calcular_todo(PERFIL_MUJER_SEDENTARIA)
    assert abs(resultado.tmb - 1432.75) < 1.0, f"TMB esperada ~1432.75, obtenida {resultado.tmb}"


def test_tmb_hombre_mayor_que_mujer():
    """Para mismo peso/talla/edad, la TMB del hombre debe ser mayor."""
    res_mujer = calcular_todo(PERFIL_MUJER_SEDENTARIA)
    res_hombre = calcular_todo({**PERFIL_MUJER_SEDENTARIA, "sexo": "hombre"})
    assert res_hombre.tmb > res_mujer.tmb


def test_tmb_aumenta_con_peso():
    """A más peso, mayor TMB."""
    res_base = calcular_todo(PERFIL_MUJER_SEDENTARIA)
    res_mas_peso = calcular_todo({**PERFIL_MUJER_SEDENTARIA, "peso_kg": 80.0})
    assert res_mas_peso.tmb > res_base.tmb


def test_tmb_rango_clinico_razonable():
    """La TMB debe estar siempre entre 800 y 4000 kcal para perfiles normales."""
    resultado = calcular_todo(PERFIL_MUJER_SEDENTARIA)
    assert 800 < resultado.tmb < 4000


# ── Tests de TDEE ─────────────────────────────────────────────────────────────

def test_tdee_mayor_que_tmb():
    """El TDEE siempre debe ser mayor que la TMB."""
    resultado = calcular_todo(PERFIL_MUJER_SEDENTARIA)
    assert resultado.tdee > resultado.tmb


def test_tdee_activo_mayor_que_sedentario():
    """Un perfil activo debe tener mayor TDEE que uno sedentario."""
    res_sedentario = calcular_todo(PERFIL_MUJER_SEDENTARIA)
    res_activo = calcular_todo({**PERFIL_MUJER_SEDENTARIA, "nivel_actividad": "activo"})
    assert res_activo.tdee > res_sedentario.tdee


# ── Tests de Calorías objetivo ────────────────────────────────────────────────

def test_calorias_deficit_menor_que_tdee():
    """En objetivo de perder grasa, las calorías objetivo deben ser menores al TDEE."""
    resultado = calcular_todo({**PERFIL_MUJER_SEDENTARIA, "objetivo_principal": "perder_grasa"})
    assert resultado.calorias_objetivo < resultado.tdee


def test_calorias_superavit_mayor_que_tdee():
    """En objetivo de ganar músculo, las calorías objetivo deben ser mayores al TDEE."""
    resultado = calcular_todo({**PERFIL_MUJER_SEDENTARIA, "objetivo_principal": "ganar_musculo"})
    assert resultado.calorias_objetivo > resultado.tdee


def test_calorias_mantenimiento_igual_tdee():
    """En mantenimiento, las calorías objetivo deben ser iguales al TDEE."""
    resultado = calcular_todo({**PERFIL_MUJER_SEDENTARIA, "objetivo_principal": "mantenimiento"})
    assert resultado.calorias_objetivo == pytest.approx(resultado.tdee, abs=1.0)


# ── Tests de Macros ───────────────────────────────────────────────────────────

def test_macros_suman_calorias_objetivo():
    """Las kcal de los macros deben sumar aproximadamente las calorías objetivo."""
    resultado = calcular_todo(PERFIL_MUJER_SEDENTARIA)
    kcal_calculadas = (resultado.proteinas_g * 4) + (resultado.carbos_g * 4) + (resultado.grasas_g * 9)
    assert abs(kcal_calculadas - resultado.calorias_objetivo) < 20


def test_proteina_minima_por_kg():
    """La proteína debe ser al menos 1.5g por kg de peso corporal."""
    resultado = calcular_todo(PERFIL_MUJER_SEDENTARIA)
    proteina_por_kg = resultado.proteinas_g / PERFIL_MUJER_SEDENTARIA["peso_kg"]
    assert proteina_por_kg >= 1.5


def test_macros_no_negativos():
    """Ningún macro puede ser negativo."""
    resultado = calcular_todo(PERFIL_MUJER_SEDENTARIA)
    assert resultado.proteinas_g >= 0
    assert resultado.carbos_g >= 0
    assert resultado.grasas_g >= 0


# ── Tests de Hidratación ──────────────────────────────────────────────────────

def test_hidratacion_razonable():
    """La hidratación debe estar entre 1500ml y 5000ml para perfiles normales."""
    resultado = calcular_todo(PERFIL_MUJER_SEDENTARIA)
    assert 1500 <= resultado.hidratacion_ml <= 5000
