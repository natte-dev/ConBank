"""
API FastAPI para o sistema de conciliação de fornecedores
"""
import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import io

from database import get_db, init_db
from models import (
    ArquivoImportado, Fornecedor, LancamentoFornecedor,
    ConciliacaoInterna, Divergencia
)
from parser import parsear_arquivo_razao, calcular_hash_arquivo
from decimal import Decimal
from conciliacao_intel import conciliar_todos_fornecedores_inteligente
from consolidador import (
    consolidar_lancamentos_fornecedor,
    consolidar_todos_fornecedores
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CORS — configurável por env em produção
# Ex: ALLOWED_ORIGINS="https://meuapp.easypanel.host"
# ---------------------------------------------------------------------------
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
CORS_ORIGINS: list = [o.strip() for o in _raw_origins.split(",") if o.strip()]


# ---------------------------------------------------------------------------
# Lifespan — substitui @app.on_event("startup") depreciado no FastAPI >= 0.93
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("✅ Banco de dados inicializado")
    yield
    # shutdown — SQLAlchemy cuida do pool automaticamente


# Criar aplicação — única instância com lifespan
app = FastAPI(
    title="Sistema de Conciliação de Fornecedores",
    description="API para conciliação interna de contas a pagar",
    version="1.0.0",
    lifespan=lifespan,
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Endpoint raiz"""
    return {
        "message": "Sistema de Conciliação de Fornecedores",
        "version": "1.0.0",
        "status": "online"
    }


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check — verifica conectividade com o banco (SQLAlchemy 2.x)"""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={"status": "unhealthy", "error": str(e)}
        )


# ==================== UPLOAD E PROCESSAMENTO ====================

@app.post("/upload")
async def upload_arquivo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload e processamento do arquivo PDF/ZIP do Razão de Fornecedores
    """
    try:
        # Ler conteúdo do arquivo
        conteudo = await file.read()
        
        # Calcular hash
        hash_arquivo = calcular_hash_arquivo(conteudo)
        
        # Verificar se já foi importado
        arquivo_existente = db.query(ArquivoImportado).filter(
            ArquivoImportado.hash_arquivo == hash_arquivo
        ).first()
        
        if arquivo_existente:
            raise HTTPException(
                status_code=400,
                detail="Arquivo já foi importado anteriormente"
            )
        
        # Criar registro do arquivo
        arquivo = ArquivoImportado(
            nome_arquivo=file.filename,
            hash_arquivo=hash_arquivo,
            status="PROCESSANDO"
        )
        db.add(arquivo)
        db.commit()
        db.refresh(arquivo)

        
        
        try:
            # Parsear arquivo
            dados = parsear_arquivo_razao(conteudo)

            print("🔧 Consolidando lançamentos...")
            dados = consolidar_todos_fornecedores(dados)

            def converter_data_br(data_valor):
                """Converte data do formato DD/MM/YYYY para datetime, ou retorna datetime se já for"""
                if not data_valor:
                    return None
                # Se já for datetime, retorna direto
                if isinstance(data_valor, datetime):
                    return data_valor
                # Se for string, converte
                try:
                    return datetime.strptime(str(data_valor), "%d/%m/%Y")
                except:
                    return None
            
            # Atualizar informações do arquivo COM CONVERSÃO DE DATAS
            arquivo.data_inicio = converter_data_br(dados.get('periodo_inicio'))
            arquivo.data_fim = converter_data_br(dados.get('periodo_fim'))
            arquivo.empresa = dados.get('empresa')
            arquivo.cnpj_empresa = dados.get('cnpj')
            arquivo.total_fornecedores = dados.get('total_fornecedores', len(dados['fornecedores']))
            
            # Calcular total de lançamentos
            total_lanc = dados.get('total_lancamentos', sum(len(f.get('lancamentos', [])) for f in dados['fornecedores']))
            arquivo.total_lancamentos = total_lanc
            
            # Inserir fornecedores e lançamentos
            print(f"💾 Inserirndo {len(dados['fornecedores'])} fornecedores...")
            for idx, forn_data in enumerate(dados['fornecedores'], 1):
                
                if idx % 20 == 0: #Mostrar progresso a cada 20
                    print(f"   Processados {idx} de {len(dados['fornecedores'])} fornecedores...")

                try:            
                    # Converter valores para Decimal antes de calcular
                    saldo_anterior = Decimal(str(forn_data.get('saldo_anterior', 0)))
                    total_credito = Decimal(str(forn_data.get('total_credito', 0)))
                    total_debito = Decimal(str(forn_data.get('total_debito', 0)))
                    
                    fornecedor = Fornecedor(
                        arquivo_origem_id=arquivo.id,
                        codigo_conta=forn_data['codigo_conta'],
                        conta_contabil=forn_data['conta_contabil'],
                        nome_fornecedor=forn_data['nome_fornecedor'],
                        saldo_anterior=saldo_anterior,
                        saldo_anterior_tipo=forn_data.get('saldo_anterior_tipo', ''),
                        total_debito=total_debito,
                        total_credito=total_credito,
                        saldo_final=saldo_anterior + total_credito - total_debito
                    )
                    db.add(fornecedor)
                    db.flush()  # Para obter o ID
                
                    # Inserir lançamentos
                    for lanc_data in forn_data.get('lancamentos', []):
                        # Converter valores para Decimal
                        valor_debito = Decimal(str(lanc_data['valor_debito']))
                        valor_credito = Decimal(str(lanc_data['valor_credito']))
                        saldo_apos = Decimal(str(lanc_data['saldo_apos_lancamento']))
                        
                        lancamento = LancamentoFornecedor(
                            fornecedor_id=fornecedor.id,
                            data_lancamento=lanc_data['data_lancamento'],
                            lote=lanc_data.get('lote'),
                            historico=lanc_data['historico'],
                            conta_partida=lanc_data.get('conta_partida'),
                            valor_debito=valor_debito,
                            valor_credito=valor_credito,
                            saldo_apos_lancamento=saldo_apos,
                            saldo_tipo=lanc_data.get('saldo_tipo', ''),
                            tipo_operacao=lanc_data['tipo_operacao'],
                            numero_nf=lanc_data.get('numero_nf'),
                            cnpj_historico=lanc_data.get('cnpj_historico'),
                            valor_saldo=valor_credito if lanc_data['tipo_operacao'] == 'COMPRA' else Decimal("0")
                        )
                        db.add(lancamento)

                except Exception as e:
                    print(f"❌ Erro ao salvar fornecedor {idx} ({forn_data.get('codigo_conta')})")
                    import traceback
                    traceback.print_exc()
                    raise

            print(f"✅ {len(dados['fornecedores'])} fornecedores inseridos")
            db.commit()
            print("✅ Dados salvos no banco de dados")

            # Executar conciliação inteligente
            print("🔄 Iniciando conciliação inteligente...")
            conciliar_todos_fornecedores_inteligente(db, arquivo.id)

            # Atualizar status dos fornecedores
            fornecedores_salvos = db.query(Fornecedor).filter(
                Fornecedor.arquivo_origem_id == arquivo.id
            ).all()

            for forn in fornecedores_salvos:
                # Cálculo direto: compras - pagamentos
                forn.valor_a_pagar = forn.total_credito - forn.total_debito
                
                # Atualizar status baseado no saldo real
                if abs(forn.valor_a_pagar) <= Decimal("0.01"):
                    forn.status_pagamento = 'QUITADO'
                elif forn.valor_a_pagar < 0:
                    forn.status_pagamento = 'ADIANTADO'
                else:
                    forn.status_pagamento = 'EM_ABERTO'

            db.commit()
            print(f"✅ Status e valores atualizados para {len(fornecedores_salvos)} fornecedores")

            # Atualizar status do arquivo
            arquivo.status = "CONCLUIDO"
            db.commit()

            return {
                "success": True,
                "arquivo_id": arquivo.id,
                "message": "Arquivo processado com sucesso",
                "dados": {
                    "total_fornecedores": arquivo.total_fornecedores,
                    "total_lancamentos": arquivo.total_lancamentos,
                    "periodo_inicio": arquivo.data_inicio.isoformat() if arquivo.data_inicio else None,
                    "periodo_fim": arquivo.data_fim.isoformat() if arquivo.data_fim else None
                },
            }
            
        except Exception as e:
            print("=" * 80)
            print("❌ ERRO DURANTE PROCESSAMENTO:")
            print("=" * 80)
            import traceback
            traceback.print_exc()
            print("=" * 80)

            arquivo.status = "ERRO"
            arquivo.mensagem_erro = str(e)
            db.commit()
            raise HTTPException(status_code=500, detail=f"Erro ao processar arquivo: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== CONSULTAS ====================

@app.get("/arquivos")
async def listar_arquivos(db: Session = Depends(get_db)):
    """Lista todos os arquivos importados"""
    arquivos = db.query(ArquivoImportado).order_by(
        ArquivoImportado.created_at.desc()
    ).all()
    
    return [{
        "id": arq.id,
        "nome_arquivo": arq.nome_arquivo,
        "status": arq.status,
        "total_fornecedores": arq.total_fornecedores,
        "total_lancamentos": arq.total_lancamentos,
        "periodo_inicio": arq.data_inicio.isoformat() if arq.data_inicio else None,
        "periodo_fim": arq.data_fim.isoformat() if arq.data_fim else None,
        "created_at": arq.created_at.isoformat()
    } for arq in arquivos]


@app.get("/resumo/{arquivo_id}")
async def obter_resumo(arquivo_id: int, db: Session = Depends(get_db)):
    """Obtém resumo geral de um arquivo"""
    arquivo = db.query(ArquivoImportado).filter(
        ArquivoImportado.id == arquivo_id
    ).first()
    
    if not arquivo:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    # Estatísticas gerais
    fornecedores = db.query(Fornecedor).filter(
        Fornecedor.arquivo_origem_id == arquivo_id
    ).all()
    
    quitados = len([f for f in fornecedores if f.status_pagamento == 'QUITADO'])
    em_aberto = len([f for f in fornecedores if f.status_pagamento == 'EM_ABERTO'])
    adiantados = len([f for f in fornecedores if f.status_pagamento == 'ADIANTADO'])
    com_divergencia = len([f for f in fornecedores if f.divergencia_calculo])
    
    valor_total_a_pagar = sum(f.valor_a_pagar or 0 for f in fornecedores)
    
    return {
        "arquivo": {
            "id": arquivo.id,
            "nome": arquivo.nome_arquivo,
            "periodo_inicio": arquivo.data_inicio.isoformat() if arquivo.data_inicio else None,
            "periodo_fim": arquivo.data_fim.isoformat() if arquivo.data_fim else None
        },
        "estatisticas": {
            "total_fornecedores": len(fornecedores),
            "total_lancamentos": arquivo.total_lancamentos,
            "fornecedores_quitados": quitados,
            "fornecedores_em_aberto": em_aberto,
            "fornecedores_adiantados": adiantados,
            "fornecedores_com_divergencia": com_divergencia,
            "valor_total_a_pagar": float(valor_total_a_pagar)
        }
    }


@app.get("/fornecedores")
async def listar_fornecedores(
    arquivo_id: int,
    status: Optional[str] = None,
    tem_parciais: Optional[bool] = Query(None, description="Filtrar fornecedores com NFs parcialmente pagas"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Lista fornecedores com filtros
    
    Parâmetros:
    - arquivo_id: ID do arquivo importado
    - status: Status geral (QUITADO, EM_ABERTO, ADIANTADO)
    - tem_parciais: Se True, retorna apenas fornecedores com NFs parciais
    - skip, limit: Paginação
    """
    query = db.query(Fornecedor).filter(
        Fornecedor.arquivo_origem_id == arquivo_id
    )
    
    if status:
        query = query.filter(Fornecedor.status_pagamento == status)
    
    # Filtro por NFs parciais
    if tem_parciais is True:
        query = query.filter(Fornecedor.qtd_nfs_parciais > 0)
    elif tem_parciais is False:
        query = query.filter(Fornecedor.qtd_nfs_parciais == 0)
    
    total = query.count()
    fornecedores = query.order_by(
        Fornecedor.valor_a_pagar.desc()
    ).offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "fornecedores": [{
            "id": f.id,
            "codigo_conta": f.codigo_conta,
            "conta_contabil": f.conta_contabil,
            "nome_fornecedor": f.nome_fornecedor,
            "total_credito": float(f.total_credito or 0),
            "total_debito": float(f.total_debito or 0),
            "saldo_final": float(f.saldo_final or 0),
            "valor_a_pagar": float(f.valor_a_pagar or 0),
            "status_pagamento": f.status_pagamento,
            "qtd_nfs_pendentes": f.qtd_nfs_pendentes,
            "qtd_nfs_parciais": f.qtd_nfs_parciais,
            "divergencia_calculo": f.divergencia_calculo
        } for f in fornecedores]
    }


