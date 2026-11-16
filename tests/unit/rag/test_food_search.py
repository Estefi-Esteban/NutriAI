
import pytest

from backend.rag import food_search
from backend.rag.models.food import Alimento, InformacionNutricional


# ============================================================
# FIXTURES
# ============================================================

def crear_alimento(
    nombre="Manzana",
    kcal=52.0,
    proteinas=0.3,
    carbos=13.8,
    grasas=0.2,
    fibra=2.4,
    outlier=False,
):
    return Alimento(
        nombre=nombre,
        nombre_normalizado=food_search._normalizar_texto(nombre),
        nutricion=InformacionNutricional(
            kcal_100g=kcal,
            proteinas_100g=proteinas,
            carbos_100g=carbos,
            grasas_100g=grasas,
            fibra_100g=fibra,
        ),
        outlier_nutricional=outlier,
    )


# ============================================================
# NORMALIZACIÓN
# ============================================================

@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("PLÁTANO", "platano"),
        ("  Manzana  ", "manzana"),
        ("Árbol", "arbol"),
        ("Leche ENTERA", "leche entera"),
        ("Tomate, rojo.", "tomate rojo"),
        ("AZÚCAR   BLANCO", "azucar blanco"),
    ],
)
def test_normalizar_texto(entrada, esperado):
    assert food_search._normalizar_texto(entrada) == esperado


def test_normalizar_texto_vacio():
    assert food_search._normalizar_texto("") == ""


def test_normalizar_texto_none():
    assert food_search._normalizar_texto(None) == ""


# ============================================================
# COINCIDENCIAS TEXTUALES
# ============================================================

def test_match_textual_encuentra_coincidencia_exacta():
    alimentos = [
        crear_alimento("Manzana"),
        crear_alimento("Pera"),
        crear_alimento("Plátano"),
    ]

    resultado = food_search._match_textual("manzana", alimentos)

    assert resultado is not None
    assert resultado["nombre"] == "Manzana"


def test_match_textual_no_inventa_equivalencias():
    alimentos = [
        crear_alimento("Plátano"),
    ]

    resultado = food_search._match_textual("banana", alimentos)

    assert resultado is None


def test_match_textual_no_acepta_coincidencia_parcial():
    alimentos = [
        crear_alimento("Leche"),
    ]

    resultado = food_search._match_textual(
        "leche de almendras",
        alimentos,
    )

    assert resultado is None


def test_match_textual_no_encuentra_resultados_en_lista_vacia():
    resultado = food_search._match_textual("manzana", [])

    assert resultado is None


# ============================================================
# VALIDACIÓN NUTRICIONAL
# ============================================================

def test_rechaza_alimento_con_nutrientes_obligatorios_ausentes():
    alimento = crear_alimento(
        kcal=None,
        proteinas=None,
        carbos=None,
        grasas=None,
    )

    assert (
        food_search._nutricionalmente_plausible_para_query(
            "manzana",
            alimento,
        )
        is False
    )

def test_rechaza_alimento_con_calorias_fuera_de_rango():
    with pytest.raises(ValueError):
        InformacionNutricional(kcal_100g=1500)


def test_rechaza_alimento_con_macronutrientes_superiores_a_100():
    alimento = crear_alimento(
        proteinas=50,
        carbos=40,
        grasas=30,
    )

    assert (
        food_search._nutricionalmente_plausible_para_query(
            "manzana",
            alimento,
        )
        is False
    )


def test_rechaza_alimento_marcado_como_outlier():
    alimento = crear_alimento(outlier=True)

    assert food_search._es_outlier(alimento) is True


def test_acepta_alimento_con_datos_nutricionales_validos():
    alimento = crear_alimento()

    assert (
        food_search._nutricionalmente_plausible_para_query(
            "manzana",
            alimento,
        )
        is True
    )


# ============================================================
# CONVERSIÓN NUMÉRICA
# ============================================================

def test_numero_conserva_cero():
    assert food_search._numero(0) == 0.0


def test_numero_conserva_valor_decimal():
    assert food_search._numero(12.5) == 12.5


def test_numero_no_convierte_none_en_cero():
    assert food_search._numero(None) is None


def test_numero_rechaza_valores_no_finitos():
    assert food_search._numero(float("nan")) is None
    assert food_search._numero(float("inf")) is None


# ============================================================
# CONVERSIÓN DE ALIMENTO
# ============================================================

def test_alimento_a_dict_conserva_nutrientes_desconocidos():
    alimento = crear_alimento(
        kcal=52,
        proteinas=None,
        carbos=13.8,
        grasas=None,
        fibra=2.4,
    )

    resultado = food_search._alimento_a_dict(alimento)

    assert resultado["nombre"] == "Manzana"
    assert resultado["kcal_100g"] == 52
    assert resultado["proteinas_100g"] is None
    assert resultado["carbos_100g"] == 13.8
    assert resultado["grasas_100g"] is None
    assert resultado["fibra_100g"] == 2.4


# ============================================================
# RESULTADO LIMPIO
# ============================================================

def test_resultado_limpio_acepta_alimento_tipado():
    alimento = crear_alimento()

    resultado = food_search._resultado_limpio(alimento)

    assert isinstance(resultado, dict)
    assert resultado["nombre"] == "Manzana"


def test_resultado_limpio_no_modifica_el_alimento_original():
    alimento = crear_alimento()

    nombre_original = alimento.nombre
    nutricion_original = alimento.nutricion.model_dump()

    food_search._resultado_limpio(alimento)

    assert alimento.nombre == nombre_original
    assert alimento.nutricion.model_dump() == nutricion_original
