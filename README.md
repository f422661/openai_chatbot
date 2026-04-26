# Simple RAG API

Minimal RAG backend built with FastAPI, PostgreSQL + pgvector, sentence-transformers, and OpenAI Responses API.

## Setup

```bash
cd simple-rag-api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set `OPENAI_API_KEY`.

## Run

```bash
docker compose up -d
python init_db.py
python ingest.py
uvicorn app:app --reload
```

## Chat

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"這個 API 使用哪些技術？"}'
```

## Add Documents

Put `.txt` or `.md` files in `documents/`, then run:

```bash
python ingest.py
```
