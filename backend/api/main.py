from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.utils.logging_config import configurar_logging
from backend.api.error_handlers import registrar_manejadores_error
from backend.api.routers import chat, planes, lista_compra, usuarios, auth, seguimiento, clinical, pathology, vision, supplements, assistant


# Configurar logging ANTES de crear la app
configurar_logging()

app = FastAPI(
    title="NutriAI API",
    description="API del sistema de nutrición personalizada con IA",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

registrar_manejadores_error(app)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(planes.router)
app.include_router(lista_compra.router)
app.include_router(usuarios.router)
app.include_router(seguimiento.router)
app.include_router(clinical.router)
app.include_router(pathology.router)
app.include_router(vision.router)
app.include_router(supplements.router)
app.include_router(assistant.router)


@app.get("/")
def root():
    return {"status": "ok", "mensaje": "NutriAI API funcionando 🥗"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/rag")
def health_rag():
    """
    Endpoint de diagnóstico del RAG.
    Úsalo para verificar que Qdrant Cloud está conectado y con datos.
    Ejemplo: GET https://tu-backend.railway.app/health/rag
    """
    from backend.rag.food_search import estado_rag
    return estado_rag()

