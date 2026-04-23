"""
Parser para extrair dados do Razão de Fornecedores (PDF).
Estratégia: IA (GPT-4o-mini) por bloco de fornecedor como primário;
parser regex como fallback quando a IA não está disponível ou falha.
"""
import logging
import re
import zipfile
import tempfile
import os
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
import hashlib
import pdfplumber
from io import BytesIO

logger = logging.getLogger(__name__)


def calcular_hash_arquivo(arquivo_bytes: bytes) -> str:
    """Calcula hash SHA256 do arquivo para evitar duplicação"""
    return hashlib.sha256(arquivo_bytes).hexdigest()


def parse_valor(texto: str) -> Decimal:
    """
    Converte string de valor para Decimal
    Exemplos: "1.234,56" -> 1234.56, "460,00" -> 460.00
    """
    if not texto or texto.strip() == "":
        return Decimal("0")
    
    # Remove espaços e trata separadores brasileiros
    texto = texto.strip().replace(".", "").replace(",", ".")
    
    # Remove caracteres não numéricos exceto ponto e sinal negativo
    texto = re.sub(r'[^\d.-]', '', texto)
    
    try:
        return Decimal(texto)
    except:
        return Decimal("0")


def parse_data(texto: str) -> Optional[datetime]:
    """
    Converte string de data para datetime
    Exemplo: "31/01/2025" -> datetime(2025, 1, 31)
    """
    try:
        return datetime.strptime(texto.strip(), "%d/%m/%Y")
    except:
        return None


def extrair_numero_nf(historico: str) -> Optional[str]:
    """
    Extrai número de NF/CT-e do histórico
    Exemplos:
    - "CONFORME NF. Nº 292065" -> "292065"
    - "PGTO REF NF 6137" -> "6137"
    - "PGTO REF REF 6137" -> "6137"
    - "NF 5346" -> "5346"
    - "21100 - F I CALDEIRARIA" -> "21100"
    """
    patterns = [
        r'NF\.?\s*N[oºº°]?\s*(\d+)',        # NF. Nº 292065, NF Nº 6137
        r'NF\s+(\d+)',                       # NF 5346
        r'REF\s+(?:REF\s+)?NF\s+(\d+)',     # REF NF 6137, REF REF NF 6137
        r'REF\s+(?:REF\s+)?(\d+)',          # REF 6137, REF REF 6137 (sem NF)
        r'CT-E\s*(\d+)',                     # CT-E 12345
        r'NOTA\s*FISCAL\s*(\d+)',            # NOTA FISCAL 12345
        r'CONFORME\s+NF[.\s]*(\d+)',        # CONFORME NF 12345
        r'^(\d{5,6})\s*-',                   # Número no início: "292065 - LOTUS"
        r'CONFORME\s+NF\s+N[ÚU]MERO\s+(\d+)',    # CONFORME NÚMERO 12345
        r'CONF\.\s*NFS\s*(\d+)', #CONF. NFS 12345GOOGLE
        ]
    
    for pattern in patterns:
        match = re.search(pattern, historico, re.IGNORECASE)
        if match:
            nf_num = match.group(1)
            # Validar se é um número de NF válido (4-6 dígitos)
            if len(nf_num) >= 4:
                return nf_num
    
    return None


def extrair_cnpj(historico: str) -> Optional[str]:
    """Extrai CNPJ do histórico se presente"""
    pattern = r'(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})'
    match = re.search(pattern, historico)
    return match.group(1) if match else None


