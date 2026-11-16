
from backend.rag.normalization import normalizador_alimentos


def test_normaliza_acentos_y_mayusculas():
    assert (
        normalizador_alimentos.normalizar_texto("PLÁTANO")
        == "platano"
    )


def test_normaliza_sinonimos():
    assert (
        normalizador_alimentos.normalizar_token("banana")
        == "platano"
    )


def test_obtiene_tokens_sin_palabras_vacias():
    assert normalizador_alimentos.obtener_tokens(
        "Yogur natural de vaca"
    ) == ("yogurt", "natural", "vaca")


def test_consultas_equivalentes():
    consultas = (
        normalizador_alimentos.obtener_consultas_equivalentes(
            "banana natural"
        )
    )

    assert "banana natural" in consultas
    assert "platano natural" in consultas


def test_penalizacion_modificador():
    assert (
        normalizador_alimentos.obtener_penalizacion_modificador(
            "helado"
        )
        == 24
    )


def test_penalizacion_inexistente():
    assert (
        normalizador_alimentos.obtener_penalizacion_modificador(
            "pollo"
        )
        == 0
    )


def test_restriccion_critica_presente():
    assert normalizador_alimentos.contiene_restricciones_criticas(
        "yogur sin lactosa",
        "yogur natural sin lactosa",
    )


def test_restriccion_critica_ausente():
    assert not normalizador_alimentos.contiene_restricciones_criticas(
        "yogur sin lactosa",
        "yogur natural",
    )
