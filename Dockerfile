# ============================================================================
<<<<<<< HEAD
# Dockerfile Único - Frontend (Node + Nginx) + Backend (Python + FastAPI)
# ============================================================================
# Baseado nos seus Dockerfiles existentes
# ============================================================================

# ============================================================================
# STAGE 1: Build do Frontend (igual ao seu frontend/Dockerfile)
# ============================================================================
FROM node:18-alpine AS frontend-build

WORKDIR /app

# Copiar package files
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

# Copiar código e fazer build
COPY frontend/ ./
RUN npm run build

# ============================================================================
# STAGE 2: Backend Python + Frontend estático (igual ao seu backend/Dockerfile)
=======
# Dockerfile Multi-Stage - Frontend + Backend Integrado
# ============================================================================
# Stage 1: Build do Frontend
# Stage 2: Backend + Frontend estático
# ============================================================================

# ============================================================================
# STAGE 1: Build do Frontend React/Vite
# ============================================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

# Copiar package files
COPY frontend/package*.json ./

# Instalar dependências
RUN npm ci --only=production

# Copiar código fonte
COPY frontend/ ./

# Build do frontend (gera pasta /frontend/dist)
RUN npm run build

# ============================================================================
# STAGE 2: Backend Python + Frontend Estático
>>>>>>> fccb0871f8b24622c34ac9631f4cfa89b67c25c7
# ============================================================================
FROM python:3.11-slim

WORKDIR /app

<<<<<<< HEAD
# Instalar dependências do backend
COPY backend/requirements.txt .
=======
# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements do backend
COPY backend/requirements.txt .

# Instalar dependências Python
>>>>>>> fccb0871f8b24622c34ac9631f4cfa89b67c25c7
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código do backend
COPY backend/ .

<<<<<<< HEAD
# Copiar frontend buildado do stage anterior (dist → static)
COPY --from=frontend-build /app/dist ./static
=======
# Copiar frontend buildado do stage anterior
COPY --from=frontend-builder /frontend/dist ./static
>>>>>>> fccb0871f8b24622c34ac9631f4cfa89b67c25c7

# Expor porta
EXPOSE 8000

<<<<<<< HEAD
# Iniciar servidor
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
=======
# Variáveis de ambiente (podem ser sobrescritas no docker-compose)
ENV DATABASE_URL=postgresql://postgres:b2ad156f04d4203f02f3@n8n_postgres:5432/ConBank
ENV PYTHONUNBUFFERED=1

# Comando para iniciar o servidor
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
>>>>>>> fccb0871f8b24622c34ac9631f4cfa89b67c25c7
