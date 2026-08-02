from openai import OpenAI
from fastapi import FastAPI, HTTPException, Header, Request

from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError

from config import (
    LINE_CHANNEL_ACCESS_TOKEN,
    LINE_CHANNEL_SECRET,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    TOP_K,
)
from db import fetch_top_chunks, fetch_top_matches
from embeddings import embed_text
from prompt_loader import load_prompt
from semantic_cache import get_semantic_cache, set_semantic_cache
from schemas import (
    ChatRequest,
    ChatResponse,
    RetrieveRequest,
    RetrieveResponse,
)


app = FastAPI(title="Simple RAG API")

line_handler = WebhookHandler(LINE_CHANNEL_SECRET)
line_config = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
RAG_SYSTEM_PROMPT = load_prompt("rag_system_prompt.md")


def build_prompt(question: str, context_chunks: list[str]) -> str:
    if context_chunks:
        context = "\n\n".join(
            f"[來源 {index}]\n{chunk}"
            for index, chunk in enumerate(context_chunks, start=1)
        )
    else:
        context = "（沒有可用的參考資料）"

    return f"參考資料：\n\n{context}\n\n使用者問題：\n{question}"


def get_openai_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured")
    return OpenAI(api_key=OPENAI_API_KEY)


def answer_question(question: str) -> ChatResponse:
    """Run the shared RAG flow used by HTTP and LINE requests."""
    question_embedding = embed_text(question)

    cached_response = get_semantic_cache(question, question_embedding)
    if cached_response:
        return ChatResponse(
            answer=cached_response["answer"],
            context=cached_response["context"],
        )

    context_chunks = fetch_top_chunks(question_embedding, TOP_K)
    prompt = build_prompt(question, context_chunks)

    client = get_openai_client()
    response = client.responses.create(
        model=OPENAI_MODEL,
        instructions=RAG_SYSTEM_PROMPT,
        input=prompt,
    )

    answer = response.output_text
    set_semantic_cache(
        question,
        question_embedding,
        answer,
        context_chunks,
    )
    return ChatResponse(answer=answer, context=context_chunks)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    question = request.question.strip()
    return answer_question(question)


@app.post("/retrieve", response_model=RetrieveResponse)
def retrieve(request: RetrieveRequest) -> RetrieveResponse:
    question = request.question.strip()
    question_embedding = embed_text(question)
    matches = fetch_top_matches(question_embedding, request.top_k)

    return RetrieveResponse(
        question=question,
        top_k=request.top_k,
        matches=matches,
    )


@app.post("/line/callback")
async def line_callback(
    request: Request,
    x_line_signature: str = Header(...),
) -> dict[str, str]:
    if not LINE_CHANNEL_SECRET or not LINE_CHANNEL_ACCESS_TOKEN:
        raise HTTPException(status_code=500, detail="LINE credentials are not configured")

    body = await request.body()
    try:
        line_handler.handle(body.decode("utf-8"), x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid LINE signature")

    return {"status": "ok"}


@line_handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event: MessageEvent) -> None:
    try:
        question = event.message.text.strip()
        result = answer_question(question)

        with ApiClient(line_config) as api_client:
            messaging_api = MessagingApi(api_client)
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=result.answer)],
                )
            )
    except Exception as e:
        import traceback
        print(f"[ERROR] handle_text_message failed: {e}")
        traceback.print_exc()
