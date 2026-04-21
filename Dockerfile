# ── Stage 1: Build React frontend ──
FROM node:18-alpine AS frontend-builder

WORKDIR /app

ARG REACT_APP_API_URL=""
ENV REACT_APP_API_URL=$REACT_APP_API_URL

COPY package*.json ./
RUN npm ci --silent

COPY public/ public/
COPY src/ src/
RUN npm run build

# ── Stage 2: Python backend + built frontend ──
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY asterdex_backend.py security.py config.py alerting.py db.py auth.py run.py ./

# Copy built frontend into backend's build/ directory (served as static files)
COPY --from=frontend-builder /app/build ./build

RUN mkdir -p data logs

EXPOSE 8080

ENV BACKEND_HOST=0.0.0.0
ENV BACKEND_PORT=8080

CMD ["python", "run.py"]
