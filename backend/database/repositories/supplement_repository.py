"""
supplement_repository.py
--------------------------
Operaciones CRUD para RecomendacionSuplementos.
"""

from sqlalchemy.orm import Session
from backend.database.models import RecomendacionSuplementos


def guardar_recomendacion(
    db: Session, user_id: int, recomendacion: dict
) -> RecomendacionSuplementos:
    """
    Crea o reemplaza la recomendación de suplementación del usuario.
    (1 usuario → 1 recomendación activa, se sobreescribe siempre)
    """
    existente = (
        db.query(RecomendacionSuplementos)
        .filter(RecomendacionSuplementos.user_id == user_id)
        .first()
    )

    if existente:
        db.delete(existente)
        db.flush()

    nueva = RecomendacionSuplementos(
        user_id=user_id,
        suplementos_necesarios=recomendacion.get("suplementos_necesarios", []),
        suplementos_opcionales=recomendacion.get("suplementos_opcionales", []),
        suplementos_innecesarios=recomendacion.get("suplementos_innecesarios", []),
        notas=recomendacion.get("notas", ""),
        resumen=recomendacion.get("resumen"),
    )

    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return nueva


def obtener_recomendacion(
    db: Session, user_id: int
) -> RecomendacionSuplementos | None:
    """Recupera la recomendación activa del usuario, o None si no existe."""
    return (
        db.query(RecomendacionSuplementos)
        .filter(RecomendacionSuplementos.user_id == user_id)
        .first()
    )
