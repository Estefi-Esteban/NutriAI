"""
user_repository.py
------------------
Capa de acceso a datos para usuarios y sus perfiles.
Todas las operaciones de BD relacionadas con 'users' y 'user_profiles'
pasan por aquí, manteniendo el resto del código limpio de SQL.
"""

from sqlalchemy.orm import Session

from backend.database.models import (
    User,
    UserProfile,
    ObjetivoPrincipal,
    VelocidadObjetivo,
    NivelActividad,
    TipoEntrenamiento,
    DietaTipo,
)


# ---------------------------------------------------------------------------
# Helpers de conversión Enum
# ---------------------------------------------------------------------------

def _to_enum(enum_class, value):
    """
    Convierte un string al Enum correspondiente.
    Si el valor ya es del tipo correcto lo devuelve tal cual.
    Lanza ValueError si el string no coincide con ningún miembro.
    
    Ejemplo:
        _to_enum(ObjetivoPrincipal, "ganar_musculo")
        → ObjetivoPrincipal.ganar_musculo
    """
    if isinstance(value, enum_class):
        return value
    try:
        return enum_class(value)
    except ValueError:
        miembros_validos = [e.value for e in enum_class]
        raise ValueError(
            f"Valor '{value}' no válido para {enum_class.__name__}. "
            f"Opciones: {miembros_validos}"
        )


def _normalizar_objetivo(valor: str) -> str:
    """
    Convierte el texto libre del agente al valor exacto del Enum ObjetivoPrincipal.
    """
    if not valor:
        return "mantenimiento"
    v = valor.lower().strip()

    tiene_perder = any(x in v for x in ["perder", "adelgaz", "bajar", "reducir grasa"])
    tiene_musculo = any(x in v for x in ["ganar", "musculo", "músculo", "masa muscular"])

    if tiene_perder and tiene_musculo:
        return "recomposicion_corporal"
    if any(x in v for x in ["recomposic"]):
        return "recomposicion_corporal"
    if tiene_perder:
        return "perder_grasa"
    if tiene_musculo:
        return "ganar_musculo"
    if any(x in v for x in ["volumen", "bulk", "voluminiz"]):
        return "volumen"
    if any(x in v for x in ["mantener", "mantenimiento", "salud"]):
        return "mantenimiento"

    return "mantenimiento"  # default seguro


def _normalizar_dieta(valor: str) -> str:
    """
    Convierte el texto libre del agente al valor exacto del Enum DietaTipo.
    """
    if not valor:
        return "omnivoro"
    v = valor.lower().strip()

    if any(x in v for x in ["vegano", "vegan"]):
        return "vegano"
    if "vegetariano" in v:
        return "vegetariano"
    if any(x in v for x in ["gluten"]):
        return "sin_gluten"
    if any(x in v for x in ["cetog", "keto"]):
        return "cetogenica"
    if "paleo" in v:
        return "paleo"

    return "omnivoro"  # default seguro


def _normalizar_actividad(valor: str) -> str:
    """
    Convierte el texto libre del agente al valor exacto del Enum NivelActividad.
    """
    if not valor:
        return "sedentario"
    v = valor.lower().strip()

    if any(x in v for x in ["muy activo", "muy_activo", "intenso", "alta"]):
        return "muy_activo"
    if any(x in v for x in ["activo", "frecuente"]):
        return "activo"
    if any(x in v for x in ["moderado", "media"]):
        return "moderado"
    if any(x in v for x in ["ligero", "leve", "poco"]):
        return "ligero"

    return "sedentario"  # default cuando dice "no hago ejercicio"


def _normalizar_tipo_entrenamiento(valor: str) -> str:
    """
    Convierte el texto libre del agente al valor exacto del Enum TipoEntrenamiento.
    """
    if not valor:
        return "ninguno"
    v = valor.lower().strip()

    if any(x in v for x in ["fuerza", "pesas", "musculaci", "resistencia"]):
        return "fuerza"
    if any(x in v for x in ["cardio", "correr", "aerobic"]):
        return "cardio"
    if any(x in v for x in ["mixto", "combinado", "funcional"]):
        return "mixto"

    return "ninguno"


# ---------------------------------------------------------------------------
# crear_usuario
# ---------------------------------------------------------------------------

