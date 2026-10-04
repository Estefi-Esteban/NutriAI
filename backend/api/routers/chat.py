from fastapi import APIRouter, Depends, HTTPException

from backend.api.schemas.chat_schema import (
    IniciarChatResponse,
    MensajeChatRequest,
    MensajeChatResponse,
)
from backend.api.dependencies import (
    crear_sesion_chat,
    obtener_sesion_chat,
    eliminar_sesion_chat,
)
from backend.api.rate_limiter import limitar_peticiones_ia
from backend.database.models import User
from backend.database.connection import SessionLocal
from backend.database.repositories.user_repository import guardar_perfil

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/iniciar", response_model=IniciarChatResponse)
def iniciar_chat(current_user: User = Depends(limitar_peticiones_ia)):
    """
    Inicia una nueva conversación con el agente de perfil.
    """
    session_id, agente = crear_sesion_chat(current_user.id)

    resultado = agente.chat("Hola")

    return IniciarChatResponse(
        session_id=session_id,
        respuesta=resultado["respuesta"],
    )


@router.post("/mensaje", response_model=MensajeChatResponse)
def enviar_mensaje(
    payload: MensajeChatRequest,
    current_user: User = Depends(limitar_peticiones_ia),
):
    """
    Envía un mensaje a la sesión activa del usuario.
    """

    agente = obtener_sesion_chat(
        payload.session_id,
        current_user.id,
    )

    resultado = agente.chat(payload.mensaje)

    if resultado["perfil_completo"]:
        with SessionLocal() as db:
            guardar_perfil(
                db,
                user_id=current_user.id,
                datos=resultado["datos"],
            )

        eliminar_sesion_chat(payload.session_id)

    return MensajeChatResponse(
        respuesta=resultado["respuesta"],
        perfil_completo=resultado["perfil_completo"],
        datos=resultado["datos"],
    )