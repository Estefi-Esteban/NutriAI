"""
test_vision_agent.py
---------------------
Tests del Agente de Visión (Fase 3.3).

Estructura:
- Tests unitarios del VisionAgent (con mocks — no consumen API real)
- Tests de integración del router /vision/analizar-plato
"""

import json
import base64
from io import BytesIO
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    return TestClient(app)


def _imagen_dummy() -> bytes:
    """Devuelve los bytes de un JPEG mínimo válido (1×1 pixel, 100% rojo)."""
    # JPEG mínimo real de 1x1 px rojo para que pase la validación de tamaño
    jpeg_bytes = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
        b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
        b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\x1e"
        b"\xef\xbf\xbd\x0b\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xc0\x00\x0b\x08"
        b"\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01"
        b"\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04"
        b"\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xf5\x0a"
        b"\xff\xd9"
    )
    # Rellenamos para superar el límite de 1000 bytes
    return jpeg_bytes + b"\x00" * 1500


def _deteccion_mock() -> dict:
    """Respuesta simulada del modelo visual."""
    return {
        "alimentos_detectados": [
            {
                "nombre": "pechuga de pollo a la plancha",
                "cantidad_estimada_g": 150,
                "confianza": "ALTA",
                "notas": None,
            },
            {
                "nombre": "arroz blanco cocido",
                "cantidad_estimada_g": 180,
                "confianza": "ALTA",
                "notas": None,
            },
            {
                "nombre": "tomate cherry",
                "cantidad_estimada_g": 50,
                "confianza": "MEDIA",
                "notas": "pequeños, difícil estimar exactamente",
            },
        ],
        "descripcion_plato": "Plato de pollo con arroz y tomates cherry.",
        "calidad_imagen": "BUENA",
        "advertencia": None,
    }


def _match_rag_pollo() -> dict:
    return {
        "nombre": "Pechuga de pollo",
        "kcal_100g": 110.0,
        "proteinas_100g": 23.0,
        "carbos_100g": 0.0,
        "grasas_100g": 2.5,
        "similitud": 0.91,
    }


def _match_rag_arroz() -> dict:
    return {
        "nombre": "Arroz blanco cocido",
        "kcal_100g": 130.0,
        "proteinas_100g": 2.7,
        "carbos_100g": 28.0,
        "grasas_100g": 0.3,
        "similitud": 0.88,
    }


def _match_rag_tomate() -> dict:
    return {
        "nombre": "Tomate",
        "kcal_100g": 18.0,
        "proteinas_100g": 0.9,
        "carbos_100g": 3.9,
        "grasas_100g": 0.2,
        "similitud": 0.79,
    }


# ── Tests unitarios de VisionAgent ──────────────────────────────────────────

class TestVisionAgentParseo:
    """Tests del parsing de respuestas del modelo."""

    def test_parsear_json_limpio(self):
        from backend.agents.vision_agent import VisionAgent
        agente = VisionAgent.__new__(VisionAgent)
        datos = {"alimentos_detectados": [{"nombre": "pollo", "cantidad_estimada_g": 100}]}
        resultado = agente._parsear_deteccion(json.dumps(datos))
        assert resultado["alimentos_detectados"][0]["nombre"] == "pollo"

    def test_parsear_json_en_markdown(self):
        from backend.agents.vision_agent import VisionAgent
        agente = VisionAgent.__new__(VisionAgent)
        texto = "Aquí está el análisis:\n```json\n{\"calidad_imagen\": \"BUENA\"}\n```"
        resultado = agente._parsear_deteccion(texto)
        assert resultado["calidad_imagen"] == "BUENA"

    def test_parsear_json_sin_backticks(self):
        from backend.agents.vision_agent import VisionAgent
        agente = VisionAgent.__new__(VisionAgent)
        texto = 'Texto antes {"alimentos_detectados": []} texto después'
        resultado = agente._parsear_deteccion(texto)
        assert "alimentos_detectados" in resultado

    def test_parsear_fallo_devuelve_fallback(self):
        from backend.agents.vision_agent import VisionAgent
        agente = VisionAgent.__new__(VisionAgent)
        resultado = agente._parsear_deteccion("esto no es JSON en absoluto !@#")
        assert "alimentos_detectados" in resultado
        assert resultado["calidad_imagen"] == "MALA"


