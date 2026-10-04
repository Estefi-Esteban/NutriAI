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
    if not valor:
        return "mantenimiento"

    v = str(valor).lower().strip()

    valores_validos = {
        "perder_grasa",
        "ganar_musculo",
        "recomposicion_corporal",
        "mantenimiento",
        "volumen",
    }

    if v in valores_validos:
        return v

    raise ValueError(
        f"Objetivo principal no válido: '{valor}'. "
        f"Valores permitidos: {sorted(valores_validos)}"
    )


def _normalizar_dieta(valor: str) -> str:
    valores_validos = {
        "omnivoro",
        "vegetariano",
        "vegano",
        "sin_gluten",
        "cetogenica",
        "paleo",
        "otro",
    }

    if not valor:
        raise ValueError("dieta_tipo es obligatorio")

    v = str(valor).lower().strip()

    if v not in valores_validos:
        raise ValueError(
            f"Tipo de dieta no válido: '{valor}'. "
            f"Valores permitidos: {sorted(valores_validos)}"
        )

    return v


def _normalizar_actividad(valor: str) -> str:
    valores_validos = {
        "sedentario",
        "ligero",
        "moderado",
        "activo",
        "muy_activo",
    }

    if not valor:
        raise ValueError("nivel_actividad es obligatorio")

    v = str(valor).lower().strip()

    if v not in valores_validos:
        raise ValueError(
            f"Nivel de actividad no válido: '{valor}'. "
            f"Valores permitidos: {sorted(valores_validos)}"
        )

    return v

def _normalizar_tipo_entrenamiento(valor: str) -> str:
    valores_validos = {
        "fuerza",
        "cardio",
        "mixto",
        "ninguno",
    }

    if not valor:
        raise ValueError("tipo_entrenamiento es obligatorio")

    v = str(valor).lower().strip()

    if v not in valores_validos:
        raise ValueError(
            f"Tipo de entrenamiento no válido: '{valor}'. "
            f"Valores permitidos: {sorted(valores_validos)}"
        )

    return v


def _normalizar_velocidad(valor: str | None) -> str | None:
    if not valor:
        return None

    v = str(valor).lower().strip()

    equivalencias = {
        "lento": "lento",
        "lenta": "lento",

        "moderado": "moderado",
        "moderada": "moderado",

        "rapido": "rapido",
        "rápido": "rapido",
        "rapida": "rapido",
        "rápida": "rapido",
    }

    if v in equivalencias:
        return equivalencias[v]

    raise ValueError(
        f"Velocidad de objetivo no reconocida: '{valor}'."
    )

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
    Crea o actualiza el perfil de un usuario.
    """

    perfil = (
        db.query(UserProfile)
        .filter(UserProfile.user_id == user_id)
        .first()
    )

    if perfil is None:
        perfil = UserProfile(user_id=user_id)
        db.add(perfil)

    perfil.peso_kg = float(datos["peso_kg"])
    perfil.altura_cm = float(datos["altura_cm"])
    perfil.edad = int(datos["edad"])
    perfil.sexo = datos["sexo"]

    porcentaje_grasa = datos.get("porcentaje_grasa")
    perfil.porcentaje_grasa = (
        float(porcentaje_grasa)
        if porcentaje_grasa is not None
        else None
    )

    perfil.objetivo_principal = _to_enum(
        ObjetivoPrincipal,
        _normalizar_objetivo(datos["objetivo_principal"])
    )

    perfil.objetivo_secundario = datos.get("objetivo_secundario")

    velocidad = datos.get("velocidad_objetivo")
    perfil.velocidad_objetivo = (
        _to_enum(VelocidadObjetivo, velocidad)
        if velocidad
        else None
    )

    perfil.nivel_actividad = _to_enum(
        NivelActividad,
        _normalizar_actividad(
            datos.get("nivel_actividad", "")
        )
    )

    perfil.dias_entrenamiento = int(
        datos.get("dias_entrenamiento") or 0
    )

    perfil.tipo_entrenamiento = _to_enum(
        TipoEntrenamiento,
        _normalizar_tipo_entrenamiento(
            datos.get("tipo_entrenamiento", "")
        )
    )

    perfil.dieta_tipo = _to_enum(
        DietaTipo,
        _normalizar_dieta(
            datos.get("dieta_tipo", "")
        )
    )

    perfil.alergias = datos.get("alergias", [])
    perfil.intolerancias = datos.get("intolerancias", [])

    presupuesto = datos.get("presupuesto_semanal")
    perfil.presupuesto_semanal = (
        float(presupuesto)
        if presupuesto is not None
        else None
    )

    perfil.tiempo_cocina_min = int(
        datos["tiempo_cocina_min"]
    )

    perfil.personas_en_casa = int(
        datos.get("personas_en_casa") or 1
    )

    perfil.medicacion = datos.get("medicacion")
    perfil.patologias = datos.get("patologias", [])

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

