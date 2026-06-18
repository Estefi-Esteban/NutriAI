from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from backend.api.schemas.seguimiento_schema import SeguimientoMensajeRequest, SeguimientoResponse
from backend.api.dependencies import (
    get_current_user,
    get_db,
    crear_sesion_seguimiento,
    obtener_sesion_seguimiento,
    eliminar_sesion_seguimiento,
    crear_tarea_plan,
)
from backend.api.services.plan_service import generar_plan_background
from backend.database.connection import SessionLocal
from backend.database.models import User
from backend.database.repositories.user_repository import obtener_perfil, guardar_perfil
from backend.database.repositories.plan_repository import obtener_plan_activo

router = APIRouter(prefix="/chat/seguimiento", tags=["Seguimiento Semanal"])


def _obtener_contexto_usuario(db: Session, user: User) -> tuple[dict, dict]:
    """Recupera y formatea el perfil y el plan activo del usuario en formato dict."""
    perfil = obtener_perfil(db, user_id=user.id)
    if perfil is None:
        raise HTTPException(
            status_code=404,
            detail="No tienes un perfil creado todavía. Completa el chat de perfil primero."
        )

    plan = obtener_plan_activo(db, user_id=user.id)
    if plan is None:
        raise HTTPException(
            status_code=404,
            detail="No tienes un plan activo generado. Genera uno primero."
        )

    perfil_data = {
        "nombre": user.nombre,
        "email": user.email,
        "edad": perfil.edad,
        "sexo": perfil.sexo,
        "peso_kg": perfil.peso_kg,
        "altura_cm": perfil.altura_cm,
        "porcentaje_grasa": perfil.porcentaje_grasa,
        "objetivo_principal": perfil.objetivo_principal.value if perfil.objetivo_principal else "",
        "objetivo_secundario": perfil.objetivo_secundario,
        "velocidad_objetivo": perfil.velocidad_objetivo.value if perfil.velocidad_objetivo else None,
        "nivel_actividad": perfil.nivel_actividad.value if perfil.nivel_actividad else "",
        "dias_entrenamiento": perfil.dias_entrenamiento,
        "tipo_entrenamiento": perfil.tipo_entrenamiento.value if perfil.tipo_entrenamiento else "",
        "dieta_tipo": perfil.dieta_tipo.value if perfil.dieta_tipo else "",
        "alergias": perfil.alergias or [],
        "intolerancias": perfil.intolerancias or [],
        "tiempo_cocina_min": perfil.tiempo_cocina_min,
        "personas_en_casa": perfil.personas_en_casa,
        "presupuesto_semanal": perfil.presupuesto_semanal,
        "patologias": perfil.patologias or [],
        "medicacion": perfil.medicacion,
    }

    plan_data = {
        "calorias_objetivo": plan.calorias_objetivo,
        "proteinas_g": plan.proteinas_g,
        "carbos_g": plan.carbos_g,
        "grasas_g": plan.grasas_g,
        "plan_semanal": plan.plan_semanal,
    }

    return perfil_data, plan_data


@router.post("/iniciar", response_model=SeguimientoResponse)
def iniciar_seguimiento(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Inicializa la sesión de seguimiento semanal cargando el contexto del usuario."""
    perfil_data, plan_data = _obtener_contexto_usuario(db, current_user)

    # Crear agente conversacional en memoria
    agent = crear_sesion_seguimiento(current_user.id, perfil_data, plan_data)
    
    # Saludo inicial automático del agente de seguimiento
    resultado = agent.chat("Hola")
    
    return SeguimientoResponse(respuesta=resultado["respuesta"])


@router.post("/mensaje", response_model=SeguimientoResponse)
def mensaje_seguimiento(
    payload: SeguimientoMensajeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Envía un mensaje al agente de seguimiento y ejecuta acciones de base de datos si son solicitadas."""
    perfil_data, plan_data = _obtener_contexto_usuario(db, current_user)
    
    # Recuperar o instanciar el agente de seguimiento
    agent = obtener_sesion_seguimiento(current_user.id, perfil_data, plan_data)
    
    # Conversar con el agente
    resultado = agent.chat(payload.mensaje)
    
    accion = resultado.get("accion")
    datos = resultado.get("datos")
    tarea_id = None
    
    # Procesar acciones si existen
    if accion == "actualizar_perfil" and datos:
        with SessionLocal() as db_session:
            datos_completos = {**perfil_data, **datos}
            guardar_perfil(db_session, user_id=current_user.id, datos=datos_completos)
            
    elif accion == "modificar_comida" and datos:
        dia = datos.get("dia")
        comida = datos.get("comida")
        nueva_comida = datos.get("nueva_comida")
        
        with SessionLocal() as db_session:
            plan = obtener_plan_activo(db_session, user_id=current_user.id)
            if plan:
                # Realizar una copia profunda para modificar el JSON mutable
                plan_semanal_copy = dict(plan.plan_semanal)
                if dia in plan_semanal_copy:
                    if "comidas" in plan_semanal_copy[dia]:
                        plan_semanal_copy[dia]["comidas"][comida] = nueva_comida
                        
                        # Recalcular totales diarios de calorías y macros
                        comidas_dia = plan_semanal_copy[dia]["comidas"]
                        totales = {
                            "calorias": 0.0,
                            "proteinas_g": 0.0,
                            "carbos_g": 0.0,
                            "grasas_g": 0.0
                        }
                        for c_key, c_val in comidas_dia.items():
                            if isinstance(c_val, dict):
                                totales["calorias"] += c_val.get("calorias") or 0.0
                                totales["proteinas_g"] += c_val.get("proteinas_g") or 0.0
                                totales["carbos_g"] += c_val.get("carbos_g") or 0.0
                                totales["grasas_g"] += c_val.get("grasas_g") or 0.0
                                
                        # Redondear a un decimal
                        for k in totales:
                            totales[k] = round(totales[k], 1)
                        plan_semanal_copy[dia]["totales_dia"] = totales
                        
                plan.plan_semanal = plan_semanal_copy
                flag_modified(plan, "plan_semanal")
                db_session.commit()
                
    elif accion == "regenerar_plan":
        # Creamos una tarea de segundo plano para regenerar
        tarea_id = crear_tarea_plan()
        background_tasks.add_task(
            generar_plan_background,
            tarea_id=tarea_id,
            perfil=perfil_data, # Usa el perfil actual cargado
            user_id=current_user.id
        )
        # Limpiar la sesión de chat tras solicitar regenerar para que empiece de cero la próxima vez
        eliminar_sesion_seguimiento(current_user.id)

    return SeguimientoResponse(
        respuesta=resultado["respuesta"],
        accion=accion,
        datos=datos,
        tarea_id=tarea_id
    )
