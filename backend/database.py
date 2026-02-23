"""
Configuração do banco de dados
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
import os
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DATABASE_URL — obrigatória em produção, lida de variável de ambiente.
# Formato: postgresql://usuario:senha@host:porta/database
#
# NÃO colocar valor default com credenciais aqui.
# Configure no EasyPanel → Environment → DATABASE_URL
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    # Log claro para aparecer nos logs do EasyPanel
    logger.error(
        "DATABASE_URL não definida! "
        "Configure em: EasyPanel → seu projeto → Environment → DATABASE_URL\n"
        "Formato: postgresql://usuario:senha@host:5432/conbank"
    )
    # Não levanta RuntimeError aqui para não impedir o uvicorn de subir
    # O erro será reportado via /health quando o banco for acessado

# Engine criada com lazy connect (só conecta de fato quando executar query)
engine = create_engine(
    DATABASE_URL or "postgresql://placeholder:placeholder@localhost/placeholder",
    pool_pre_ping=True,   # re-testa conexão antes de usar do pool
    pool_size=5,
    max_overflow=10,
    echo=False,
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency — fornece sessão de banco e fecha ao final."""
    if not DATABASE_URL:
        raise HTTPException(
            status_code=503,
            detail="Banco de dados não configurado. Defina DATABASE_URL no ambiente."
        )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Cria todas as tabelas (idempotente — não apaga dados existentes)."""
    if not DATABASE_URL:
        logger.warning("init_db ignorado: DATABASE_URL não configurada.")
        return
    from models import Base
    Base.metadata.create_all(bind=engine)
    logger.info("Banco de dados inicializado (tabelas verificadas/criadas).")
