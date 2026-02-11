"""
Configuração do banco de dados
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import os

# URL do banco de dados
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:b2ad156f04d4203f02f3@n8n_postgres:5432/ConBank")

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
