"""
exceptions.py
--------------
Excepciones propias de NutriAI. Permiten distinguir errores esperados
del dominio (perfil inválido, sesión no encontrada...) de errores
inesperados de programación, y responder de forma distinta a cada uno.
"""


class NutriAIError(Exception):
    """Excepción base de la que heredan todos los errores del dominio."""
    pass


class AgenteError(NutriAIError):
    """Error al comunicarse con un agente de IA (Groq, parseo de JSON, etc.)."""
    pass


class SesionNoEncontradaError(NutriAIError):
    """La sesión de chat o tarea solicitada no existe o expiró."""
    pass


class PerfilInvalidoError(NutriAIError):
    """Los datos del perfil no cumplen las validaciones necesarias."""
    pass


class RecursoNoEncontradoError(NutriAIError):
    """Un recurso (usuario, plan, perfil) no existe en la base de datos."""
    pass
