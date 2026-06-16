from pydantic import BaseModel
from typing import Optional


class IniciarChatResponse(BaseModel):
    """Lo que devolvemos al iniciar una conversación nueva."""
    session_id: str
    respuesta: str


class MensajeChatRequest(BaseModel):
    """Lo que el cliente nos envía en cada mensaje."""
    session_id: str
    mensaje: str


class MensajeChatResponse(BaseModel):
    """Lo que devolvemos tras procesar un mensaje."""
    respuesta: str
    perfil_completo: bool
    datos: Optional[dict] = None
