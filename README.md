# Simple RAG API

一個最小可用的 RAG backend 範例，使用 FastAPI、PostgreSQL + pgvector、OpenAI Embeddings 與 Responses API，並整合 LINE Messaging API 機器人。

## 系統架構

```mermaid
flowchart TB
    %% ── Channels ──────────────────────────────────────────────
    subgraph CHANNELS["01 · Channels"]
        direction LR
        WEB["REST Client<br/>Swagger UI"]
        LINE["LINE User<br/>LINE Platform"]
    end

    EDGE["Cloudflare Tunnel<br/>Public HTTPS"]

    %% ── API boundary ──────────────────────────────────────────
    subgraph API_LAYER["02 · API Layer"]
        direction LR
        CHAT_API["POST /chat"]
        RETRIEVE_API["POST /retrieve"]
        LINE_API["POST /line/callback"]
    end

    %% ── Online answer path ────────────────────────────────────
    subgraph RAG["03 · Shared RAG Answer Pipeline"]
        direction LR
        SERVICE["Answer Service"]
        QUERY_EMBED["Create Query<br/>Embedding"]
        REDIS[("Redis<br/>Semantic Cache")]
        HIT{"Similarity<br/>≥ threshold?"}
        PG[("PostgreSQL<br/>pgvector")]
        PROMPT["Build Prompt<br/>with Top-K Context"]
        OPENAI["OpenAI<br/>Responses API"]
        SAVE["Cache Answer<br/>with TTL"]
        RESPONSE(["Return Answer"])

        SERVICE --> QUERY_EMBED --> REDIS --> HIT
        HIT -->|"Yes · Cache hit"| RESPONSE
        HIT -->|"No · Cache miss"| PG
        PG --> PROMPT --> OPENAI --> SAVE --> RESPONSE
        SAVE -.->|"question · vector · answer · context"| REDIS
    end

    %% ── Offline knowledge pipeline ────────────────────────────
    subgraph KNOWLEDGE["04 · Knowledge Ingestion"]
        direction LR
        FILES["Documents<br/>PDF · MD · TXT"]
        CHUNK["Clean & Chunk"]
        DOC_EMBED["Create Document<br/>Embeddings"]
        FILES --> CHUNK --> DOC_EMBED
    end

    %% ── Request routing ───────────────────────────────────────
    WEB --> CHAT_API
    WEB --> RETRIEVE_API
    LINE --> EDGE --> LINE_API
    CHAT_API --> SERVICE
    LINE_API --> SERVICE
    RETRIEVE_API -->|"Embed + Top-K search only"| PG
    DOC_EMBED -->|"Store chunks + vectors"| PG

    %% ── Operations ────────────────────────────────────────────
    ADMINER["Adminer"] -.->|"Inspect"| PG
    INSIGHT["RedisInsight"] -.->|"Inspect"| REDIS

    %% ── Visual system ─────────────────────────────────────────
    classDef channel fill:#FFFFFF,stroke:#64748B,color:#0F172A,stroke-width:1.5px
    classDef api fill:#E0F2FE,stroke:#0284C7,color:#0C4A6E,stroke-width:1.5px
    classDef process fill:#EEF2FF,stroke:#6366F1,color:#312E81,stroke-width:1.5px
    classDef data fill:#FFF7ED,stroke:#F97316,color:#7C2D12,stroke-width:1.5px
    classDef decision fill:#FEF3C7,stroke:#D97706,color:#78350F,stroke-width:1.5px
    classDef output fill:#DCFCE7,stroke:#16A34A,color:#14532D,stroke-width:2px
    classDef muted fill:#F8FAFC,stroke:#94A3B8,color:#475569,stroke-width:1px,stroke-dasharray:4 3

    class WEB,LINE channel
    class EDGE,CHAT_API,RETRIEVE_API,LINE_API api
    class SERVICE,QUERY_EMBED,PROMPT,OPENAI,SAVE,CHUNK,DOC_EMBED process
    class REDIS,PG data
    class HIT decision
    class RESPONSE output
    class FILES,ADMINER,INSIGHT muted

    style CHANNELS fill:#F8FAFC,stroke:#CBD5E1,stroke-width:1px
    style API_LAYER fill:#F0F9FF,stroke:#7DD3FC,stroke-width:1px
    style RAG fill:#FAFAFF,stroke:#C7D2FE,stroke-width:1px
    style KNOWLEDGE fill:#F8FAFC,stroke:#CBD5E1,stroke-width:1px
```

