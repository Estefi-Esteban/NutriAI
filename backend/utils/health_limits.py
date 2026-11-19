"""
Validación de perfiles de NutriAI.

Este módulo es independiente de FastAPI y de los proveedores de IA.
No aplica diagnósticos ni decide tratamientos: valida integridad de datos
y evita generar planes automáticos para menores con una fórmula de adultos.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from backend.utils.exceptions import PerfilInvalidoError, PerfilNoAptoError

# ---------------------------------------------------------------------------
# Rangos de PLAUSIBILIDAD (integridad de datos)
# ---------------------------------------------------------------------------
# Detectan errores de unidades o de tecleo (p. ej. la altura en metros o un peso
# de 5000 kg). NO son criterios de elegibilidad clínica ni de constitución.
PESO_MIN_KG, PESO_MAX_KG = 25.0, 400.0
ALTURA_MIN_CM, ALTURA_MAX_CM = 100.0, 250.0

# ---------------------------------------------------------------------------
# Límites de seguridad del cálculo
# ---------------------------------------------------------------------------
# IMPORTANTE: son mínimos convencionales habituales en guías de práctica y deben
# ser validados por un dietista-nutricionista antes de usarse con usuarios reales.

# Suelo calórico absoluto (kcal/día). En un déficit nunca se baja del mayor
# entre este valor y la TMB de la persona.
SUELO_KCAL_ABSOLUTO: dict[str, float] = {"mujer": 1200.0, "hombre": 1500.0}

# Tope técnico de proteína como fracción de las kcal totales. Evita que la dosis
# por kg de peso total consuma casi todo el presupuesto energético en perfiles
# con peso alto y calorías bajas (carbohidratos negativos). No es una
# recomendación clínica.
PROTEINA_MAX_PCT_KCAL = 0.40

_SEXO_HOMBRE = frozenset({"hombre", "masculino", "male", "m"})
_SEXO_MUJER = frozenset({"mujer", "femenino", "female", "f"})


def _numero_finito(datos: Mapping[str, Any], campo: str, problemas: list[str]) -> float | None:
    valor = datos.get(campo)
    if isinstance(valor, bool) or valor is None:
        problemas.append(f"{campo}: es obligatorio y debe ser numérico.")
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        problemas.append(f"{campo}: debe ser numérico.")
        return None
    if not math.isfinite(numero):
        problemas.append(f"{campo}: debe ser un número finito.")
        return None
    return numero


def _problemas_rango_biometrico(peso: float | None, altura: float | None) -> list[str]:
    """Problemas de plausibilidad de peso y altura (ignora los valores ausentes)."""
    problemas: list[str] = []
    if peso is not None and not PESO_MIN_KG <= peso <= PESO_MAX_KG:
        problemas.append(
            f"peso_kg: debe estar entre {PESO_MIN_KG:g} y {PESO_MAX_KG:g} kg."
        )
    if altura is not None and not ALTURA_MIN_CM <= altura <= ALTURA_MAX_CM:
        problemas.append(
            f"altura_cm: debe estar entre {ALTURA_MIN_CM:g} y {ALTURA_MAX_CM:g} cm "
            "(¿está en centímetros?)."
        )
    return problemas


def validar_biometria_para_calculo(peso_kg: float, altura_cm: float) -> None:
    """Lanza PerfilInvalidoError si el peso o la altura no son plausibles."""
    problemas = _problemas_rango_biometrico(peso_kg, altura_cm)
    if problemas:
        raise PerfilInvalidoError(problemas)


def normalizar_sexo(valor: Any) -> str:
    """Devuelve 'hombre' o 'mujer'. Lanza PerfilInvalidoError si no se reconoce."""
    texto = str(valor or "").strip().casefold()
    if texto in _SEXO_HOMBRE:
        return "hombre"
    if texto in _SEXO_MUJER:
        return "mujer"
    raise PerfilInvalidoError(["sexo: valor no reconocido."])


def suelo_calorico(sexo: Any, tmb: float) -> float:
    """Mínimo seguro de kcal/día: el mayor entre el suelo absoluto y la TMB."""
    return max(SUELO_KCAL_ABSOLUTO[normalizar_sexo(sexo)], float(tmb))


def aplicar_suelo_calorico(calorias: float, sexo: Any, tmb: float) -> tuple[float, bool]:
    """
    Devuelve (calorias_finales, fue_ajustado).
    Si las calorías objetivo caen por debajo del suelo, se elevan hasta el suelo.
    """
    suelo = suelo_calorico(sexo, tmb)
    if calorias < suelo:
        return suelo, True
    return calorias, False


def validar_perfil(datos: Mapping[str, Any]) -> None:
    """
    Valida un perfil antes de persistirlo.

    Esta función comprueba integridad de datos, no elegibilidad clínica.
    No establece umbrales de IMC ni excluye por peso o constitución.
    """
    if not isinstance(datos, Mapping):
        raise PerfilInvalidoError(["El perfil debe ser un objeto de datos."])

    problemas: list[str] = []

    edad_num = _numero_finito(datos, "edad", problemas)
    peso = _numero_finito(datos, "peso_kg", problemas)
    altura = _numero_finito(datos, "altura_cm", problemas)

    if edad_num is not None:
        if not edad_num.is_integer() or not 1 <= edad_num <= 120:
            problemas.append("edad: debe ser un número entero entre 1 y 120.")
    problemas.extend(_problemas_rango_biometrico(peso, altura))

    sexo = datos.get("sexo")
    if not isinstance(sexo, str) or sexo.strip().casefold() not in (
        _SEXO_HOMBRE | _SEXO_MUJER
    ):
        problemas.append("sexo: valor no reconocido.")

    campos_texto = (
        "objetivo_principal",
        "nivel_actividad",
        "tipo_entrenamiento",
        "dieta_tipo",
    )
    for campo in campos_texto:
        valor = datos.get(campo)
        if not isinstance(valor, str) or not valor.strip():
            problemas.append(f"{campo}: es obligatorio.")

    porcentaje = datos.get("porcentaje_grasa")
    if porcentaje is not None:
        numero = _numero_finito(datos, "porcentaje_grasa", problemas)
        if numero is not None and not 0 < numero < 100:
            problemas.append("porcentaje_grasa: debe estar entre 0 y 100.")

    dias = datos.get("dias_entrenamiento", 0)
    if isinstance(dias, bool):
        problemas.append("dias_entrenamiento: debe ser un entero entre 0 y 7.")
    else:
        try:
            dias_num = int(dias)
            if str(dias).strip() not in {str(dias_num), f"{dias_num}.0"} or not 0 <= dias_num <= 7:
                problemas.append("dias_entrenamiento: debe ser un entero entre 0 y 7.")
        except (TypeError, ValueError):
            problemas.append("dias_entrenamiento: debe ser un entero entre 0 y 7.")

    for campo, minimo in (("tiempo_cocina_min", 0), ("personas_en_casa", 1)):
        valor = datos.get(campo)
        if isinstance(valor, bool):
            problemas.append(f"{campo}: valor entero no válido.")
            continue
        if valor is None:
            problemas.append(f"{campo}: es obligatorio.")
            continue
        try:
            numero = int(valor)
            if numero != float(valor) or numero < minimo:
                problemas.append(f"{campo}: debe ser un entero mayor o igual que {minimo}.")
        except (TypeError, ValueError):
            problemas.append(f"{campo}: debe ser un entero mayor o igual que {minimo}.")

    presupuesto = datos.get("presupuesto_semanal")
    if presupuesto is not None:
        numero = _numero_finito(datos, "presupuesto_semanal", problemas)
        if numero is not None and numero < 0:
            problemas.append("presupuesto_semanal: no puede ser negativo.")

    for campo in ("alergias", "intolerancias", "patologias"):
        valor = datos.get(campo, [])
        if valor is not None and (
            not isinstance(valor, (list, tuple))
            or any(not isinstance(item, str) or not item.strip() for item in valor)
        ):
            problemas.append(f"{campo}: debe ser una colección de textos no vacíos.")

    if problemas:
        raise PerfilInvalidoError(problemas)




def validar_elegibilidad_plan(datos: Mapping[str, Any]) -> None:
    """
    Política conservadora para el motor actual de planes de adultos.

    Debe invocarse en el caso de uso que genera el plan, no al guardar el
    perfil. Así se puede conservar el perfil sin iniciar una recomendación
    nutricional automática que use fórmulas no pediátricas.
    """
    edad = _numero_finito(datos, "edad", [])
    if edad is None or not edad.is_integer():
        raise PerfilInvalidoError(["edad: debe ser un número entero válido."])
    if edad < 18:
        raise PerfilNoAptoError(
            "El generador actual de NutriAI está diseñado para adultos y no "
            "genera planes automáticos para menores de 18 años. Se requiere "
            "un flujo específico con supervisión profesional."
        )
