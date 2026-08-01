from pydantic import BaseModel, Field

from config import TOP_K


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    answer: str
    context: list[str]


class RetrieveRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(default=TOP_K, ge=1, le=20)


class RetrievedChunk(BaseModel):
    id: int
    content: str
    distance: float


class RetrieveResponse(BaseModel):
    question: str
    top_k: int
    matches: list[RetrievedChunk]