def classificar_tipo_operacao(historico: str, valor_debito: Decimal, valor_credito: Decimal) -> str:
    """
    Classifica o tipo de operação baseado no histórico e valores
    
    REGRAS:
    - PAGAMENTO: Débito com palavras-chave específicas
    - COMPRA: Crédito com palavras-chave de aquisição
    - ADIANTAMENTO: Crédito explícito de adiantamento
    """
    historico_upper = historico.upper()
    
    if valor_debito > 0:
        # Débito = Pagamento ou Devolução
        if any(palavra in historico_upper for palavra in [
            "PGTO", "PAGAMENTO", "BAIXA", 
            "VLR REF", "VALOR REF"
        ]):
            return "PAGAMENTO"
        elif "DEVOLUCAO" in historico_upper or "ESTORNO" in historico_upper:
            return "DEVOLUCAO"
        else:
            return "DEBITO"
    
    elif valor_credito > 0:
        # Crédito = Compra ou Adiantamento
        if any(palavra in historico_upper for palavra in [
            "COMPRA", "NF", "NOTA FISCAL", "SERVICO", "SERVIÇO", 
            "CT-E", "ADQUIRIDO", "AQUISICAO", "AQUISIÇÃO", "CONFORME"
        ]):
            return "COMPRA"
        elif "ADTO" in historico_upper or "ADIANTAMENTO" in historico_upper:
            # ATENÇÃO: Este caso não deve acontecer mais, pois adiantamentos
            # agora são classificados como DÉBITO (pagamento antecipado)
            return "ADIANTAMENTO"
        else:
            return "CREDITO"
    
    return "OUTRO"


def parsear_lancamento_linha(linha: str) -> Optional[Dict]:
    """
    Parseia uma ÚNICA linha de lançamento
    
    LÓGICA CONTÁBIL DO RAZÃO:
    - Coluna DÉBITO = Pagamentos (reduz saldo devedor/credor)
    - Coluna CRÉDITO = Compras (aumenta saldo credor)
    
    Formatos esperados:
    1. DÉBITO (pagamento):
       31/01/2025 3825 PGTO REF BDG TRANSPORTES 1336 460,00 0,00
       Formato: DATA LOTE HISTORICO CPC DEBITO SALDO
       
    2. CRÉDITO (compra):
       10/01/2025 9 COMPRAS CONFORME NF. Nº 21100 55 4.524,08 8.654,11C
       Formato: DATA LOTE HISTORICO CPC CREDITO SALDO
       
    3. Sem CPC:
       08/01/2025 4 COMPRAS CONFORME NF. 292065 1.994,40 1.994,40C
       Formato: DATA LOTE HISTORICO CREDITO SALDO
    """
    # Verificar se começa com data
    match_inicio = re.match(r'^(\d{2}/\d{2}/\d{4})\s+(\d+)\s+(.+)$', linha)
    if not match_inicio:
        return None
    
    data_str = match_inicio.group(1)
    lote = match_inicio.group(2)
    resto = match_inicio.group(3)
    
    # Extrair todos os valores numéricos do final da linha
    valores = re.findall(r'[\d.,]+', resto)
    
    if len(valores) < 2:  # Precisa de pelo menos: valor + saldo
        return None
    
    # O último valor é SEMPRE o saldo
    saldo_str = valores[-1]
    saldo = parse_valor(saldo_str)
    
    # Detectar tipo de saldo (C ou D) olhando o texto após o número
    match_saldo_tipo = re.search(r'[\d.,]+([CD])', resto)
    saldo_tipo = match_saldo_tipo.group(1) if match_saldo_tipo else ''
    
    # Identificar CPC (conta de contrapartida)
    # CPC é um número curto (1-4 dígitos) que aparece antes do valor monetário
    cpc = None
    valor_monetario = None
    
    # Tentar identificar CPC
    # Padrão: "HISTORICO [CPC] VALOR SALDO"
    # CPC não tem pontos/vírgulas, VALOR tem
    
    # Pegar os últimos 2 valores antes do saldo
    if len(valores) >= 3:
        penultimo = valores[-2]  # Pode ser VALOR ou CPC
        antepenultimo = valores[-3]  # Pode ser CPC
        
        # Verificar se penúltimo é CPC (número pequeno sem formatação monetária)
        if ',' not in penultimo and '.' not in penultimo and len(penultimo) <= 4:
            cpc = penultimo
            valor_monetario = antepenultimo if len(valores) >= 4 else None
        else:
            # Penúltimo é o valor monetário
            valor_monetario = penultimo
            # Verificar se antepenúltimo é CPC
            if ',' not in antepenultimo and '.' not in antepenultimo and len(antepenultimo) <= 4:
                cpc = antepenultimo
    else:
        # Apenas 2 valores: VALOR SALDO
        valor_monetario = valores[-2]
    
    # Converter valor monetário
    valor = parse_valor(valor_monetario) if valor_monetario else Decimal("0")
    
    # CLASSIFICAR: É DÉBITO ou CRÉDITO?
    # REGRA: Analisar o histórico
    historico_upper = resto.upper()
    
    debito = Decimal("0")
    credito = Decimal("0")
    
    # Palavras-chave que indicam PAGAMENTO (débito)
    palavras_pagamento = [
        "PGTO", "PAGAMENTO", "BAIXA",
        "VLR REF", "VALOR REF",           # VLR REF IMPORTAÇÃO, VALOR REF ADIANTAMENTOS
        "ADTO", "ADIANTAMENTO",           # Adiantamentos
    ]
    
    if any(palavra in historico_upper for palavra in palavras_pagamento):
        # É um PAGAMENTO = DÉBITO
        debito = valor
    else:
        # É uma COMPRA/LANÇAMENTO = CRÉDITO
        credito = valor
    
    # Extrair histórico (remover valores numéricos do final)
    historico = resto
    
    # Remover os valores do final (valor monetário, CPC se existe, saldo)
    for val in [saldo_str, valor_monetario, cpc]:
        if val:
            # Substituir última ocorrência
            idx = historico.rfind(str(val))
            if idx != -1:
                historico = historico[:idx] + historico[idx + len(str(val)):]
    
    # Remover indicador C/D
    historico = re.sub(r'[CD]\s*$', '', historico)
    historico = historico.strip()
    
    return {
        'data_lancamento': parse_data(data_str),
        'lote': lote,
        'historico': historico,
        'conta_partida': cpc,
        'valor_debito': debito,
        'valor_credito': credito,
        'saldo_apos_lancamento': saldo,
        'saldo_tipo': saldo_tipo,
        'numero_nf': extrair_numero_nf(historico),
        'cnpj_historico': extrair_cnpj(historico),
        'tipo_operacao': classificar_tipo_operacao(historico, debito, credito)
    }


