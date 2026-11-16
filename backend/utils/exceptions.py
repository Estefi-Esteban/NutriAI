"""
Excepciones propias de NutriAI.
"""


class NutriAIError(Exception):
    """Base para errores esperados del dominio."""


class AgenteError(NutriAIError):
    """Error al comunicarse con un agente de IA."""


class SesionNoEncontradaError(NutriAIError):
    """La sesión solicitada no existe o ha expirado."""


class PerfilInvalidoError(NutriAIError):
    """Los datos del perfil son incorrectos pero corregibles."""

    def __init__(self, problemas: list[str] | tuple[str, ...]):
        self.problemas = tuple(str(problema) for problema in problemas)
        self.mensaje = "El perfil contiene datos no válidos."
        super().__init__(self.mensaje + " " + " ".join(self.problemas))


class PerfilNoAptoError(NutriAIError):
    """El perfil requiere supervisión y no puede recibir el flujo automático."""

    def __init__(self, mensaje: str):
        self.mensaje = mensaje
        super().__init__(mensaje)


class RecursoNoEncontradoError(NutriAIError):
    """Un recurso no existe en la base de datos."""
