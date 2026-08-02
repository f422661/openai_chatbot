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

def build_prompt(question: str, context_chunks: list[str]) -> str:
    context = "\n\n".join(context_chunks) if context_chunks else "沒有找到相關資料。"
    return f"根據以下資料回答:\n{context}\n\n問題:{question}"


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
        input=[
            {
                "role": "system",
                "content": "你是嚴謹的 RAG 助理。只根據提供資料回答；若資料不足可以使用你自己的通用知識補充，但必須清楚區分：哪些內容來自提供資料，哪些是模型補充。",
            },
            {"role": "user", "content": prompt},
        ],
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