## Features

- `POST /chat` 問答 API
- `POST /retrieve` 顯示最相近的 RAG chunks，不呼叫 OpenAI
- `POST /line/callback` LINE Bot webhook，接收訊息並回覆 RAG 答案
- 使用 `text-embedding-3-small` 產生 384 維 embedding
- 使用 PostgreSQL + pgvector 做相似度搜尋
- 使用 Redis Stack (Vector Search) 提供語意快取 (Semantic Cache)，降低 API 延遲與 Token 費用
- 使用 OpenAI Responses API 產生回答
- 支援匯入 `documents/` 裡的 `.txt`、`.md` 與文字型 `.pdf` 文件

## Project Structure

```text
simple-rag-api/
├── README.md              # Setup、architecture and usage guide
├── Dockerfile             # FastAPI container image
├── app.py                 # FastAPI app、/chat、/retrieve、/line/callback
├── config.py              # Environment variable settings
├── db.py                  # Database connection and vector search helper
├── embeddings.py          # OpenAI embedding helper
├── prompt_loader.py       # Load and cache prompt files
├── semantic_cache.py      # Redis vector semantic cache module
├── schemas.py             # Pydantic request/response data models
├── init_db.py             # Create pgvector extension and document_chunks table
├── ingest.py              # Read documents, chunk text, embed, and insert into DB
├── requirements.txt       # Python dependencies
├── docker-compose.yml     # PostgreSQL + pgvector + Redis Stack services
├── .env.example           # Environment variable template
├── prompts/
│   └── rag_system_prompt.md # RAG system instructions
├── documents/
│   └── example.md         # Example document
└── tests/
    └── test_app.py        # Shared chat flow unit tests
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

Create your local `.env` file from the template:

```bash
cp .env.example .env
```

Edit `.env`：

```env
DATABASE_URL=postgresql+psycopg://rag_user:rag_password@localhost:5432/rag_db
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=384
TOP_K=5
LINE_CHANNEL_SECRET=your-line-channel-secret
LINE_CHANNEL_ACCESS_TOKEN=your-line-channel-access-token
REDIS_URL=redis://localhost:6379/0
CACHE_TTL=86400
SIMILARITY_THRESHOLD=0.92
DEBUG_VECTOR_LOGS=false
```


Do not commit `.env`. It is already ignored by `.gitignore`.

## Run Locally

Start PostgreSQL and Redis only:

```bash
docker compose up -d postgres redis
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

Docker Compose 會自動依序啟動所有服務，包含資料庫初始化、文件 ingest 與 HTTPS tunnel：

```bash
docker compose up -d --build
```

啟動順序：

```text
postgres (healthy) → init (init_db + ingest) → api + cloudflared
```

查看 init 進度：

```bash
docker compose logs -f init
```

看到 `Ingested X chunks.` 代表成功。

查看 Cloudflare Tunnel 的 HTTPS URL：

```bash
docker compose logs cloudflared
```

輸出範例：

```text
Your quick Tunnel has been created! Visit it at:
https://abc-def-123.trycloudflare.com
```

Services:

```text
FastAPI:   http://127.0.0.1:8000
Swagger:   http://127.0.0.1:8000/docs
Adminer:   http://127.0.0.1:8080
Postgres:  localhost:5432
Redis:     localhost:6379
Redis UI:  http://127.0.0.1:5540
HTTPS:     https://abc-def-123.trycloudflare.com  (從 logs 取得)
```

## Deploy to Railway

Railway 會自動偵測根目錄的 `Dockerfile`，並使用 `railway.json` 的 `/health`
健康檢查。容器會監聽 Railway 注入的 `PORT`，本機仍預設使用 `8000`。

### 1. 建立服務

1. 在 Railway 建立 Project，加入這個 GitHub repository。
2. 從 Railway Template Marketplace 部署 **pgvector PostgreSQL**。不要使用標準
   PostgreSQL，因為標準 image 不包含 pgvector extension。
3. 若要保留語意快取，部署支援 RediSearch/RedisJSON 的 **Redis Stack** image
   (`redis/redis-stack-server`)；Railway 的標準 Redis 不支援此專案使用的 `FT.*`
   指令。若使用標準 Redis，聊天與 RAG 仍能運作，但 semantic cache 會自動略過。

