from dotenv import load_dotenv
import os

load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")
database_url = os.getenv("DATABASE_URL")
chroma_path = os.getenv("CHROMA_PATH")