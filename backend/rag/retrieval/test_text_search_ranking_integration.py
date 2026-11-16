
"""Pruebas de integración entre búsqueda textual y ranking."""

from types import SimpleNamespace

from backend.rag.models import CandidatoAlimento, FuenteBusqueda
from backend.rag.retrieval import text_search


def crear_registro(
    identificador: str,
    nombre: str,
    categorias: str = "",
    kcal: float = 91.0,
):
    return SimpleNamespace(
        id=identificador,
        payload={
            "nombre": nombre,
            "categorias": categorias,
            "kcal_100g": kcal,
        },
    )


def test_busqueda_aplica_ranking_y_conserva_senales(monkeypatch):
    candidatos = [
        crear_registro("chips", "Plátano chip", "Snacks"),
        crear_registro("exacto", "Plátano", "Frutas"),
        crear_registro("helado", "Helado de plátano", "Postres"),
    ]

    monkeypatch.setattr(
        text_search,
        "search_by_text_paginated",
        lambda **kwargs: candidatos,
    )

    resultados = text_search.buscar_por_texto(
        "plátano",
        limite=10,
    )

    assert resultados
    primero = resultados[0]

    assert isinstance(primero, CandidatoAlimento)
    assert primero.alimento.id == "exacto"
    assert primero.alimento.nombre == "Plátano"
    assert primero.puntuacion_textual > 0
    assert primero.puntuacion is not None
    assert primero.puntuacion.total > 0
    assert primero.puntuacion.desglose.nombre_exacto > 0
    assert "nombre_exacto" in primero.puntuacion.motivos
    assert primero.alimento.nutricion.kcal_100g == 91.0
    assert primero.fuentes == (FuenteBusqueda.TEXTUAL,)


def test_busqueda_descarta_candidatos_que_incumplen_restricciones(
    monkeypatch,
):
    candidatos = [
        crear_registro("natural", "Yogurt natural"),
        crear_registro("sin", "Yogurt sin azúcar"),
    ]

    monkeypatch.setattr(
        text_search,
        "search_by_text_paginated",
        lambda **kwargs: candidatos,
    )

    resultados = text_search.buscar_por_texto(
        "yogurt sin azúcar",
        limite=10,
    )

    assert resultados
    assert [
        resultado.alimento.id
        for resultado in resultados
    ] == ["sin"]

    assert all(
        resultado.puntuacion_textual > 0
        for resultado in resultados
    )


def test_busqueda_respeta_limite_y_devuelve_modelos_tipados(
    monkeypatch,
):
    candidatos = [
        crear_registro(str(indice), f"Producto plátano {indice}")
        for indice in range(8)
    ]

    monkeypatch.setattr(
        text_search,
        "search_by_text_paginated",
        lambda **kwargs: candidatos,
    )

    resultados = text_search.buscar_por_texto(
        "plátano",
        limite=3,
    )

    assert len(resultados) == 3
    assert all(
        isinstance(resultado, CandidatoAlimento)
        for resultado in resultados
    )
    assert all(
        resultado.puntuacion is not None
        for resultado in resultados
    )


def test_busqueda_sin_ranking_usa_puntuacion_textual(
    monkeypatch,
):
    candidatos = [
        crear_registro("chips", "Plátano chip"),
        crear_registro("exacto", "Plátano"),
    ]

    monkeypatch.setattr(
        text_search,
        "search_by_text_paginated",
        lambda **kwargs: candidatos,
    )

    resultados = text_search.buscar_por_texto(
        "plátano",
        limite=10,
        aplicar_ranking=False,
    )

    assert resultados[0].alimento.id == "exacto"
    assert all(
        resultado.puntuacion is None
        for resultado in resultados
    )