def parsear_fornecedor(linhas: List[str]) -> Optional[Dict]:
    """
    Parseia um bloco de linhas referente a um fornecedor
    """
    fornecedor = None
    lancamentos = []
    lancamento_atual = None
    historico_pendente = []  # Buffer de linhas antes da data
    
    for linha in linhas:
        linha = linha.strip()
        if not linha:
            continue
        
        # Detectar início de conta
        match_conta = re.match(r'Conta:\s*(\d+)\s*-\s*([\d.]+)\s+(.+)$', linha)
        if match_conta:
            fornecedor = {
                'codigo_conta': match_conta.group(1),
                'conta_contabil': match_conta.group(2),
                'nome_fornecedor': match_conta.group(3).strip(),
                'lancamentos': []
            }
            lancamento_atual = None
            historico_pendente = []
            continue
        
        if not fornecedor:
            continue
        
        # Detectar saldo anterior
        if 'SALDO ANTERIOR' in linha:
            match_saldo = re.search(r'([\d.,]+)(C|D)?', linha)
            if match_saldo:
                fornecedor['saldo_anterior'] = parse_valor(match_saldo.group(1))
                fornecedor['saldo_anterior_tipo'] = match_saldo.group(2) or ''
            historico_pendente = []  # Limpar buffer
            continue
        
        # Detectar total da conta
        if 'Total da conta:' in linha:
            match_total = re.search(r'([\d.,]+)\s+([\d.,]+)', linha)
            if match_total:
                fornecedor['total_debito'] = parse_valor(match_total.group(1))
                fornecedor['total_credito'] = parse_valor(match_total.group(2))
            break
        
        # Tentar parsear lançamento
        lancamento = parsear_lancamento_linha(linha)
        
        if lancamento:
            # Nova linha de lançamento
            if lancamento_atual:
                # Salvar lançamento anterior
                lancamentos.append(lancamento_atual)
            
            # APLICAR HISTÓRICO PENDENTE ao novo lançamento
            if historico_pendente:
                historico_pre = " ".join(historico_pendente).strip()
                lancamento['historico'] = historico_pre + " " + lancamento['historico']
                lancamento['numero_nf'] = extrair_numero_nf(lancamento['historico']) or lancamento['numero_nf']
                historico_pendente = []
            
            lancamento_atual = lancamento
        
        elif lancamento_atual and linha and not re.match(r'^\d{2}/\d{2}/\d{4}', linha):
            # Ignorar linhas que são apenas o nome do fornecedor repetido (ruído do PDF)
            nome_norm = re.sub(r'\s+', ' ', fornecedor.get('nome_fornecedor', '').upper().strip())
            linha_norm = re.sub(r'\s+', ' ', linha.upper().strip())
            if nome_norm and (linha_norm == nome_norm or linha_norm.startswith(nome_norm)):
                continue

            # Continuação do histórico APÓS data
            lancamento_atual['historico'] += " " + linha

            # Tentar extrair NF da linha continuação E do histórico acumulado
            nf_linha = extrair_numero_nf(linha)
            nf_historico = extrair_numero_nf(lancamento_atual['historico'])

            # Priorizar NF mais longa/completa
            if nf_historico:
                lancamento_atual['numero_nf'] = nf_historico
            elif nf_linha and not lancamento_atual['numero_nf']:
                lancamento_atual['numero_nf'] = nf_linha
        
        elif not lancamento_atual and linha and not re.match(r'^\d{2}/\d{2}/\d{4}', linha):
            # Linha sem data ANTES do primeiro lançamento = buffer para próximo lançamento
            historico_pendente.append(linha)
    
    # Salvar último lançamento
    if lancamento_atual:
        lancamentos.append(lancamento_atual)
    
    if fornecedor and lancamentos:
        # Atualizar tipo de operação e NF em todos os lançamentos
        for lanc in lancamentos:
            # Recalcular tipo com histórico completo
            tipo = classificar_tipo_operacao(
                lanc['historico'],
                lanc['valor_debito'],
                lanc['valor_credito']
            )
            lanc['tipo_operacao'] = tipo

            # Marcar como incerto quando o regex usou o catch-all
            historico_upper = lanc['historico'].upper()
            nf_esperada = (
                lanc.get('numero_nf') is None
                and lanc['valor_credito'] > 0
                and any(kw in historico_upper for kw in ("NF", "NOTA", "NUMERO"))
            )
            lanc['classificacao_incerta'] = tipo in ("DEBITO", "CREDITO", "OUTRO") or nf_esperada

            # SEMPRE re-extrair NF com histórico completo
            # (histórico pode conter NF em linha seguinte)
            nf_historico_completo = extrair_numero_nf(lanc['historico'])
            if nf_historico_completo:
                lanc['numero_nf'] = nf_historico_completo
        
        fornecedor['lancamentos'] = lancamentos
        return fornecedor
    
    return None


