from dotenv import load_dotenv
import os

load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")
database_url = os.getenv("DATABASE_URL")

# RAG vectorial — Qdrant Cloud
qdrant_url = os.getenv("QDRANT_URL")
qdrant_api_key = os.getenv("QDRANT_API_KEY")

# Seguridad y Autenticación
jwt_secret_key = os.getenv("JWT_SECRET_KEY")
jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
jwt_expire_minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))
google_client_id = os.getenv("GOOGLE_CLIENT_ID")

# Tesseract path config
TESSERACT_PATH = os.getenv("TESSERACT_PATH")
GROQ_API_KEY = groq_api_key

# PubMed API Key
PUBMED_API_KEY = os.getenv("PUBMED_API_KEY")
pubmed_api_key = PUBMED_API_KEY

