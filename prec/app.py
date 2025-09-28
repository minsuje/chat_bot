from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from supabase import Client, create_client

from .openai_client import OpenAIChatClient, OpenAIEmbeddingClient
from .service import ChatbotService
from .settings import Settings
from .vector_store import SupabaseVectorStore


class IngestRequest(BaseModel):
    pdf_paths: List[str] = Field(..., description="List of PDF file paths to ingest")


class IngestedDocumentSummary(BaseModel):
    path: str
    chunks: int


class IngestResponse(BaseModel):
    ingested: List[IngestedDocumentSummary]
    total_chunks: int


class QueryRequest(BaseModel):
    question: str = Field(..., description="User question to answer")
    top_k: Optional[int] = Field(
        8, ge=1, le=20, description="Number of relevant chunks to retrieve"
    )


class SourceChunk(BaseModel):
    id: str
    source: str
    page: Optional[int]
    score: float
    text: str


class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceChunk]


def create_chatbot_service(settings: Settings | None = None) -> ChatbotService:
    settings = settings or Settings.from_env()

    supabase_client: Client = create_client(settings.supabase_url, settings.supabase_key)
    vector_store = SupabaseVectorStore(
        supabase_client,
        table=settings.supabase_table,
        query_function=settings.supabase_query_function,
    )
    embeddings_client = OpenAIEmbeddingClient(
        api_key=settings.openai_api_key,
        model=settings.openai_embedding_model,
    )
    chat_client = OpenAIChatClient(
        api_key=settings.openai_api_key,
        model=settings.openai_chat_model,
    )

    return ChatbotService(
        embeddings=embeddings_client,
        chat=chat_client,
        vector_store=vector_store,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    service = create_chatbot_service(settings)
    app = FastAPI(title="Policy Chatbot API", version="0.1.0")

    app.state.chatbot_service = service

    @app.post("/ingest", response_model=IngestResponse)
    async def ingest_documents(request: IngestRequest) -> IngestResponse:
        service: ChatbotService = app.state.chatbot_service
        try:
            paths = [Path(item).expanduser() for item in request.pdf_paths]
            ingested_docs = service.ingest(paths)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        summaries = [
            IngestedDocumentSummary(path=str(doc.path), chunks=len(doc.chunks))
            for doc in ingested_docs
        ]
        total_chunks = sum(summary.chunks for summary in summaries)
        return IngestResponse(ingested=summaries, total_chunks=total_chunks)

    @app.post("/query", response_model=QueryResponse)
    async def query_bot(request: QueryRequest) -> QueryResponse:
        service: ChatbotService = app.state.chatbot_service
        try:
            result = service.answer(request.question, top_k=request.top_k or 5)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        sources = [
            SourceChunk(
                id=item["id"],
                source=item["source"],
                page=item["page"],
                score=item["score"],
                text=item["text"],
            )
            for item in result["sources"]
        ]
        return QueryResponse(answer=result["answer"], sources=sources)

    return app
