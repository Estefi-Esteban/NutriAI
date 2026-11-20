"""
Evaluación del buscador de alimentos.

Mide, con consultas reales y su respuesta correcta, cuántas veces el sistema
acierta, se equivoca (falsos positivos de identidad o nutricionales) o se abstiene.

    python -m backend.rag.evaluation.evaluar
"""

from backend.rag.evaluation.casos import CasoEvaluacion, cargar_casos
from backend.rag.evaluation.metricas import (
    ResultadoCaso,
    Veredicto,
    evaluar_respuesta,
    resumir,
)

__all__ = [
    "CasoEvaluacion",
    "ResultadoCaso",
    "Veredicto",
    "cargar_casos",
    "evaluar_respuesta",
    "resumir",
]
