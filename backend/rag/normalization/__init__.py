
"""Punto de entrada público del paquete de normalización."""

from .food_normalizer import (
    MODIFICADORES_PRODUCTO,
    PALABRAS_VACIAS,
    REGLAS_SINONIMOS,
    RESTRICCIONES_CRITICAS,
    ModificadorProducto,
    NormalizadorAlimentos,
    ReglaSinonimo,
    normalizador_alimentos,
)

__all__ = [
    "MODIFICADORES_PRODUCTO",
    "PALABRAS_VACIAS",
    "REGLAS_SINONIMOS",
    "RESTRICCIONES_CRITICAS",
    "ModificadorProducto",
    "NormalizadorAlimentos",
    "ReglaSinonimo",
    "normalizador_alimentos",
]
