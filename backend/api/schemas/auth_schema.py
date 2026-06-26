from pydantic import BaseModel, EmailStr
from typing import Optional


class RegistroRequest(BaseModel):
    nombre: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleLoginRequest(BaseModel):
    token: str  # El ID Token enviado por el frontend


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: int
    nombre: str
    email: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str

