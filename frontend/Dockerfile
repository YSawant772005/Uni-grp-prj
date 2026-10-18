# syntax=docker/dockerfile:1
# Two targets used by docker-compose.yml:
#   dev  -> vite dev server (hot reload) behind host port 5173
#   prod -> static bundle served by the NGINX container (config mounted from infra/nginx.conf)

FROM node:24-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# --- dev: Vite dev server -------------------------------------------------
FROM deps AS dev
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# --- build: production bundle (typecheck runs as part of `npm run build`) --
FROM deps AS build
COPY . .
ARG VITE_API_BASE=/api/v1
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

# --- prod: NGINX serving the built bundle ---------------------------------
FROM nginx:1.29-alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
