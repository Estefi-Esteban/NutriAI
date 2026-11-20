"""
Métricas de evaluación del buscador de alimentos (funciones puras, sin red).

Prioridad del proyecto: reducir los FALSOS POSITIVOS (devolver un alimento que no
es el pedido, o el correcto con calorías imposibles) y abstenerse cuando no hay
evidencia suficiente. Por eso se miden por separado:

    falso_positivo_identidad    devolvió otro alimento
    falso_positivo_nutricional  devolvió el alimento correcto pero con calorías fuera
                                de un rango plausible (dato erróneo del catálogo)
    falso_negativo              había una respuesta correcta y se abstuvo
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from backend.rag.evaluation.casos import CasoEvaluacion


class Veredicto(StrEnum):
    CORRECTO = "correcto"
    ABSTENCION_CORRECTA = "abstencion_correcta"
    ABSTENCION_ACEPTABLE = "abstencion_aceptable"
    FALSO_NEGATIVO = "falso_negativo"
    FALSO_POSITIVO_IDENTIDAD = "falso_positivo_identidad"
    FALSO_POSITIVO_NUTRICIONAL = "falso_positivo_nutricional"
    ERROR = "error"


FALSOS_POSITIVOS = (
    Veredicto.FALSO_POSITIVO_IDENTIDAD,
    Veredicto.FALSO_POSITIVO_NUTRICIONAL,
)
ACIERTOS = (
    Veredicto.CORRECTO,
    Veredicto.ABSTENCION_CORRECTA,
    Veredicto.ABSTENCION_ACEPTABLE,
)


def normalizar(texto: Any) -> str:
    """Minúsculas, sin tildes, solo letras/dígitos/% separados por un espacio."""
    limpio = "".join(
        c
        for c in unicodedata.normalize("NFD", str(texto or "").lower())
        if not unicodedata.combining(c)
    )
    return " ".join(re.findall(r"[a-z0-9ñ%]+", limpio))


def evaluar_respuesta(
    caso: CasoEvaluacion,
    respuesta: Mapping[str, Any] | None,
) -> Veredicto:
    """
    Compara la respuesta del buscador (un dict con 'nombre' y 'kcal_100g', o None
    si se abstuvo) con lo que el caso considera correcto.
    """
    if respuesta is None:
        if caso.decision_esperada == "abstener":
            return Veredicto.ABSTENCION_CORRECTA
        if caso.decision_esperada == "ambiguo" or caso.abstencion_aceptable:
            return Veredicto.ABSTENCION_ACEPTABLE
        return Veredicto.FALSO_NEGATIVO

    kcal = respuesta.get("kcal_100g")

    if caso.decision_esperada == "abstener":
        # No existe una respuesta fiable. Si hay rango de referencia y la kcal
        # devuelta lo incumple, el problema es el dato (nutricional); si no, es
        # haber devuelto algo sin evidencia.
        if caso.kcal_ref and not caso.kcal_plausible(kcal):
            return Veredicto.FALSO_POSITIVO_NUTRICIONAL
        return Veredicto.FALSO_POSITIVO_IDENTIDAD

    nombre = normalizar(respuesta.get("nombre"))
    if not re.match(caso.acepta_regex or "", nombre):
        return Veredicto.FALSO_POSITIVO_IDENTIDAD
    if not caso.kcal_plausible(kcal):
        return Veredicto.FALSO_POSITIVO_NUTRICIONAL
    return Veredicto.CORRECTO


@dataclass(frozen=True)
class ResultadoCaso:
    caso_id: str
    consulta: str
    categoria: str
    origen: str
    decision_esperada: str
    veredicto: Veredicto
    nombre_devuelto: str | None = None
    kcal_devuelta: float | None = None
    similitud: float | None = None
    segundos: float = 0.0
    error: str | None = None


def percentil(valores: Sequence[float], p: float) -> float | None:
    """Percentil por rango más cercano. None si no hay valores."""
    if not valores:
        return None
    ordenados = sorted(valores)
    posicion = max(1, math.ceil(p / 100 * len(ordenados)))
    return ordenados[posicion - 1]


def _razon(numerador: int, denominador: int) -> float | None:
    return numerador / denominador if denominador else None


def resumir(resultados: Iterable[ResultadoCaso]) -> dict[str, Any]:
    """Métricas globales y por categoría. Los casos con error no cuentan en las razones."""
    todos = list(resultados)
    validos = [r for r in todos if r.veredicto != Veredicto.ERROR]
    cuenta = defaultdict(int)
    for r in validos:
        cuenta[r.veredicto] += 1

    respuestas = sum(1 for r in validos if r.nombre_devuelto is not None)
    correctos = cuenta[Veredicto.CORRECTO]
    fp_id = cuenta[Veredicto.FALSO_POSITIVO_IDENTIDAD]
    fp_nut = cuenta[Veredicto.FALSO_POSITIVO_NUTRICIONAL]
    abstenibles = sum(1 for r in validos if r.decision_esperada == "abstener")
    respondibles = len(validos) - abstenibles

    por_categoria: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "correctos": 0, "falsos_positivos": 0, "falsos_negativos": 0, "abstenciones_ok": 0}
    )
    for r in validos:
        fila = por_categoria[r.categoria]
        fila["total"] += 1
        if r.veredicto == Veredicto.CORRECTO:
            fila["correctos"] += 1
        elif r.veredicto in FALSOS_POSITIVOS:
            fila["falsos_positivos"] += 1
        elif r.veredicto == Veredicto.FALSO_NEGATIVO:
            fila["falsos_negativos"] += 1
        else:
            fila["abstenciones_ok"] += 1

    tiempos = [r.segundos for r in validos]

    return {
        "total": len(todos),
        "errores": len(todos) - len(validos),
        "respuestas": respuestas,
        "abstenciones": len(validos) - respuestas,
        "correctos": correctos,
        "falsos_positivos_identidad": fp_id,
        "falsos_positivos_nutricionales": fp_nut,
        "falsos_negativos": cuenta[Veredicto.FALSO_NEGATIVO],
        "abstenciones_correctas": cuenta[Veredicto.ABSTENCION_CORRECTA],
        "abstenciones_aceptables": cuenta[Veredicto.ABSTENCION_ACEPTABLE],
        # --- razones ---
        "precision_de_respuestas": _razon(correctos, respuestas),
        "tasa_falsos_positivos": _razon(fp_id + fp_nut, respuestas),
        "tasa_falsos_positivos_nutricionales": _razon(fp_nut, respuestas),
        "recall_respondibles": _razon(correctos, respondibles),
        "abstencion_correcta": _razon(cuenta[Veredicto.ABSTENCION_CORRECTA], abstenibles),
        "decisiones_acertadas": _razon(sum(cuenta[v] for v in ACIERTOS), len(validos)),
        # --- tiempo ---
        "segundos_p50": percentil(tiempos, 50),
        "segundos_p95": percentil(tiempos, 95),
        "segundos_media": (sum(tiempos) / len(tiempos)) if tiempos else None,
        "por_categoria": {k: dict(v) for k, v in sorted(por_categoria.items())},
    }