class TestVisionAgentEnriquecimiento:
    """Tests del enriquecimiento con ChromaDB."""

    def test_enriquece_con_rag_cuando_hay_match(self):
        from backend.agents.vision_agent import VisionAgent
        agente = VisionAgent.__new__(VisionAgent)

        alimentos = [{"nombre": "pollo", "cantidad_estimada_g": 150, "confianza": "ALTA", "notas": None}]

        with patch("backend.agents.vision_agent.buscar_mejor_match", return_value=_match_rag_pollo()):
            resultado = agente._enriquecer_con_rag(alimentos)

        assert resultado[0]["verificado_rag"] is True
        assert resultado[0]["kcal"] == round(110.0 * 1.5, 1)
        assert resultado[0]["proteinas_g"] == round(23.0 * 1.5, 1)

    def test_no_enriquece_cuando_similitud_baja(self):
        from backend.agents.vision_agent import VisionAgent
        agente = VisionAgent.__new__(VisionAgent)

        alimentos = [{"nombre": "alimento_raro", "cantidad_estimada_g": 100, "confianza": "BAJA", "notas": None}]
        match_bajo = {**_match_rag_pollo(), "similitud": 0.40}

        with patch("backend.agents.vision_agent.buscar_mejor_match", return_value=match_bajo):
            resultado = agente._enriquecer_con_rag(alimentos)

        assert resultado[0]["verificado_rag"] is False
        assert resultado[0]["kcal"] is None

    def test_no_enriquece_cuando_rag_devuelve_none(self):
        from backend.agents.vision_agent import VisionAgent
        agente = VisionAgent.__new__(VisionAgent)

        alimentos = [{"nombre": "algo", "cantidad_estimada_g": 100, "confianza": "MEDIA", "notas": None}]

        with patch("backend.agents.vision_agent.buscar_mejor_match", return_value=None):
            resultado = agente._enriquecer_con_rag(alimentos)

        assert resultado[0]["verificado_rag"] is False


class TestVisionAgentTotales:
    """Tests del cálculo de totales del plato."""

    def test_suma_solo_verificados(self):
        from backend.agents.vision_agent import VisionAgent
        agente = VisionAgent.__new__(VisionAgent)

        alimentos = [
            {"nombre_detectado": "pollo", "verificado_rag": True, "kcal": 165.0, "proteinas_g": 34.5, "carbos_g": 0.0, "grasas_g": 3.75},
            {"nombre_detectado": "algo_sin_datos", "verificado_rag": False, "kcal": None, "proteinas_g": None, "carbos_g": None, "grasas_g": None},
        ]
        totales = agente._calcular_totales(alimentos)

        assert totales["kcal"] == 165.0
        assert totales["proteinas_g"] == 34.5
        assert "algo_sin_datos" in totales["alimentos_sin_datos"]

    def test_totales_plato_completo(self):
        from backend.agents.vision_agent import VisionAgent
        agente = VisionAgent.__new__(VisionAgent)

        alimentos = [
            {"nombre_detectado": "pollo", "verificado_rag": True, "kcal": 165.0, "proteinas_g": 34.5, "carbos_g": 0.0, "grasas_g": 3.75},
            {"nombre_detectado": "arroz", "verificado_rag": True, "kcal": 234.0, "proteinas_g": 4.86, "carbos_g": 50.4, "grasas_g": 0.54},
        ]
        totales = agente._calcular_totales(alimentos)

        assert totales["kcal"] == round(165.0 + 234.0, 1)
        assert totales["carbos_g"] == round(0.0 + 50.4, 1)
        assert totales["alimentos_sin_datos"] == []


# ── Tests de integración del router ─────────────────────────────────────────

