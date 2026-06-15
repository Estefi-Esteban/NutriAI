"""
Motor de Cálculo Nutricional — NutriAI
======================================
Funciones puras de matemática nutricional. Sin IA, sin base de datos.

Fórmulas utilizadas:
  - TMB:  Mifflin-St Jeor (la más precisa según la literatura científica actual)
  - TDEE: Harris-Benedict activity multipliers
  - Macros: distribución basada en objetivo y peso corporal

Autora: NutriAI
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Factores de actividad (Harris-Benedict)
# ---------------------------------------------------------------------------

FACTORES_ACTIVIDAD: dict[str, float] = {
    "sedentario":  1.2,    # Poco o ningún ejercicio
    "ligero":      1.375,  # Ejercicio ligero 1-3 días/semana
    "moderado":    1.55,   # Ejercicio moderado 3-5 días/semana
    "activo":      1.725,  # Ejercicio intenso 6-7 días/semana
    "muy_activo":  1.9,    # Ejercicio muy intenso + trabajo físico
}

# ---------------------------------------------------------------------------
# Ajuste calórico según objetivo principal
# ---------------------------------------------------------------------------

AJUSTE_CALORICO: dict[str, int] = {
    "perder_grasa":         -400,   # Déficit moderado (~0.4 kg/semana)
    "ganar_musculo":        +350,   # Superávit moderado
    "recomposicion_corporal": -200, # Déficit suave para recomp
    "mantenimiento":           0,
    "volumen":              +400,   # Superávit para volumen limpio
}

# ---------------------------------------------------------------------------
# Ratios de macros por objetivo  (proteína g/kg, grasa % calorías)
# ---------------------------------------------------------------------------

MACRO_RATIOS: dict[str, dict] = {
    "perder_grasa": {
        "proteina_por_kg": 2.2,  # Alta proteína para preservar músculo
        "grasa_pct":       0.25,
    },
    "ganar_musculo": {
        "proteina_por_kg": 2.0,
        "grasa_pct":       0.25,
    },
    "recomposicion_corporal": {
        "proteina_por_kg": 2.0,
        "grasa_pct":       0.25,
    },
    "mantenimiento": {
        "proteina_por_kg": 1.8,
        "grasa_pct":       0.30,
    },
    "volumen": {
        "proteina_por_kg": 1.8,
        "grasa_pct":       0.20,  # Más carbos en volumen
    },
}

# Calorías por gramo de cada macronutriente
KCAL_PROTEINA = 4
KCAL_CARBO    = 4
KCAL_GRASA    = 9

# Hidratación: 35 ml por kg de peso corporal
ML_POR_KG = 35


# ---------------------------------------------------------------------------
# Dataclass de resultado completo
# ---------------------------------------------------------------------------

@dataclass
class ResultadoNutricional:
    """Resultado completo del cálculo nutricional para un usuario."""

    # Metabolismo
    tmb:              float  # Tasa Metabólica Basal (kcal)
    tdee:             float  # Gasto energético total diario (kcal)
    calorias_objetivo: float  # Calorías ajustadas al objetivo (kcal)

    # Macronutrientes
    proteinas_g: float
    carbos_g:    float
    grasas_g:    float

    # Proteínas en kcal (útil para verificación)
    proteinas_kcal: float
    carbos_kcal:    float
    grasas_kcal:    float

    # Hidratación
    hidratacion_ml: int

    def __str__(self) -> str:
        return (
            f"TMB:              {self.tmb:.0f} kcal\n"
            f"TDEE:             {self.tdee:.0f} kcal\n"
            f"Calorías objetivo:{self.calorias_objetivo:.0f} kcal\n"
            f"Proteínas:        {self.proteinas_g:.0f} g  ({self.proteinas_kcal:.0f} kcal)\n"
            f"Carbohidratos:    {self.carbos_g:.0f} g  ({self.carbos_kcal:.0f} kcal)\n"
            f"Grasas:           {self.grasas_g:.0f} g  ({self.grasas_kcal:.0f} kcal)\n"
            f"Hidratación:      {self.hidratacion_ml} ml"
        )

    def to_dict(self) -> dict:
        return {
            "tmb":               round(self.tmb, 1),
            "tdee":              round(self.tdee, 1),
            "calorias_objetivo": round(self.calorias_objetivo, 1),
            "macros": {
                "proteinas_g": round(self.proteinas_g, 1),
                "carbos_g":    round(self.carbos_g, 1),
                "grasas_g":    round(self.grasas_g, 1),
            },
            "macros_kcal": {
                "proteinas_kcal": round(self.proteinas_kcal, 1),
                "carbos_kcal":    round(self.carbos_kcal, 1),
                "grasas_kcal":    round(self.grasas_kcal, 1),
            },
            "hidratacion_ml": self.hidratacion_ml,
        }


# ---------------------------------------------------------------------------
# Funciones individuales
# ---------------------------------------------------------------------------

def calcular_tmb(
    peso_kg:   float,
    altura_cm: float,
    edad:      int,
    sexo:      str,          # "hombre" | "mujer"
) -> float:
    """
    Calcula la Tasa Metabólica Basal con la fórmula Mifflin-St Jeor.

    Args:
        peso_kg:   Peso en kilogramos.
        altura_cm: Altura en centímetros.
        edad:      Edad en años.
        sexo:      "hombre" o "mujer" (acepta mayúsculas y variantes).

    Returns:
        TMB en kilocalorías (float).

    Raises:
        ValueError: Si los parámetros están fuera de rango o el sexo es inválido.

    Ejemplo:
        >>> calcular_tmb(68, 163, 21, "mujer")
        1432.75
    """
    if peso_kg <= 0:
        raise ValueError(f"peso_kg debe ser positivo, recibido: {peso_kg}")
    if altura_cm <= 0:
        raise ValueError(f"altura_cm debe ser positiva, recibida: {altura_cm}")
    if not (5 <= edad <= 120):
        raise ValueError(f"edad debe estar entre 5 y 120, recibida: {edad}")

    sexo_norm = sexo.strip().lower()

    base = (10 * peso_kg) + (6.25 * altura_cm) - (5 * edad)

    if sexo_norm in ("hombre", "masculino", "male", "m"):
        return base + 5
    elif sexo_norm in ("mujer", "femenino", "female", "f"):
        return base - 161
    else:
        raise ValueError(
            f"sexo no reconocido: '{sexo}'. Usa 'hombre' o 'mujer'."
        )


def calcular_tdee(
    tmb:             float,
    nivel_actividad: str,  # Enum.value o string libre
) -> float:
    """
    Calcula el Gasto Energético Total Diario (TDEE).

    Args:
        tmb:             TMB obtenida con calcular_tmb().
        nivel_actividad: Uno de: sedentario, ligero, moderado, activo, muy_activo.

    Returns:
        TDEE en kilocalorías (float).

    Raises:
        ValueError: Si nivel_actividad no es reconocido.
    """
    nivel = nivel_actividad.strip().lower()
    factor = FACTORES_ACTIVIDAD.get(nivel)

    if factor is None:
        validos = ", ".join(FACTORES_ACTIVIDAD.keys())
        raise ValueError(
            f"nivel_actividad '{nivel_actividad}' no reconocido. "
            f"Valores válidos: {validos}"
        )

    return tmb * factor


def calcular_calorias_objetivo(
    tdee:              float,
    objetivo_principal: str,
) -> float:
    """
    Ajusta el TDEE según el objetivo nutricional del usuario.

    Args:
        tdee:               TDEE obtenido con calcular_tdee().
        objetivo_principal: Enum.value o string del ObjetivoPrincipal.

    Returns:
        Calorías diarias objetivo (float).

    Raises:
        ValueError: Si el objetivo no es reconocido.
    """
    obj = objetivo_principal.strip().lower()
    ajuste = AJUSTE_CALORICO.get(obj)

    if ajuste is None:
        validos = ", ".join(AJUSTE_CALORICO.keys())
        raise ValueError(
            f"objetivo_principal '{objetivo_principal}' no reconocido. "
            f"Valores válidos: {validos}"
        )

    return tdee + ajuste


def calcular_macros(
    calorias:          float,
    peso_kg:           float,
    objetivo_principal: str,
) -> dict:
    """
    Distribuye las calorías objetivo entre proteínas, carbohidratos y grasas.

    Distribución:
      1. Proteínas:      ratio g/kg según objetivo (prioridad para preservar músculo)
      2. Grasas:         porcentaje de calorías según objetivo
      3. Carbohidratos:  calorías restantes

    Args:
        calorias:          Calorías objetivo del día.
        peso_kg:           Peso del usuario en kg (para calcular proteínas).
        objetivo_principal: Mismo valor que en calcular_calorias_objetivo().

    Returns:
        dict con proteinas_g, carbos_g, grasas_g y sus equivalentes en kcal.

    Raises:
        ValueError: Si el objetivo no es reconocido o los carbohidratos resultan negativos.
    """
    obj = objetivo_principal.strip().lower()
    ratios = MACRO_RATIOS.get(obj)

    if ratios is None:
        validos = ", ".join(MACRO_RATIOS.keys())
        raise ValueError(
            f"objetivo_principal '{objetivo_principal}' no reconocido. "
            f"Valores válidos: {validos}"
        )

    # 1 — Proteínas
    proteinas_g    = ratios["proteina_por_kg"] * peso_kg
    proteinas_kcal = proteinas_g * KCAL_PROTEINA

    # 2 — Grasas
    grasas_kcal = calorias * ratios["grasa_pct"]
    grasas_g    = grasas_kcal / KCAL_GRASA

    # 3 — Carbohidratos (resto)
    carbos_kcal = calorias - proteinas_kcal - grasas_kcal
    if carbos_kcal < 0:
        raise ValueError(
            f"Los carbohidratos resultaron negativos ({carbos_kcal:.0f} kcal). "
            "Revisa las calorías objetivo o el peso del usuario."
        )
    carbos_g = carbos_kcal / KCAL_CARBO

    return {
        "proteinas_g":    round(proteinas_g, 1),
        "carbos_g":       round(carbos_g, 1),
        "grasas_g":       round(grasas_g, 1),
        "proteinas_kcal": round(proteinas_kcal, 1),
        "carbos_kcal":    round(carbos_kcal, 1),
        "grasas_kcal":    round(grasas_kcal, 1),
    }


# ---------------------------------------------------------------------------
# Función principal — recibe el objeto UserProfile directamente
# ---------------------------------------------------------------------------

def calcular_todo(perfil) -> ResultadoNutricional:
    """
    Calcula el plan nutricional completo a partir del perfil del usuario.

    Acepta tanto un objeto UserProfile de SQLAlchemy como cualquier objeto
    (o dict) con los atributos equivalentes.

    Args:
        perfil: Objeto UserProfile (o duck-typing compatible) con:
                  peso_kg, altura_cm, edad, sexo,
                  nivel_actividad, objetivo_principal.

    Returns:
        ResultadoNutricional con todos los valores calculados.

    Ejemplo:
        >>> from backend.database.models import UserProfile
        >>> resultado = calcular_todo(perfil_marta)
        >>> print(resultado)
    """
    # Soporte para dict y objetos SQLAlchemy / dataclass
    def _get(attr: str):
        if isinstance(perfil, dict):
            return perfil[attr]
        return getattr(perfil, attr)

    peso_kg    = float(_get("peso_kg"))
    altura_cm  = float(_get("altura_cm"))
    edad       = int(_get("edad"))
    sexo       = str(_get("sexo"))

    # nivel_actividad y objetivo_principal pueden ser Enum o string
    nivel_act  = str(_get("nivel_actividad")).split(".")[-1]   # "NivelActividad.sedentario" → "sedentario"
    objetivo   = str(_get("objetivo_principal")).split(".")[-1]

    # ── Cadena de cálculo ──────────────────────────────────────────────
    tmb       = calcular_tmb(peso_kg, altura_cm, edad, sexo)
    tdee      = calcular_tdee(tmb, nivel_act)
    calorias  = calcular_calorias_objetivo(tdee, objetivo)
    macros    = calcular_macros(calorias, peso_kg, objetivo)

    hidratacion_ml = round(peso_kg * ML_POR_KG)

    return ResultadoNutricional(
        tmb=tmb,
        tdee=tdee,
        calorias_objetivo=calorias,
        proteinas_g=macros["proteinas_g"],
        carbos_g=macros["carbos_g"],
        grasas_g=macros["grasas_g"],
        proteinas_kcal=macros["proteinas_kcal"],
        carbos_kcal=macros["carbos_kcal"],
        grasas_kcal=macros["grasas_kcal"],
        hidratacion_ml=hidratacion_ml,
    )


# ---------------------------------------------------------------------------
# Test rápido al ejecutar directamente: python nutrition_calculator.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys, io, json
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    print("=" * 55)
    print("  TEST - Perfil de Marta")
    print("=" * 55)

    perfil_marta = {
        "peso_kg":           68.0,
        "altura_cm":         163.0,
        "edad":              21,
        "sexo":              "mujer",
        "nivel_actividad":   "sedentario",
        "objetivo_principal": "recomposicion_corporal",
    }

    resultado = calcular_todo(perfil_marta)

    print(resultado)
    print()
    print("-- Verificacion manual (valores esperados) -------------")
    print("  TMB esperada:       1432.75 kcal")
    print("  TDEE esperado:      1719.3  kcal")
    print("  Calorias objetivo:  1519.3  kcal")
    print("  Proteinas:          136 g   (544 kcal)")
    print("  Grasas:              42 g   (380 kcal)")
    print("  Carbohidratos:      149 g   (596 kcal)")
    print("  Hidratacion:        2380 ml")
    print()

    print("-- JSON listo para el Agente ---------------------------")
    print(json.dumps(resultado.to_dict(), indent=2, ensure_ascii=False))
