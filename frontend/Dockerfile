# ==========================================
# Estágio 1: Build da Aplicação React/Vite
# ==========================================
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .
RUN npm run build

# ==========================================
# Estágio 2: Servidor Web Nginx de Produção
# ==========================================
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
