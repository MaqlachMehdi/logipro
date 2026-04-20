# ---- Frontend LogiPro ----
# Stage 1: build Vite
FROM node:20-slim AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

# VITE_API_URL='' → les appels API seront relatifs (/api/...) 
# Nginx se charge du proxy vers le backend
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# Stage 2: servir les fichiers statiques avec Nginx
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
