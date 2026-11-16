
"""Modelos tipados del dominio de alimentos de NutriAI.

Los datos externos de Qdrant se convierten aquí a modelos Pydantic.
El resto de la aplicación trabaja con objetos tipados.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from math import isfinite
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ModeloNutriAI(BaseModel):
    """Configuración común de los modelos del dominio."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class InformacionNutricional(ModeloNutriAI):
    """Información nutricional por cada 100 gramos."""

    kcal_100g: float | None = Field(default=None, ge=0.0, le=1000.0)
    proteinas_100g: float | None = Field(default=None, ge=0.0, le=100.0)
    carbos_100g: float | None = Field(default=None, ge=0.0, le=100.0)
    azucares_100g: float | None = Field(default=None, ge=0.0, le=100.0)
    grasas_100g: float | None = Field(default=None, ge=0.0, le=100.0)
    fibra_100g: float | None = Field(default=None, ge=0.0, le=100.0)
    sal_100g: float | None = Field(default=None, ge=0.0, le=100.0)


class Alimento(ModeloNutriAI):
    """Representación interna y tipada de un alimento."""

    id: str | None = None
    nombre: str = Field(min_length=1, max_length=200)
    nombre_normalizado: str = Field(default="", max_length=200)
    nutricion: InformacionNutricional = Field(
        default_factory=InformacionNutricional
    )
    alergenos: str = Field(default="", max_length=300)
    categorias: str = Field(default="", max_length=500)
    calidad_nutricional: str = ""
    score_calidad: float = Field(default=0.0, ge=0.0, le=100.0)
    estado_alimento: str = ""
    outlier_nutricional: bool = False

    @classmethod
    def desde_payload(
        cls,
        payload: Mapping[str, Any],
        identificador: str | int | None = None,
    ) -> Alimento:
        """Convierte el payload externo de Qdrant en un Alimento."""

        return cls(
            id=None if identificador is None else str(identificador),
            nombre=str(payload.get("nombre") or "Alimento sin nombre"),
            nombre_normalizado=str(
                payload.get("nombre_normalizado") or ""
            ),
            nutricion=InformacionNutricional(
                kcal_100g=_nutriente_externo(payload.get("kcal_100g")),
                proteinas_100g=_nutriente_externo(
                    payload.get("proteinas_100g")
                ),
                carbos_100g=_nutriente_externo(
                    payload.get("carbos_100g")
                ),
                azucares_100g=_nutriente_externo(
                    payload.get("azucares_100g")
                ),
                grasas_100g=_nutriente_externo(
                    payload.get("grasas_100g")
                ),
                fibra_100g=_nutriente_externo(payload.get("fibra_100g")),
                sal_100g=_nutriente_externo(payload.get("sal_100g")),
            ),
            alergenos=str(payload.get("alergenos") or ""),
            categorias=str(payload.get("categorias") or ""),
            calidad_nutricional=str(
                payload.get("calidad_nutricional") or ""
            ),
            score_calidad=_numero_externo(
                payload.get("score_calidad")
            ),
            estado_alimento=str(payload.get("estado_alimento") or ""),
            outlier_nutricional=_booleano_externo(
                payload.get("outlier_nutricional")
            ),
        )


class FuenteBusqueda(StrEnum):
    TEXTUAL = "textual"
    VECTORIAL = "vectorial"


class MetricasRanking(ModeloNutriAI):
    """Valores normalizados utilizados para calcular el ranking."""

    nombre_exacto: float = Field(default=0.0, ge=0.0, le=1.0)
    cobertura: float = Field(default=0.0, ge=0.0, le=1.0)
    frase_completa: float = Field(default=0.0, ge=0.0, le=1.0)
    orden: float = Field(default=0.0, ge=0.0, le=1.0)
    similitud_vectorial: float = Field(default=0.0, ge=0.0, le=1.0)
    fusion_rrf: float = Field(default=0.0, ge=0.0, le=1.0)


