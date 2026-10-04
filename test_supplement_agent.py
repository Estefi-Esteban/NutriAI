"""
test_supplement_agent.py
-------------------------
Tests del Módulo de Suplementación (Fase 3.4).

Estructura:
- Tests unitarios del SupplementAgent (mocks — sin llamadas reales al LLM)
- Tests de integración del router /suplementos/
"""

import json
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
import os
from backend.api.main import app


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    return TestClient(app)


def _mock_usuario():
    user = MagicMock()
    user.id = 1
    user.email = "test@nutriai.com"
    return user


def _mock_perfil():
    """Perfil ORM simulado de un usuario tipo."""
    p = MagicMock()
    p.objetivo_principal.value = "ganar_musculo"
    p.dieta_tipo.value = "omnivoro"
    p.nivel_actividad.value = "activo"
    p.tipo_entrenamiento.value = "fuerza"
    p.dias_entrenamiento = 4
    p.edad = 28
    p.sexo = "hombre"
    p.peso_kg = 80.0
    p.patologias = []
    p.alergias = []
    p.intolerancias = []
    p.medicacion = None
    return p


def _recomendacion_mock() -> dict:
    """Respuesta simulada del SupplementAgent."""
    return {
        "suplementos_necesarios": [
            {
                "nombre": "Vitamina D3",
                "dosis": "2000 UI/día",
                "momento": "Con el desayuno junto a grasa",
                "duracion": "Todo el año",
                "justificacion": "Déficit muy común. Niveles insuficientes en perfil.",
                "coste_estimado_mes": "bajo",
            }
        ],
        "suplementos_opcionales": [
            {
                "nombre": "Creatina monohidrato",
                "dosis": "3-5g/día",
                "momento": "En cualquier momento del día",
                "duracion": "Indefinido mientras entrenes",
                "justificacion": "Entrenas fuerza 4 días/semana. Evidencia A.",
                "coste_estimado_mes": "bajo",
            }
        ],
        "suplementos_innecesarios": [
            {
                "nombre": "BCAA",
                "motivo": "Tu ingesta proteica cubre todos los aminoácidos esenciales.",
            }
        ],
        "notas": "Consulta con tu médico si tomas medicación.",
        "resumen": "Solo vitamina D es necesaria. Creatina muy recomendable para tu objetivo.",
    }


# ── Tests unitarios del agente ───────────────────────────────────────────────

class TestSupplementAgentParseo:
    """Tests del parsing de respuestas del modelo."""

    def test_parsear_json_limpio(self):
        from backend.agents.supplement_agent import SupplementAgent
        agente = SupplementAgent.__new__(SupplementAgent)
        datos = _recomendacion_mock()
        resultado = agente._parsear_respuesta(json.dumps(datos))
        assert "suplementos_necesarios" in resultado
        assert resultado["suplementos_necesarios"][0]["nombre"] == "Vitamina D3"

    def test_parsear_json_en_markdown(self):
        from backend.agents.supplement_agent import SupplementAgent
        agente = SupplementAgent.__new__(SupplementAgent)
        datos = _recomendacion_mock()
        texto = f"Aquí va el análisis:\n```json\n{json.dumps(datos)}\n```"
        resultado = agente._parsear_respuesta(texto)
        assert "suplementos_opcionales" in resultado

    def test_parsear_json_con_texto_alrededor(self):
        from backend.agents.supplement_agent import SupplementAgent
        agente = SupplementAgent.__new__(SupplementAgent)
        datos = _recomendacion_mock()
        texto = f"Introducción larga... {json.dumps(datos)} texto posterior"
        resultado = agente._parsear_respuesta(texto)
        assert "suplementos_innecesarios" in resultado

    def test_parsear_fallo_lanza_excepcion(self):
        from backend.agents.supplement_agent import SupplementAgent
        agente = SupplementAgent.__new__(SupplementAgent)
        with pytest.raises(ValueError, match="JSON válido"):
            agente._parsear_respuesta("esto no tiene JSON de ningún tipo @!#")


