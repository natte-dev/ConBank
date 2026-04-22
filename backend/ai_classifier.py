"""
Módulo de IA para o parser de Razão de Fornecedores.

Duas responsabilidades:
1. parsear_bloco_fornecedor_ia() — parsing completo de um bloco de fornecedor
   via GPT-4o-mini, usado como substituto robusto ao parser regex.
2. classificar_lancamentos_incertos() — fallback secundário para lançamentos
   que o parser regex classificou como DEBITO/CREDITO/OUTRO genérico.
"""
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

TIPOS_INCERTOS = {"DEBITO", "CREDITO", "OUTRO"}

# ---------------------------------------------------------------------------
# Prompt principal — parsing de bloco completo
# ---------------------------------------------------------------------------
PARSE_SYSTEM_PROMPT = """Você é um parser especializado em Razão de Fornecedores (contabilidade brasileira).

Receberá o texto bruto de um bloco de fornecedor extraído de PDF. PDFs diferentes produzem formatos distintos — você deve reconhecer e tratar todos eles.

FORMATOS POSSÍVEIS:

Formato 1 — linha única (histórico junto com data):
  "10/01/2025 4 COMPRAS CONFORME NF. Nº 21100 55 4.524,08 8.654,11C"
  → data=10/01/2025, lote=4, historico="COMPRAS CONFORME NF. Nº 21100", conta_partida=55, valor_credito=4524.08, saldo_apos=8654.11, saldo_tipo=C

Formato 2 — histórico ANTES da linha de data (muito comum em PDFs de tabela):
  "COMPRA CONFORME NF NÚMERO 1263290 DE 13.101,10C"   ← histórico + saldo (sem data)
  "CASSOL MATERIAIS DE CONSTRUCAO LTDA"               ← ruído — IGNORE
  "26/04/2024 7459 902 13.101,10"                     ← data + lote + CPC + valor
  → data=26/04/2024, lote=7459, historico="COMPRA CONFORME NF NÚMERO 1263290 DE", conta_partida=902, valor_credito=13101.10, saldo_apos=13101.10, saldo_tipo=C

Formato 3 — pagamento com histórico intercalado antes do lote:
  "09/05/2024 SISPAG BOLETO BANCO 341 7715 SISPAG BOLETO BANCO 341 552 4.150,00 SISPAG BOLETO BANCO 341 35.166,01C"
  → data=09/05/2024, lote=7715, historico="SISPAG BOLETO BANCO 341", conta_partida=552, valor_debito=4150.00, saldo_apos=35166.01, saldo_tipo=C

REGRAS OBRIGATÓRIAS:
1. Valores em formato brasileiro (1.234,56) → retorne como float padrão (1234.56)
2. Ignore linhas que são apenas o nome do fornecedor repetido (ruído do PDF)
3. DÉBITO (valor_debito > 0) = pagamento: SISPAG, BOLETO, TED, PIX, PGTO, PAGAMENTO, BAIXA, TRANSF, DOC
4. CRÉDITO (valor_credito > 0) = compra/aquisição: NF, NOTA FISCAL, CT-E, COMPRA, CONFORME, SERVIÇO, AQUISIÇÃO
5. A linha "SALDO ANTERIOR" indica o saldo inicial do fornecedor
6. A linha "Total da conta: X Y" → X = total_debito, Y = total_credito do período
7. O saldo crescente com sufixo C = credor; D = devedor
8. tipo_operacao deve ser: COMPRA, PAGAMENTO, DEVOLUCAO, DEBITO, ou CREDITO

ATENÇÃO:
- No Formato 2, o valor que aparece na linha sem data (ex: "13.101,10C") é o SALDO após o lançamento, não o valor do lançamento. O valor do lançamento está na linha com data (ex: "902 13.101,10" — onde 902 é o CPC e 13.101,10 é o valor).
- Sempre associe o histórico correto a cada data/lote.

Retorne APENAS JSON válido, sem comentários:
{
  "saldo_anterior": 0.0,
  "saldo_anterior_tipo": "",
  "total_debito": 0.0,
  "total_credito": 0.0,
  "lancamentos": [
    {
      "data": "DD/MM/YYYY",
      "lote": "string",
      "historico": "texto limpo sem repetições do nome do fornecedor",
      "conta_partida": "número ou null",
      "valor_debito": 0.0,
      "valor_credito": 0.0,
      "saldo_apos": 0.0,
      "saldo_tipo": "C ou D ou vazio",
      "tipo_operacao": "COMPRA"
    }
  ]
}"""

