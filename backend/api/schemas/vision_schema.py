"""
vision_schema.py
-----------------
Schemas Pydantic para el endpoint de análisis visual de platos.
"""

from typing import Optional
from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Modelos de respuesta (lo que devuelve el agente)
# ------------------------------------------------------------------

class AlimentoDetectado(BaseModel):
    """Un alimento individual identificado en la foto y enriquecido con macros."""
    nombre_detectado: str = Field(..., description="Nombre tal como lo detectó el modelo visual")
    cantidad_g: float = Field(..., description="Cantidad estimada en gramos")
    confianza_vision: str = Field(..., description="ALTA, MEDIA o BAJA")
    notas_vision: Optional[str] = Field(None, description="Notas del modelo si había ambigüedad")

    # Datos verificados de ChromaDB
    verificado_rag: bool = Field(False, description="True si se encontró match en ChromaDB")
    nombre_rag: Optional[str] = Field(None, description="Nombre del alimento en la base de datos")
    similitud_rag: Optional[float] = Field(None, description="Similitud semántica 0-1 con ChromaDB")
    kcal: Optional[float] = Field(None, description="Calorías calculadas para la cantidad detectada")
    proteinas_g: Optional[float] = Field(None, description="Proteínas en gramos")
    carbos_g: Optional[float] = Field(None, description="Carbohidratos en gramos")
    grasas_g: Optional[float] = Field(None, description="Grasas en gramos")


class TotalesPlato(BaseModel):
    """Macros totales del plato (solo suma de alimentos verificados por RAG)."""
    kcal: float
    proteinas_g: float
    carbos_g: float
    grasas_g: float
    alimentos_sin_datos: list[str] = Field(
        default_factory=list,
        description="Alimentos detectados para los que no se encontraron macros verificados"
    )


class AnalisisVisualResponse(BaseModel):
    """Respuesta completa del análisis visual de un plato."""
    descripcion_plato: str = Field(..., description="Descripción textual breve del plato")
    calidad_imagen: str = Field(..., description="BUENA, ACEPTABLE o MALA")
    advertencia: Optional[str] = Field(None, description="Advertencia si la imagen es poco clara")
    alimentos: list[AlimentoDetectado]
    totales: TotalesPlato
    disclaimer: str = Field(
        ...,
        description="Aviso de que las cantidades son estimaciones con margen de error"
    )
