from fastapi import FastAPI
from sqlalchemy import text

from app.database import engine

app = FastAPI(
    title="Finance AI Planing",
    version="0.1.0",
)

@app.get("/")
def root():
    return {
        "name": "Finance AI Planing",
        "status": "running",
    }


@app.get("/health")
def health():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

        pgvector_installed = connection.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')"
            )
        ).scalar()

    return {
        "status": "healthy",
        "database:": "connected",
        "pgvector": bool(pgvector_installed),
    }

