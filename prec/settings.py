from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_CHAT_MODEL = "gpt-4.1-mini"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_SUPABASE_TABLE = "policy_chunks"
DEFAULT_SUPABASE_QUERY_FUNCTION = "match_policy_chunks"


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
        )