@app.get("/fornecedores/{fornecedor_id}")
async def obter_fornecedor_detalhado(
    fornecedor_id: int,
    db: Session = Depends(get_db)
):
    """Obtém detalhes completos de um fornecedor"""
    fornecedor = db.query(Fornecedor).filter(
        Fornecedor.id == fornecedor_id
    ).first()
    
    if not fornecedor:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado")
    
    # Buscar lançamentos
    lancamentos = db.query(LancamentoFornecedor).filter(
        LancamentoFornecedor.fornecedor_id == fornecedor_id
    ).order_by(LancamentoFornecedor.data_lancamento).all()
    
    # Separar compras e pagamentos
    compras = [l for l in lancamentos if l.tipo_operacao == 'COMPRA']
    pagamentos = [l for l in lancamentos if l.tipo_operacao == 'PAGAMENTO']
    
    # Compras não quitadas
    compras_pendentes = [c for c in compras if c.valor_saldo > 0]
    
    return {
        "fornecedor": {
            "id": fornecedor.id,
            "codigo_conta": fornecedor.codigo_conta,
            "conta_contabil": fornecedor.conta_contabil,
            "nome_fornecedor": fornecedor.nome_fornecedor,
            "cnpj": fornecedor.cnpj,
            "saldo_anterior": float(fornecedor.saldo_anterior or 0),
            "total_credito": float(fornecedor.total_credito or 0),
            "total_debito": float(fornecedor.total_debito or 0),
            "saldo_final": float(fornecedor.saldo_final or 0),
            "valor_a_pagar": float(fornecedor.valor_a_pagar or 0),
            "status_pagamento": fornecedor.status_pagamento,
            "divergencia_calculo": fornecedor.divergencia_calculo
        },
        "compras_pendentes": [{
            "id": c.id,
            "data_lancamento": c.data_lancamento.isoformat() if c.data_lancamento else None,
            "numero_nf": c.numero_nf,
            "historico": c.historico,
            "valor_total": float(c.valor_credito),
            "valor_pago_parcial": float(c.valor_pago_parcial or 0),
            "valor_saldo": float(c.valor_saldo or 0),
            "status_pagamento": c.status_pagamento
        } for c in compras_pendentes],
        "todos_lancamentos": [{
            "id": l.id,
            "data": l.data_lancamento.isoformat() if l.data_lancamento else None,
            "lote": l.lote,
            "historico": l.historico,
            "tipo_operacao": l.tipo_operacao,
            "valor_debito": float(l.valor_debito or 0),
            "valor_credito": float(l.valor_credito or 0),
            "saldo_apos": float(l.saldo_apos_lancamento or 0)
        } for l in lancamentos]
    }