def extrair_texto_pdf(arquivo_bytes: bytes) -> str:
    """
    Extrai texto de um PDF usando pdfplumber
    """
    texto_completo = []
    
    try:
        with pdfplumber.open(BytesIO(arquivo_bytes)) as pdf:
            total_paginas = len(pdf.pages)
            
            print(f"📄 PDF detectado: {total_paginas} páginas")
            
            for i, pagina in enumerate(pdf.pages, 1):
                # layout=True preserves physical column positions, preventing
                # character interleaving when pdfplumber reads multi-column tables
                texto = pagina.extract_text(layout=True)
                if texto:
                    texto_completo.append(texto)
                
                if i % 10 == 0:
                    print(f"   Processadas {i}/{total_paginas} páginas...")
            
            print(f"✅ Extração concluída: {len(texto_completo)} páginas com texto")
    
    except Exception as e:
        raise ValueError(f"Erro ao extrair texto do PDF: {str(e)}")
    
    return "\n\n".join(texto_completo)


def detectar_formato_arquivo(arquivo_bytes: bytes) -> str:
    """
    Detecta se o arquivo é PDF ou ZIP
    Retorna: 'PDF' ou 'ZIP'
    """
    # Verificar assinatura do arquivo (magic numbers)
    if arquivo_bytes[:4] == b'%PDF':
        return 'PDF'
    elif arquivo_bytes[:2] == b'PK':  # ZIP
        return 'ZIP'
    else:
        # Tentar como ZIP primeiro
        if zipfile.is_zipfile(BytesIO(arquivo_bytes)):
            return 'ZIP'
        else:
            return 'PDF'


