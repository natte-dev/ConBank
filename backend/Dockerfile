# ============================================================
# Stage 1: Builder — instala dependências com build tools
# ============================================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Dependências de sistema para compilar psycopg2, Levenshtein etc.
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

# Apenas libpq em runtime (para psycopg2-binary não precisa, mas é boa prática)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copiar pacotes instalados do builder
COPY --from=builder /install /usr/local

# Copiar código da aplicação
COPY . .

# Usuário não-root para segurança
RUN useradd -m -u 1001 appuser && chown -R appuser:appuser /app
USER appuser

# Porta configurável via env (default 8000)
ENV PORT=8000

EXPOSE 8000

# Healthcheck interno do container
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')" || exit 1

# Graceful shutdown: uvicorn já trata SIGTERM
CMD ["sh", "-c", "python -m uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 1 --timeout-keep-alive 75"]
