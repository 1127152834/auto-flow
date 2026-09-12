FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    REDROID_STATIC_DIR=/app/static REDROID_UPLOAD_DIR=/data/apks \
    REDROID_BIND_HOST=0.0.0.0 PORT=8080
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ ./backend/
COPY licenses/ ./licenses/
COPY THIRD_PARTY.md ./
COPY --from=frontend /build/dist ./static/
EXPOSE 8080
CMD ["python", "-m", "backend.app"]
