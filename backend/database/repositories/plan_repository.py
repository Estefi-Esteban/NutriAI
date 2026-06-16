"""
plan_repository.py
------------------
Capa de acceso a datos para planes nutricionales semanales.
Todas las operaciones de BD relacionadas con 'nutrition_plans' pasan por aquí.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.database.models import NutritionPlan


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# guardar_plan
# ---------------------------------------------------------------------------

def guardar_plan(
    db: Session,
    user_id: int,
    calculos: dict,
    menu_semana: dict,
) -> NutritionPlan:
    """
    Guarda un plan nutricional semanal completo en la tabla 'nutrition_plans'.

    Antes de insertar el nuevo plan, desactiva todos los planes anteriores
    del usuario (activo=False) para que solo exista un plan vigente.

    Parámetros:
        db          — sesión SQLAlchemy activa
        user_id     — id del usuario al que pertenece el plan
        calculos    — dict con los resultados del motor nutricional.
                      Debe contener:
                        "calorias_objetivo": float
                        "macros": {"proteinas_g": float, "carbos_g": float, "grasas_g": float}
        menu_semana — dict completo del menú semanal (salida de DietistAgent.generar_semana()).
                      Se guarda íntegro en la columna JSON 'plan_semanal'.

    Devuelve:
        El objeto NutritionPlan recién creado con su id asignado por la BD.

    Ejemplo de uso:
        plan = guardar_plan(
            db=db,
            user_id=1,
            calculos=calculos,
            menu_semana={"Lunes": {...}, "Martes": {...}, ...}
        )
        print(f"Plan guardado con id={plan.id}")
    """
    # 1) Desactivar planes anteriores del usuario
    planes_anteriores = (
        db.query(NutritionPlan)
        .filter(NutritionPlan.user_id == user_id, NutritionPlan.activo == True)
        .all()
    )
    if planes_anteriores:
        logger.info(
            "plan_repository: desactivando %d plan(es) anterior(es) del usuario %d",
            len(planes_anteriores), user_id
        )
        for plan_viejo in planes_anteriores:
            plan_viejo.activo = False
        db.flush()  # aplica los UPDATEs antes del INSERT siguiente

    # 2) Extraer macros del dict de cálculos
    macros = calculos.get("macros", {})

    # 3) Crear el nuevo plan
    plan = NutritionPlan(
        user_id=user_id,
        calorias_objetivo=float(calculos["calorias_objetivo"]),
        proteinas_g=float(macros["proteinas_g"]),
        carbos_g=float(macros["carbos_g"]),
        grasas_g=float(macros["grasas_g"]),
        plan_semanal=menu_semana,
        fecha_generacion=datetime.utcnow(),
        activo=True,
    )

    db.add(plan)
    db.commit()
    db.refresh(plan)

    logger.info(
        "plan_repository: plan id=%d guardado para user_id=%d (%.0f kcal/día)",
        plan.id, user_id, plan.calorias_objetivo
    )
    return plan


# ---------------------------------------------------------------------------
# obtener_plan_activo
# ---------------------------------------------------------------------------

def obtener_plan_activo(db: Session, user_id: int) -> Optional[NutritionPlan]:
    """
    Recupera el plan nutricional activo de un usuario.

    Devuelve:
        El objeto NutritionPlan activo, o None si el usuario no tiene ninguno.
    """
    return (
        db.query(NutritionPlan)
        .filter(NutritionPlan.user_id == user_id, NutritionPlan.activo == True)
        .order_by(NutritionPlan.fecha_generacion.desc())
        .first()
    )


# ---------------------------------------------------------------------------
# listar_planes
# ---------------------------------------------------------------------------

def listar_planes(db: Session, user_id: int) -> list[NutritionPlan]:
    """
    Devuelve todos los planes nutricionales de un usuario, ordenados del más
    reciente al más antiguo (activo o no).

    Útil para mostrar el historial de planes en la UI.
    """
    return (
        db.query(NutritionPlan)
        .filter(NutritionPlan.user_id == user_id)
        .order_by(NutritionPlan.fecha_generacion.desc())
        .all()
    )