def consolidar_fornecedores_duplicados(fornecedores: List[Dict]) -> List[Dict]:
    """
    Consolida fornecedores com mesmo código de conta que foram quebrados entre páginas
    
    Quando um fornecedor aparece em múltiplas páginas, o pdfplumber cria múltiplas
    entradas com "Conta: XXXX". Esta função:
    1. Agrupa por código de conta
    2. Combina todos os lançamentos
    3. Usa o último "Total da conta:" (que é o acumulado final)
    """
    from collections import defaultdict
    
    # Agrupar por código de conta
    por_codigo = defaultdict(list)
    for forn in fornecedores:
        codigo = forn.get('codigo_conta')
        if codigo:
            por_codigo[codigo].append(forn)
    
    fornecedores_consolidados = []
    
    for codigo, lista_forn in por_codigo.items():
        if len(lista_forn) == 1:
            # Não há duplicação
            fornecedores_consolidados.append(lista_forn[0])
        else:
            # Há duplicação - consolidar
            print(f"   🔧 Consolidando {len(lista_forn)} registros do código {codigo} - {lista_forn[0]['nome_fornecedor']}")
            
            # Pegar o primeiro como base
            consolidado = lista_forn[0].copy()
            
            # Combinar todos os lançamentos
            todos_lancamentos = []
            for forn in lista_forn:
                todos_lancamentos.extend(forn.get('lancamentos', []))
            
            consolidado['lancamentos'] = todos_lancamentos
            
            # Usar os totais do ÚLTIMO registro (que tem o "Total da conta:" final)
            ultimo = lista_forn[-1]
            consolidado['total_debito'] = ultimo.get('total_debito', Decimal("0"))
            consolidado['total_credito'] = ultimo.get('total_credito', Decimal("0"))
            
            # Se tiver saldo_anterior, pegar do primeiro
            if 'saldo_anterior' in lista_forn[0]:
                consolidado['saldo_anterior'] = lista_forn[0]['saldo_anterior']
                consolidado['saldo_anterior_tipo'] = lista_forn[0].get('saldo_anterior_tipo', '')
            
            fornecedores_consolidados.append(consolidado)
    
    return fornecedores_consolidados


def _ia_decimal(val) -> Decimal:
    """Converte valor retornado pela IA para Decimal.
    Aceita float/int nativos do JSON ou strings em formato brasileiro ('1.234,56').
    """
    if val is None:
        return Decimal("0")
    if isinstance(val, (int, float)):
        return Decimal(str(val))
    s = str(val).strip().replace(" ", "")
    try:
        return Decimal(s)
    except Exception:
        # Tenta formato brasileiro: "1.234,56" → "1234.56"
        s = s.replace(".", "").replace(",", ".")
        try:
            return Decimal(s)
        except Exception:
            return Decimal("0")


