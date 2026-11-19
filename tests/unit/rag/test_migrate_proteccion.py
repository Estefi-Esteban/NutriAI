"""
Protección de la migración a Qdrant: nunca se elimina una colección existente
sin autorización explícita. Usa un cliente falso: no toca Qdrant real.
"""

from types import SimpleNamespace

import pytest

from backend.rag import migrate_to_qdrant as mod
from backend.rag.migrate_to_qdrant import (
    COLECCION,
    ReconstruccionNoAutorizadaError,
    comprobar_autorizacion_reconstruccion,
    reconstruir_coleccion,
)


class ClienteFalso:
    """Imita lo mínimo del cliente de Qdrant y registra cada operación."""

    def __init__(self, existentes=(), puntos=126674):
        self.existentes = list(existentes)
        self.puntos = puntos
        self.llamadas = []

    def get_collections(self):
        return SimpleNamespace(
            collections=[SimpleNamespace(name=n) for n in self.existentes]
        )

    def get_collection(self, nombre):
        self.llamadas.append(("get_collection", nombre))
        return SimpleNamespace(points_count=self.puntos)

    def delete_collection(self, collection_name):
        self.llamadas.append(("delete_collection", collection_name))

    def create_collection(self, collection_name, vectors_config):
        self.llamadas.append(("create_collection", collection_name))

    def operaciones_destructivas(self):
        return [op for op, _ in self.llamadas if op in ("delete_collection", "create_collection")]


# ---------------------------------------------------------------------------
# comprobar_autorizacion_reconstruccion
# ---------------------------------------------------------------------------

def test_si_no_existe_no_hay_nada_que_proteger():
    comprobar_autorizacion_reconstruccion(
        existe=False, puntos_existentes=None, reconstruir=False, confirmar=None
    )


def test_si_existe_y_no_se_autoriza_se_bloquea():
    with pytest.raises(ReconstruccionNoAutorizadaError) as exc:
        comprobar_autorizacion_reconstruccion(
            existe=True, puntos_existentes=126674, reconstruir=False, confirmar=None
        )
    mensaje = str(exc.value)
    assert COLECCION in mensaje
    assert "126.674" in mensaje
    assert "--reconstruir" in mensaje and "snapshot" in mensaje


def test_reconstruir_sin_confirmar_el_nombre_se_bloquea():
    with pytest.raises(ReconstruccionNoAutorizadaError):
        comprobar_autorizacion_reconstruccion(
            existe=True, puntos_existentes=10, reconstruir=True, confirmar=None
        )


def test_confirmar_con_otro_nombre_se_bloquea():
    with pytest.raises(ReconstruccionNoAutorizadaError):
        comprobar_autorizacion_reconstruccion(
            existe=True, puntos_existentes=10, reconstruir=True, confirmar="otra"
        )


def test_confirmar_sin_reconstruir_se_bloquea():
    with pytest.raises(ReconstruccionNoAutorizadaError):
        comprobar_autorizacion_reconstruccion(
            existe=True, puntos_existentes=10, reconstruir=False, confirmar=COLECCION
        )


def test_doble_confirmacion_correcta_permite_reconstruir():
    comprobar_autorizacion_reconstruccion(
        existe=True, puntos_existentes=10, reconstruir=True, confirmar=COLECCION
    )


# ---------------------------------------------------------------------------
# reconstruir_coleccion
# ---------------------------------------------------------------------------

def test_reconstruir_coleccion_existente_sin_autorizar_no_borra_nada():
    cliente = ClienteFalso(existentes=[COLECCION])
    with pytest.raises(ReconstruccionNoAutorizadaError):
        reconstruir_coleccion(cliente)
    assert cliente.operaciones_destructivas() == []


def test_reconstruir_coleccion_existente_autorizada_borra_y_crea():
    cliente = ClienteFalso(existentes=[COLECCION])
    reconstruir_coleccion(cliente, autorizado=True)
    assert cliente.operaciones_destructivas() == ["delete_collection", "create_collection"]


def test_reconstruir_coleccion_inexistente_solo_crea():
    cliente = ClienteFalso(existentes=[])
    reconstruir_coleccion(cliente)
    assert cliente.operaciones_destructivas() == ["create_collection"]


# ---------------------------------------------------------------------------
# migrar(): la protección actúa antes de leer el CSV o cargar el modelo
# ---------------------------------------------------------------------------

def _preparar_migrar(monkeypatch, cliente):
    monkeypatch.setenv("QDRANT_URL", "https://ejemplo.invalid")
    monkeypatch.setenv("QDRANT_API_KEY", "clave-falsa")
    monkeypatch.setattr(mod, "QdrantClient", lambda **kwargs: cliente)


def test_migrar_por_defecto_aborta_si_la_coleccion_existe(monkeypatch):
    cliente = ClienteFalso(existentes=[COLECCION])
    _preparar_migrar(monkeypatch, cliente)
    with pytest.raises(SystemExit) as salida:
        mod.migrar()
    assert salida.value.code == 1
    assert cliente.operaciones_destructivas() == []


def test_migrar_con_confirmacion_incorrecta_aborta(monkeypatch):
    cliente = ClienteFalso(existentes=[COLECCION])
    _preparar_migrar(monkeypatch, cliente)
    with pytest.raises(SystemExit):
        mod.migrar(reconstruir=True, confirmar="otra")
    assert cliente.operaciones_destructivas() == []


# ---------------------------------------------------------------------------
# Línea de comandos
# ---------------------------------------------------------------------------

def test_cli_por_defecto_no_autoriza_nada():
    args = mod._parsear_argumentos([])
    assert args.reconstruir is False and args.confirmar is None


def test_cli_acepta_la_doble_confirmacion():
    args = mod._parsear_argumentos(["--reconstruir", "--confirmar", COLECCION])
    assert args.reconstruir is True and args.confirmar == COLECCION
