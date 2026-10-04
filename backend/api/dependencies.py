import uuid
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.agents.profile_agent import ProfileAgent
from backend.agents.followup_agent import FollowupAgent
from backend.database.connection import SessionLocal
from backend.database.models import User
from backend.utils.security import verificar_token_acceso
from backend.utils.exceptions import SesionNoEncontradaError

# Diccionario en memoria — vive mientras el servidor esté corriendo.
# Clave: user_id (int) → Valor: instancia de ProfileAgent
sesiones_chat: dict[str, dict] = {}


def crear_sesion_chat(user_id: int) -> tuple[str, ProfileAgent]:
    """
    Crea una nueva sesión de chat asociada al usuario.
    Devuelve el session_id y el agente.
    """
    session_id = str(uuid.uuid4())
    agente = ProfileAgent()

    sesiones_chat[session_id] = {
        "user_id": user_id,
        "agent": agente,
    }

    return session_id, agente


def obtener_sesion_chat(session_id: str, user_id: int) -> ProfileAgent:
    """
    Recupera una sesión comprobando que pertenece al usuario autenticado.
    """
    sesion = sesiones_chat.get(session_id)

    if sesion is None:
        raise SesionNoEncontradaError(
            f"La sesión '{session_id}' no existe o ha expirado."
        )

    if sesion["user_id"] != user_id:
        raise SesionNoEncontradaError(
            "La sesión no pertenece al usuario autenticado."
        )

    return sesion["agent"]


def eliminar_sesion_chat(session_id: str) -> None:
    """Elimina una sesión terminada."""
    sesiones_chat.pop(session_id, None)



# ── Tareas de generación de plan (NUEVO) ─────────────────────────────────
tareas_planes: dict[str, dict] = {}
# Estructura de cada tarea:
# {
#     "estado": "iniciado" | "generando" | "completado" | "error",
#     "progreso": 0-100,
#     "dia_actual": str | None,
#     "user_id": int | None,
#     "plan_id": int | None,
#     "error": str | None,
# }


def crear_tarea_plan() -> str:
    """Crea una nueva tarea de generación y devuelve su id."""
    tarea_id = str(uuid.uuid4())
    tareas_planes[tarea_id] = {
        "estado": "iniciado",
        "progreso": 0,
        "dia_actual": None,
        "user_id": None,
        "plan_id": None,
        "error": None,
    }
    return tarea_id


def actualizar_tarea_plan(tarea_id: str, **cambios) -> None:
    """Actualiza campos de una tarea existente."""
    if tarea_id in tareas_planes:
        tareas_planes[tarea_id].update(cambios)


def obtener_tarea_plan(tarea_id: str) -> Optional[dict]:
    """Recupera el estado actual de una tarea."""
    return tareas_planes.get(tarea_id)


# ── Middleware / Dependencias de Autenticación ───────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


from fastapi import Query

def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    token_query: Optional[str] = Query(None, alias="token"),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependencia para obtener el usuario autenticado a partir del JWT.
    Lanza HTTP 401 si no hay token o es inválido.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autorizado o token inválido/expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    actual_token = token or token_query
    if not actual_token:
        raise credentials_exception

    user_id_str = verificar_token_acceso(actual_token)
    if user_id_str is None:
        raise credentials_exception

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise credentials_exception

    usuario = db.query(User).filter(User.id == user_id).first()
    if usuario is None:
        raise credentials_exception

    return usuario


# ── Sesiones de Chat de Seguimiento Semanal (Fase 2.2) ───────────────────
sesiones_seguimiento: dict[int, FollowupAgent] = {}


def crear_sesion_seguimiento(user_id: int, perfil_data: dict, plan_data: dict) -> FollowupAgent:
    """Crea una sesión de chat de seguimiento fresca."""
    agente = FollowupAgent(perfil_data=perfil_data, plan_data=plan_data)
    sesiones_seguimiento[user_id] = agente
    return agente


def obtener_sesion_seguimiento(user_id: int, perfil_data: dict, plan_data: dict) -> FollowupAgent:
    """Recupera la sesión de seguimiento activa."""
    if user_id not in sesiones_seguimiento:
        raise SesionNoEncontradaError(f"Sesión de seguimiento para el usuario '{user_id}' no encontrada o expirada. Por favor, inicie la sesión de seguimiento primero.")
    return sesiones_seguimiento[user_id]


def eliminar_sesion_seguimiento(user_id: int) -> None:
    """Elimina la sesión de seguimiento activa."""
    sesiones_seguimiento.pop(user_id, None)

