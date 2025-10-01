from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable, List

from .app import create_chatbot_service
from .service import ChatbotService
from .settings import Settings


def _build_service(settings: Settings | None = None) -> ChatbotService:
    return create_chatbot_service(settings)


def _collect_pdf_files(targets: Iterable[str], recursive: bool) -> List[Path]:
    collected: List[Path] = []
    seen = set()
    for target in targets:
        path = Path(target).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        if path.is_file():
            if path.suffix.lower() != ".pdf":
                continue
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                collected.append(resolved)
        elif path.is_dir():
            iterator = path.rglob("*.pdf") if recursive else path.glob("*.pdf")
            for pdf in iterator:
                resolved = pdf.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    collected.append(resolved)
        else:
            raise FileNotFoundError(f"Unsupported path type: {path}")
    collected.sort()
    return collected


def _handle_ingest(args: argparse.Namespace) -> int:
    settings = None
    try:
        settings = Settings.from_env()
        service = _build_service(settings)
    except Exception as exc:  # pragma: no cover - CLI feedback
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    try:
        pdf_files = _collect_pdf_files(args.paths, args.recursive)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not pdf_files:
        print("No PDF files found. Provide files or directories containing PDFs.")
        return 1

    ingested = service.ingest(pdf_files)
    total_chunks = sum(len(doc.chunks) for doc in ingested)
    print(f"Ingested {len(ingested)} document(s) with {total_chunks} chunks.")
    for doc in ingested:
        print(f"- {doc.path} ({len(doc.chunks)} chunks)")
    return 0


def _handle_query(args: argparse.Namespace) -> int:
    settings = None
    try:
        settings = Settings.from_env()
        service = _build_service(settings)
    except Exception as exc:  # pragma: no cover - CLI feedback
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    try:
        result = service.answer(
            args.question,
            top_k=args.top_k,
            with_evaluation=args.with_eval,
            with_rerank=args.with_rerank,
        )
    except Exception as exc:
        print(f"Query failed: {exc}", file=sys.stderr)
        return 1

    print("Answer:\n")
    print(result["answer"].strip())
    latency_seconds = float(result.get("latency_seconds", 0.0) or 0.0)
    latency_ms = latency_seconds * 1000.0
    print(f"\nLatency: {latency_ms:.0f} ms")
    print("\nSources:")
    for source in result["sources"]:
        location = source["source"]
        if source["page"] is not None:
            location = f"{location} (page {source['page']})"
        score = f"{source['score']:.4f}" if source.get("score") is not None else "n/a"
        vector_score = source.get("vector_score")
        score_display = score
        if vector_score is not None:
            score_display = f"{score} (vector {vector_score:.4f})"
        print(
            f"- [{score_display}] {location}\n  {source['text'][:300]}"
            + ("..." if len(source['text']) > 300 else "")
        )

    evaluation = result.get("evaluation")
    if evaluation:
        print("\nEvaluation:")
        eval_latency = float(evaluation.get("latency_seconds", latency_seconds) or 0.0)
        eval_latency_ms = eval_latency * 1000.0
        print(
            f"  Quality: {evaluation['quality_score']:.3f}\n"
            f"  Speed:   {evaluation['speed_score']:.3f}\n"
            f"  Final:   {evaluation['final_score']:.3f}\n"
            f"  Latency: {eval_latency_ms:.0f} ms\n"
            f"  Reason:  {evaluation['reasoning']}"
        )

    if result.get("rerank_applied"):
        print("\nRerank: enabled")
    return 0


def _handle_serve(args: argparse.Namespace) -> int:
    try:
        settings = Settings.from_env()
    except Exception as exc:  # pragma: no cover - CLI feedback
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    from uvicorn import run  # Local import to avoid dependency during compile time

    app = args.app_factory(settings)
    host = args.host or os.getenv("HOST", "0.0.0.0")
    port = args.port or int(os.getenv("PORT", "8000"))
    run(app, host=host, port=port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Policy chatbot CLI for ingesting PDFs and asking questions."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Ingest PDF files into Supabase.")
    ingest_parser.add_argument(
        "paths",
        nargs="+",
        help="PDF file or directory paths to ingest.",
    )
    ingest_parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively search directories for PDFs.",
    )
    ingest_parser.set_defaults(func=_handle_ingest)

    query_parser = subparsers.add_parser("ask", help="Ask a question against the knowledge base.")
    query_parser.add_argument("question", help="The natural language question to ask.")
    query_parser.add_argument(
        "--top-k",
        type=int,
        default=20,
        help="Number of relevant chunks to retrieve (default: 20).",
    )
    query_parser.add_argument(
        "--with-eval",
        action="store_true",
        help="Run LLM-based self-evaluation and scoring.",
    )
    query_parser.add_argument(
        "--with-rerank",
        action="store_true",
        help="Apply cross-encoder reranking before answering.",
    )
    query_parser.set_defaults(func=_handle_query)

    serve_parser = subparsers.add_parser("serve", help="Run the FastAPI server (optional).")
    serve_parser.add_argument(
        "--host",
        default=os.getenv("HOST"),
        help="Host interface to bind (defaults to HOST env or 0.0.0.0).",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8000")),
        help="Port to bind (defaults to PORT env or 8000).",
    )
    serve_parser.set_defaults(func=_handle_serve, app_factory=create_app_wrapper)

    return parser


def create_app_wrapper(settings: Settings) -> object:
    from .app import create_app

    return create_app(settings)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
