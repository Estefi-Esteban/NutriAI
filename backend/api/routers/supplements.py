"""
supplements.py — Router de Suplementación
------------------------------------------
POST /suplementos/generar
    Genera recomendaciones personalizadas llamando al SupplementAgent.
    Opcionalmente enriquece con analítica clínica y protocolo de patologías.
    Guarda el resultado en BD.

GET /suplementos/mis-suplementos
    Devuelve las recomendaciones guardadas sin volver a llamar al modelo.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException

from backend.api.schemas.supplement_schema import (
    RecomendacionRequest,
    RecomendacionResponse,
)
from backend.api.dependencies import get_current_user
from backend.agents.supplement_agent import SupplementAgent
from backend.database.connection import SessionLocal
from backend.database.repositories.user_repository import obtener_perfil
from backend.database.repositories.supplement_repository import (
    guardar_recomendacion,
    obtener_recomendacion,
)
from backend.database.repositories.protocol_repository import obtener_protocolo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/suplementos", tags=["Suplementación"])


def _perfil_a_dict(perfil, user=None) -> dict:
    """Convierte el ORM UserProfile a un dict limpio para el agente."""
    return {
        "objetivo_principal": perfil.objetivo_principal.value if perfil.objetivo_principal else None,
        "dieta_tipo": perfil.dieta_tipo.value if perfil.dieta_tipo else None,
        "dias_entrenamiento": perfil.dias_entrenamiento,
        "tipo_entrenamiento": perfil.tipo_entrenamiento.value if perfil.tipo_entrenamiento else None,
        "nivel_actividad": perfil.nivel_actividad.value if perfil.nivel_actividad else None,
        "edad": perfil.edad,
        "sexo": perfil.sexo,
        "peso_kg": perfil.peso_kg,
        "patologias": perfil.patologias or [],
        "alergias": perfil.alergias or [],
        "intolerancias": perfil.intolerancias or [],
        "medicacion": perfil.medicacion,
    }


@router.post("/generar", response_model=RecomendacionResponse)
def generar_recomendacion(
    payload: RecomendacionRequest,
    current_user=Depends(get_current_user),
):
    """
    Genera recomendaciones de suplementación personalizadas.

    El agente clasifica en tres categorías:
    - **Necesarios**: déficit real demostrado o riesgo muy alto
    - **Opcionales**: mejoran el objetivo sin ser imprescindibles
    - **Innecesarios**: gasto evitable para este perfil concreto

    Usa `incluir_protocolo_patologias: true` si el usuario tiene patologías
    activas registradas para obtener recomendaciones más precisas.
    """
    with SessionLocal() as db:
        perfil = obtener_perfil(db, user_id=current_user.id)
        if perfil is None:
            raise HTTPException(
                status_code=404,
                detail="Completa tu perfil antes de generar recomendaciones de suplementación.",
            )

        perfil_dict = _perfil_a_dict(perfil)

        # Protocolo de patologías (opcional)
        protocolo_dict = None
        if payload.incluir_protocolo_patologias:
            protocolo_db = obtener_protocolo(db, user_id=current_user.id)
            if protocolo_db:
                protocolo_dict = {
                    "patologias_activas": protocolo_db.patologias_activas,
                    "restricciones": protocolo_db.restricciones,
                    "alimentos_prohibidos": protocolo_db.alimentos_prohibidos,
                    "alimentos_prioritarios": protocolo_db.alimentos_prioritarios,
                    "notas_dietista": protocolo_db.notas_dietista,
                }
                logger.info(
                    "suplementos: incluyendo protocolo de patologías del usuario %s",
                    current_user.id,
                )
            else:
                logger.info(
                    "suplementos: usuario %s no tiene protocolo de patologías guardado",
                    current_user.id,
                )

    # El análisis clínico se podría pasar en el futuro desde la BD —
    # por ahora el router lo deja en None (el agente ya lo maneja)
    analisis_clinico = None

    logger.info("suplementos: generando recomendaciones para usuario %s", current_user.id)

    agente = SupplementAgent()
    try:
        recomendacion = agente.recomendar(
            perfil=perfil_dict,
            analisis_clinico=analisis_clinico,
            protocolo_patologias=protocolo_dict,
        )
    except ValueError as e:
        logger.error("suplementos: el agente no devolvió JSON válido — %s", e)
        raise HTTPException(
            status_code=502,
            detail="El agente no pudo generar las recomendaciones. Inténtalo de nuevo.",
        )
    except Exception as e:
        logger.error("suplementos: error inesperado — %s", e)
        raise HTTPException(status_code=500, detail="Error interno al generar recomendaciones.")

    # Guardar en BD
    with SessionLocal() as db:
        guardar_recomendacion(db, user_id=current_user.id, recomendacion=recomendacion)

    return RecomendacionResponse(**recomendacion)


@router.get("/mis-suplementos", response_model=RecomendacionResponse)
def obtener_mis_suplementos(current_user=Depends(get_current_user)):
    """
    Devuelve las recomendaciones de suplementación guardadas del usuario.

    No llama al modelo — devuelve el resultado de la última generación.
    Para actualizar las recomendaciones usa `POST /suplementos/generar`.
    """
    with SessionLocal() as db:
        rec = obtener_recomendacion(db, user_id=current_user.id)

    if rec is None:
        raise HTTPException(
            status_code=404,
            detail="No tienes recomendaciones generadas. Usa POST /suplementos/generar primero.",
        )

    return RecomendacionResponse(
        suplementos_necesarios=rec.suplementos_necesarios or [],
        suplementos_opcionales=rec.suplementos_opcionales or [],
        suplementos_innecesarios=rec.suplementos_innecesarios or [],
        notas=rec.notas or "",
        resumen=rec.resumen,
    )
