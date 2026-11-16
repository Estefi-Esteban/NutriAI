"""Esquemas de entrada y salida del análisis visual nutricional."""
from typing import Any

from pydantic import BaseModel, Field


class MacrosNutricionales(BaseModel):
    """Macros de una ración; None significa que el dato no está disponible."""

    kcal: float | None = Field(default=None, ge=0)
    proteinas_g: float | None = Field(default=None, ge=0)
    carbos_g: float | None = Field(default=None, ge=0)
    grasas_g: float | None = Field(default=None, ge=0)

    class Config:
        extra = "allow"


class AlimentoDetectado(BaseModel):
    """Alimento detectado y enriquecido, manteniendo la procedencia de los macros."""

    nombre_detectado: str
    cantidad_g: float | None = Field(default=None, gt=0, le=2000)
    confianza_vision: str
    notas_vision: str | None = None

    verificado_rag: bool = False
    nombre_rag: str | None = None
    similitud_rag: float | None = Field(default=None, ge=0, le=1)

    # Campos históricos: reflejan la fuente seleccionada para ese alimento.
    kcal: float | None = Field(default=None, ge=0)
    proteinas_g: float | None = Field(default=None, ge=0)
    carbos_g: float | None = Field(default=None, ge=0)
    grasas_g: float | None = Field(default=None, ge=0)

    macros_verificados: MacrosNutricionales | None = None
    macros_estimados: MacrosNutricionales | None = None
    origen_macros: str | None = None
    motivo_no_verificado: str | None = None

    class Config:
        extra = "allow"


class TotalesPlato(BaseModel):
    """Totales de macros; un None indica que el total no puede calcularse completo."""

    kcal: float | None = Field(default=None, ge=0)
    proteinas_g: float | None = Field(default=None, ge=0)
    carbos_g: float | None = Field(default=None, ge=0)
    grasas_g: float | None = Field(default=None, ge=0)
    alimentos_sin_datos: list[str] = Field(default_factory=list)

    class Config:
        extra = "allow"


class AnalisisVisualResponse(BaseModel):
    descripcion_plato: str
    calidad_imagen: str
    advertencia: str | None = None
    alimentos: list[AlimentoDetectado] = Field(default_factory=list)

    # "totales" conserva compatibilidad y representa el total combinado.
    totales: TotalesPlato
    totales_estimados: dict[str, Any] | None = None
    totales_verificados: dict[str, Any] | None = None
    totales_combinados: dict[str, Any] | None = None
    validacion_nutricional: dict[str, Any] | None = None

    disclaimer: str

    class Config:
        extra = "allow"
