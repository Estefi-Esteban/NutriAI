"""
Seguridad del cálculo nutricional: suelo calórico, adultos, datos plausibles.

No requieren red, claves ni base de datos.
"""

import math

import pytest

from backend.utils.exceptions import PerfilInvalidoError, PerfilNoAptoError
from backend.utils.health_limits import (
    ALTURA_MAX_CM,
    ALTURA_MIN_CM,
    PESO_MAX_KG,
    PESO_MIN_KG,
    SUELO_KCAL_ABSOLUTO,
    aplicar_suelo_calorico,
    normalizar_sexo,
    suelo_calorico,
    validar_biometria_para_calculo,
    validar_perfil,
)
from backend.utils.nutrition_calculator import calcular_todo

PERFIL_CALCULO = {
    "peso_kg": 68, "altura_cm": 163, "edad": 30, "sexo": "mujer",
    "nivel_actividad": "moderado", "objetivo_principal": "mantenimiento",
}

PERFIL_VALIDO = {
    "edad": 28, "peso_kg": 70, "altura_cm": 175, "sexo": "hombre",
    "objetivo_principal": "mantenimiento", "nivel_actividad": "moderado",
    "tipo_entrenamiento": "mixto", "dieta_tipo": "omnivoro",
    "dias_entrenamiento": 3, "tiempo_cocina_min": 30, "personas_en_casa": 1,
}


# ---------------------------------------------------------------------------
# Plausibilidad de peso y altura (errores de unidades o de tecleo)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("peso_kg", 5000), ("peso_kg", 12), ("peso_kg", PESO_MIN_KG - 0.1),
        ("altura_cm", 1.75), ("altura_cm", 1750), ("altura_cm", ALTURA_MAX_CM + 1),
    ],
)
def test_validar_perfil_rechaza_peso_y_altura_implausibles(campo, valor):
    with pytest.raises(PerfilInvalidoError):
        validar_perfil({**PERFIL_VALIDO, campo: valor})


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("peso_kg", PESO_MIN_KG), ("peso_kg", PESO_MAX_KG),
     ("altura_cm", ALTURA_MIN_CM), ("altura_cm", ALTURA_MAX_CM)],
)
def test_validar_perfil_acepta_los_limites_inclusivos(campo, valor):
    validar_perfil({**PERFIL_VALIDO, campo: valor})


def test_no_se_excluye_por_imc():
    # Decisión de diseño: no hay umbrales de IMC; solo plausibilidad de unidades.
    validar_perfil({**PERFIL_VALIDO, "peso_kg": 160, "altura_cm": 150})


def test_mensaje_de_altura_sugiere_revisar_unidades():
    with pytest.raises(PerfilInvalidoError) as exc:
        validar_biometria_para_calculo(70, 1.75)
    assert "centímetros" in str(exc.value)


# ---------------------------------------------------------------------------
# Elegibilidad: la calculadora ya no genera planes para menores
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("edad", [5, 8, 14, 17])
def test_calcular_todo_no_genera_plan_a_menores(edad):
    with pytest.raises(PerfilNoAptoError):
        calcular_todo({**PERFIL_CALCULO, "edad": edad, "objetivo_principal": "perder_grasa"})


def test_calcular_todo_acepta_la_mayoria_de_edad():
    assert calcular_todo({**PERFIL_CALCULO, "edad": 18}).calorias_objetivo > 0


def test_calcular_todo_rechaza_datos_implausibles():
    with pytest.raises(PerfilInvalidoError):
        calcular_todo({**PERFIL_CALCULO, "peso_kg": 5000})


# ---------------------------------------------------------------------------
# Suelo calórico
# ---------------------------------------------------------------------------

def test_normalizar_sexo():
    assert normalizar_sexo("Masculino") == "hombre"
    assert normalizar_sexo("F") == "mujer"
    with pytest.raises(PerfilInvalidoError):
        normalizar_sexo("otro")


def test_suelo_es_el_mayor_entre_absoluto_y_tmb():
    assert suelo_calorico("mujer", 1100) == SUELO_KCAL_ABSOLUTO["mujer"]
    assert suelo_calorico("hombre", 1800) == 1800


def test_aplicar_suelo():
    assert aplicar_suelo_calorico(900, "mujer", 1100) == (SUELO_KCAL_ABSOLUTO["mujer"], True)
    assert aplicar_suelo_calorico(2000, "mujer", 1100) == (2000, False)


def test_caso_real_mujer_pequena_ya_no_baja_del_minimo():
    """Antes: 958 kcal, por debajo de su propia TMB de 1132."""
    r = calcular_todo({
        "peso_kg": 45, "altura_cm": 150, "edad": 19, "sexo": "mujer",
        "nivel_actividad": "sedentario", "objetivo_principal": "perder_grasa",
    })
    assert r.ajustado_por_seguridad is True
    assert r.calorias_objetivo >= SUELO_KCAL_ABSOLUTO["mujer"]
    assert r.calorias_objetivo >= r.tmb
    assert r.advertencias, "debe avisar al usuario del ajuste"
    resumen = r.to_dict()
    assert resumen["ajustado_por_seguridad"] is True and resumen["advertencias"]


@pytest.mark.parametrize("objetivo", ["mantenimiento", "ganar_musculo", "volumen"])
def test_mantenimiento_y_superavit_nunca_se_ajustan(objetivo):
    r = calcular_todo({**PERFIL_CALCULO, "objetivo_principal": objetivo})
    assert r.ajustado_por_seguridad is False
    assert r.advertencias == []


# ---------------------------------------------------------------------------
# Invariantes sobre una rejilla de perfiles plausibles
# ---------------------------------------------------------------------------

def test_invariantes_en_rejilla_de_perfiles_plausibles():
    """
    Para cualquier adulto con datos plausibles (incluido peso alto con altura baja,
    sin umbral de IMC): nunca se baja del suelo, ningún macro es negativo, los macros
    suman las calorías y no se lanza ningún error inesperado.
    """
    objetivos = ("perder_grasa", "recomposicion_corporal", "mantenimiento", "ganar_musculo", "volumen")
    calculados = 0
    for sexo in ("hombre", "mujer"):
        for edad in (18, 30, 50, 70, 95):
            for peso in (25, 45, 80, 150, 250, 400):
                for altura in (100, 120, 150, 170, 200, 250):
                    for objetivo in objetivos:
                        r = calcular_todo({
                            "peso_kg": peso, "altura_cm": altura, "edad": edad, "sexo": sexo,
                            "nivel_actividad": "sedentario", "objetivo_principal": objetivo,
                        })
                        calculados += 1
                        assert r.calorias_objetivo >= SUELO_KCAL_ABSOLUTO[sexo] - 1e-6
                        assert min(r.proteinas_g, r.carbos_g, r.grasas_g) >= 0
                        suma = r.proteinas_kcal + r.carbos_kcal + r.grasas_kcal
                        assert math.isclose(suma, r.calorias_objetivo, abs_tol=1.5)
    assert calculados == 2 * 5 * 6 * 6 * 5
