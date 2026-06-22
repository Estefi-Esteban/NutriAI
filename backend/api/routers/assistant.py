from fastapi import APIRouter, Depends, HTTPException

from backend.api.schemas.assistant_schema import (
    MensajeRequest, MensajeResponse, HistorialResponse, MensajeHistorial
)
from backend.api.dependencies import get_current_user
from backend.agents.assistant_agent import AssistantAgent
from backend.database.connection import SessionLocal
from backend.database.repositories.user_repository import obtener_perfil
from backend.database.repositories.plan_repository import obtener_plan_activo
from backend.database.repositories.protocol_repository import obtener_protocolo
from backend.database.repositories.chat_repository import (
    guardar_mensaje,
    obtener_historial_reciente,
    limpiar_historial,
)

router = APIRouter(prefix="/asistente", tags=["Asistente General"])


@router.post("/mensaje", response_model=MensajeResponse)
def enviar_mensaje(
    payload: MensajeRequest,
    current_user = Depends(get_current_user),
):
    """
    Envía un mensaje al asistente nutricional personal.
    El asistente recuerda conversaciones anteriores y conoce
    tu perfil, plan y restricciones clínicas activas.
    """
    if not payload.mensaje.strip():
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")

    user_id = current_user.id

    with SessionLocal() as db:
        # Cargar todo el contexto del usuario
        perfil = obtener_perfil(db, user_id=user_id)
        if perfil is None:
            raise HTTPException(
                status_code=404,
                detail="Completa tu perfil antes de usar el asistente"
            )

        plan = obtener_plan_activo(db, user_id=user_id)
        protocolo = obtener_protocolo(db, user_id=user_id)
        historial_db = obtener_historial_reciente(
            db, user_id=user_id, limite=AssistantAgent.MAX_HISTORIAL
        )

        # Convertir objetos ORM a dicts simples antes de cerrar la sesión
        perfil_dict = {
            "nombre": perfil.usuario.nombre if perfil.usuario else "usuario",
            "edad": perfil.edad,
            "sexo": perfil.sexo,
            "peso_kg": perfil.peso_kg,
            "altura_cm": perfil.altura_cm,
            "objetivo_principal": perfil.objetivo_principal.value if perfil.objetivo_principal else "-",
            "nivel_actividad": perfil.nivel_actividad.value if perfil.nivel_actividad else "-",
            "tipo_entrenamiento": perfil.tipo_entrenamiento.value if perfil.tipo_entrenamiento else "-",
            "dias_entrenamiento": perfil.dias_entrenamiento,
            "dieta_tipo": perfil.dieta_tipo.value if perfil.dieta_tipo else "-",
            "alergias": perfil.alergias or [],
            "patologias": perfil.patologias or [],
        }

        plan_dict = None
        if plan:
            plan_dict = {
                "calorias_objetivo": plan.calorias_objetivo,
                "proteinas_g": plan.proteinas_g,
                "carbos_g": plan.carbos_g,
                "grasas_g": plan.grasas_g,
            }

        protocolo_dict = None
        if protocolo:
            protocolo_dict = {
                "notas_dietista": protocolo.notas_dietista,
                "restricciones": protocolo.restricciones or [],
            }

        historial = [
            {"rol": m.rol, "contenido": m.contenido}
            for m in historial_db
        ]

    # Llamar al agente (fuera del with para no tener la sesión abierta)
    agente = AssistantAgent()
    respuesta = agente.responder(
        mensaje_usuario=payload.mensaje,
        perfil=perfil_dict,
        plan_activo=plan_dict,
        protocolo=protocolo_dict,
        historial=historial,
    )

    # Guardar el intercambio en el historial persistente
    with SessionLocal() as db:
        guardar_mensaje(db, user_id=user_id, rol="user", contenido=payload.mensaje)
        guardar_mensaje(db, user_id=user_id, rol="assistant", contenido=respuesta)

    return MensajeResponse(respuesta=respuesta, user_id=user_id)


@router.get("/historial", response_model=HistorialResponse)
def obtener_historial(
    limite: int = 20,
    current_user = Depends(get_current_user),
):
    """Devuelve el historial de conversación del usuario."""
    with SessionLocal() as db:
        mensajes_db = obtener_historial_reciente(
            db, user_id=current_user.id, limite=limite
        )
        mensajes = [
            MensajeHistorial(
                rol=m.rol,
                contenido=m.contenido,
                fecha=m.fecha,
            )
            for m in mensajes_db
        ]

    return HistorialResponse(mensajes=mensajes, total=len(mensajes))


@router.delete("/historial")
def borrar_historial(current_user = Depends(get_current_user)):
    """Borra todo el historial de conversación del usuario."""
    with SessionLocal() as db:
        borrados = limpiar_historial(db, user_id=current_user.id)

    return {"mensaje": f"Historial borrado — {borrados} mensajes eliminados"}
