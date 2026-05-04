# Simple RAG API

一個最小可用的 RAG backend 範例，使用 FastAPI、PostgreSQL + pgvector、sentence-transformers 與 OpenAI Responses API，並整合 LINE Messaging API 機器人。

## 系統架構

```mermaid
graph LR
    classDef userNode fill:#E3F2FD,stroke:#1565C0,stroke-width:2px,color:#1A237E
    classDef lineNode fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px,color:#1B5E20
    classDef appNode  fill:#FFF8E1,stroke:#E65100,stroke-width:2px,color:#BF360C
    classDef dbNode   fill:#FBE9E7,stroke:#BF360C,stroke-width:2px,color:#7F0000
    classDef mlNode   fill:#EDE7F6,stroke:#4527A0,stroke-width:2px,color:#311B92
    classDef fileNode fill:#F5F5F5,stroke:#616161,stroke-width:1px,color:#212121

    subgraph ClientZone["用戶端"]
        U["REST Client"]:::userNode
        LU["LINE 使用者"]:::userNode
    end

    subgraph LineZone["LINE Cloud"]
        LP["LINE Platform"]:::lineNode
    end

    subgraph ServerZone["Application Server　(Docker Compose)"]
        API["FastAPI\n:8000"]:::appNode
        ST["sentence-\ntransformers"]:::mlNode
        PG[("PostgreSQL\n+ pgvector")]:::dbNode
        ADM["Adminer\n:8080"]:::appNode
    end

    OAI["OpenAI\nAPI"]:::mlNode

    DOCS["documents/\n.txt .md .pdf"]:::fileNode --> ING["ingest.py"]:::fileNode
    ING -->|embed & store| PG

    U -->|"POST /chat · /retrieve"| API
    LU -->|"傳訊息"| LP
    LP -->|"POST /line/callback"| API

    API -->|"vector search"| PG
    PG -->|"top-K chunks"| API
    API -->|"prompt + context"| OAI
    OAI -->|"answer"| API
    API -->|"reply"| LP

    ADM -. "browse" .-> PG
```

## Features

- `POST /chat` 問答 API
- `POST /retrieve` 顯示最相近的 RAG chunks，不呼叫 OpenAI
- `POST /line/callback` LINE Bot webhook，接收訊息並回覆 RAG 答案
- 使用 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` 產生 384 維 embedding
- 使用 PostgreSQL + pgvector 做相似度搜尋
- 使用 OpenAI Responses API 產生回答
- 支援匯入 `documents/` 裡的 `.txt`、`.md` 與文字型 `.pdf` 文件

## Project Structure

```text
simple-rag-api/
├── app.py                 # FastAPI app、/chat、/retrieve、/line/callback
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
- LINE Developers 帳號（LINE Bot 功能）

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

Edit `.env`：

```env
DATABASE_URL=postgresql+psycopg://rag_user:rag_password@localhost:5432/rag_db
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4o-mini
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
TOP_K=5
LINE_CHANNEL_SECRET=your-line-channel-secret
LINE_CHANNEL_ACCESS_TOKEN=your-line-channel-access-token
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

## LINE Bot Setup

### 1. 建立 LINE Messaging API Channel

1. 前往 [LINE Developers Console](https://developers.line.biz/console/)
2. 建立 Provider（若尚未有）
3. 建立 **Messaging API** channel
4. 在 channel 設定頁面取得：
   - **Channel Secret**（Basic settings）
   - **Channel Access Token**（Messaging API → Issue）

### 2. 填入 `.env`

```env
LINE_CHANNEL_SECRET=your-channel-secret
LINE_CHANNEL_ACCESS_TOKEN=your-channel-access-token
```

### 3. 設定 Webhook URL

LINE 需要一個公開的 HTTPS URL。本機開發可以使用 [ngrok](https://ngrok.com/)：

```bash
ngrok http 8000
```

複製 ngrok 產生的 HTTPS URL，到 LINE Developers Console → Messaging API → Webhook settings 填入：

```text
https://xxxx.ngrok.io/line/callback
```

啟用 **Use webhook** 開關，並按 **Verify** 確認連線成功。

### 4. 關閉自動回覆

在 LINE Official Account Manager → 回應設定中，關閉「自動回應訊息」與「加入好友的歡迎訊息」，避免和 webhook 回覆衝突。

### 5. 測試

加入 LINE Bot 為好友（掃描 QR Code），傳送任意文字訊息，Bot 將根據 RAG 知識庫回覆答案。

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

### LINE Webhook

LINE 平台會自動呼叫此端點，不需手動觸發。端點格式如下：

```text
POST /line/callback
Header: X-Line-Signature: <HMAC-SHA256 signature>
Body: LINE webhook event JSON
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

After ingesting, call `/chat` or send a LINE message to ask questions about the new documents.

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

### LINE webhook 回傳 400 Invalid signature

確認 `.env` 中的 `LINE_CHANNEL_SECRET` 與 LINE Developers Console 上的 Channel Secret 完全一致。

### LINE webhook 回傳 500

確認 `LINE_CHANNEL_ACCESS_TOKEN` 已填入且未過期。可在 LINE Developers Console → Messaging API → Channel access token 重新 Issue。

### LINE Bot 沒有回覆訊息

1. 確認 LINE Developers Console 的 **Use webhook** 已啟用
2. 確認 Official Account Manager 的「自動回應訊息」已關閉
3. 確認 ngrok（或正式 HTTPS）URL 可正常連到本機 8000 port

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
