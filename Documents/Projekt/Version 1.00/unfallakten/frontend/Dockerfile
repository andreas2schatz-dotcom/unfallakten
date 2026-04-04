# ─────────────────────────────────────────────────────────────────────────────
# frontend/Dockerfile – Multi-Stage Build
#
# Stage 1 (builder): Node 20 + Vite – baut React-App nach /app/dist
# Stage 2 (runtime): nginx:alpine   – serviert statische Dateien
#
# Build-Argumente:
#   VITE_API_URL      – Backend-URL (leer = gleiche Domain, nginx routet intern)
#   VITE_DEMO_MODE    – true | false
#
# Beispiel:
#   docker build \
#     --build-arg VITE_API_URL="" \
#     --build-arg VITE_DEMO_MODE=false \
#     -t unfallakten-frontend:prod .
# ─────────────────────────────────────────────────────────────────────────────

# ════════════════════════════════════════════════════════════════════════════
# STAGE 1: Builder
# ════════════════════════════════════════════════════════════════════════════
FROM node:20-alpine AS builder

LABEL stage=builder

WORKDIR /app

# Build-Argumente (werden als VITE_* Env-Variablen ins Bundle eingebettet)
ARG VITE_API_URL=""
ARG VITE_DEMO_MODE="false"
ARG VITE_APP_TITEL="Unfallakten – Koch, Schatz & Kollegen"
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_DEMO_MODE=$VITE_DEMO_MODE
ENV VITE_APP_TITEL=$VITE_APP_TITEL

# Abhängigkeiten separat cachen (nur bei package.json Änderungen neu)
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund

# Quellcode
# Cache-Bust: Bei jeder Änderung muss --build-arg CACHEBUST=$(date +%s) übergeben werden
ARG CACHEBUST=1
COPY . .

# Produktions-Build
RUN npm run build

# Build-Artefakte prüfen
RUN test -f dist/index.html || (echo "ERROR: Build fehlgeschlagen – dist/index.html nicht gefunden" && exit 1)
RUN du -sh dist/ && ls -lh dist/

# ════════════════════════════════════════════════════════════════════════════
# STAGE 2: Runtime (nginx)
# ════════════════════════════════════════════════════════════════════════════
FROM nginx:1.27-alpine AS runtime

LABEL maintainer="Koch, Schatz & Kollegen IT <it@anwalt-offenbach.de>"
LABEL version="1.0"
LABEL description="Unfallakten Frontend (React + Vite)"

# Statische Dateien aus Builder-Stage kopieren
COPY --from=builder /app/dist /usr/share/nginx/html

# curl für Health-Check installieren
RUN apk add --no-cache curl

# nginx-Konfiguration für SPA (Single Page Application)
# Alle Routen → index.html, damit React Router funktioniert
COPY docker/nginx-spa.conf /etc/nginx/conf.d/default.conf

# Sicherheit: nginx als non-root (nutzt Port 8080 statt 80)
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html

EXPOSE 8080

# Healthcheck: HTTP GET auf /
HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
  CMD curl -fs http://localhost:8080/nginx-health || exit 1

CMD ["nginx", "-g", "daemon off;"]
