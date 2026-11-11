"""Ask the knowledge base: uv run python cli.py 'your question'."""

from rag import config  # Load .env before any LangChain/LangGraph imports.

import argparse
import sys

from rag.graph import ask


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the Northwind Data DBA knowledge base.")
    parser.add_argument("question", help="Enclose the question in quotes.")
    args = parser.parse_args()
    result = ask(args.question, run_metadata={"interface": "cli"})
    print(result["answer"])
    print("\nCitations:")
    for citation in result["citations"]:
        print(f"  [{citation['n']}] {citation['title']} > {citation['section']}")
    if not result["citations"]:
        print("  (none)")
    print(f"\nConfidence: {result['confidence']}")
    print(f"Escalated: {result['escalated']}")
    print("Stale warning: " + ("Cited sources are older than 180 days." if result["stale_warning"] else "none"))
    print("\nLatency (ms; repeated nodes accumulated):")
    for node, elapsed in result["timings"].items():
        print(f"  {node}: {elapsed:.1f}")
    print(f"  total: {result['total_ms']:.1f}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"DBA Assistant failed: {exc}", file=sys.stderr)
        sys.exit(1)
