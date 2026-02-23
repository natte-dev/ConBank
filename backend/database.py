"""
Configuração do banco de dados
"""
import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DATABASE_URL — obrigatória em produção, lida de variável de ambiente.
# Formato: postgresql://usuario:senha@host:porta/database
#
# Configure no EasyPanel → seu projeto → Environment → DATABASE_URL
# ---------------------------------------------------------------------------
DATABASE_URL: str = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    logger.error(
        "DATABASE_URL não definida! O backend vai subir mas o banco não funcionará.\n"
        "Configure: EasyPanel → Environment → DATABASE_URL\n"
        "Formato:   postgresql://usuario:senha@host:5432/conbank"
    )

# ---------------------------------------------------------------------------
# Engine — criada de forma lazy (só conecta ao banco quando executar a 1ª query)
# pool_pre_ping: descarta conexões mortas automaticamente
# pool_size / max_overflow: dimensionado para uvicorn single-worker
# ---------------------------------------------------------------------------
_engine_url = DATABASE_URL or "postgresql+psycopg2://noop:noop@localhost/noop"

engine = create_engine(
    _engine_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency — fornece sessão de banco e fecha ao final."""
    if not DATABASE_URL:
        raise HTTPException(
            status_code=503,
            detail="Banco de dados não configurado. Defina DATABASE_URL no ambiente.",
        )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Cria todas as tabelas (idempotente — nunca apaga dados existentes)."""
    if not DATABASE_URL:
        logger.warning("init_db ignorado: DATABASE_URL não configurada.")
        return
    from models import Base
    Base.metadata.create_all(bind=engine)
    logger.info("Tabelas verificadas/criadas com sucesso.")
