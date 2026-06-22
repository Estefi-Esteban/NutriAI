from sqlalchemy.orm import Session
from backend.database.models import ProtocoloNutricional


def guardar_protocolo(db: Session, user_id: int, protocolo: dict) -> ProtocoloNutricional:
    """Crea o actualiza el protocolo nutricional activo del usuario."""
    existente = db.query(ProtocoloNutricional).filter(
        ProtocoloNutricional.user_id == user_id
    ).first()

    if existente:
        db.delete(existente)
        db.flush()

    nuevo = ProtocoloNutricional(
        user_id=user_id,
        patologias_activas=protocolo.get("patologias_identificadas", []),
        restricciones=protocolo.get("restricciones", []),
        alimentos_prohibidos=protocolo.get("alimentos_prohibidos", []),
        alimentos_prioritarios=protocolo.get("alimentos_prioritarios", []),
        notas_dietista=protocolo.get("notas_dietista", ""),
    )

    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


def obtener_protocolo(db: Session, user_id: int) -> ProtocoloNutricional | None:
    """Recupera el protocolo activo de un usuario."""
    return db.query(ProtocoloNutricional).filter(
        ProtocoloNutricional.user_id == user_id
    ).first()
