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

    # ── Migrations idempotentes — alarga colunas que cresceram ────────────────
    # Cada ALTER TABLE roda em transação própria com try/except em Python.
    # Isso é mais robusto que o bloco DO $$ que pode engolir erros silenciosamente.
    _migrations = [
        # lote: VARCHAR(10) → VARCHAR(50)  (lotes como '2500000002616' têm 13+ chars)
        (
            "lancamento_fornecedor.lote → VARCHAR(50)",
            "ALTER TABLE lancamento_fornecedor ALTER COLUMN lote TYPE VARCHAR(50)",
        ),
        # conta_partida: VARCHAR(10) → VARCHAR(20)
        (
            "lancamento_fornecedor.conta_partida → VARCHAR(20)",
            "ALTER TABLE lancamento_fornecedor ALTER COLUMN conta_partida TYPE VARCHAR(20)",
        ),
    ]

    # Valida conexão antes de iniciar as migrations
    with engine.begin() as conn:
        conn.execute(text("SELECT 1"))

    for desc, sql in _migrations:
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
            logger.info("✅ Migration aplicada: %s", desc)
        except Exception as exc:
            # Pode ocorrer se a coluna já tem o tamanho correto (no-op no Postgres)
            # ou se a tabela ainda não existe (primeiro boot sem DB).
            logger.info("ℹ️  Migration ignorada (%s): %s", desc, str(exc)[:120])

    logger.info("✅ Banco de dados: tabelas verificadas/criadas, migrations aplicadas, conexão OK.")