def _ia_data(val) -> Optional[datetime]:
    """Converte data retornada pela IA para datetime.
    Aceita DD/MM/YYYY (brasileiro) e YYYY-MM-DD (ISO).
    """
    if not val:
        return None
    s = str(val).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _normalizar_lancamento_ia(lanc_ia: dict) -> Optional[Dict]:
    """Converte um lançamento retornado pelo GPT para o formato interno do parser."""
    try:
        data = _ia_data(lanc_ia.get("data"))
        if not data:
            return None

        vd = _ia_decimal(lanc_ia.get("valor_debito"))
        vc = _ia_decimal(lanc_ia.get("valor_credito"))
        saldo = _ia_decimal(lanc_ia.get("saldo_apos"))
        historico = (lanc_ia.get("historico") or "").strip()
        cpc = lanc_ia.get("conta_partida")
        cpc = str(cpc).strip() if cpc else None

        # Usar tipo retornado pela IA quando disponível; fallback para regex
        tipo_ia = (lanc_ia.get("tipo_operacao") or "").upper()
        if tipo_ia in ("COMPRA", "PAGAMENTO", "DEVOLUCAO", "DEBITO", "CREDITO", "OUTRO"):
            tipo = tipo_ia
        else:
            tipo = classificar_tipo_operacao(historico, vd, vc)

        nf = extrair_numero_nf(historico)
        cnpj = extrair_cnpj(historico)

        return {
            "data_lancamento": data,
            "lote": str(lanc_ia.get("lote", "") or ""),
            "historico": historico,
            "conta_partida": cpc,
            "valor_debito": vd,
            "valor_credito": vc,
            "saldo_apos_lancamento": saldo,
            "saldo_tipo": str(lanc_ia.get("saldo_tipo") or ""),
            "tipo_operacao": tipo,
            "numero_nf": nf,
            "cnpj_historico": cnpj,
            "classificacao_incerta": tipo in ("DEBITO", "CREDITO", "OUTRO"),
            "classificado_por_ia": True,
        }
    except Exception as exc:
        logger.warning("⚠️ _normalizar_lancamento_ia falhou: %s", exc)
        return None


def _construir_fornecedor_de_ia(dados_ia: dict, linhas: List[str]) -> Optional[Dict]:
    """
    Combina o header do fornecedor (extraído por regex da linha 'Conta:')
    com os dados financeiros retornados pela IA.
    """
    conta_match = None
    for linha in linhas:
        m = re.match(r"Conta:\s*(\d+)\s*-\s*([\d.]+)\s+(.+)$", linha.strip())
        if m:
            conta_match = m
            break

    if not conta_match:
        return None

    lancamentos = []
    for lanc_ia in dados_ia.get("lancamentos", []):
        normalizado = _normalizar_lancamento_ia(lanc_ia)
        if normalizado:
            lancamentos.append(normalizado)

    if not lancamentos:
        brutos = dados_ia.get("lancamentos", [])
        print(
            f"⚠️ IA: {len(brutos)} lançamentos brutos mas nenhum normalizou. "
            f"Primeiro: {brutos[0] if brutos else 'vazio'}"
        )
        return None

    print(
        f"✅ IA parseou bloco: {len(lancamentos)} lançamentos, "
        f"débito={float(dados_ia.get('total_debito') or 0):.2f}, "
        f"crédito={float(dados_ia.get('total_credito') or 0):.2f}"
    )

    return {
        "codigo_conta": conta_match.group(1),
        "conta_contabil": conta_match.group(2),
        "nome_fornecedor": conta_match.group(3).strip(),
        "saldo_anterior": _ia_decimal(dados_ia.get("saldo_anterior")),
        "saldo_anterior_tipo": str(dados_ia.get("saldo_anterior_tipo") or ""),
        "total_debito": _ia_decimal(dados_ia.get("total_debito")),
        "total_credito": _ia_decimal(dados_ia.get("total_credito")),
        "lancamentos": lancamentos,
    }