@app.get("/divergencias")
async def listar_divergencias(
    arquivo_id: int,
    db: Session = Depends(get_db)
):
    """Lista todas as divergências encontradas"""
    divergencias = db.query(Divergencia).join(Fornecedor).filter(
        Fornecedor.arquivo_origem_id == arquivo_id,
        Divergencia.resolvido.is_(False)
    ).all()
    
    return [{
        "id": d.id,
        "fornecedor_id": d.fornecedor_id,
        "tipo": d.tipo,
        "severidade": d.severidade,
        "descricao": d.descricao,
        "diferenca": float(d.diferenca or 0),
        "created_at": d.created_at.isoformat()
    } for d in divergencias]


@app.get("/export/excel/{arquivo_id}")
async def exportar_excel(
    arquivo_id: int,
    tipo: str = Query("completo", pattern="^(completo|em_aberto|divergencias)$"),
    db: Session = Depends(get_db)
):
    """Exporta dados para Excel"""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    
    arquivo = db.query(ArquivoImportado).filter(
        ArquivoImportado.id == arquivo_id
    ).first()
    
    if not arquivo:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    # Criar workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Conciliação Fornecedores"
    
    # Cabeçalho
    headers = [
        "Código", "Conta Contábil", "Fornecedor", "CNPJ",
        "Total Compras", "Total Pagamentos", "Saldo a Pagar",
        "Status", "NFs Pendentes", "Divergência"
    ]
    
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        cell.font = Font(color="FFFFFF", bold=True)
    
    # Buscar dados
    query = db.query(Fornecedor).filter(Fornecedor.arquivo_origem_id == arquivo_id)
    
    if tipo == "em_aberto":
        query = query.filter(Fornecedor.status_pagamento == 'EM_ABERTO')
    elif tipo == "divergencias":
        query = query.filter(Fornecedor.divergencia_calculo == True)
    
    fornecedores = query.order_by(Fornecedor.valor_a_pagar.desc()).all()
    
    # Preencher dados
    for row, forn in enumerate(fornecedores, start=2):
        ws.cell(row=row, column=1, value=forn.codigo_conta)
        ws.cell(row=row, column=2, value=forn.conta_contabil)
        ws.cell(row=row, column=3, value=forn.nome_fornecedor)
        ws.cell(row=row, column=4, value=forn.cnpj)
        ws.cell(row=row, column=5, value=float(forn.total_credito or 0))
        ws.cell(row=row, column=6, value=float(forn.total_debito or 0))
        ws.cell(row=row, column=7, value=float(forn.valor_a_pagar or 0))
        ws.cell(row=row, column=8, value=forn.status_pagamento)
        ws.cell(row=row, column=9, value=forn.qtd_nfs_pendentes)
        ws.cell(row=row, column=10, value="Sim" if forn.divergencia_calculo else "Não")
    
    # Ajustar largura das colunas
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 20
    
    # Salvar em memória
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=conciliacao_fornecedores_{tipo}.xlsx"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)