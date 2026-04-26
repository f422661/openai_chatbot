# Simple RAG API

一個最小可用的 RAG backend 範例，使用 FastAPI、PostgreSQL + pgvector、sentence-transformers 與 OpenAI Responses API。

使用流程：

```text
User -> POST /chat -> FastAPI -> Embedding -> pgvector search -> Prompt -> OpenAI -> Answer
```

## Features

- `POST /chat` 問答 API
- `POST /retrieve` 顯示最相近的 RAG chunks，不呼叫 OpenAI
- 使用 `sentence-transformers/all-MiniLM-L6-v2` 產生 384 維 embedding
- 使用 PostgreSQL + pgvector 做相似度搜尋
- 使用 OpenAI Responses API 產生回答
- 支援匯入 `documents/` 裡的 `.txt`、`.md` 與文字型 `.pdf` 文件

## Project Structure

```text
simple-rag-api/
├── app.py                 # FastAPI app and /chat endpoint
├── config.py              # Environment variable settings
├── db.py                  # Database connection and vector search helper
├── embeddings.py          # sentence-transformers embedding helper
├── init_db.py             # Create pgvector extension and document_chunks table
├── ingest.py              # Read documents, chunk text, embed, and insert into DB
├── requirements.txt       # Python dependencies
├── docker-compose.yml     # PostgreSQL + pgvector service
├── .env.example           # Environment variable template
└── documents/
    └── example.md         # Example document
```

## Requirements

- Python 3.10+
- Docker Desktop
- OpenAI API key

## Setup

Clone the repository, then enter the project folder:

```bash
git clone https://github.com/f422661/openai.git
cd openai
```

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create your local `.env` file:

```bash
touch .env
```

Edit `.env`:

```env
DATABASE_URL=postgresql+psycopg://rag_user:rag_password@localhost:5432/rag_db
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4o-mini
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
TOP_K=5
```

Do not commit `.env`. It is already ignored by `.gitignore`.

## Run Locally

Start PostgreSQL with pgvector:

```bash
docker compose up -d
```

Initialize the database:

```bash
python init_db.py
```

Ingest documents:

```bash
python ingest.py
```

Start the API server:

```bash
uvicorn app:app --reload
```

The API will run at:

```text
http://127.0.0.1:8000
```

## Run with Docker Compose

This starts FastAPI, PostgreSQL + pgvector, and Adminer together:

```bash
docker compose up --build
```

Services:

```text
FastAPI:  http://127.0.0.1:8000
Swagger:  http://127.0.0.1:8000/docs
Adminer:  http://127.0.0.1:8080
Postgres: localhost:5432
```

Inside Docker Compose, the API connects to PostgreSQL through:

```text
postgresql+psycopg://rag_user:rag_password@postgres:5432/rag_db
```

Initialize and ingest through the API container:

```bash
docker compose run --rm api python init_db.py
docker compose run --rm api python ingest.py
```

## View Database in Browser

This project includes Adminer, a simple web UI for PostgreSQL.

Start services:

```bash
docker compose up -d
```

Open:

```text
http://127.0.0.1:8080
```

Login with:

```text
System: PostgreSQL
Server: postgres
Username: rag_user
Password: rag_password
Database: rag_db
```

After logging in, open the `document_chunks` table to view ingested chunks and embeddings.

## API Usage

### Health Check

```bash
curl http://127.0.0.1:8000/health
```

Response:

```json
{
  "status": "ok"
}
```

### Chat

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"這個 API 使用哪些技術？"}'
```

Example response:

```json
{
  "answer": "這個 API 使用 FastAPI、PostgreSQL pgvector、sentence-transformers 和 OpenAI Responses API。",
  "context": [
    "Simple RAG API 是一個使用 FastAPI、PostgreSQL pgvector..."
  ]
}
```

### Retrieve Similar Chunks

Use this endpoint to inspect the most similar RAG chunks without calling OpenAI:

```bash
curl -X POST http://127.0.0.1:8000/retrieve \
  -H "Content-Type: application/json" \
  -d '{"question":"selection sort 是什麼？","top_k":3}'
```

Example response:

```json
{
  "question": "selection sort 是什麼？",
  "top_k": 3,
  "matches": [
    {
      "id": 259,
      "content": "selection sort...",
      "distance": 0.32
    }
  ]
}
```

## Add Your Own Documents

Put `.txt`, `.md`, or text-based `.pdf` files into the `documents/` folder:

```text
documents/
├── example.md
├── product_faq.md
├── company_policy.txt
└── user_manual.pdf
```

Then run:

```bash
python ingest.py
```

`ingest.py` will:

1. Read supported files from `documents/`
2. Split text into chunks
3. Generate embeddings
4. Clear old chunks from `document_chunks`
5. Insert new chunks into PostgreSQL

After ingesting, call `/chat` again to ask questions about the new documents.

PDF support uses `pypdf` text extraction. It works for PDFs that contain selectable text. Scanned image PDFs require OCR and are not supported by default.

## Database

The database container uses:

```text
database: rag_db
user: rag_user
password: rag_password
port: 5432
```

The main table is:

```sql
CREATE TABLE document_chunks (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(384) NOT NULL
);
```

Retrieval uses cosine distance:

```sql
SELECT content
FROM document_chunks
ORDER BY embedding <=> :vec
LIMIT 5;
```

## Troubleshooting

### Docker is not running

If `docker compose up -d` fails, open Docker Desktop first and run the command again.

### Database connection failed

Check that PostgreSQL is running:

```bash
docker compose ps
```

If needed, restart it:

```bash
docker compose down
docker compose up -d
```

### OPENAI_API_KEY is not configured

Make sure `.env` exists and contains:

```env
OPENAI_API_KEY=your-openai-api-key
```

Then restart `uvicorn`.

### GitHub push asks for password

GitHub does not support account passwords for Git pushes over HTTPS. Use a Personal Access Token as the password, or login with GitHub CLI:

```bash
gh auth login
git push -u origin main
```

## Development Commands

Compile-check Python files:

```bash
python -m py_compile app.py init_db.py ingest.py config.py db.py embeddings.py
```

Stop the database:

```bash
docker compose down
```

Remove the database volume and reset all data:

```bash
docker compose down -v
```
