from backend.config import database_url
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(
    database_url,
    connect_args={
        "connect_timeout": 5,
        "options": "-c statement_timeout=5000"
    }
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

