
"""Tests del pipeline híbrido de recuperación de NutriAI."""

import pytest

from backend.rag.models import (
    Alimento,
    CandidatoAlimento,
    FuenteBusqueda,
    ResultadoBusqueda,
)
from backend.rag.retrieval import search_pipeline


def crear_candidato(
    identificador: str,
    nombre: str,
    fuente: FuenteBusqueda,
    puntuacion_textual: float = 0.0,
    similitud: float | None = None,
) -> CandidatoAlimento:
    """Construye un candidato tipado para las pruebas."""

    alimento = Alimento(
        id=identificador,
        nombre=nombre,
        nombre_normalizado=nombre.lower(),
    )

    return CandidatoAlimento(
        alimento=alimento,
        puntuacion_textual=puntuacion_textual,
        similitud=similitud,
        fuentes=(fuente,),
    )


def test_ejecuta_ambas_busquedas(monkeypatch):
    candidato_textual = crear_candidato(
        "pollo-1",
        "Pechuga de pollo",
        FuenteBusqueda.TEXTUAL,
        puntuacion_textual=100.0,
    )

    candidato_vectorial = crear_candidato(
        "pollo-2",
        "Pollo asado",
        FuenteBusqueda.VECTORIAL,
        similitud=0.90,
    )

    monkeypatch.setattr(
        search_pipeline,
        "buscar_candidatos_por_texto",
        lambda *args, **kwargs: [candidato_textual],
    )

    monkeypatch.setattr(
        search_pipeline,
        "buscar_candidatos_por_vector",
        lambda *args, **kwargs: [candidato_vectorial],
    )

    resultado = search_pipeline.recuperar_resultado("pollo")

    assert isinstance(resultado, ResultadoBusqueda)
    assert resultado.busqueda_textual_correcta is True
    assert resultado.busqueda_vectorial_correcta is True
    assert len(resultado.candidatos) == 2


def test_fusiona_candidato_encontrado_por_ambas_fuentes(monkeypatch):
    candidato_textual = crear_candidato(
        "pollo-1",
        "Pechuga de pollo",
        FuenteBusqueda.TEXTUAL,
        puntuacion_textual=100.0,
    )

    candidato_vectorial = crear_candidato(
        "pollo-1",
        "Pechuga de pollo",
        FuenteBusqueda.VECTORIAL,
        similitud=0.90,
    )

    monkeypatch.setattr(
        search_pipeline,
        "buscar_candidatos_por_texto",
        lambda *args, **kwargs: [candidato_textual],
    )

    monkeypatch.setattr(
        search_pipeline,
        "buscar_candidatos_por_vector",
        lambda *args, **kwargs: [candidato_vectorial],
    )

    resultado = search_pipeline.recuperar_resultado("pollo")

    assert len(resultado.candidatos) == 1

    candidato = resultado.candidatos[0]

    assert isinstance(candidato, CandidatoAlimento)
    assert candidato.alimento.nombre == "Pechuga de pollo"
    assert FuenteBusqueda.TEXTUAL in candidato.fuentes
    assert FuenteBusqueda.VECTORIAL in candidato.fuentes
    assert candidato.puntuacion_rrf > 0.0


def test_continua_si_falla_busqueda_textual(monkeypatch):
    candidato_vectorial = crear_candidato(
        "pollo-1",
        "Pechuga de pollo",
        FuenteBusqueda.VECTORIAL,
        similitud=0.90,
    )

    def fallo_textual(*args, **kwargs):
        raise RuntimeError("Error textual")

    monkeypatch.setattr(
        search_pipeline,
        "buscar_candidatos_por_texto",
        fallo_textual,
    )

    monkeypatch.setattr(
        search_pipeline,
        "buscar_candidatos_por_vector",
        lambda *args, **kwargs: [candidato_vectorial],
    )

    resultado = search_pipeline.recuperar_resultado("pollo")

    assert resultado.busqueda_textual_correcta is False
    assert resultado.busqueda_vectorial_correcta is True
    assert len(resultado.candidatos) == 1
    assert resultado.candidatos[0].alimento.nombre == "Pechuga de pollo"


