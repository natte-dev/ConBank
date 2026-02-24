# =============================================================================
# frontend/Dockerfile — ConBank UI (React + Vite → Nginx)
# (VERSÃO compatível com build context no ROOT do repo)
# =============================================================================

FROM node:20-alpine AS builder
WORKDIR /app

# Dependências (cache)
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --ignore-scripts

# Código-fonte
COPY frontend/ ./

# Build-time API URL
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL

RUN node ./node_modules/vite/bin/vite.js build

FROM nginx:1.25-alpine AS runtime
RUN rm /etc/nginx/conf.d/default.conf

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK \
  --interval=30s \
  --timeout=5s \
  --start-period=15s \
  --retries=3 \
  CMD wget -qO- http://127.0.0.1:80/nginx-health || exit 1

CMD ["nginx", "-g", "daemon off;"]