# Simple RAG API 範例文件

Simple RAG API 是一個使用 FastAPI、PostgreSQL pgvector、sentence-transformers 和 OpenAI Responses API 的最小 RAG 後端。

使用者會呼叫 `/chat` API 並送出問題。系統會先把問題轉成 embedding，接著從 `document_chunks` 資料表取回最相近的內容片段，最後把資料與問題組成 prompt 交給 OpenAI 產生回答。
