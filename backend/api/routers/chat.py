from fastapi import APIRouter, HTTPException, Depends

from backend.api.schemas.chat_schema import (
    IniciarChatResponse,
    MensajeChatRequest,
    MensajeChatResponse,
)
from backend.api.dependencies import (
    crear_sesion_chat,
    obtener_sesion_chat,
    eliminar_sesion_chat,
    get_current_user,
)
from backend.database.models import User

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/iniciar", response_model=IniciarChatResponse)
def iniciar_chat(current_user: User = Depends(get_current_user)):
    """
    Inicia una nueva conversación con el Agente Perfil para el usuario autenticado.
    Devuelve un session_id (que es el ID del usuario como string).
    """
    agente = crear_sesion_chat(current_user.id)

    # El agente saluda primero, igual que en el test_agent.py
    resultado = agente.chat("Hola")

    return IniciarChatResponse(
        session_id=str(current_user.id),
        respuesta=resultado["respuesta"],
    )


@router.post("/mensaje", response_model=MensajeChatResponse)
def enviar_mensaje(payload: MensajeChatRequest, current_user: User = Depends(get_current_user)):
    """
    Envía un mensaje a la sesión de chat activa del usuario autenticado.
    Cuando el perfil queda completo, la respuesta incluye
    perfil_completo=true y los datos extraídos.
    """
    agente = obtener_sesion_chat(current_user.id)

    resultado = agente.chat(payload.mensaje)

    # Si el perfil se completó, podemos limpiar la sesión de memoria
    if resultado["perfil_completo"]:
        eliminar_sesion_chat(current_user.id)

    return MensajeChatResponse(
        respuesta=resultado["respuesta"],
        perfil_completo=resultado["perfil_completo"],
        datos=resultado["datos"],
    )
