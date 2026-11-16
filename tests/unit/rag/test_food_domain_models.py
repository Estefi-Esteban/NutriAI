
import pytest
from pydantic import ValidationError

from backend.rag.models import (
    Alimento,
    CandidatoAlimento,
    FuenteBusqueda,
    InformacionNutricional,
    Ingrediente,
    PuntuacionRanking,
    ResultadoBusqueda,
    ResultadoVerificacionNutricional,
)


def test_adapta_payload_de_qdrant():
    alimento = Alimento.desde_payload(
        {
            "nombre": "Pechuga de pollo",
            "nombre_normalizado": "pechuga de pollo",
            "kcal_100g": 110.0,
            "proteinas_100g": 23.0,
            "carbos_100g": 0.0,
            "azucares_100g": 0.0,
            "grasas_100g": 1.5,
            "fibra_100g": 0.0,
            "sal_100g": 0.12,
            "alergenos": "",
            "categorias": "es:carnes, es:aves",
            "calidad_nutricional": "alta",
            "score_calidad": 92.0,
            "estado_alimento": "validado",
            "outlier_nutricional": False,
        },
        identificador="food-1",
    )

    assert alimento.id == "food-1"
    assert alimento.nombre == "Pechuga de pollo"
    assert alimento.nutricion.kcal_100g == 110.0
    assert alimento.nutricion.proteinas_100g == 23.0
    assert alimento.nutricion.carbos_100g == 0.0


def test_nutriente_ausente_se_conserva_como_none():
    alimento = Alimento.desde_payload(
        {
            "nombre": "Alimento de prueba",
            "kcal_100g": None,
            "proteinas_100g": 0,
        }
    )

    assert alimento.nutricion.kcal_100g is None
    assert alimento.nutricion.proteinas_100g == 0.0


def test_nutrientes_ausentes_por_defecto_son_none():
    nutricion = InformacionNutricional()

    assert nutricion.kcal_100g is None
    assert nutricion.proteinas_100g is None
    assert nutricion.carbos_100g is None
    assert nutricion.azucares_100g is None
    assert nutricion.grasas_100g is None
    assert nutricion.fibra_100g is None
    assert nutricion.sal_100g is None


def test_nutriente_invalido_no_se_convierte_en_cero():
    alimento = Alimento.desde_payload(
        {
            "nombre": "Alimento de prueba",
            "kcal_100g": "nan",
            "proteinas_100g": -3,
        }
    )

    assert alimento.nutricion.kcal_100g is None
    assert alimento.nutricion.proteinas_100g is None


def test_rechaza_nutrientes_negativos():
    with pytest.raises(ValidationError):
        InformacionNutricional(kcal_100g=-10)


def test_rechaza_nutrientes_fuera_de_rango():
    with pytest.raises(ValidationError):
        InformacionNutricional(proteinas_100g=101)


def test_alimento_requiere_nombre():
    with pytest.raises(ValidationError):
        Alimento(nombre="")


def test_candidato_y_resultado_son_tipados():
    alimento = Alimento(
        nombre="Yogur natural",
        nutricion=InformacionNutricional(
            kcal_100g=65,
            proteinas_100g=4,
        ),
    )

    candidato = CandidatoAlimento(
        alimento=alimento,
        similitud=0.91,
        fuentes=(
            FuenteBusqueda.TEXTUAL,
            FuenteBusqueda.VECTORIAL,
        ),
        puntuacion=PuntuacionRanking(
            total=0.92,
            coincidencia_exacta=1.0,
        ),
    )

    resultado = ResultadoBusqueda(
        consulta="yogur natural",
        candidatos=(candidato,),
        candidato_seleccionado=candidato,
    )

    assert resultado.candidato_seleccionado == candidato
    assert resultado.candidatos[0].alimento.nombre == "Yogur natural"


def test_ingrediente_valida_cantidad_y_unidad():
    ingrediente = Ingrediente(
        nombre="Arroz",
        cantidad=80,
        unidad="g",
    )

    assert ingrediente.cantidad == 80

    with pytest.raises(ValidationError):
        Ingrediente(nombre="Arroz", cantidad=0, unidad="g")

    with pytest.raises(ValidationError):
        Ingrediente(nombre="Arroz", cantidad=80, unidad="taza")


def test_resultado_verificacion_nutricional():
    resultado = ResultadoVerificacionNutricional(
        aprobado=False,
        motivos=("Diferencia energética elevada",),
        energia_calculada_kcal_100g=220,
        energia_declarada_kcal_100g=90,
        diferencia_energetica_porcentual=144.4,
    )

    assert resultado.aprobado is False
    assert resultado.motivos[0] == "Diferencia energética elevada"
