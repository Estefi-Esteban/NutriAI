import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.api.dependencies import get_current_user, get_db
from backend.database.models import User, UserProfile
from backend.agents.clinical_agent import ClinicalAgent

client = TestClient(app)

dummy_user = User(id=999, nombre="Usuario Test", email="test@example.com")


def test_analisis_manual_ok():
    """Prueba que el endpoint manual devuelve la respuesta interpretada correctamente."""
    app.dependency_overrides[get_current_user] = lambda: dummy_user
    
    # Mockear DB para retornar un UserProfile
    mock_db = MagicMock()
    mock_profile = UserProfile(
        user_id=999,
        sexo="mujer",
        edad=30,
        peso_kg=60.0,
        altura_cm=165.0,
        objetivo_principal="perder_grasa",
        patologias=["hipotiroidismo"],
        alergias=[],
        dieta_tipo="omnivoro",
        nivel_actividad="sedentario",
        dias_entrenamiento=0,
        tipo_entrenamiento="ninguno",
        tiempo_cocina_min=30
    )
    mock_db.query.return_value.filter.return_value.first.return_value = mock_profile
    app.dependency_overrides[get_db] = lambda: mock_db
    
    # Mockear el clinical agent
    mock_agent_response = {
        "resumen_general": "Valores analíticos interpretados correctamente.",
        "marcadores": {
            "glucosa": {
                "valor": 110.0,
                "estado": "elevado",
                "explicacion": "Glucosa ligeramente alta.",
                "accion_nutricional": "Reducir carbos simples"
            }
        },
        "alertas": [
            {
                "marcador": "glucosa",
                "severidad": "moderada",
                "mensaje": "Glucosa elevada"
            }
        ],
        "recomendaciones_nutricionales": ["Evitar azúcares añadidos"],
        "notas_para_dietista": "Controlar IG",
        "requiere_atencion_medica": False,
        "motivo_atencion_medica": None
    }
    
    with patch("backend.agents.clinical_agent.ClinicalAgent.analizar", return_value=mock_agent_response):
        respuesta = client.post("/analitica/manual", json={
            "valores": {
                "glucosa": 110.0
            }
        })
        assert respuesta.status_code == 200
        data = respuesta.json()
        assert data["resumen_general"] == "Valores analíticos interpretados correctamente."
        assert "glucosa" in data["marcadores"]
        assert data["requiere_atencion_medica"] is False

    app.dependency_overrides.clear()


def test_subir_archivo_pdf_ok():
    """Prueba subir un archivo de analítica y obtener el análisis."""
    app.dependency_overrides[get_current_user] = lambda: dummy_user
    
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    app.dependency_overrides[get_db] = lambda: mock_db
    
    mock_agent_response = {
        "resumen_general": "Valores analíticos interpretados correctamente.",
        "marcadores": {
            "ldl": {
                "valor": 165.0,
                "estado": "elevado",
                "explicacion": "LDL alto.",
                "accion_nutricional": "Reducir grasas saturadas"
            }
        },
        "alertas": [
            {
                "marcador": "ldl",
                "severidad": "moderada",
                "mensaje": "LDL elevado"
            }
        ],
        "recomendaciones_nutricionales": ["Aumentar fibra"],
        "notas_para_dietista": "Menos grasas saturadas",
        "requiere_atencion_medica": False,
        "motivo_atencion_medica": None
    }
    
    # Crear un PDF de prueba vacío en memoria
    import io
    pdf_content = b"%PDF-1.4 ... dummy pdf content ..."
    file_payload = {"archivo": ("analitica.pdf", io.BytesIO(pdf_content), "application/pdf")}
    
    with patch("backend.api.routers.clinical.extraer_texto_analitica", return_value="colesterol total 240, ldl 165"), \
         patch("backend.api.routers.clinical.parsear_valores_analitica", return_value={"ldl": 165.0}), \
         patch("backend.agents.clinical_agent.ClinicalAgent.analizar", return_value=mock_agent_response):
        
        respuesta = client.post("/analitica/subir-archivo", files=file_payload)
        assert respuesta.status_code == 200
        data = respuesta.json()
        assert "ldl" in data["marcadores"]
        assert data["marcadores"]["ldl"]["valor"] == 165.0
        
    app.dependency_overrides.clear()
