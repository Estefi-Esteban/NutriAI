from pydantic import BaseModel
from typing import Optional


class GenerarPlanRequest(BaseModel):
    """Solicitud para generar un nuevo plan nutricional."""
    pass


class GenerarPlanResponse(BaseModel):
    """Respuesta inmediata al lanzar la generación."""
    tarea_id: str
    estado: str


class EstadoTareaResponse(BaseModel):
    """Estado actual de una tarea de generación (para polling)."""
    estado: str
    progreso: int
    dia_actual: Optional[str] = None
    user_id: Optional[int] = None
    plan_id: Optional[int] = None
    error: Optional[str] = None


class PlanCompletoResponse(BaseModel):
    """El plan completo, tal como se guarda en BD."""
    plan_id: int
    user_id: int
    calorias_objetivo: float
    proteinas_g: float
    carbos_g: float
    grasas_g: float
    plan_semanal: dict
    activo: bool
