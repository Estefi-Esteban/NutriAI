from pydantic import BaseModel, Field
from typing import Optional


class IniciarChatResponse(BaseModel):
    """Respuesta al iniciar una conversación."""
    session_id: str
    respuesta: str


class MensajeChatRequest(BaseModel):
    """Mensaje enviado por el cliente."""
    session_id: str = Field(..., min_length=1)
    mensaje: str = Field(..., min_length=1)


class MensajeChatResponse(BaseModel):
    """Respuesta del agente."""
    respuesta: str
    perfil_completo: bool
    datos: Optional[dict] = None