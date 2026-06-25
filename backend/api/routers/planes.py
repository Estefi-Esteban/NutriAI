from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
import io

from backend.api.schemas.plan_schema import (
    GenerarPlanRequest,
    GenerarPlanResponse,
    EstadoTareaResponse,
    PlanCompletoResponse,
)
from backend.api.dependencies import crear_tarea_plan, obtener_tarea_plan, get_current_user
from backend.api.rate_limiter import limitar_peticiones_ia
from backend.api.services.plan_service import generar_plan_background
from backend.database.connection import SessionLocal
from backend.database.repositories.user_repository import obtener_perfil
from backend.database.repositories.plan_repository import obtener_plan_activo
from backend.database.repositories.protocol_repository import obtener_protocolo
from backend.database.repositories.supplement_repository import obtener_recomendacion
from backend.rag.clinical_knowledge_search import buscar_evidencia
from backend.utils.pdf_generator import generar_pdf_reporte
from backend.database.models import User
from backend.utils.exceptions import RecursoNoEncontradoError

router = APIRouter(prefix="/planes", tags=["Planes"])


@router.post("/generar", response_model=GenerarPlanResponse)
def generar_plan(
    payload: GenerarPlanRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(limitar_peticiones_ia)
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
        raise RecursoNoEncontradoError(f"Tarea '{tarea_id}' no encontrada")

    return EstadoTareaResponse(**tarea)


@router.get("/activo", response_model=PlanCompletoResponse)
def plan_activo(current_user: User = Depends(get_current_user)):
    """Obtiene el plan activo guardado del usuario autenticado."""
    with SessionLocal() as db:
        plan = obtener_plan_activo(db, user_id=current_user.id)
        if plan is None:
            raise RecursoNoEncontradoError("No hay plan activo para este usuario")

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


@router.get("/reporte")
def descargar_reporte(current_user: User = Depends(get_current_user)):
    """
    Genera y descarga el informe mensual de evolución en PDF para el usuario autenticado.
    """
    with SessionLocal() as db:
        perfil = obtener_perfil(db, user_id=current_user.id)
        if perfil is None:
            raise RecursoNoEncontradoError(
                "No se encontró el perfil de usuario. Por favor completa el onboarding."
            )

        plan = obtener_plan_activo(db, user_id=current_user.id)
        protocolo = obtener_protocolo(db, user_id=current_user.id)
        suplementos = obtener_recomendacion(db, user_id=current_user.id)

        # Buscar en RAG clínico sobre patologías y objetivos
        query_parts = []
        if perfil.objetivo_principal:
            query_parts.append(perfil.objetivo_principal.value)
        if perfil.patologias:
            query_parts.extend(perfil.patologias)

        query_rag = " ".join(query_parts) if query_parts else "nutrition clinical healthy guidelines"
        evidencias = buscar_evidencia(query_rag, n_resultados=2)

        # Convertir modelos SQLAlchemy a diccionarios planos
        perfil_dict = {
            "nombre": current_user.nombre,
            "edad": perfil.edad,
            "sexo": perfil.sexo,
            "peso_kg": perfil.peso_kg,
            "altura_cm": perfil.altura_cm,
            "porcentaje_grasa": perfil.porcentaje_grasa,
            "objetivo_principal": perfil.objetivo_principal.value if perfil.objetivo_principal else "mantenimiento",
            "objetivo_secundario": perfil.objetivo_secundario,
            "velocidad_objetivo": perfil.velocidad_objetivo.value if perfil.velocidad_objetivo else "moderado",
            "nivel_actividad": perfil.nivel_actividad.value if perfil.nivel_actividad else "sedentario",
            "dias_entrenamiento": perfil.dias_entrenamiento,
            "tipo_entrenamiento": perfil.tipo_entrenamiento.value if perfil.tipo_entrenamiento else "ninguno",
            "dieta_tipo": perfil.dieta_tipo.value if perfil.dieta_tipo else "omnivoro",
            "alergias": perfil.alergias or [],
            "intolerancias": perfil.intolerancias or [],
            "presupuesto_semanal": perfil.presupuesto_semanal,
            "tiempo_cocina_min": perfil.tiempo_cocina_min,
            "personas_en_casa": perfil.personas_en_casa,
            "medicacion": perfil.medicacion,
            "patologias": perfil.patologias or [],
        }

        plan_dict = {
            "calorias_objetivo": plan.calorias_objetivo,
            "proteinas_g": plan.proteinas_g,
            "carbos_g": plan.carbos_g,
            "grasas_g": plan.grasas_g,
            "plan_semanal": plan.plan_semanal,
        } if plan else None

        protocolo_dict = {
            "alimentos_prohibidos": protocolo.alimentos_prohibidos or [],
            "alimentos_prioritarios": protocolo.alimentos_prioritarios or [],
            "notas_dietista": protocolo.notas_dietista,
        } if protocolo else None

        suplementos_dict = {
            "suplementos_necesarios": suplementos.suplementos_necesarios or [],
            "suplementos_opcionales": suplementos.suplementos_opcionales or [],
            "suplementos_innecesarios": suplementos.suplementos_innecesarios or [],
        } if suplementos else None

        # Generar PDF en bytes
        pdf_bytes = generar_pdf_reporte(
            perfil=perfil_dict,
            plan=plan_dict,
            protocolo=protocolo_dict,
            suplementos=suplementos_dict,
            evidencias=evidencias
        )

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="reporte_mensual_{current_user.nombre.lower()}.pdf"'
            }
        )
