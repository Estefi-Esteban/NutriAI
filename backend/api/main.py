from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routers import chat, planes, lista_compra, usuarios, auth

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

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(planes.router)
app.include_router(lista_compra.router)
app.include_router(usuarios.router)

@app.get("/")
def root():
    return {"status": "ok", "mensaje": "NutriAI API funcionando 🥗"}