def test_continua_si_falla_busqueda_vectorial(monkeypatch):
    candidato_textual = crear_candidato(
        "pollo-1",
        "Pechuga de pollo",
        FuenteBusqueda.TEXTUAL,
        puntuacion_textual=100.0,
    )

    def fallo_vectorial(*args, **kwargs):
        raise RuntimeError("Error vectorial")

    monkeypatch.setattr(
        search_pipeline,
        "buscar_candidatos_por_texto",
        lambda *args, **kwargs: [candidato_textual],
    )

    monkeypatch.setattr(
        search_pipeline,
        "buscar_candidatos_por_vector",
        fallo_vectorial,
    )

    resultado = search_pipeline.recuperar_resultado("pollo")

    assert resultado.busqueda_textual_correcta is True
    assert resultado.busqueda_vectorial_correcta is False
    assert len(resultado.candidatos) == 1


def test_registra_si_fallan_ambas_busquedas(monkeypatch):
    def fallo_textual(*args, **kwargs):
        raise RuntimeError("Error textual")

    def fallo_vectorial(*args, **kwargs):
        raise RuntimeError("Error vectorial")

    monkeypatch.setattr(
        search_pipeline,
        "buscar_candidatos_por_texto",
        fallo_textual,
    )

    monkeypatch.setattr(
        search_pipeline,
        "buscar_candidatos_por_vector",
        fallo_vectorial,
    )

    resultado = search_pipeline.recuperar_resultado("pollo")

    assert resultado.candidatos == ()
    assert resultado.candidato_seleccionado is None
    assert resultado.busqueda_textual_correcta is False
    assert resultado.busqueda_vectorial_correcta is False


def test_selecciona_el_primer_candidato_del_ranking(monkeypatch):
    candidato = crear_candidato(
        "pollo-1",
        "Pollo",
        FuenteBusqueda.TEXTUAL,
        puntuacion_textual=100.0,
    )

    monkeypatch.setattr(
        search_pipeline,
        "buscar_candidatos_por_texto",
        lambda *args, **kwargs: [candidato],
    )

    monkeypatch.setattr(
        search_pipeline,
        "buscar_candidatos_por_vector",
        lambda *args, **kwargs: [],
    )

    resultado = search_pipeline.recuperar_resultado("pollo")

    assert resultado.candidato_seleccionado is not None
    assert (
        resultado.candidato_seleccionado.alimento.nombre
        == resultado.candidatos[0].alimento.nombre
    )


def test_recuperar_candidatos_devuelve_lista_tipada(monkeypatch):
    candidato = crear_candidato(
        "pollo-1",
        "Pollo",
        FuenteBusqueda.TEXTUAL,
        puntuacion_textual=100.0,
    )

    monkeypatch.setattr(
        search_pipeline,
        "buscar_candidatos_por_texto",
        lambda *args, **kwargs: [candidato],
    )

    monkeypatch.setattr(
        search_pipeline,
        "buscar_candidatos_por_vector",
        lambda *args, **kwargs: [],
    )

    resultado = search_pipeline.recuperar_candidatos("pollo")

    assert isinstance(resultado, list)
    assert len(resultado) == 1
    assert isinstance(resultado[0], CandidatoAlimento)


def test_consulta_vacia_devuelve_lista_vacia():
    resultado = search_pipeline.recuperar_candidatos("")

    assert resultado == []


def test_resultado_rechaza_consulta_vacia():
    with pytest.raises(ValueError):
        search_pipeline.recuperar_resultado("")


def test_rechaza_limite_textual_invalido():
    with pytest.raises(ValueError):
        search_pipeline.recuperar_resultado(
            "pollo",
            limite_textual=0,
        )


def test_rechaza_limite_vectorial_invalido():
    with pytest.raises(ValueError):
        search_pipeline.recuperar_resultado(
            "pollo",
            limite_vectorial=0,
        )


def test_rechaza_limite_final_invalido():
    with pytest.raises(ValueError):
        search_pipeline.recuperar_resultado(
            "pollo",
            limite_final=0,
        )


def test_rechaza_rrf_k_invalido():
    with pytest.raises(ValueError):
        search_pipeline.recuperar_resultado(
            "pollo",
            rrf_k=0,
        )