def crear_usuario(
    db: Session,
    nombre: str,
    email: str,
    password_hash: str = None,
    google_id: str = None,
    auth_provider: str = "email"
) -> User:
    """
    Crea un nuevo registro en la tabla 'users'.

    Parámetros:
        db            — sesión SQLAlchemy activa
        nombre        — nombre del usuario
        email         — email único del usuario
        password_hash — hash bcrypt de la contraseña (si es registro tradicional)
        google_id     — ID único de Google (si es login con Google)
        auth_provider — Proveedor de autenticación ('email' o 'google')

    Devuelve:
        El objeto User recién creado con su id asignado por la BD.
    """
    usuario = User(
        nombre=nombre,
        email=email,
        password_hash=password_hash,
        google_id=google_id,
        auth_provider=auth_provider
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


# ---------------------------------------------------------------------------
# guardar_perfil
# ---------------------------------------------------------------------------

def guardar_perfil(db: Session, user_id: int, datos: dict) -> UserProfile:
    """
    Crea o actualiza el perfil de un usuario en 'user_profiles'.

    Si ya existe un perfil para ese user_id se reemplaza el registro
    completo (delete + insert) para evitar conflictos de campos parciales.

    Parámetros:
        db      — sesión SQLAlchemy activa
        user_id — id del usuario al que pertenece el perfil
        datos   — dict con los campos devueltos por el agente conversacional

    Devuelve:
        El objeto UserProfile guardado con su id asignado por la BD.

    Conversión de Enums:
        Los campos objetivo_principal, velocidad_objetivo, nivel_actividad,
        tipo_entrenamiento y dieta_tipo llegan como strings desde el agente
        y se convierten al Enum correcto antes de persistirlos.
    """
    # Si ya existe un perfil previo para este usuario, lo borramos primero
    perfil_existente = (
        db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    )
    if perfil_existente:
        db.delete(perfil_existente)
        db.flush()  # ejecuta el DELETE antes del INSERT siguiente

    perfil = UserProfile(
        user_id=user_id,

        # ── Biométricos ─────────────────────────────────────────────────────
        peso_kg=float(datos["peso_kg"]),
        altura_cm=float(datos["altura_cm"]),
        edad=int(datos["edad"]),
        sexo=datos["sexo"],
        porcentaje_grasa=(
            float(datos["porcentaje_grasa"])
            if datos.get("porcentaje_grasa") is not None
            else None
        ),

        # ── Objetivos ───────────────────────────────────────────────────────
        objetivo_principal=_to_enum(
            ObjetivoPrincipal,
            _normalizar_objetivo(datos["objetivo_principal"])
        ),
        objetivo_secundario=datos.get("objetivo_secundario"),
        velocidad_objetivo=(
            _to_enum(VelocidadObjetivo, datos["velocidad_objetivo"])
            if datos.get("velocidad_objetivo")
            else None
        ),

        # ── Actividad ───────────────────────────────────────────────────────
        nivel_actividad=_to_enum(
            NivelActividad,
            _normalizar_actividad(datos.get("nivel_actividad", ""))
        ),
        dias_entrenamiento=int(datos.get("dias_entrenamiento") or 0),
        tipo_entrenamiento=_to_enum(
            TipoEntrenamiento,
            _normalizar_tipo_entrenamiento(datos.get("tipo_entrenamiento", ""))
        ),

        # ── Preferencias ────────────────────────────────────────────────────
        dieta_tipo=_to_enum(
            DietaTipo,
            _normalizar_dieta(datos.get("dieta_tipo", ""))
        ),
        alergias=datos.get("alergias", []),
        intolerancias=datos.get("intolerancias", []),
        presupuesto_semanal=float(datos["presupuesto_semanal"]) if datos.get("presupuesto_semanal") else None,
        tiempo_cocina_min=int(datos["tiempo_cocina_min"]),
        personas_en_casa=int(datos.get("personas_en_casa", 1)),

        # ── Estado de salud ─────────────────────────────────────────────────
        medicacion=datos.get("medicacion"),
        patologias=datos.get("patologias", []),
    )

    db.add(perfil)
    db.commit()
    db.refresh(perfil)
    return perfil


# ---------------------------------------------------------------------------
# obtener_perfil
# ---------------------------------------------------------------------------

def obtener_perfil(db: Session, user_id: int) -> UserProfile | None:
    """
    Recupera el perfil completo de un usuario.

    Parámetros:
        db      — sesión SQLAlchemy activa
        user_id — id del usuario cuyo perfil se quiere obtener

    Devuelve:
        El objeto UserProfile si existe, o None si el usuario no tiene
        perfil guardado todavía.

    Uso típico en los agentes siguientes:
        perfil = obtener_perfil(db, user_id)
        if perfil is None:
            raise ValueError("El usuario no tiene perfil aún")
        calorias = calcular_tdee(perfil)
    """
    return (
        db.query(UserProfile)
        .filter(UserProfile.user_id == user_id)
        .first()
    )
