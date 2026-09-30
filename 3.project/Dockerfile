# Multi-stage Dockerfile: Frontend build + Backend FastAPI Single-container packaging

# 1. Build React/TypeScript Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# 2. Python FastAPI Runtime
FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies (excluding Windows-only winocr)
COPY requirements.txt .
RUN sed -i '/winocr/d' requirements.txt && pip install --no-cache-dir -r requirements.txt

# Copy backend application code and sample files
COPY backend /app/backend
COPY sample-data /app/sample-data

# Copy frontend build output so backend serves the full SPA
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

EXPOSE 8000
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
