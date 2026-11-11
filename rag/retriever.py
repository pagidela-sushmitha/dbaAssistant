"""BM25, cosine, and reciprocal-rank retrieval: uv run python -m rag.retriever."""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from rag import config  # Initialize tracing before importing LangChain.

import numpy as np
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, Field
from rank_bm25 import BM25Okapi

Mode = Literal["hybrid", "dense", "bm25"]
INDEX_DIR = Path(__file__).resolve().parent.parent / "index"
TOKEN_PATTERN = re.compile(r"[a-z0-9_]+(?:[.\-][a-z0-9_]+)*")


def tokenize(text: str) -> list[str]:
    """Keep SQLSTATEs, SQL identifiers, and dotted/hyphenated names intact."""
    return TOKEN_PATTERN.findall(text.lower())


class HybridRetriever:
    """Load the index once and reuse query embeddings across search modes.

    Pure modes score by BM25 or cosine similarity. Hybrid mode scores only
    the union of the two top-20 lists with RRF. Ranks refer to these lists;
    an uncomputed rank (for the other pure mode) is None.
    """

    def __init__(self, index_dir: str | Path = INDEX_DIR) -> None:
        index_dir = Path(index_dir)
        with (index_dir / "chunks.jsonl").open(encoding="utf-8") as handle:
            self.chunks = [json.loads(line) for line in handle if line.strip()]
        self.embeddings = np.load(index_dir / "embeddings.npy", allow_pickle=False)
        if (
            not self.chunks
            or self.embeddings.ndim != 2
            or self.embeddings.shape[0] != len(self.chunks)
            or self.embeddings.shape[1] == 0
        ):
            raise ValueError("Index must contain chunks and one embedding row per chunk. Re-run ingestion.")
        if not np.isfinite(self.embeddings).all() or not np.allclose(
            np.linalg.norm(self.embeddings, axis=1), 1, atol=1e-4
        ):
            raise ValueError("Index embeddings must be finite and L2-normalized. Re-run ingestion.")
        ids = [chunk["id"] for chunk in self.chunks]
        if len(set(ids)) != len(ids):
            raise ValueError("Index contains duplicate chunk IDs. Re-run ingestion.")
        tokens = [tokenize(chunk["text"]) for chunk in self.chunks]
        if not any(tokens):
            raise ValueError("Index has no searchable tokens.")
        self.bm25 = BM25Okapi(tokens)
        self._embedding_client = None
        self._query_cache: dict[str, np.ndarray] = {}

    def _query_vector(self, query: str) -> np.ndarray:
        if query not in self._query_cache:
            # BM25-only searches do not need a provider connection.
            if self._embedding_client is None:
                from rag.llm import get_embeddings

                self._embedding_client = get_embeddings()
            vector = np.asarray(self._embedding_client.embed_query(query), dtype=np.float32)
            if vector.shape != (self.embeddings.shape[1],):
                raise ValueError(
                    f"Query embedding must have dimension {self.embeddings.shape[1]}; "
                    "use the same EMBED_MODEL as ingestion."
                )
            norm = np.linalg.norm(vector)
            if not np.isfinite(vector).all() or not np.isfinite(norm) or norm == 0:
                raise ValueError("Query embedding must be finite and nonzero.")
            self._query_cache[query] = vector / norm
        return self._query_cache[query]

    def search(self, query: str, mode: Mode = "hybrid", k: int = 8) -> list[dict]:
        if mode not in {"hybrid", "dense", "bm25"}:
            raise ValueError("mode must be 'hybrid', 'dense', or 'bm25'.")
        if not isinstance(k, int) or isinstance(k, bool) or k < 1:
            raise ValueError("k must be a positive integer.")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a nonempty string.")

        bm25_ranks: dict[int, int] = {}
        dense_ranks: dict[int, int] = {}
        # Stable sorting gives tied scores a reproducible index-order ranking.
        if mode in {"hybrid", "bm25"}:
            bm25_scores = np.asarray(self.bm25.get_scores(tokenize(query)))
            bm25_order = np.argsort(-bm25_scores, kind="stable")
            bm25_ranks = {int(i): rank for rank, i in enumerate(bm25_order[:20], 1)}
        if mode in {"hybrid", "dense"}:
            dense_scores = self.embeddings @ self._query_vector(query)
            dense_order = np.argsort(-dense_scores, kind="stable")
            dense_ranks = {int(i): rank for rank, i in enumerate(dense_order[:20], 1)}

        if mode == "hybrid":
            scores: dict[int, float] = {}
            for ranks in (bm25_ranks, dense_ranks):
                for i, rank in ranks.items():
                    scores[i] = scores.get(i, 0.0) + 1.0 / (60 + rank)
            order = sorted(scores, key=lambda i: (-scores[i], i))[:k]
        elif mode == "bm25":
            order = bm25_order[:k]
            scores = bm25_scores
        else:
            order = dense_order[:k]
            scores = dense_scores

        return [
            {
                "id": self.chunks[i]["id"],
                "text": self.chunks[i]["text"],
                "metadata": dict(self.chunks[i]["metadata"]),
                "score": float(scores[i]),
                "bm25_rank": bm25_ranks.get(int(i)),
                "dense_rank": dense_ranks.get(int(i)),
            }
            for i in order
        ]


@lru_cache(maxsize=1)
def get_retriever() -> HybridRetriever:
    """Lazily load the default index and build BM25 once per process."""
    return HybridRetriever()


class DBARetriever(BaseRetriever):
    """LangChain adapter; e.g. DBARetriever(mode='hybrid', k=8).invoke(query)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    hybrid_retriever: HybridRetriever = Field(default_factory=get_retriever)
    mode: Mode = "hybrid"
    k: int = Field(default=8, gt=0)

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        return [
            Document(
                page_content=result["text"],
                metadata={
                    **result["metadata"],
                    "id": result["id"],
                    "score": result["score"],
                    "bm25_rank": result["bm25_rank"],
                    "dense_rank": result["dense_rank"],
                },
            )
            for result in self.hybrid_retriever.search(query, mode=self.mode, k=self.k)
        ]


def main() -> None:
    retriever = get_retriever()
    queries = [
        "what does 40P01 mean",
        "disk is full because of WAL",
        "who approves break-glass access",
        "pg-billing too many clients after a deploy",
    ]
    modes: tuple[Mode, ...] = ("hybrid", "dense", "bm25")
    for query in queries:
        results = {mode: retriever.search(query, mode=mode, k=5) for mode in modes}
        width = max(6, *(len(result["id"]) for hits in results.values() for result in hits))
        print(f"\nQuery: {query}")
        print("Rank | " + " | ".join(mode.ljust(width) for mode in modes))
        print("-----+-" + "-+-".join("-" * width for _ in modes))
        for rank in range(max(map(len, results.values()))):
            cells = [results[mode][rank]["id"] if rank < len(results[mode]) else "" for mode in modes]
            print(f"{rank + 1:4} | " + " | ".join(cell.ljust(width) for cell in cells))


if __name__ == "__main__":
    main()
