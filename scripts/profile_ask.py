"""Profile individual asks, without running evaluation or changing scoring.

Run: uv run python -m scripts.profile_ask --runs 2
The second call measures reuse in the same process, including query caching.
"""

import argparse
import cProfile
import json
import pstats

from rag.graph import ask


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", default=(
        "It's 2am and an inactive replication slot is filling the disk — "
        "what approvals do I need to drop it, and when is the emergency change ticket due?"
    ))
    parser.add_argument("--runs", type=int, default=1)
    args = parser.parse_args()
    print(f"Question: {args.question}", flush=True)
    for run in range(1, args.runs + 1):
        profiler = cProfile.Profile()
        result = profiler.runcall(ask, args.question)
        stats = pstats.Stats(profiler).stats

        def elapsed(file_suffix, function):
            return sum(value[3] for (file, _, name), value in stats.items()
                       if file.endswith(file_suffix) and name == function) * 1000

        # BM25Okapi.__init__ calls its superclass: count only the outer call.
        bm25_entries = [value[3] * 1000 for (file, _, name), value in stats.items()
                        if file.endswith("rank_bm25.py") and name == "__init__"]
        bm25 = max(bm25_entries, default=0)
        construction = elapsed("rag/retriever.py", "__init__")
        search = elapsed("rag/retriever.py", "search")
        query_vector = elapsed("rag/retriever.py", "_query_vector")
        print(json.dumps({
            "run": run,
            "breakdown_ms": {
                "index_load_validation_tokenization": max(0, construction - bm25),
                "bm25_build": bm25,
                "embed_query_api": elapsed("embeddings/base.py", "embed_query"),
                "query_vector_including_client_setup": query_vector,
                "scoring_and_result_assembly": max(0, search - query_vector),
            },
            "node_ms": result["timings"],
            "total_ms": result["total_ms"],
            "answer": result["answer"],
        }, indent=2), flush=True)


if __name__ == "__main__":
    main()
