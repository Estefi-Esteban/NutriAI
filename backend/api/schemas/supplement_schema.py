"""
supplement_schema.py
---------------------
Schemas Pydantic para el módulo de suplementación.
"""

from typing import Optional
from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Tipos de suplemento
# ------------------------------------------------------------------

class SuplementoNecesario(BaseModel):
    """Un suplemento con déficit real o riesgo alto demostrado."""
    nombre: str = Field(..., description="Nombre genérico del suplemento, sin marcas comerciales")
    dosis: str = Field(..., description="Cantidad concreta con unidades (ej: '2000 UI/día')")
    momento: str = Field(..., description="Cuándo y cómo tomarlo para máxima absorción")
    duracion: str = Field(..., description="Duración recomendada del ciclo")
    justificacion: str = Field(..., description="Razón específica para este usuario")
    coste_estimado_mes: str = Field(..., description="'bajo' (<10€), 'medio' (10-30€) o 'alto' (>30€)")


class SuplementoInnecesario(BaseModel):
    """Un suplemento que no tiene justificación real para este usuario."""
    nombre: str = Field(..., description="Nombre genérico")
    motivo: str = Field(..., description="Por qué no lo necesita este usuario en concreto")


# ------------------------------------------------------------------
# Request
# ------------------------------------------------------------------

class RecomendacionRequest(BaseModel):
    """Parámetros para personalizar la generación de recomendaciones."""
    incluir_analisis_clinico: bool = Field(
        False,
        description="Si True, incluye los datos de la analítica clínica del usuario (si la subió)"
    )
    incluir_protocolo_patologias: bool = Field(
        False,
        description="Si True, incluye el protocolo de patologías activo del usuario"
    )


# ------------------------------------------------------------------
# Response
# ------------------------------------------------------------------

class RecomendacionResponse(BaseModel):
    """Respuesta completa con las tres categorías de suplementos."""
    suplementos_necesarios: list[SuplementoNecesario] = Field(
        default_factory=list,
        description="Suplementos con déficit demostrado — prioritarios"
    )
    suplementos_opcionales: list[SuplementoNecesario] = Field(
        default_factory=list,
        description="Suplementos que mejoran el objetivo sin ser imprescindibles"
    )
    suplementos_innecesarios: list[SuplementoInnecesario] = Field(
        default_factory=list,
        description="Suplementos populares que no añaden valor para este perfil"
    )
    notas: str = Field(
        "",
        description="Advertencias generales (interacciones, consulta médica, etc.)"
    )
    resumen: Optional[str] = Field(
        None,
        description="Resumen ejecutivo de las recomendaciones para este usuario"
    )