### 2. 設定 API service variables

在 API service 的 **Variables** 加入：

```env
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=384
TOP_K=5
DOCUMENTS_DIR=documents
CACHE_TTL=86400
SIMILARITY_THRESHOLD=0.92
DEBUG_VECTOR_LOGS=false
LINE_CHANNEL_SECRET=your-line-channel-secret
LINE_CHANNEL_ACCESS_TOKEN=your-line-channel-access-token
```

`Postgres` 與 `Redis` 必須改成 Railway canvas 上實際的 service 名稱。若暫時不使用
LINE Bot，可省略兩個 `LINE_*` 變數。

### 3. 初始化並匯入文件

第一次部署後，在 API service 使用 Railway Shell 執行：

```bash
python init_db.py
python ingest.py
```

`ingest.py` 會先清空 `document_chunks` 再重新匯入，因此不要把它設為每次部署都執行
的 pre-deploy command。只有在 `documents/` 或 embedding 設定變更時才需再執行。

### 4. 建立公開網址

在 API service 的 **Settings → Networking** 產生 Railway domain，並確認：

```text
https://your-service.up.railway.app/health
https://your-service.up.railway.app/docs
```

LINE Developers 的 Webhook URL 設成：

```text
https://your-service.up.railway.app/line/callback
```

Inside Docker Compose, the API connects to PostgreSQL through:

```text
postgresql+psycopg://rag_user:rag_password@postgres:5432/rag_db
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

LINE 需要一個公開的 HTTPS URL。本專案使用 **Cloudflare Tunnel**，不需帳號即可取得 HTTPS URL。

啟動 Docker Compose 後，執行：

```bash
docker compose logs cloudflared
```

複製輸出中的 URL，到 LINE Developers Console → Messaging API → Webhook settings 填入：

```text
https://abc-def-123.trycloudflare.com/line/callback
```

啟用 **Use webhook** 開關，並按 **Verify** 確認連線成功。

> **注意**：每次重啟 Docker Compose，Cloudflare Tunnel URL 都會改變，需重新更新 LINE Webhook 設定。

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
  "answer": "這個 API 使用 FastAPI、PostgreSQL pgvector、OpenAI Embeddings 和 Responses API。",
  "context": [
    "Simple RAG API 是一個使用 FastAPI、PostgreSQL pgvector..."
  ]
}
```

`/chat` 與 LINE 訊息共用同一套問答流程。系統只會為每個問題產生一次 query embedding，接著先搜尋 Redis semantic cache：

```text
question → embedding → Redis semantic cache
                         ├── hit  → return cached answer
                         └── miss → pgvector retrieval → OpenAI
                                    → store answer in Redis → return answer
```

Redis 使用共同的 key prefix 與 RediSearch index：

```text
Key:    semantic_cache:<uuid>
Prefix: semantic_cache:
Index:  idx:semantic_cache
```

索引會搜尋所有以 `semantic_cache:` 開頭的 Hash，因此舊格式 `semantic_cache:<uuid>` 與曾建立的 `semantic_cache:v2:<uuid>` 都會一起參與相似度搜尋。每筆資料會在 `CACHE_TTL` 到期後自動刪除。

若要在 API log 查看 query vector、命中向量，以及 Redis/Python 計算出的 cosine distance，可暫時啟用：

```env
DEBUG_VECTOR_LOGS=true
```

重新建立 API 容器並查看 log：

```bash
docker compose up -d --build api
docker compose logs -f api
```

正式使用時建議保持 `DEBUG_VECTOR_LOGS=false`，避免每次搜尋額外讀取向量並產生大量 log。

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
docker compose up -d init
```

或在 Docker Compose 之外直接執行：

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

The main table uses `EMBEDDING_DIM=384` by default:

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
3. 確認 Cloudflare Tunnel URL 是否已更新（重啟後 URL 會變）：`docker compose logs cloudflared`

### GitHub push asks for password

GitHub does not support account passwords for Git pushes over HTTPS. Use a Personal Access Token as the password, or login with GitHub CLI:

```bash
gh auth login
git push -u origin main
```

## Development Commands

Compile-check Python files:

```bash
python -m py_compile *.py tests/*.py
```

Run unit tests:

```bash
python -m unittest discover -s tests -v
```

Stop the database:

```bash
docker compose down
```

Remove the database volume and reset all data:

```bash
docker compose down -v
```