class TestSupplementAgentLogica:
    """Tests de la lógica de construcción del mensaje al modelo."""

    def test_recomendar_incluye_perfil_en_entrada(self):
        from backend.agents.supplement_agent import SupplementAgent

        perfil = {
            "objetivo_principal": "perder_grasa",
            "dieta_tipo": "vegano",
            "dias_entrenamiento": 3,
            "tipo_entrenamiento": "cardio",
            "nivel_actividad": "moderado",
            "edad": 35,
            "sexo": "mujer",
            "peso_kg": 65.0,
            "patologias": [],
            "alergias": [],
            "medicacion": None,
        }

        mensajes_capturados = []

        with patch.object(
            SupplementAgent,
            "__init__",
            lambda self: (
                setattr(self, "llm", MagicMock()),
                setattr(self, "system_prompt", "prompt de prueba"),
            ) and None,
        ):
            agente = SupplementAgent()
            mock_respuesta = MagicMock()
            mock_respuesta.content = json.dumps(_recomendacion_mock())
            agente.llm.invoke = lambda msgs: (mensajes_capturados.extend(msgs) or mock_respuesta)

            resultado = agente.recomendar(perfil=perfil)

        # Verificar que el mensaje de usuario contiene el perfil
        mensaje_usuario = mensajes_capturados[-1].content
        entrada = json.loads(mensaje_usuario)
        assert entrada["perfil"]["dieta_tipo"] == "vegano"
        assert entrada["perfil"]["objetivo_principal"] == "perder_grasa"
        assert entrada["analisis_clinico"] is None

    def test_recomendar_incluye_protocolo_cuando_se_pasa(self):
        from backend.agents.supplement_agent import SupplementAgent

        perfil = {
            "objetivo_principal": "mantenimiento",
            "dieta_tipo": "omnivoro",
            "dias_entrenamiento": 2,
            "tipo_entrenamiento": "mixto",
            "nivel_actividad": "ligero",
            "edad": 50,
            "sexo": "mujer",
            "peso_kg": 70.0,
            "patologias": ["hipotiroidismo"],
            "alergias": [],
            "medicacion": "levotiroxina",
        }
        protocolo = {
            "patologias_activas": ["hipotiroidismo"],
            "restricciones": ["bajo_yodo"],
        }

        mensajes_capturados = []

        with patch.object(
            SupplementAgent,
            "__init__",
            lambda self: (
                setattr(self, "llm", MagicMock()),
                setattr(self, "system_prompt", "prompt de prueba"),
            ) and None,
        ):
            agente = SupplementAgent()
            mock_respuesta = MagicMock()
            mock_respuesta.content = json.dumps(_recomendacion_mock())
            agente.llm.invoke = lambda msgs: (mensajes_capturados.extend(msgs) or mock_respuesta)

            resultado = agente.recomendar(perfil=perfil, protocolo_patologias=protocolo)

        mensaje_usuario = mensajes_capturados[-1].content
        entrada = json.loads(mensaje_usuario)
        assert entrada["protocolo_patologias"] is not None
        assert "bajo_yodo" in entrada["protocolo_patologias"]["restricciones"]


# ── Tests de integración del router ─────────────────────────────────────────

