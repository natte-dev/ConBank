"""
Configuração do banco de dados
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# URL do banco de dados — DEVE ser definida via variável de ambiente em produção
# Formato: postgresql://usuario:senha@host:porta/database
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "Variável de ambiente DATABASE_URL não definida. "
        "Exemplo: postgresql://user:pass@host:5432/conbank"
    )

# Criar engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency para obter sessão do banco"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Inicializa o banco de dados criando todas as tabelas"""
    from models import Base
    Base.metadata.create_all(bind=engine)