# ---------------------------------------------------------------------------
# Prompt secundário — classificação de lançamentos incertos
# ---------------------------------------------------------------------------
CLASSIFY_SYSTEM_PROMPT = """Você é um assistente contábil especializado em lançamentos do Razão de Fornecedores brasileiro.

Classifique cada lançamento:
- COMPRA: aquisição de mercadoria ou serviço (crédito ao fornecedor)
- PAGAMENTO: quitação via boleto, transferência, SISPAG, TED, DOC, PIX
- DEVOLUCAO: devolução ou estorno
- DEBITO: débito genérico não identificável
- CREDITO: crédito genérico não identificável

Extraia também o número da NF/CT-e se houver (apenas dígitos).

Responda EXCLUSIVAMENTE com JSON:
{"resultados": [{"index": 0, "tipo_operacao": "PAGAMENTO", "numero_nf": null}]}"""


# ---------------------------------------------------------------------------
# Cliente OpenAI (singleton lazy)
# ---------------------------------------------------------------------------
def _get_client():
    """Instancia o cliente OpenAI. Retorna None se a chave não estiver configurada."""
    try:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY não configurada — IA desativada.")
            return None
        return OpenAI(api_key=api_key)
    except ImportError:
        logger.warning("Pacote 'openai' não instalado — IA desativada.")
        return None


# ---------------------------------------------------------------------------
# Parsing completo de bloco via IA
# ---------------------------------------------------------------------------
def parsear_bloco_fornecedor_ia(bloco_texto: str) -> Optional[dict]:
    """
    Envia o texto bruto de um bloco de fornecedor ao GPT-4o-mini e retorna
    o dict com saldo_anterior, total_debito, total_credito e lancamentos.
    Retorna None se a IA não estiver configurada ou falhar (parser regex assume).
    """
    if not bloco_texto or len(bloco_texto.strip()) < 30:
        return None

    client = _get_client()
    if client is None:
        return None

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": PARSE_SYSTEM_PROMPT},
                {"role": "user", "content": bloco_texto},
            ],
            max_tokens=4096,
            temperature=0,
        )

        data = json.loads(response.choices[0].message.content)

        if not isinstance(data.get("lancamentos"), list):
            logger.warning("⚠️ IA retornou JSON sem lista 'lancamentos'.")
            return None

        usage = response.usage
        logger.debug(
            "🤖 Bloco parseado — tokens: %d in / %d out",
            usage.prompt_tokens if usage else 0,
            usage.completion_tokens if usage else 0,
        )
        return data

    except Exception as exc:
        logger.warning("⚠️ parsear_bloco_fornecedor_ia falhou: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Classificação secundária de lançamentos incertos
# ---------------------------------------------------------------------------
def classificar_lancamentos_incertos(lancamentos: list) -> None:
    """
    Reclassifica em batch os lançamentos marcados como classificacao_incerta=True.
    Atualiza os dicts in-place. Falha silenciosa (mantém classificação anterior).
    """
    incertos = [l for l in lancamentos if l.get("classificacao_incerta")]
    if not incertos:
        return

    client = _get_client()
    if client is None:
        return

    itens = []
    for i, lanc in enumerate(incertos):
        debito = float(lanc.get("valor_debito", 0))
        credito = float(lanc.get("valor_credito", 0))
        historico = (lanc.get("historico") or "").strip()
        itens.append(
            f'{i}. Histórico: "{historico}" | Débito: {debito:.2f} | Crédito: {credito:.2f}'
        )

    user_message = "Classifique os lançamentos:\n\n" + "\n".join(itens)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=1024,
            temperature=0,
        )

        data = json.loads(response.choices[0].message.content)
        for item in data.get("resultados", []):
            idx = item.get("index")
            if idx is None or idx >= len(incertos):
                continue

            lanc = incertos[idx]
            tipo_ia = item.get("tipo_operacao", "").upper()
            nf_ia: Optional[str] = item.get("numero_nf")

            if tipo_ia in ("COMPRA", "PAGAMENTO", "DEVOLUCAO", "DEBITO", "CREDITO", "OUTRO"):
                lanc["tipo_operacao"] = tipo_ia
                lanc["classificado_por_ia"] = True

            if nf_ia and not lanc.get("numero_nf"):
                nf_str = str(nf_ia).strip()
                if len(nf_str) >= 4:
                    lanc["numero_nf"] = nf_str
                    lanc["classificado_por_ia"] = True

        logger.info(
            "✅ Classificação secundária: %d/%d lançamentos atualizados.",
            sum(1 for l in incertos if l.get("classificado_por_ia")),
            len(incertos),
        )

    except Exception as exc:
        logger.warning("⚠️ classificar_lancamentos_incertos falhou: %s", exc)
