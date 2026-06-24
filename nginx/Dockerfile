FROM node:22-alpine AS frontend-build

WORKDIR /app

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /app/dist /usr/share/nginx/html

EXPOSE 80
