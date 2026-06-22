import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.api.dependencies import get_current_user, get_db
from backend.database.models import (
    User, UserProfile, ProtocoloNutricional,
    ObjetivoPrincipal, NivelActividad, TipoEntrenamiento, DietaTipo
)
from backend.agents.pathology_agent import PathologyAgent

client = TestClient(app)

dummy_user = User(id=999, nombre="Usuario Test", email="test@example.com")


def test_analizar_patologias_ok():
    """Prueba que el endpoint analizar genera y guarda el protocolo nutricional."""
    app.dependency_overrides[get_current_user] = lambda: dummy_user
    
    mock_db = MagicMock()
    mock_profile = UserProfile(
        user_id=999,
        sexo="hombre",
        edad=35,
        peso_kg=85.0,
        altura_cm=180.0,
        objetivo_principal=ObjetivoPrincipal.mantenimiento,
        nivel_actividad=NivelActividad.moderado,
        dias_entrenamiento=3,
        tipo_entrenamiento=TipoEntrenamiento.mixto,
        dieta_tipo=DietaTipo.omnivoro,
        tiempo_cocina_min=45
    )
    # Simular la consulta del perfil
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        mock_profile,  # obtener_perfil
        None,          # existente protocolo en guardar_protocolo
    ]
    app.dependency_overrides[get_db] = lambda: mock_db
    
    mock_agent_response = {
        "patologias_identificadas": ["diabetes", "hipertension"],
        "restricciones": ["bajo_indice_glucemico", "bajo_sodio"],
        "alimentos_prohibidos": ["azúcar", "sal"],
        "alimentos_prioritarios": ["avena", "verduras"],
        "conflictos_detectados": [],
        "notas_dietista": "Dieta de bajo IG y bajo sodio.",
        "nivel_restriccion": "alto"
    }
    
    with patch("backend.agents.pathology_agent.PathologyAgent.analizar", return_value=mock_agent_response):
        respuesta = client.post("/patologias/analizar", json={
            "patologias": ["diabetes", "hipertension"],
            "alertas_clinicas": []
        })
        assert respuesta.status_code == 200
        data = respuesta.json()
        assert "diabetes" in data["patologias_identificadas"]
        assert "bajo_sodio" in data["restricciones"]
        assert data["nivel_restriccion"] == "alto"

    app.dependency_overrides.clear()


def test_obtener_mi_protocolo_vacio():
    """Prueba obtener el protocolo de un usuario cuando no tiene ninguno activo."""
    app.dependency_overrides[get_current_user] = lambda: dummy_user
    
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    app.dependency_overrides[get_db] = lambda: mock_db
    
    respuesta = client.get("/patologias/mi-protocolo")
    assert respuesta.status_code == 200
    data = respuesta.json()
    assert data["patologias_identificadas"] == []
    assert data["nivel_restriccion"] == "bajo"
    
    app.dependency_overrides.clear()


def test_obtener_mi_protocolo_existente():
    """Prueba obtener el protocolo de un usuario cuando tiene uno activo guardado."""
    app.dependency_overrides[get_current_user] = lambda: dummy_user
    
    mock_db = MagicMock()
    mock_protocol = ProtocoloNutricional(
        user_id=999,
        patologias_activas=["diabetes"],
        restricciones=["bajo_indice_glucemico"],
        alimentos_prohibidos=["azúcar"],
        alimentos_prioritarios=["avena"],
        notas_dietista="Evitar azúcar refinado."
    )
    mock_db.query.return_value.filter.return_value.first.return_value = mock_protocol
    app.dependency_overrides[get_db] = lambda: mock_db
    
    respuesta = client.get("/patologias/mi-protocolo")
    assert respuesta.status_code == 200
    data = respuesta.json()
    assert data["patologias_identificadas"] == ["diabetes"]
    assert "bajo_indice_glucemico" in data["restricciones"]
    assert data["nivel_restriccion"] == "moderado"
    
    app.dependency_overrides.clear()
