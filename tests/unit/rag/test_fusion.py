
import pytest

from backend.rag.models import (
    Alimento,
    CandidatoAlimento,
    FuenteBusqueda,
)
from backend.rag.retrieval.fusion import fusionar_resultados


def crear_candidato(
    identificador: str,
    nombre: str,
    similitud: float | None = None,
    puntuacion_textual: float = 0.0,
    fuente: FuenteBusqueda = FuenteBusqueda.TEXTUAL,
) -> CandidatoAlimento:
    return CandidatoAlimento(
        alimento=Alimento(
            id=identificador,
            nombre=nombre,
        ),
        similitud=similitud,
        puntuacion_textual=puntuacion_textual,
        fuentes=(fuente,),
    )


def test_fusiona_resultados_textuales_y_vectoriales():
    textual = [
        crear_candidato(
            "1",
            "Yogur natural",
            puntuacion_textual=85.0,
        ),
        crear_candidato(
            "2",
            "Leche entera",
            puntuacion_textual=70.0,
        ),
    ]

    vectorial = [
        crear_candidato(
            "2",
            "Leche entera",
            similitud=0.95,
            fuente=FuenteBusqueda.VECTORIAL,
        ),
        crear_candidato(
            "1",
            "Yogur natural",
            similitud=0.90,
            fuente=FuenteBusqueda.VECTORIAL,
        ),
    ]

    resultados = fusionar_resultados(
        textual,
        vectorial,
    )

    assert len(resultados) == 2

    yogur = next(
        candidato
        for candidato in resultados
        if candidato.alimento.id == "1"
    )

    assert yogur.similitud == pytest.approx(0.90)
    assert yogur.puntuacion_textual == pytest.approx(85.0)
    assert yogur.posicion_textual == 1
    assert yogur.posicion_vectorial == 2
    assert yogur.fuentes == (
        FuenteBusqueda.TEXTUAL,
        FuenteBusqueda.VECTORIAL,
    )


def test_calcula_puntuacion_rrf():
    textual = [
        crear_candidato(
            "1",
            "Yogur natural",
            puntuacion_textual=80.0,
        )
    ]

    vectorial = [
        crear_candidato(
            "1",
            "Yogur natural",
            similitud=0.95,
            fuente=FuenteBusqueda.VECTORIAL,
        )
    ]

    resultados = fusionar_resultados(
        textual,
        vectorial,
        k=60,
    )

    esperado = (1 / 61) + (1 / 61)

    assert resultados[0].puntuacion_rrf == pytest.approx(
        esperado
    )

    assert resultados[0].puntuacion_rrf_normalizada == pytest.approx(
        1.0
    )



def test_normaliza_puntuacion_rrf():
    textual = [
        crear_candidato("1", "Yogur natural"),
        crear_candidato("2", "Leche entera"),
    ]

    resultados = fusionar_resultados(
        textual,
        [],
        k=60,
    )

    assert resultados[0].puntuacion_rrf_normalizada == pytest.approx(
        0.5
    )

    assert resultados[1].puntuacion_rrf_normalizada == pytest.approx(
        61 / 124
    )



def test_identifica_candidatos_sin_id_por_nombre():
    textual = [
        crear_candidato("", "Yogur natural")
    ]

    vectorial = [
        crear_candidato("", "YÓGUR NATURAL")
    ]

    resultados = fusionar_resultados(
        textual,
        vectorial,
    )

    assert len(resultados) == 1
    assert len(resultados[0].fuentes) == 2


def test_no_modifica_los_candidatos_originales():
    textual = [
        crear_candidato("1", "Yogur natural")
    ]

    fusionar_resultados(textual, [])

    assert textual[0].puntuacion_rrf == 0.0
    assert textual[0].posicion_textual is None


def test_rechaza_k_invalido():
    with pytest.raises(ValueError):
        fusionar_resultados([], [], k=0)


def test_rechaza_resultados_no_tipados():
    with pytest.raises(TypeError):
        fusionar_resultados(
            [{"nombre": "Yogur natural"}],
            [],
        )


def test_no_duplica_contribucion_misma_fuente():
    textual = [
        crear_candidato("1", "Yogur natural"),
        crear_candidato("1", "Yogur natural"),
    ]

    resultado = fusionar_resultados(textual, [])

    assert len(resultado) == 1
    assert resultado[0].puntuacion_rrf == pytest.approx(1 / 61)


def test_similitud_vectorial_procede_de_la_busqueda_actual():
    textual = [
        crear_candidato(
            "1",
            "Yogur natural",
            similitud=0.40,
        )
    ]
    vectorial = [
        crear_candidato(
            "1",
            "Yogur natural",
            similitud=0.95,
            fuente=FuenteBusqueda.VECTORIAL,
        )
    ]

    resultado = fusionar_resultados(textual, vectorial)

    assert resultado[0].similitud == pytest.approx(0.95)


def test_fuentes_se_reconstruyen_en_cada_fusion():
    textual = [
        crear_candidato(
            "1",
            "Yogur natural",
            fuente=FuenteBusqueda.VECTORIAL,
        )
    ]

    resultado = fusionar_resultados(textual, [])

    assert resultado[0].fuentes == (FuenteBusqueda.TEXTUAL,)


def test_fusion_no_acumula_puntuacion_anterior():
    textual = [crear_candidato("1", "Yogur natural")]

    primera = fusionar_resultados(textual, [])
    segunda = fusionar_resultados(primera, [])

    assert segunda[0].puntuacion_rrf == pytest.approx(1 / 61)


def test_rechaza_k_booleano():
    with pytest.raises(ValueError):
        fusionar_resultados([], [], k=True)


def test_rechaza_k_decimal():
    with pytest.raises(ValueError):
        fusionar_resultados([], [], k=1.5)

