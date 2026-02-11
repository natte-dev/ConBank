# ============================================================================
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
# ============================================================================
FROM python:3.11-slim

WORKDIR /app

# Instalar dependências do backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código do backend
COPY backend/ .

# Copiar frontend buildado do stage anterior (dist → static)
COPY --from=frontend-build /app/dist ./static

# Expor porta
EXPOSE 8000

# Iniciar servidor
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
