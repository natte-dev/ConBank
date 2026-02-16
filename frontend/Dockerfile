FROM node:18-alpine AS build
WORKDIR /app

# copia manifests primeiro (cache)
COPY package.json package-lock.json* ./

# instala deps limpo
RUN npm ci || npm install

# garante executável nos bins (vite)
RUN chmod -R a+rx /app/node_modules/.bin || true

# copia o resto
COPY . .

# build
RUN npm run build

# serve estático
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
