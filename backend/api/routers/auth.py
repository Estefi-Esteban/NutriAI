from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from backend.api.schemas.auth_schema import RegistroRequest, LoginRequest, GoogleLoginRequest, TokenResponse
from backend.database.connection import SessionLocal
from backend.database.models import User
from backend.database.repositories.user_repository import crear_usuario
from backend.utils.security import (
    obtener_hash_password,
    verificar_password,
    crear_token_acceso,
    verificar_google_token,
)

router = APIRouter(prefix="/auth", tags=["Autenticación"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/registro", response_model=TokenResponse)
def registro(payload: RegistroRequest, db: Session = Depends(get_db)):
    """Registra un nuevo usuario con email y contraseña."""
    # Verificar si el email ya existe
    existente = db.query(User).filter(User.email == payload.email).first()
    if existente:
        raise HTTPException(
            status_code=400,
            detail="El correo electrónico ya está registrado"
        )

    # Hashear contraseña y crear usuario
    hashed_pwd = obtener_hash_password(payload.password)
    usuario = crear_usuario(
        db,
        nombre=payload.nombre,
        email=payload.email,
        password_hash=hashed_pwd,
        auth_provider="email"
    )

    # Generar token de acceso
    access_token = crear_token_acceso(subject=usuario.id)
    return TokenResponse(
        access_token=access_token,
        user_id=usuario.id,
        nombre=usuario.nombre,
        email=usuario.email,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Inicia sesión con email y contraseña."""
    usuario = db.query(User).filter(User.email == payload.email).first()
    if not usuario or usuario.auth_provider != "email":
        raise HTTPException(
            status_code=400,
            detail="Credenciales incorrectas o el usuario inició sesión con otro proveedor"
        )

    # Verificar contraseña
    if not verificar_password(payload.password, usuario.password_hash):
        raise HTTPException(
            status_code=400,
            detail="Credenciales incorrectas"
        )

    # Generar token
    access_token = crear_token_acceso(subject=usuario.id)
    return TokenResponse(
        access_token=access_token,
        user_id=usuario.id,
        nombre=usuario.nombre,
        email=usuario.email,
    )


@router.post("/google", response_model=TokenResponse)
def login_google(payload: GoogleLoginRequest, db: Session = Depends(get_db)):
    """Inicia sesión o registra un usuario con Google OAuth."""
    # Verificar el token de Google
    id_info = verificar_google_token(payload.token)
    if id_info is None:
        raise HTTPException(
            status_code=400,
            detail="Token de Google inválido o expirado"
        )

    google_id = id_info.get("sub")
    email = id_info.get("email")
    nombre = id_info.get("name", "Usuario Google")

    if not google_id or not email:
        raise HTTPException(
            status_code=400,
            detail="Falta información de identidad de Google"
        )

    # Buscar si ya existe por google_id
    usuario = db.query(User).filter(User.google_id == google_id).first()

    # Si no existe por google_id, buscar por email para enlazar cuentas o crear
    if not usuario:
        usuario_por_email = db.query(User).filter(User.email == email).first()
        if usuario_por_email:
            # Enlazar cuenta existente convirtiéndola/asociándola a Google
            usuario_por_email.google_id = google_id
            usuario_por_email.auth_provider = "google"
            db.commit()
            db.refresh(usuario_por_email)
            usuario = usuario_por_email
        else:
            # Registrar nuevo usuario
            usuario = crear_usuario(
                db,
                nombre=nombre,
                email=email,
                google_id=google_id,
                auth_provider="google"
            )

    # Generar token de acceso propio de NutriAI
    access_token = crear_token_acceso(subject=usuario.id)
    return TokenResponse(
        access_token=access_token,
        user_id=usuario.id,
        nombre=usuario.nombre,
        email=usuario.email,
    )
