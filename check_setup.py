"""List provider models, then optionally smoke-test the configured clients."""

import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main() -> None:
    # Import here so configuration errors receive the same concise CLI handling.
    from rag import config
    from rag.llm import get_embeddings, get_llm

    request = Request(
        config.NEBIUS_BASE_URL.rstrip("/") + "/models",
        headers={"Authorization": f"Bearer {config.NEBIUS_API_KEY}"},
    )
    try:
        with urlopen(request, timeout=60) as response:
            models = json.load(response)["data"]
    except HTTPError as exc:
        raise RuntimeError(
            f"GET /models returned HTTP {exc.code}; check NEBIUS_API_KEY and NEBIUS_BASE_URL."
        ) from exc

    groups: dict[str, list[str]] = {"likely embedding": [], "chat": []}
    for model in models:
        model_id = model["id"]
        group = (
            "likely embedding"
            if any(token in model_id.lower() for token in ("embed", "bge", "e5", "gte"))
            else "chat"
        )
        groups[group].append(model_id)
    for group, ids in groups.items():
        print(f"\n{group}:", flush=True)
        for model_id in sorted(ids):
            print(f"  {model_id}", flush=True)
        if not ids:
            print("  (none)", flush=True)

    if config.EMBED_MODEL and config.LLM_MODEL:
        vector = get_embeddings().embed_query("PostgreSQL replication lag troubleshooting")
        print(f"\nTest embedding vector dimension: {len(vector)}", flush=True)
        response = get_llm().invoke("Reply with only: DBA Assistant ready")
        print(f"Test chat response: {response.content}", flush=True)
    else:
        print("\nSet EMBED_MODEL and LLM_MODEL in .env, then rerun to test both clients.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Setup check failed: {exc}", file=sys.stderr)
        sys.exit(1)
