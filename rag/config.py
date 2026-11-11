"""Load project settings from the environment, with .env as a fallback."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env", override=False)

NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY", "").strip()
NEBIUS_BASE_URL = os.getenv(
    "NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/"
).strip() or "https://api.tokenfactory.nebius.com/v1/"
EMBED_MODEL = os.getenv("EMBED_MODEL", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "").strip()
FAST_LLM_MODEL = os.getenv("FAST_LLM_MODEL", "").strip()
LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "false").strip().lower()
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "").strip()
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "dba-assistant").strip() or "dba-assistant"

# LangChain/LangGraph read tracing settings directly from the environment.
os.environ.setdefault("LANGSMITH_TRACING", LANGSMITH_TRACING)
os.environ["LANGSMITH_PROJECT"] = LANGSMITH_PROJECT

if not NEBIUS_API_KEY:
    raise RuntimeError(
        "NEBIUS_API_KEY is missing. Copy .env.example to .env and set your Nebius API key."
    )
