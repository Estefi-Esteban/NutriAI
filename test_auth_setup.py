
import importlib


def test_dependencias_autenticacion():
    """Comprueba que las dependencias de autenticación están instaladas."""
    for modulo in ("jose", "passlib", "google.auth"):
        importlib.import_module(modulo)


def test_modelo_usuario_importable():
    """Comprueba que el modelo User se puede importar sin conectar a Supabase."""
    from backend.database.models import User

    assert User is not None
