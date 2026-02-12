# ============================================================================
# Dockerfile DEFINITIVO - Sem NODE_ENV=production durante build
# ============================================================================

FROM node:18-alpine AS frontend-build

WORKDIR /app

# NÃO definir NODE_ENV=production aqui!
# NODE_ENV=production faz npm ignorar devDependencies
ENV NODE_OPTIONS="--max-old-space-size=2048"

# Copiar package files
COPY frontend/package.json frontend/package-lock.json* ./

# Instalar TODAS as dependências (dev + prod)
RUN npm ci --include=dev || npm install

# Copiar código
COPY frontend/ ./

# Build (agora tsc vai estar disponível)
RUN npm run build

# Verificar
RUN test -d dist || (echo "ERRO: dist não criado" && exit 1)

# ============================================================================
# Stage 2: Backend + Frontend
# ============================================================================
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY --from=frontend-build /app/dist ./static

RUN test -f frontend/index.html || (echo "ERRO: frontend/index.html não encontrado" && exit 1)

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
