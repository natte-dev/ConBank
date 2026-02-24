# =============================================================================
# frontend/Dockerfile — conBank UI (React + Vite → Nginx)
# Deploy: EasyPanel → App → Dockerfile
# Build context: ./frontend
# Porta interna: 80
#
# Build arg obrigatório no EasyPanel:
#   VITE_API_URL=https://seu-backend.easypanel.host
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: builder — compila o React com Vite
# -----------------------------------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

# Instala dependências primeiro (cache de camada — só reinstala se package.json mudar)
COPY package.json package-lock.json* ./
RUN npm ci --ignore-scripts

# Código-fonte
COPY . .

# URL base da API — injetada em tempo de build pelo Vite (VITE_* vira string no bundle)
# Passe via Build Args no EasyPanel: VITE_API_URL=https://backend.easypanel.host
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL

RUN node ./node_modules/vite/bin/vite.js build

# -----------------------------------------------------------------------------
# Stage 2: runtime — Nginx serve os assets estáticos
# -----------------------------------------------------------------------------
FROM nginx:1.25-alpine AS runtime

# Remove config padrão do Nginx e substitui pela nossa
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Assets buildados pelo Vite
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

# Healthcheck: endpoint /nginx-health sem log de acesso
HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=15s \
    --retries=3 \
  CMD wget -qO- http://localhost:80/nginx-health || exit 1

CMD ["nginx", "-g", "daemon off;"]
