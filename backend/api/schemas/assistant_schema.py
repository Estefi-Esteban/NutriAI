from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class MensajeRequest(BaseModel):
    mensaje: str


class MensajeResponse(BaseModel):
    respuesta: str
    user_id: int


class MensajeHistorial(BaseModel):
    rol: str
    contenido: str
    fecha: datetime


class HistorialResponse(BaseModel):
    mensajes: list[MensajeHistorial]
    total: int
