import time
import threading
from typing import Optional
from fastapi import Request, HTTPException, Depends, status

from backend.database.models import User
from backend.api.dependencies import get_current_user

# Bloqueos en memoria
_lock = threading.Lock()

# Estructura: "ip:X.X.X.X" o "email:ejemplo@correo.com" -> [timestamp1, timestamp2, ...]
_failed_logins: dict[str, list[float]] = {}

# Estructura: user_id (int) -> [timestamp1, timestamp2, ...]
_ai_requests: dict[int, list[float]] = {}

# Parámetros de Configuración
FAILED_LOGIN_LIMIT = 5
FAILED_LOGIN_WINDOW = 900  # 15 minutos en segundos
AI_REQUEST_LIMIT = 30
AI_REQUEST_WINDOW = 60    # 1 minuto en segundos


def check_failed_login(ip: str, email: str):
    """
    Verifica si una IP o un correo electrónico específico están bloqueados
    debido a demasiados intentos de inicio de sesión fallidos.
    Lanza HTTPException con código 429 si están bloqueados.
    """
    ahora = time.time()
    
    with _lock:
        for key in (f"ip:{ip}", f"email:{email}"):
            if key in _failed_logins:
                # Filtrar intentos fuera de la ventana de 15 minutos
                intentos = [t for t in _failed_logins[key] if ahora - t < FAILED_LOGIN_WINDOW]
                _failed_logins[key] = intentos
                
                if len(intentos) >= FAILED_LOGIN_LIMIT:
                    tiempo_transcurrido = ahora - intentos[0]
                    tiempo_restante = max(0.0, FAILED_LOGIN_WINDOW - tiempo_transcurrido)
                    minutos_restantes = int(tiempo_restante // 60) + 1
                    
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Demasiados intentos de inicio de sesión fallidos. Bloqueado temporalmente. Reintenta en {minutos_restantes} minuto(s)."
                    )


def add_failed_attempt(ip: str, email: str):
    """Registra un intento fallido de inicio de sesión para la IP y el email."""
    ahora = time.time()
    with _lock:
        for key in (f"ip:{ip}", f"email:{email}"):
            if key not in _failed_logins:
                _failed_logins[key] = []
            _failed_logins[key].append(ahora)


def reset_failed_attempts(ip: str, email: str):
    """Limpia el registro de intentos fallidos al iniciar sesión con éxito."""
    with _lock:
        for key in (f"ip:{ip}", f"email:{email}"):
            _failed_logins.pop(key, None)


def limitar_peticiones_ia(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependencia de FastAPI para limitar la tasa de peticiones en endpoints de IA.
    Máximo 10 peticiones por minuto por usuario.
    """
    ahora = time.time()
    user_id = current_user.id
    
    with _lock:
        if user_id not in _ai_requests:
            _ai_requests[user_id] = []
            
        # Filtrar peticiones fuera de la ventana de 1 minuto
        peticiones = [t for t in _ai_requests[user_id] if ahora - t < AI_REQUEST_WINDOW]
        _ai_requests[user_id] = peticiones
        
        if len(peticiones) >= AI_REQUEST_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Límite de solicitudes de IA excedido (máximo 10 por minuto). Por favor, espera un momento."
            )
            
        _ai_requests[user_id].append(ahora)
        
    return current_user
