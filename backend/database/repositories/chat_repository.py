from sqlalchemy.orm import Session
from sqlalchemy import desc
from backend.database.models import ChatMessage


def guardar_mensaje(
    db: Session, user_id: int, rol: str, contenido: str
) -> ChatMessage:
    """Guarda un mensaje en el historial persistente."""
    mensaje = ChatMessage(
        user_id=user_id,
        rol=rol,
        contenido=contenido,
    )
    db.add(mensaje)
    db.commit()
    db.refresh(mensaje)
    return mensaje


def obtener_historial_reciente(
    db: Session, user_id: int, limite: int = 10
) -> list[ChatMessage]:
    """
    Recupera los últimos N mensajes del usuario, en orden cronológico.
    Limite por defecto: 10 (5 intercambios usuario-asistente).
    """
    mensajes = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user_id)
        .order_by(desc(ChatMessage.fecha))
        .limit(limite)
        .all()
    )
    # Invertimos para tener orden cronológico (más antiguo primero)
    return list(reversed(mensajes))


def limpiar_historial(db: Session, user_id: int) -> int:
    """Borra todo el historial de chat de un usuario. Devuelve nº de mensajes borrados."""
    borrados = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user_id)
        .delete()
    )
    db.commit()
    return borrados
