# ---- Stage 1: build the React frontend ----
FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: backend, serving the built frontend as static files ----
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Pre-download models at build time so the container starts fast
RUN python -c "\
from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('nomic-ai/nomic-embed-text-v1.5', trust_remote_code=True); \
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

COPY api/ ./api/
COPY insights/ ./insights/
COPY rag/ ./rag/
COPY llm/ ./llm/
COPY ingestion/ ./ingestion/
COPY embeddings/ ./embeddings/
COPY vectorstore/ ./vectorstore/

COPY --from=frontend-build /frontend/dist ./static
RUN mkdir -p data/raw data/processed chroma_db

EXPOSE 80
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "80"]