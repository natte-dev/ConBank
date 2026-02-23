# ============================================================
# Stage 1: Build (Node + Vite)
# ============================================================
FROM node:20-alpine AS builder

WORKDIR /app

# Instalar dependências antes de copiar código (cache de camada)
COPY package.json package-lock.json* ./
RUN npm ci --ignore-scripts

# Copiar código-fonte e buildar
COPY . .

# VITE_API_ORIGIN vazio = frontend usa caminho relativo /api/*
# O Nginx (ou Traefik no EasyPanel) faz o proxy
ARG VITE_API_ORIGIN=""
ENV VITE_API_ORIGIN=$VITE_API_ORIGIN

RUN node ./node_modules/vite/bin/vite.js build

# ============================================================
# Stage 2: Runtime (Nginx servindo estático)
# ============================================================
FROM nginx:1.25-alpine AS runtime

# Configuração personalizada do Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Assets compilados pelo Vite
COPY --from=builder /app/dist /usr/share/nginx/html

# Healthcheck: verifica que o Nginx responde
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:80/ || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
