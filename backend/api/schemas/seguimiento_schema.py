from pydantic import BaseModel
from typing import Optional, Dict, Any

class SeguimientoMensajeRequest(BaseModel):
    mensaje: str

class SeguimientoResponse(BaseModel):
    respuesta: str
    accion: Optional[str] = None
    datos: Optional[Dict[str, Any]] = None
    tarea_id: Optional[str] = None
