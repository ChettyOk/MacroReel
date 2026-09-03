# MacroReel — single container: FastAPI API + React PWA static files
# Build: docker build -t macroreel .
# Run:   docker run -p 8000:8000 -e GEMINI_API_KEY=... -v macroreel-data:/data macroreel

FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Same-origin API in production (FastAPI serves /recipes, /profile, …)
ENV VITE_API_URL=
ARG VITE_GOOGLE_CLIENT_ID=
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID
RUN npm run build

FROM python:3.12-slim AS backend
WORKDIR /app

# ffmpeg optional but enables deep video extract (ENABLE_MEDIA_PIPELINE=true)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY --from=frontend /app/frontend/dist ./static

ENV DATA_DIR=/data
ENV STATIC_DIR=/app/static
ENV PORT=8000
# Image includes ffmpeg — enable deep extract by default (override with false on Render if needed).
ENV ENABLE_MEDIA_PIPELINE=true
EXPOSE 8000

VOLUME /data

HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
