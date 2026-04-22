"""
Classificador de lançamentos via OpenAI — fallback para o parser regex.
Acionado apenas quando a classificação regex retorna tipos genéricos
(DEBITO, CREDITO, OUTRO) ou quando a NF deveria existir mas não foi extraída.
"""
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Tipos considerados incertos pelo parser regex
TIPOS_INCERTOS = {"DEBITO", "CREDITO", "OUTRO"}

SYSTEM_PROMPT = """Você é um assistente contábil especializado em lançamentos do Razão de Fornecedores brasileiro.

Classifique cada lançamento conforme as regras abaixo:
- COMPRA: aquisição de mercadoria ou serviço — o fornecedor tem um crédito (ex: nota fiscal, CT-e, fatura)
- PAGAMENTO: quitação de dívida com o fornecedor — débito via boleto, transferência, SISPAG, TED, DOC, pix
- DEVOLUCAO: devolução de mercadoria ou estorno de lançamento
- DEBITO: débito genérico não identificável como pagamento
- CREDITO: crédito genérico não identificável como compra

Extraia também o número da NF/CT-e se houver no histórico (apenas dígitos, sem prefixo).

Responda EXCLUSIVAMENTE com JSON válido no formato:
{"resultados": [{"index": 0, "tipo_operacao": "PAGAMENTO", "numero_nf": null}, ...]}"""


def _get_client():
    """Instancia o cliente OpenAI. Retorna None se a chave não estiver configurada."""
    try:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY não configurada — classificação IA desativada.")
            return None
        return OpenAI(api_key=api_key)
    except ImportError:
        logger.warning("Pacote 'openai' não instalado — classificação IA desativada.")
        return None


def classificar_lancamentos_incertos(lancamentos: list) -> None:
    """
    Reclassifica em batch os lançamentos com tipo genérico (DEBITO/CREDITO/OUTRO).
    Atualiza os dicts in-place. Se a API falhar, mantém a classificação do regex.

    Args:
        lancamentos: lista de dicts com chaves historico, valor_debito,
                     valor_credito, tipo_operacao, numero_nf.
                     Apenas os marcados com classificacao_incerta=True são enviados.
    """
    incertos = [l for l in lancamentos if l.get("classificacao_incerta")]
    if not incertos:
        return

    client = _get_client()
    if client is None:
        return

    # Montar a lista de itens para o prompt
    itens = []
    for i, lanc in enumerate(incertos):
        debito = float(lanc.get("valor_debito", 0))
        credito = float(lanc.get("valor_credito", 0))
        historico = (lanc.get("historico") or "").strip()
        itens.append(
            f'{i}. Histórico: "{historico}" | Débito: {debito:.2f} | Crédito: {credito:.2f}'
        )

    user_message = "Classifique os lançamentos abaixo:\n\n" + "\n".join(itens)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=1024,
            temperature=0,
        )

        content = response.choices[0].message.content
        data = json.loads(content)
        resultados = data.get("resultados", [])

        for item in resultados:
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
            "✅ IA classificou %d lançamentos (de %d incertos enviados).",
            sum(1 for l in incertos if l.get("classificado_por_ia")),
            len(incertos),
        )

    except Exception as exc:
        logger.warning("⚠️ Classificação IA falhou — mantendo resultado do regex. Erro: %s", exc)
