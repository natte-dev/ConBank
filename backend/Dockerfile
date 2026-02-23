# ============================================================
# Stage 1: Builder — instala dependências com build tools
# ============================================================
FROM python:3.11-slim AS builder

WORKDIR /app

# gcc + libpq-dev necessários para compilar psycopg2 e python-Levenshtein
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ============================================================
# Stage 2: Runtime — imagem enxuta
# ============================================================
FROM python:3.11-slim AS runtime

WORKDIR /app

# libpq5 para psycopg2 em runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Pacotes Python do builder
COPY --from=builder /install /usr/local

# Código da aplicação
COPY . .

# Usuário não-root
RUN useradd -m -u 1001 appuser && chown -R appuser:appuser /app
USER appuser

# Porta padrão (sobrescrita por env PORT no compose/EasyPanel)
ENV PORT=8000

EXPOSE 8000

# HEALTHCHECK — usa sh -c para expandir $PORT corretamente em runtime
# start-period de 60s dá tempo ao uvicorn + DB conectar antes do primeiro check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
  CMD sh -c "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:$PORT/health')\"" || exit 1

# CMD via sh para que $PORT seja expandido pelo shell
CMD ["sh", "-c", "python -m uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1 --timeout-keep-alive 75"]