class DesgloseRanking(ModeloNutriAI):
    """Aportación de cada señal a la puntuación de 0 a 100."""

    nombre_exacto: float = Field(default=0.0, ge=0.0, le=30.0)
    cobertura: float = Field(default=0.0, ge=0.0, le=25.0)
    frase_completa: float = Field(default=0.0, ge=0.0, le=15.0)
    orden: float = Field(default=0.0, ge=0.0, le=10.0)
    similitud_vectorial: float = Field(default=0.0, ge=0.0, le=15.0)
    fusion_rrf: float = Field(default=0.0, ge=0.0, le=5.0)



class PuntuacionRanking(ModeloNutriAI):
    """Evaluación explicable de la relevancia de un candidato."""

    total: float = Field(ge=0.0, le=1.0)

    # Señales normalizadas: conservamos la interfaz original.
    coincidencia_exacta: float = Field(default=0.0, ge=0.0, le=1.0)
    cobertura: float = Field(default=0.0, ge=0.0, le=1.0)
    coincidencia_frase: float = Field(default=0.0, ge=0.0, le=1.0)
    orden_tokens: float = Field(default=0.0, ge=0.0, le=1.0)
    similitud_vectorial: float = Field(default=0.0, ge=0.0, le=1.0)
    fusion_rrf: float = Field(default=0.0, ge=0.0, le=1.0)

    # Desglose explicativo de la puntuación de 0 a 100.
    desglose: DesgloseRanking = Field(
        default_factory=DesgloseRanking
    )

    motivos: tuple[str, ...] = ()


class CandidatoAlimento(ModeloNutriAI):
    """Alimento recuperado por el buscador."""

    alimento: Alimento
    similitud: float | None = Field(default=None, ge=0.0, le=1.0)
    puntuacion_textual: float = Field(default=0.0, ge=0.0)
    puntuacion_rrf: float = Field(default=0.0, ge=0.0)
    puntuacion_rrf_normalizada: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )
    posicion_textual: int | None = Field(default=None, ge=1)
    posicion_vectorial: int | None = Field(default=None, ge=1)
    fuentes: tuple[FuenteBusqueda, ...] = ()
    puntuacion: PuntuacionRanking | None = None


class ResultadoBusqueda(ModeloNutriAI):
    """Resultado completo del buscador híbrido."""

    consulta: str = Field(min_length=1, max_length=500)
    candidatos: tuple[CandidatoAlimento, ...] = ()
    candidato_seleccionado: CandidatoAlimento | None = None
    fuentes_consultadas: tuple[FuenteBusqueda, ...] = ()
    busqueda_textual_correcta: bool = True
    busqueda_vectorial_correcta: bool = True


class Ingrediente(ModeloNutriAI):
    """Ingrediente de una comida."""

    nombre: str = Field(min_length=1, max_length=200)
    cantidad: float = Field(gt=0.0, le=10000.0)
    unidad: str = Field(default="g", pattern=r"^(g|ml)$")
    alimento_verificado: Alimento | None = None


class ResultadoVerificacionNutricional(ModeloNutriAI):
    """Resultado de la validación de coherencia nutricional."""

    aprobado: bool
    motivos: tuple[str, ...] = ()
    energia_calculada_kcal_100g: float | None = Field(
        default=None, ge=0.0
    )
    energia_declarada_kcal_100g: float | None = Field(
        default=None, ge=0.0
    )
    diferencia_energetica_porcentual: float | None = Field(
        default=None, ge=0.0
    )


def _numero_externo(value: object) -> float:
    """Normaliza un valor numérico recibido de una fuente externa."""

    if value is None or isinstance(value, bool):
        return 0.0

    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0

    return number if isfinite(number) and number >= 0.0 else 0.0


def _nutriente_externo(value: object) -> float | None:
    """Convierte un nutriente externo sin confundir ausencia con cero."""

    if value is None or isinstance(value, bool):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not isfinite(number) or number < 0.0:
        return None

    return number


def _booleano_externo(value: object) -> bool:
    """Normaliza un booleano recibido de una fuente externa."""

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value != 0

    if isinstance(value, str):
        return value.strip().lower() in {
            "true", "1", "yes", "si", "sí"
        }

    return False
