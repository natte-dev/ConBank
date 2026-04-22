"""
Modelos de dados para o sistema de conciliação de fornecedores
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, Date, ForeignKey, Text, Index
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class ArquivoImportado(Base):
    """Arquivo PDF importado"""
    __tablename__ = "arquivo_importado"
    
    id = Column(Integer, primary_key=True, index=True)
    nome_arquivo = Column(String(255), nullable=False)
    hash_arquivo = Column(String(64), unique=True, nullable=False)
    empresa = Column(String(255))
    cnpj_empresa = Column(String(18))
    total_fornecedores = Column(Integer, default=0)
    total_lancamentos = Column(Integer, default=0)
    data_inicio = Column(Date)
    data_fim = Column(Date)
    status = Column(String(20), default="PROCESSANDO")  # PROCESSANDO, CONCLUIDO, ERRO
    mensagem_erro = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    fornecedores = relationship("Fornecedor", back_populates="arquivo_origem")


class Fornecedor(Base):
    """Conta de fornecedor (contas a pagar)"""
    __tablename__ = "fornecedor"
    
    id = Column(Integer, primary_key=True, index=True)
    arquivo_origem_id = Column(Integer, ForeignKey("arquivo_importado.id"))
    
    # Identificação
    codigo_conta = Column(String(10), nullable=False)
    conta_contabil = Column(String(50), nullable=False)
    nome_fornecedor = Column(Text, nullable=False)
    cnpj = Column(String(18))
    
    # Saldos
    saldo_anterior = Column(Numeric(15, 2), default=0)
    saldo_anterior_tipo = Column(String(1))  # 'C' = Credor, 'D' = Devedor
    total_debito = Column(Numeric(15, 2), default=0)
    total_credito = Column(Numeric(15, 2), default=0)
    saldo_final = Column(Numeric(15, 2), default=0)
    saldo_final_tipo = Column(String(1))
    
    # Análise
    status_pagamento = Column(String(20))  # QUITADO, EM_ABERTO, ADIANTADO
    valor_a_pagar = Column(Numeric(15, 2), default=0)
    qtd_nfs_pendentes = Column(Integer, default=0)
    qtd_nfs_parciais = Column(Integer, default=0)
    
    # Auditoria
    divergencia_calculo = Column(Boolean, default=False)
    mensagem_erro = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    arquivo_origem = relationship("ArquivoImportado", back_populates="fornecedores")
    lancamentos = relationship("LancamentoFornecedor", back_populates="fornecedor", cascade="all, delete-orphan")
    conciliacoes = relationship("ConciliacaoInterna", back_populates="fornecedor", cascade="all, delete-orphan")
    
    # Índices
    __table_args__ = (
        Index('idx_fornecedor_conta', 'codigo_conta', 'conta_contabil'),
        Index('idx_fornecedor_status', 'status_pagamento'),
    )


class LancamentoFornecedor(Base):
    """Lançamento individual no razão do fornecedor"""
    __tablename__ = "lancamento_fornecedor"
    
    id = Column(Integer, primary_key=True, index=True)
    fornecedor_id = Column(Integer, ForeignKey("fornecedor.id"), nullable=False)
    
    # Dados do lançamento
    data_lancamento = Column(Date, nullable=False)
    lote = Column(String(10))
    historico = Column(Text, nullable=False)
    conta_partida = Column(String(10))
    
    # Valores
    valor_debito = Column(Numeric(15, 2), default=0)
    valor_credito = Column(Numeric(15, 2), default=0)
    saldo_apos_lancamento = Column(Numeric(15, 2))
    saldo_tipo = Column(String(1))
    
    # Classificação
    tipo_operacao = Column(String(20))  # COMPRA, PAGAMENTO, DEVOLUCAO
    numero_nf = Column(String(50))
    cnpj_historico = Column(String(18))
    
    # Conciliação interna
    valor_pago_parcial = Column(Numeric(15, 2), default=0)
    valor_saldo = Column(Numeric(15, 2), default=0)
    status_pagamento = Column(String(20))  # PAGO, PARCIAL, PENDENTE

    # Auditoria de classificação
    classificado_por_ia = Column(Boolean, default=False, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    fornecedor = relationship("Fornecedor", back_populates="lancamentos")
    conciliacoes_credito = relationship("ConciliacaoInterna", 
                                        foreign_keys="ConciliacaoInterna.lancamento_credito_id",
                                        back_populates="lancamento_credito")
    conciliacoes_debito = relationship("ConciliacaoInterna",
                                      foreign_keys="ConciliacaoInterna.lancamento_debito_id", 
                                      back_populates="lancamento_debito")
    
    # Índices
    __table_args__ = (
        Index('idx_lancamento_fornecedor_data', 'fornecedor_id', 'data_lancamento'),
        Index('idx_lancamento_tipo', 'tipo_operacao'),
        Index('idx_lancamento_status', 'status_pagamento'),
        Index('idx_lancamento_nf', 'numero_nf'),
    )


class ConciliacaoInterna(Base):
    """Relacionamento entre créditos (compras) e débitos (pagamentos)"""
    __tablename__ = "conciliacao_interna"
    
    id = Column(Integer, primary_key=True, index=True)
    fornecedor_id = Column(Integer, ForeignKey("fornecedor.id"), nullable=False)
    lancamento_credito_id = Column(Integer, ForeignKey("lancamento_fornecedor.id"))
    lancamento_debito_id = Column(Integer, ForeignKey("lancamento_fornecedor.id"))
    
    valor_conciliado = Column(Numeric(15, 2), nullable=False)
    metodo_match = Column(String(20))  # AUTO_NF, AUTO_VALOR_EXATO, AUTO_FIFO, MANUAL
    confianca = Column(Integer)  # 0-100
    
    observacao = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    fornecedor = relationship("Fornecedor", back_populates="conciliacoes")
    lancamento_credito = relationship("LancamentoFornecedor", 
                                     foreign_keys=[lancamento_credito_id],
                                     back_populates="conciliacoes_credito")
    lancamento_debito = relationship("LancamentoFornecedor",
                                    foreign_keys=[lancamento_debito_id],
                                    back_populates="conciliacoes_debito")
    
    # Índices
    __table_args__ = (
        Index('idx_conciliacao_fornecedor', 'fornecedor_id'),
    )


class Divergencia(Base):
    """Registro de divergências encontradas"""
    __tablename__ = "divergencia"
    
    id = Column(Integer, primary_key=True, index=True)
    fornecedor_id = Column(Integer, ForeignKey("fornecedor.id"))
    lancamento_id = Column(Integer, ForeignKey("lancamento_fornecedor.id"))
    
    tipo = Column(String(50), nullable=False)  # DIVERGENCIA_SALDO, PAGAMENTO_SEM_COMPRA, etc
    severidade = Column(String(20))  # CRITICA, ALTA, MEDIA, BAIXA
    descricao = Column(Text, nullable=False)
    valor_esperado = Column(Numeric(15, 2))
    valor_encontrado = Column(Numeric(15, 2))
    diferenca = Column(Numeric(15, 2))
    
    resolvido = Column(Boolean, default=False)
    observacao_resolucao = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Índices
    __table_args__ = (
        Index('idx_divergencia_fornecedor', 'fornecedor_id'),
        Index('idx_divergencia_resolvido', 'resolvido'),
    )