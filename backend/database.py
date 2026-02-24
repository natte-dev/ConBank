"""
Configuração do banco de dados — SQLAlchemy 2.x
"""
import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# DATABASE_URL — obrigatória em produção.
# Configure no EasyPanel → App → Environment → DATABASE_URL
# Formato: postgresql://usuario:senha@host:5432/nome_do_banco
# -----------------------------------------------------------------------------
DATABASE_URL: str = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    logger.error(
        "\n"
        "╔══════════════════════════════════════════════════════════╗\n"
        "║  ERRO: DATABASE_URL não definida!                        ║\n"
        "║  Configure no EasyPanel → App → Environment              ║\n"
        "║  Formato: postgresql://user:pass@host:5432/conbank        ║\n"
        "╚══════════════════════════════════════════════════════════╝"
    )

# Engine com pool configurado para single-worker (uvicorn --workers 1)
# pool_pre_ping: testa a conexão antes de usá-la (detecta reconexão após idle)
engine = create_engine(
    DATABASE_URL or "postgresql+psycopg2://noop:noop@localhost/noop",
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    FastAPI dependency — abre sessão e garante fechamento ao fim da request.
    Levanta 503 imediatamente se DATABASE_URL não estiver configurada.
    """
    if not DATABASE_URL:
        raise HTTPException(
            status_code=503,
            detail="Banco de dados não configurado. Defina DATABASE_URL.",
        )
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Cria todas as tabelas declaradas nos models (idempotente — usa CREATE IF NOT EXISTS).
    Chamado no startup do FastAPI via lifespan.
    Silencioso se DATABASE_URL não estiver definida.
    """
    if not DATABASE_URL:
        logger.warning("init_db ignorado: DATABASE_URL não configurada.")
        return

    from models import Base
    Base.metadata.create_all(bind=engine)

    # Valida que a conexão realmente funciona
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    logger.info("✅ Banco de dados: tabelas verificadas/criadas, conexão OK.")