class TestVisionRouter:
    """Tests de integración del endpoint /vision/analizar-plato."""

    def _mock_usuario(self):
        user = MagicMock()
        user.id = 42
        user.email = "test@nutriai.com"
        return user

    def _override_auth(self, app_instance):
        """Sobreescribe la dependencia de autenticación usando dependency_overrides."""
        from backend.api.dependencies import get_current_user
        mock_user = self._mock_usuario()
        app_instance.dependency_overrides[get_current_user] = lambda: mock_user
        return mock_user

    def _clear_overrides(self, app_instance):
        app_instance.dependency_overrides.clear()

    def test_analizar_plato_exitoso(self, client):
        """El endpoint debe devolver el análisis completo con los campos correctos."""
        imagen = _imagen_dummy()
        self._override_auth(app)
        rag_side_effects = [_match_rag_pollo(), _match_rag_arroz(), _match_rag_tomate()]

        try:
            with (
                patch("backend.agents.vision_agent.VisionAgent._detectar_alimentos", return_value=_deteccion_mock()),
                patch("backend.agents.vision_agent.buscar_mejor_match", side_effect=rag_side_effects),
            ):
                resp = client.post(
                    "/vision/analizar-plato",
                    files={"foto": ("plato.jpg", imagen, "image/jpeg")},
                )
        finally:
            self._clear_overrides(app)

        assert resp.status_code == 200
        data = resp.json()
        assert "alimentos" in data
        assert "totales" in data
        assert "disclaimer" in data
        assert len(data["alimentos"]) == 3

    def test_formato_invalido_rechazado(self, client):
        """Un formato no soportado debe devolver 400."""
        self._override_auth(app)
        try:
            resp = client.post(
                "/vision/analizar-plato",
                files={"foto": ("scan.pdf", b"datos", "application/pdf")},
            )
        finally:
            self._clear_overrides(app)
        assert resp.status_code == 400

    def test_archivo_vacio_rechazado(self, client):
        """Un archivo casi vacío debe devolver 400."""
        self._override_auth(app)
        try:
            resp = client.post(
                "/vision/analizar-plato",
                files={"foto": ("foto.jpg", b"tiny", "image/jpeg")},
            )
        finally:
            self._clear_overrides(app)
        assert resp.status_code == 400

    def test_error_modelo_devuelve_503(self, client):
        """Si el agente falla (rate-limit total), debe devolver 503."""
        imagen = _imagen_dummy()
        self._override_auth(app)

        try:
            with patch(
                "backend.agents.vision_agent.VisionAgent._detectar_alimentos",
                side_effect=RuntimeError("Todos los modelos fallaron"),
            ):
                resp = client.post(
                    "/vision/analizar-plato",
                    files={"foto": ("plato.jpg", imagen, "image/jpeg")},
                )
        finally:
            self._clear_overrides(app)

        assert resp.status_code == 503

    def test_disclaimer_presente(self, client):
        """El disclaimer de estimación debe estar siempre presente."""
        imagen = _imagen_dummy()
        self._override_auth(app)
        rag_side_effects = [_match_rag_pollo(), _match_rag_arroz(), _match_rag_tomate()]

        try:
            with (
                patch("backend.agents.vision_agent.VisionAgent._detectar_alimentos", return_value=_deteccion_mock()),
                patch("backend.agents.vision_agent.buscar_mejor_match", side_effect=rag_side_effects),
            ):
                resp = client.post(
                    "/vision/analizar-plato",
                    files={"foto": ("plato.jpg", imagen, "image/jpeg")},
                )
        finally:
            self._clear_overrides(app)

        data = resp.json()
        assert "disclaimer" in data
        assert len(data["disclaimer"]) > 20

    def test_alimentos_sin_rag_aparecen_en_sin_datos(self, client):
        """Alimentos sin match RAG deben aparecer en totales.alimentos_sin_datos."""
        imagen = _imagen_dummy()
        self._override_auth(app)

        try:
            with (
                patch("backend.agents.vision_agent.VisionAgent._detectar_alimentos", return_value=_deteccion_mock()),
                patch("backend.agents.vision_agent.buscar_mejor_match", return_value=None),
            ):
                resp = client.post(
                    "/vision/analizar-plato",
                    files={"foto": ("plato.jpg", imagen, "image/jpeg")},
                )
        finally:
            self._clear_overrides(app)

        data = resp.json()
        assert len(data["totales"]["alimentos_sin_datos"]) == 3
        assert data["totales"]["kcal"] == 0.0
