import pytest

from backend.utils.exceptions import PerfilInvalidoError, PerfilNoAptoError
from backend.utils.health_limits import validar_elegibilidad_plan, validar_perfil


PERFIL_VALIDO = {
    "edad": 28,
    "peso_kg": 70,
    "altura_cm": 175,
    "sexo": "hombre",
    "objetivo_principal": "mantenimiento",
    "nivel_actividad": "moderado",
    "tipo_entrenamiento": "mixto",
    "dieta_tipo": "omnivoro",
    "dias_entrenamiento": 3,
    "tiempo_cocina_min": 30,
    "personas_en_casa": 1,
    "alergias": [],
    "intolerancias": [],
}


def test_acepta_perfil_adulto_valido():
    validar_perfil(PERFIL_VALIDO)


def test_permite_guardar_perfil_de_menor_sin_generar_plan():
    validar_perfil({**PERFIL_VALIDO, "edad": 17})


def test_bloquea_plan_automatico_para_menores():
    with pytest.raises(PerfilNoAptoError):
        validar_elegibilidad_plan({**PERFIL_VALIDO, "edad": 17})


def test_permite_plan_automatico_para_adulto():
    validar_elegibilidad_plan(PERFIL_VALIDO)


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("peso_kg", 0),
        ("altura_cm", -1),
        ("edad", 28.5),
        ("edad", 121),
        ("sexo", "desconocido"),
        ("dias_entrenamiento", 8),
        ("tiempo_cocina_min", -1),
        ("personas_en_casa", 0),
        ("presupuesto_semanal", -10),
        ("peso_kg", float("nan")),
        ("altura_cm", float("inf")),
    ],
)
def test_rechaza_datos_invalidos(campo, valor):
    with pytest.raises(PerfilInvalidoError):
        validar_perfil({**PERFIL_VALIDO, campo: valor})


def test_no_exige_campos_opcionales_de_salud():
    validar_perfil(PERFIL_VALIDO)


def test_rechaza_alergias_con_formato_incorrecto():
    with pytest.raises(PerfilInvalidoError):
        validar_perfil({**PERFIL_VALIDO, "alergias": "cacahuete"})
