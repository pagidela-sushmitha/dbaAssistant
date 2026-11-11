"""Construct LangChain clients for Nebius's OpenAI-compatible API."""

# Tracing environment must exist before LangChain imports initialize clients.
from rag import config

from langchain_openai import ChatOpenAI, OpenAIEmbeddings


def get_embeddings() -> OpenAIEmbeddings:
    if not config.EMBED_MODEL:
        raise ValueError("Set EMBED_MODEL in .env; run uv run python check_setup.py to list IDs.")
    return OpenAIEmbeddings(
        model=config.EMBED_MODEL,
        base_url=config.NEBIUS_BASE_URL,
        api_key=config.NEBIUS_API_KEY,
        # Send raw text: OpenAI tokenization is not valid for third-party models.
        check_embedding_ctx_length=False,
        chunk_size=32,
        timeout=60,
    )


def get_llm(fast: bool = False) -> ChatOpenAI:
    model = config.FAST_LLM_MODEL if fast else config.LLM_MODEL
    setting = "FAST_LLM_MODEL" if fast else "LLM_MODEL"
    if not model:
        raise ValueError(f"Set {setting} in .env; run uv run python check_setup.py to list IDs.")
    return ChatOpenAI(
        model=model,
        base_url=config.NEBIUS_BASE_URL,
        api_key=config.NEBIUS_API_KEY,
        temperature=0,
        timeout=60,
    )
