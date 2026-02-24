# =============================================================================
# backend/Dockerfile — conBank API (FastAPI + Uvicorn)
# Deploy: EasyPanel → App → Dockerfile
# Build context: ./backend
# Porta interna: 8000
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: builder — compila dependências nativas (psycopg2, Levenshtein)
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2: runtime — imagem final enxuta
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

WORKDIR /app

# Apenas libpq em runtime (psycopg2-binary já linka dinamicamente)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Pacotes Python instalados no builder
COPY --from=builder /install /usr/local

# Código-fonte
COPY . .

# Usuário não-root para segurança
RUN useradd -m -u 1001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Healthcheck: bate em /health — sem sh -c para evitar ambiguidade
HEALTHCHECK \
    --interval=30s \
    --timeout=10s \
    --start-period=60s \
    --retries=5 \
  CMD python -c \
    "import urllib.request, sys; \
     r = urllib.request.urlopen('http://localhost:8000/health', timeout=8); \
     sys.exit(0 if r.status == 200 else 1)"

# CMD com exec-form (sem shell) — uvicorn recebe SIGTERM diretamente
CMD ["python", "-m", "uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--timeout-keep-alive", "75", \
     "--log-level", "info"]
