# syntax=docker/dockerfile:1

########################
# Stage 1: build the Vite bundle
########################
FROM node:20-alpine AS build

WORKDIR /app

# Install deps against the lockfile for reproducible builds
COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

# VITE_API_URL is baked in at build time; override with:
#   docker compose build --build-arg VITE_API_URL=https://api.example.com
ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build


########################
# Stage 2: nginx static server + /api proxy
########################
FROM nginx:alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
