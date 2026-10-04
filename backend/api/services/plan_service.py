"""
plan_service.py
----------------
Lógica de generación del plan completo, diseñada para ejecutarse
en segundo plano (BackgroundTasks de FastAPI) y reportar progreso
a través del diccionario de tareas en memoria.
"""

import time
from sqlalchemy.exc import IntegrityError

from backend.utils.nutrition_calculator import calcular_todo
from backend.utils.shopping_list_generator import generar_lista_compra
from backend.agents.nutrition_agent import NutritionAgent
from backend.agents.dietist_agent import DietistAgent, DIAS_SEMANA
from backend.database.connection import SessionLocal
from backend.database.repositories.user_repository import crear_usuario
from backend.database.repositories.plan_repository import guardar_plan  
from backend.database.models import User
from backend.api.dependencies import actualizar_tarea_plan
from backend.database.repositories.protocol_repository import obtener_protocolo

PAUSA_ENTRE_DIAS_SEG = 15


def generar_plan_background(tarea_id: str, perfil: dict, user_id: int) -> None:
    """
    Ejecuta todo el pipeline (cálculo + nutricionista + dietista 7 días + guardado)
    y va actualizando el estado de la tarea en cada paso.

    Diseñada para lanzarse con BackgroundTasks — no devuelve nada directamente,
    el resultado se consulta vía /planes/estado/{tarea_id}.
    """
    try:
        actualizar_tarea_plan(tarea_id, estado="generando", progreso=5)

        # Cargar protocolo de patologías si existe
        with SessionLocal() as db:
            protocolo = obtener_protocolo(db, user_id=user_id)

        if protocolo:
            perfil = {
                    **perfil,
                    "patologias_activas": protocolo.patologias_activas or [],
                    "restricciones_clinicas": protocolo.notas_dietista or "",
                    "restricciones": protocolo.restricciones or [],
                    "alimentos_prohibidos": protocolo.alimentos_prohibidos or [],
                    "alimentos_prioritarios": protocolo.alimentos_prioritarios or [],
                }

            actualizar_tarea_plan(
                tarea_id,
                estado="generando",
                progreso=5,
                dia_actual="Preparando protocolo nutricional"
            )

        # PASO 1 — Cálculos
        calculos = calcular_todo(perfil).to_dict()
        actualizar_tarea_plan(tarea_id, progreso=15)

        # PASO 2 — Nutricionista
        analisis = NutritionAgent().analizar(perfil=perfil, calculos=calculos)
        actualizar_tarea_plan(tarea_id, progreso=25)

        # PASO 3 — Dietista, 7 días
        dietist = DietistAgent()
        menu_semana: dict = {}
        comidas_previas: list[str] = []

        for i, dia in enumerate(DIAS_SEMANA):
            actualizar_tarea_plan(
                tarea_id,
                dia_actual=dia,
                progreso=25 + int(i * 9),
            )

            menu_dia = dietist.generar_dia(
                perfil=perfil,
                calculos=calculos,
                analisis=analisis,
                dia_semana=dia,
                comidas_previas=comidas_previas,
            )
            menu_semana[dia] = menu_dia

            nuevos = [
                v["nombre"] for v in menu_dia.get("comidas", {}).values()
                if isinstance(v, dict) and "nombre" in v
            ]
            comidas_previas.extend(nuevos)

            if i < len(DIAS_SEMANA) - 1:
                time.sleep(PAUSA_ENTRE_DIAS_SEG)

        actualizar_tarea_plan(tarea_id, progreso=90, dia_actual=None)

        # PASO 4 — Lista de la compra (se genera pero no se guarda aquí,
        # se recalcula on-demand en el endpoint de lista de compra)
        generar_lista_compra(menu_semana)

        # PASO 5 — Guardar en Supabase
        with SessionLocal() as db:
            plan = guardar_plan(db, user_id=user_id, calculos=calculos, menu_semana=menu_semana)
            plan_id = int(plan.id)

        actualizar_tarea_plan(
            tarea_id,
            estado="completado",
            progreso=100,
            user_id=user_id,
            plan_id=plan_id,
        )

    except Exception as exc:
        actualizar_tarea_plan(
            tarea_id,
            estado="error",
            error=str(exc),
        )
