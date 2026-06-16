from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends

from backend.api.schemas.plan_schema import (
    GenerarPlanRequest,
    GenerarPlanResponse,
    EstadoTareaResponse,
    PlanCompletoResponse,
)
from backend.api.dependencies import crear_tarea_plan, obtener_tarea_plan, get_current_user
from backend.api.services.plan_service import generar_plan_background
from backend.database.connection import SessionLocal
from backend.database.repositories.plan_repository import obtener_plan_activo
from backend.database.models import User

router = APIRouter(prefix="/planes", tags=["Planes"])


@router.post("/generar", response_model=GenerarPlanResponse)
def generar_plan(
    payload: GenerarPlanRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Lanza la generación de un plan completo en segundo plano para el usuario autenticado.
    Devuelve inmediatamente un tarea_id para consultar el progreso
    con GET /planes/estado/{tarea_id}.
    """
    tarea_id = crear_tarea_plan()

    background_tasks.add_task(
        generar_plan_background,
        tarea_id=tarea_id,
        perfil=payload.perfil,
        user_id=current_user.id,
    )

    return GenerarPlanResponse(tarea_id=tarea_id, estado="iniciado")


@router.get("/estado/{tarea_id}", response_model=EstadoTareaResponse)
def estado_tarea(tarea_id: str):
    """
    Consulta el progreso de una tarea de generación.
    El cliente debe llamar a este endpoint periódicamente (polling)
    hasta que estado sea 'completado' o 'error'.
    """
    tarea = obtener_tarea_plan(tarea_id)
    if tarea is None:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    return EstadoTareaResponse(**tarea)


@router.get("/activo", response_model=PlanCompletoResponse)
def plan_activo(current_user: User = Depends(get_current_user)):
    """Obtiene el plan activo guardado del usuario autenticado."""
    with SessionLocal() as db:
        plan = obtener_plan_activo(db, user_id=current_user.id)
        if plan is None:
            raise HTTPException(status_code=404, detail="No hay plan activo para este usuario")

        return PlanCompletoResponse(
            plan_id=plan.id,
            user_id=plan.user_id,
            calorias_objetivo=plan.calorias_objetivo,
            proteinas_g=plan.proteinas_g,
            carbos_g=plan.carbos_g,
            grasas_g=plan.grasas_g,
            plan_semanal=plan.plan_semanal,
            activo=plan.activo,
        )
