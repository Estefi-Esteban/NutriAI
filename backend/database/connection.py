from backend.config import database_url
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

url = make_url(database_url)

if url.drivername == "postgresql":
    url = url.set(drivername="postgresql+psycopg2")

engine = create_engine(
    url,
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
