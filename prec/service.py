from __future__ import annotations

from pathlib import Path
from time import perf_counter
from threading import RLock
from typing import List, Optional, Sequence

from .openai_client import OpenAIChatClient, OpenAIEmbeddingClient
from .pdf_loader import build_chunks
from .types import ChunkInput, DocumentChunk, IngestedDocument
from .vector_store import RankedChunk, SupabaseVectorStore
from .eval import EvaluationResult, ResponseEvaluator


SYSTEM_PROMPT = (
    "당신은 임산부·임신 예정자·영유아 관련 정책 정보를 안내하는 전문가입니다. "
    "반드시 한국어로 답변하고, 제공된 문서 내용을 벗어나 추측하지 마세요. "
    "답변에는 중요 근거를 요약해 포함하고, 가능한 경우 출처 파일 이름과 페이지를 괄호로 표시하십시오. "
    "맥락에 정보가 없으면 '정보를 찾을 수 없습니다.'라고 말하세요."
)


class ChatbotService:
    def __init__(
        self,
        *,
        embeddings: OpenAIEmbeddingClient,
        chat: OpenAIChatClient,
        vector_store: SupabaseVectorStore,
        evaluator: ResponseEvaluator | None = None,
        evaluation_default: bool = False,
        chunk_size: int = 1200,
        chunk_overlap: int = 200,
    ) -> None:
        self._embeddings = embeddings
        self._chat = chat
        self._vector_store = vector_store
        self._evaluator = evaluator
        self._evaluation_default = evaluation_default
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._lock = RLock()

    def ingest(self, document_paths: Sequence[Path]) -> List[IngestedDocument]:
        ingested: List[IngestedDocument] = []
        for path in document_paths:
            chunks = build_chunks(
                path, chunk_size=self._chunk_size, overlap=self._chunk_overlap
            )
            if not chunks:
                continue
            embeddings = self._embed_chunks(chunks)
            stored_chunks = [
                DocumentChunk(
                    id=chunk.id,
                    text=chunk.text,
                    metadata=chunk.metadata,
                    embedding=embedding,
                )
                for chunk, embedding in zip(chunks, embeddings, strict=True)
            ]
            self._vector_store.add_chunks(stored_chunks)
            ingested.append(IngestedDocument(path=path, chunks=stored_chunks))
        return ingested

    def _embed_chunks(self, chunks: Sequence[ChunkInput]) -> List[List[float]]:
        texts = [chunk.text for chunk in chunks]
        return self._embeddings.embed(texts)

    def _build_context(self, ranked_chunks: Sequence[RankedChunk]) -> tuple[List[str], str]:
        sections: List[str] = []
        for item in ranked_chunks:
            metadata = item.chunk.metadata
            header = metadata.source
            if metadata.page is not None:
                header = f"{header} (page {metadata.page})"
            section = f"Source: {header}\n{item.chunk.text}"
            sections.append(section)
        context_text = "\n\n".join(sections) if sections else "No context available."
        return sections, context_text

    def _build_prompt(self, question: str, context_text: str) -> List[dict]:
        user_message = (
            "Answer the user question using ONLY the context below. Quote relevant "
            "sections when helpful. If the context does not contain enough "
            "information, respond with '정보를 찾을 수 없습니다.'.\n\n"
            f"Context:\n{context_text}\n\n"
            f"Question: {question}"
        )
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

    def answer(self, question: str, *, top_k: int = 8, with_evaluation: Optional[bool] = None) -> dict:
        if not question.strip():
            raise ValueError("Question must not be empty")
        if self._vector_store.is_empty():
            raise RuntimeError("Vector store is empty. Ingest documents first.")

        query_embedding = self._embeddings.embed([question])[0]
        ranked = self._vector_store.top_k(query_embedding, k=top_k)
        if not ranked:
            ranked = self._vector_store.top_k(query_embedding, k=max(10, top_k))
        _, context_text = self._build_context(ranked)
        messages = self._build_prompt(question, context_text)

        start = perf_counter()
        answer = self._chat.complete(messages)
        latency = perf_counter() - start

        sources = [
            {
                "id": item.chunk.id,
                "source": item.chunk.metadata.source,
                "page": item.chunk.metadata.page,
                "score": item.score,
                "text": item.chunk.text,
            }
            for item in ranked
        ]

        evaluation_result: EvaluationResult | None = None
        should_evaluate = (
            with_evaluation
            if with_evaluation is not None
            else self._evaluation_default
        )
        if should_evaluate and self._evaluator is not None:
            evaluation_result = self._evaluator.evaluate(
                question=question,
                answer=answer,
                context=context_text,
                latency_seconds=latency,
            )

        response: dict = {"answer": answer, "sources": sources, "latency_seconds": latency}
        if evaluation_result is not None:
            response["evaluation"] = evaluation_result.to_dict()
        return response
