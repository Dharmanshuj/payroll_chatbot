# FastAPI backend (payroll chatbot API)
# Build & run from the repository root:
#   docker build -t payroll-chatbot-api .
#   docker run -p 8000:8000 --env-file .env payroll-chatbot-api
#
# On Render: create a "Web Service" pointing at this Dockerfile (root context),
# and set the environment variables listed in .env (DB_*, GEMINI_API_KEY,
# SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD, SPRING_MCP_URL, ...) in the
# Render dashboard. Render injects $PORT automatically; the CMD below binds to it.

FROM python:3.12-slim

WORKDIR /app

# Build tools for any dependency that doesn't ship a prebuilt wheel for this
# platform (the langchain/torch/sentence-transformers stack occasionally needs this).
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first so this layer is cached unless requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code, including the prebuilt vector_store/ FAISS index that
# rag/retriever.py loads at import time (documents/ is excluded via .dockerignore;
# it's only read by the offline ingest.py script, not the running server).
COPY . .

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Render sets $PORT; default to 8000 for local `docker run`.
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
