from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session

from backend.api.schemas.auth_schema import (
    RegistroRequest,
    LoginRequest,
    GoogleLoginRequest,
    TokenResponse,
    RefreshTokenRequest,
)
from backend.database.connection import SessionLocal
from backend.database.models import User, RefreshToken
from backend.database.repositories.user_repository import crear_usuario
from backend.utils.security import (
    obtener_hash_password,
    verificar_password,
    crear_token_acceso,
    crear_token_refresco,
    verificar_google_token,
)
from backend.api.rate_limiter import (
    check_failed_login,
    add_failed_attempt,
    reset_failed_attempts,
)

router = APIRouter(prefix="/auth", tags=["Autenticación"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generar_y_guardar_token_refresco(db: Session, user_id: int) -> str:
    """Genera un nuevo refresh token, lo guarda en la BD y lo retorna."""
    token_str = crear_token_refresco()
    expiracion = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=30)
    db_token = RefreshToken(
        user_id=user_id,
        token=token_str,
        fecha_expiracion=expiracion,
        revocado=False
    )
    db.add(db_token)
    db.commit()
    return token_str


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

    # Generar token de acceso y de refresco
    access_token = crear_token_acceso(subject=usuario.id)
    refresh_token = generar_y_guardar_token_refresco(db, usuario.id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=usuario.id,
        nombre=usuario.nombre,
        email=usuario.email,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Inicia sesión con email y contraseña."""
    ip = request.client.host if request.client else "127.0.0.1"
    
    # Verificar si está bloqueado por rate limit
    check_failed_login(ip, payload.email)
    
    usuario = db.query(User).filter(User.email == payload.email).first()
    if not usuario or usuario.auth_provider != "email":
        add_failed_attempt(ip, payload.email)
        raise HTTPException(
            status_code=400,
            detail="Credenciales incorrectas o el usuario inició sesión con otro proveedor"
        )

    # Verificar contraseña
    if not verificar_password(payload.password, usuario.password_hash):
        add_failed_attempt(ip, payload.email)
        raise HTTPException(
            status_code=400,
            detail="Credenciales incorrectas"
        )

    # Login exitoso, resetear intentos fallidos
    reset_failed_attempts(ip, payload.email)

    # Generar tokens
    access_token = crear_token_acceso(subject=usuario.id)
    refresh_token = generar_y_guardar_token_refresco(db, usuario.id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
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

    # Generar token de acceso propio de NutriAI y de refresco
    access_token = crear_token_acceso(subject=usuario.id)
    refresh_token = generar_y_guardar_token_refresco(db, usuario.id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=usuario.id,
        nombre=usuario.nombre,
        email=usuario.email,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Renueva un access token expirado usando un refresh token válido."""
    # 1. Buscar el refresh token en la base de datos
    db_token = db.query(RefreshToken).filter(
        RefreshToken.token == payload.refresh_token,
        RefreshToken.revocado == False
    ).first()

    if not db_token:
        raise HTTPException(
            status_code=401,
            detail="Token de refresco inválido o ya utilizado/revocado"
        )

    # 2. Verificar que no haya expirado
    if db_token.fecha_expiracion < datetime.now(timezone.utc).replace(tzinfo=None):
        db_token.revocado = True
        db.commit()
        raise HTTPException(
            status_code=401,
            detail="Token de refresco expirado"
        )

    # 3. Obtener el usuario
    usuario = db.query(User).filter(User.id == db_token.user_id).first()
    if not usuario:
        raise HTTPException(
            status_code=401,
            detail="Usuario no encontrado"
        )

    # 4. Rotación de tokens: Revocar el token actual
    db_token.revocado = True
    db.commit()

    # 5. Generar nuevos tokens
    nuevo_access = crear_token_acceso(subject=usuario.id)
    nuevo_refresh = generar_y_guardar_token_refresco(db, usuario.id)

    return TokenResponse(
        access_token=nuevo_access,
        refresh_token=nuevo_refresh,
        user_id=usuario.id,
        nombre=usuario.nombre,
        email=usuario.email,
    )


@router.post("/logout")
def logout(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Revoca el refresh token para cerrar sesión activamente."""
    db_token = db.query(RefreshToken).filter(
        RefreshToken.token == payload.refresh_token
    ).first()
    if db_token:
        db_token.revocado = True
        db.commit()
    return {"mensaje": "Sesión cerrada correctamente"}

