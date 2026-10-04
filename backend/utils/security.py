from datetime import datetime, timedelta, timezone
import secrets
from typing import Optional, Union, Any
import bcrypt
from jose import jwt, JWTError
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from backend.config import jwt_secret_key, jwt_algorithm, jwt_expire_minutes, google_client_id


def crear_token_refresco() -> str:
    """Genera un token de refresco aleatorio y criptográficamente seguro."""
    return secrets.token_hex(32)


def obtener_hash_password(password: str) -> str:
    """Genera el hash bcrypt de una contraseña."""
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')


def verificar_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si una contraseña en texto plano coincide con el hash guardado."""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False


def crear_token_acceso(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Genera un token JWT firmado.
    Por defecto expira según la configuración de la app o el delta provisto.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=jwt_expire_minutes)

    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, jwt_secret_key, algorithm=jwt_algorithm)
    return encoded_jwt


def verificar_token_acceso(token: str) -> Optional[str]:
    """
    Verifica un token JWT.
    Si es válido y no ha expirado, devuelve el subject ('sub'),
    de lo contrario devuelve None.
    """
    try:
        payload = jwt.decode(token, jwt_secret_key, algorithms=[jwt_algorithm])
        subject: str = payload.get("sub")
        if subject is None:
            return None
        return subject
    except JWTError:
        return None


def verificar_google_token(token: str) -> Optional[dict]:
    """
    Valida un ID Token recibido desde el cliente de Google.
    Devuelve la información del usuario (dict) si es válido, de lo contrario None.
    """
    try:
        id_info = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            google_client_id
        )
        
        # Validar el emisor
        if id_info["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
            return None
            
        return id_info
    except Exception:
        return None
