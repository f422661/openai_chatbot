from openai import OpenAI
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException

from config import OPENAI_API_KEY, OPENAI_MODEL, TOP_K
from db import fetch_top_chunks
from embeddings import embed_text


app = FastAPI(title="Simple RAG API")


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    answer: str
    context: list[str]


def build_prompt(question: str, context_chunks: list[str]) -> str:
    context = "\n\n".join(context_chunks) if context_chunks else "沒有找到相關資料。"
    return f"根據以下資料回答:\n{context}\n\n問題:{question}"


def get_openai_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured")
    return OpenAI(api_key=OPENAI_API_KEY)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    question = request.question.strip()
    question_embedding = embed_text(question)
    context_chunks = fetch_top_chunks(question_embedding, TOP_K)
    prompt = build_prompt(question, context_chunks)

    client = get_openai_client()
    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {
                "role": "system",
                "content": "你是嚴謹的 RAG 助理。只根據提供資料回答；若資料不足，請明確說明。",
            },
            {"role": "user", "content": prompt},
        ],
    )

    return ChatResponse(answer=response.output_text, context=context_chunks)
