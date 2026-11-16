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
from backend.utils.health_limits import PerfilInvalidoError, PerfilNoAptoError

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/iniciar", response_model=IniciarChatResponse)
def iniciar_chat(current_user: User = Depends(limitar_peticiones_ia)):
    """Inicia una nueva conversación con el agente de perfil."""
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
    """Procesa un mensaje y guarda el perfil cuando está completo y validado.

    Los perfiles no aptos cierran la sesión. Los datos corregibles devuelven
    HTTP 422, pero mantienen la sesión para que el usuario pueda rectificarlos.
    """
    agente = obtener_sesion_chat(payload.session_id, current_user.id)
    resultado = agente.chat(payload.mensaje)

    if resultado["perfil_completo"]:
        try:
            with SessionLocal() as db:
                guardar_perfil(
                    db,
                    user_id=current_user.id,
                    datos=resultado["datos"],
                )
        except PerfilNoAptoError as exc:
            # Perfil completo pero fuera de la política de uso (por ejemplo,
            # una persona menor de edad): no debe continuar esta sesión.
            eliminar_sesion_chat(payload.session_id)
            raise HTTPException(status_code=422, detail=exc.mensaje) from exc
        except PerfilInvalidoError as exc:
            # Datos incorrectos pero corregibles: conservar la sesión activa.
            raise HTTPException(
                status_code=422,
                detail=(
                    "Hay datos del perfil que no son válidos: "
                    + " ".join(exc.problemas)
                ),
            ) from exc

        eliminar_sesion_chat(payload.session_id)

    return MensajeChatResponse(
        respuesta=resultado["respuesta"],
        perfil_completo=resultado["perfil_completo"],
        datos=resultado["datos"],
    )