class TestSupplementsRouter:
    """Tests de integración de los endpoints de suplementación."""

    def _override_auth(self):
        from backend.api.dependencies import get_current_user
        app.dependency_overrides[get_current_user] = lambda: _mock_usuario()

    def _clear_overrides(self):
        app.dependency_overrides.clear()

    def test_generar_recomendacion_exitoso(self, client):
        """POST /suplementos/generar debe devolver las tres categorías."""
        self._override_auth()
        try:
            with (
                patch("backend.api.routers.supplements.obtener_perfil", return_value=_mock_perfil()),
                patch("backend.api.routers.supplements.obtener_protocolo", return_value=None),
                patch("backend.agents.supplement_agent.SupplementAgent.recomendar",
                      return_value=_recomendacion_mock()),
                patch("backend.api.routers.supplements.guardar_recomendacion", return_value=MagicMock()),
            ):
                resp = client.post(
                    "/suplementos/generar",
                    json={"incluir_analisis_clinico": False, "incluir_protocolo_patologias": False},
                )
        finally:
            self._clear_overrides()

        assert resp.status_code == 200
        data = resp.json()
        assert "suplementos_necesarios" in data
        assert "suplementos_opcionales" in data
        assert "suplementos_innecesarios" in data
        assert "notas" in data

    def test_generar_sin_perfil_devuelve_404(self, client):
        """Si el usuario no tiene perfil, debe devolver 404."""
        self._override_auth()
        try:
            with patch("backend.api.routers.supplements.obtener_perfil", return_value=None):
                resp = client.post(
                    "/suplementos/generar",
                    json={"incluir_analisis_clinico": False, "incluir_protocolo_patologias": False},
                )
        finally:
            self._clear_overrides()

        assert resp.status_code == 404

    def test_generar_con_protocolo_patologias(self, client):
        """Con incluir_protocolo_patologias=True, debe cargar el protocolo."""
        mock_protocolo = MagicMock()
        mock_protocolo.patologias_activas = ["diabetes"]
        mock_protocolo.restricciones = ["bajo_indice_glucemico"]
        mock_protocolo.alimentos_prohibidos = []
        mock_protocolo.alimentos_prioritarios = []
        mock_protocolo.notas_dietista = "Control estricto de carbohidratos"

        self._override_auth()
        try:
            with (
                patch("backend.api.routers.supplements.obtener_perfil", return_value=_mock_perfil()),
                patch("backend.api.routers.supplements.obtener_protocolo", return_value=mock_protocolo),
                patch("backend.agents.supplement_agent.SupplementAgent.recomendar",
                      return_value=_recomendacion_mock()),
                patch("backend.api.routers.supplements.guardar_recomendacion", return_value=MagicMock()),
            ):
                resp = client.post(
                    "/suplementos/generar",
                    json={"incluir_analisis_clinico": False, "incluir_protocolo_patologias": True},
                )
        finally:
            self._clear_overrides()

        assert resp.status_code == 200

    def test_mis_suplementos_sin_recomendacion_devuelve_404(self, client):
        """GET /mis-suplementos sin datos guardados debe devolver 404."""
        self._override_auth()
        try:
            with patch("backend.api.routers.supplements.obtener_recomendacion", return_value=None):
                resp = client.get("/suplementos/mis-suplementos")
        finally:
            self._clear_overrides()

        assert resp.status_code == 404

    def test_mis_suplementos_devuelve_datos_guardados(self, client):
        """GET /mis-suplementos debe devolver los datos de la BD sin llamar al modelo."""
        mock_rec = MagicMock()
        mock_rec.suplementos_necesarios = _recomendacion_mock()["suplementos_necesarios"]
        mock_rec.suplementos_opcionales = _recomendacion_mock()["suplementos_opcionales"]
        mock_rec.suplementos_innecesarios = _recomendacion_mock()["suplementos_innecesarios"]
        mock_rec.notas = "Consulta con tu médico."
        mock_rec.resumen = "Solo vitamina D es necesaria."

        self._override_auth()
        try:
            with patch("backend.api.routers.supplements.obtener_recomendacion", return_value=mock_rec):
                resp = client.get("/suplementos/mis-suplementos")
        finally:
            self._clear_overrides()

        assert resp.status_code == 200
        data = resp.json()
        assert data["suplementos_necesarios"][0]["nombre"] == "Vitamina D3"
        assert data["resumen"] == "Solo vitamina D es necesaria."

    def test_error_agente_devuelve_502(self, client):
        """Si el agente lanza ValueError (JSON inválido), debe devolver 502."""
        self._override_auth()
        try:
            with (
                patch("backend.api.routers.supplements.obtener_perfil", return_value=_mock_perfil()),
                patch("backend.api.routers.supplements.obtener_protocolo", return_value=None),
                patch(
                    "backend.agents.supplement_agent.SupplementAgent.recomendar",
                    side_effect=ValueError("JSON válido no encontrado"),
                ),
            ):
                resp = client.post(
                    "/suplementos/generar",
                    json={"incluir_analisis_clinico": False, "incluir_protocolo_patologias": False},
                )
        finally:
            self._clear_overrides()

        assert resp.status_code == 502

    def test_estructura_suplemento_necesario(self, client):
        """Cada suplemento necesario debe tener todos los campos requeridos."""
        self._override_auth()
        try:
            with (
                patch("backend.api.routers.supplements.obtener_perfil", return_value=_mock_perfil()),
                patch("backend.api.routers.supplements.obtener_protocolo", return_value=None),
                patch("backend.agents.supplement_agent.SupplementAgent.recomendar",
                      return_value=_recomendacion_mock()),
                patch("backend.api.routers.supplements.guardar_recomendacion", return_value=MagicMock()),
            ):
                resp = client.post(
                    "/suplementos/generar",
                    json={"incluir_analisis_clinico": False, "incluir_protocolo_patologias": False},
                )
        finally:
            self._clear_overrides()

        assert resp.status_code == 200
        sup = resp.json()["suplementos_necesarios"][0]
        campos_requeridos = ["nombre", "dosis", "momento", "duracion", "justificacion", "coste_estimado_mes"]
        for campo in campos_requeridos:
            assert campo in sup, f"Campo '{campo}' falta en suplemento necesario"