def parsear_arquivo_razao(arquivo_bytes: bytes) -> Dict:
    """
    Função principal que parseia todo o arquivo PDF
    """
    # Calcular hash
    hash_arquivo = calcular_hash_arquivo(arquivo_bytes)
    
    # Detectar formato do arquivo
    formato = detectar_formato_arquivo(arquivo_bytes)
    print(f"🔍 Formato detectado: {formato}")
    
    if formato != 'PDF':
        raise ValueError(
            f"Formato '{formato}' não suportado nesta versão. "
            "Este parser funciona apenas com PDFs que contenham texto extraível. "
            "Se você tem um ZIP ou imagens escaneadas, será necessário OCR."
        )
    
    # Extrair texto do PDF
    print("📖 Extraindo texto do PDF...")
    texto_completo = extrair_texto_pdf(arquivo_bytes)
    
    if not texto_completo or len(texto_completo) < 100:
        raise ValueError(
            "Não foi possível extrair texto do PDF. "
            "O arquivo pode estar vazio, corrompido ou ser uma imagem escaneada. "
            "Para imagens escaneadas, será necessário OCR."
        )
    
    print(f"✅ Texto extraído: {len(texto_completo)} caracteres")
    
    # Importação lazy para evitar dependência circular em testes
    from ai_classifier import parsear_bloco_fornecedor_ia

    # Processar o texto extraído
    fornecedores = []
    fornecedor_atual = []
    blocos_ia = 0
    blocos_regex = 0

    linhas = texto_completo.split('\n')

    def _processar_bloco(linhas_bloco: List[str]) -> None:
        nonlocal blocos_ia, blocos_regex
        if not linhas_bloco:
            return

        bloco_texto = '\n'.join(linhas_bloco)

        # Tentativa 1: parser IA
        dados_ia = parsear_bloco_fornecedor_ia(bloco_texto)
        if dados_ia:
            fornecedor = _construir_fornecedor_de_ia(dados_ia, linhas_bloco)
            if fornecedor:
                fornecedores.append(fornecedor)
                blocos_ia += 1
                return

        # Tentativa 2: parser regex (fallback)
        fornecedor = parsear_fornecedor(linhas_bloco)
        if fornecedor:
            fornecedores.append(fornecedor)
            blocos_regex += 1
        else:
            logger.warning(
                "⚠️ Bloco descartado (IA e regex falharam): %d linhas | primeiras: %s",
                len(linhas_bloco),
                linhas_bloco[:3],
            )

    for linha in linhas:
        linha = linha.strip()

        if linha.startswith('Conta:'):
            _processar_bloco(fornecedor_atual)
            fornecedor_atual = []

        fornecedor_atual.append(linha)

    _processar_bloco(fornecedor_atual)
    
    # CONSOLIDAR FORNECEDORES DUPLICADOS (quebrados entre páginas)
    print(f"📋 Total de registros antes da consolidação: {len(fornecedores)}")
    if len(fornecedores) > 0:
        fornecedores = consolidar_fornecedores_duplicados(fornecedores)

    # Extrair informações gerais
    empresa = "IRRIGA FOUR LTDA"
    cnpj = "49.636.189/0001-00"
    periodo_inicio = None
    periodo_fim = None
    
    # Buscar informações no texto
    match_periodo = re.search(r'(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})', texto_completo)
    if match_periodo:
        periodo_inicio = parse_data(match_periodo.group(1))
        periodo_fim = parse_data(match_periodo.group(2))
    
    # Buscar empresa e CNPJ
    match_empresa = re.search(r'Empresa:\s*(.+?)(?:\s+Folha:|\n)', texto_completo)
    if match_empresa:
        empresa = match_empresa.group(1).strip()
    
    match_cnpj = re.search(r'C\.N\.P\.J\.:\s*([\d./-]+)', texto_completo)
    if match_cnpj:
        cnpj = match_cnpj.group(1).strip()
    
    print(
        f"✅ Processamento concluído: {len(fornecedores)} fornecedores "
        f"(IA: {blocos_ia} | regex: {blocos_regex})"
    )
    
    return {
        'hash_arquivo': hash_arquivo,
        'empresa': empresa,
        'cnpj': cnpj,
        'periodo_inicio': periodo_inicio,
        'periodo_fim': periodo_fim,
        'total_fornecedores': len(fornecedores),
        'total_lancamentos': sum(len(f.get('lancamentos', [])) for f in fornecedores),
        'fornecedores': fornecedores
    }