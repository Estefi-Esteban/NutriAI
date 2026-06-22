from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.schemas.pathology_schema import (
    AnalizarPatologiasRequest, ProtocoloResponse
)
from backend.api.dependencies import get_current_user, get_db
from backend.agents.pathology_agent import PathologyAgent
from backend.database.repositories.protocol_repository import (
    guardar_protocolo, obtener_protocolo
)
from backend.database.repositories.user_repository import obtener_perfil

router = APIRouter(prefix="/patologias", tags=["Patologías"])


@router.post("/analizar", response_model=ProtocoloResponse)
def analizar_patologias(
    payload: AnalizarPatologiasRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Genera el protocolo nutricional para las patologías indicadas
    y lo guarda en BD para que se use en futuros planes.
    """
    perfil = obtener_perfil(db, user_id=current_user.id)
    perfil_dict = {}
    if perfil:
        objetivo = perfil.objetivo_principal
        if hasattr(objetivo, "value"):
            objetivo = objetivo.value
        perfil_dict = {
            "sexo": perfil.sexo,
            "edad": perfil.edad,
            "objetivo_principal": objetivo,
        }

    agente = PathologyAgent()
    protocolo = agente.analizar(
        perfil=perfil_dict,
        patologias_declaradas=payload.patologias,
        alertas_clinicas=payload.alertas_clinicas,
    )

    guardar_protocolo(db, user_id=current_user.id, protocolo=protocolo)

    return ProtocoloResponse(**protocolo)


@router.get("/mi-protocolo", response_model=ProtocoloResponse)
def obtener_mi_protocolo(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Devuelve el protocolo nutricional activo del usuario."""
    protocolo = obtener_protocolo(db, user_id=current_user.id)

    if protocolo is None:
        return ProtocoloResponse(
            patologias_identificadas=[],
            restricciones=[],
            alimentos_prohibidos=[],
            alimentos_prioritarios=[],
            conflictos_detectados=[],
            notas_dietista="",
            nivel_restriccion="bajo",
        )

    return ProtocoloResponse(
        patologias_identificadas=protocolo.patologias_activas or [],
        restricciones=protocolo.restricciones or [],
        alimentos_prohibidos=protocolo.alimentos_prohibidos or [],
        alimentos_prioritarios=protocolo.alimentos_prioritarios or [],
        conflictos_detectados=[],
        notas_dietista=protocolo.notas_dietista or "",
        nivel_restriccion="moderado" if protocolo.patologias_activas else "bajo",
    )
