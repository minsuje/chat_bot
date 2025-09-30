from __future__ import annotations

import os
from dataclasses import dataclass


def _get_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_float(value: str | None, default: float) -> float:
    try:
        return float(value) if value is not None else default
    except ValueError:
        return default


def _get_int(value: str | None, default: int | None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


DEFAULT_CHAT_MODEL = "gpt-4.1"
DEFAULT_EMBEDDING_MODEL = "upskyy/bge-m3-korean"
DEFAULT_SUPABASE_TABLE = "policy_chunks"
DEFAULT_SUPABASE_QUERY_FUNCTION = "match_policy_chunks"
DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-large"


# Load environment variables from a local .env file if present.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:
    pass


@dataclass
class Settings:
    openai_api_key: str
    supabase_url: str
    supabase_key: str
    openai_chat_model: str = DEFAULT_CHAT_MODEL
    openai_embedding_model: str = DEFAULT_EMBEDDING_MODEL
    chunk_size: int = 1200
    chunk_overlap: int = 200
    supabase_table: str = DEFAULT_SUPABASE_TABLE
    supabase_query_function: str = DEFAULT_SUPABASE_QUERY_FUNCTION
    evaluation_enabled: bool = False
    evaluation_model: str = DEFAULT_CHAT_MODEL
    evaluation_quality_weight: float = 0.7
    evaluation_speed_weight: float = 0.3
    evaluation_target_latency: float = 5.0
    reranking_enabled: bool = False
    reranker_model: str = DEFAULT_RERANKER_MODEL
    rerank_top_n: int | None = 8

    @classmethod
    def from_env(cls) -> "Settings":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY must be set")

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv(
            "SUPABASE_ANON_KEY"
        )
        if not supabase_url or not supabase_key:
            raise EnvironmentError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY) must be set"
            )

        return cls(
            openai_api_key=api_key,
            supabase_url=supabase_url,
            supabase_key=supabase_key,
            openai_chat_model=os.getenv("OPENAI_CHAT_MODEL", DEFAULT_CHAT_MODEL),
            openai_embedding_model=os.getenv(
                "OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL
            ),
            chunk_size=int(os.getenv("CHUNK_SIZE", "1200")),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "200")),
            supabase_table=os.getenv("SUPABASE_TABLE", DEFAULT_SUPABASE_TABLE),
            supabase_query_function=os.getenv(
                "SUPABASE_QUERY_FUNCTION", DEFAULT_SUPABASE_QUERY_FUNCTION
            ),
            evaluation_enabled=_get_bool(os.getenv("ENABLE_EVALUATION"), default=False),
            evaluation_model=os.getenv("EVALUATION_MODEL", DEFAULT_CHAT_MODEL),
            evaluation_quality_weight=_get_float(
                os.getenv("EVALUATION_QUALITY_WEIGHT"), default=0.7
            ),
            evaluation_speed_weight=_get_float(
                os.getenv("EVALUATION_SPEED_WEIGHT"), default=0.3
            ),
            evaluation_target_latency=_get_float(
                os.getenv("EVALUATION_TARGET_LATENCY"), default=5.0
            ),
            reranking_enabled=_get_bool(os.getenv("ENABLE_RERANKING"), default=False),
            reranker_model=os.getenv("RERANKER_MODEL", DEFAULT_RERANKER_MODEL),
            rerank_top_n=_get_int(os.getenv("RERANK_TOP_N"), default=5),
        )
