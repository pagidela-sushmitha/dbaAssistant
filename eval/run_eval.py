"""Run with uv run python eval/run_eval.py --tag baseline [--only-retrieval]."""

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from time import perf_counter

ROOT_DIR = Path(__file__).resolve().parent.parent
if __package__ in {None, ""}:
    sys.path.insert(0, str(ROOT_DIR))

from eval.metrics import (
    citation_accuracy, hit_at_5, key_fact_recall, parse_judgement,
    percentile, reciprocal_rank,
)

MODES = ("bm25", "dense", "hybrid")


def load_questions(path: Path) -> list[dict]:
    questions = json.loads(path.read_text(encoding="utf-8"))
    if len(questions) != 20 or len({item["id"] for item in questions}) != 20:
        raise ValueError("Expected exactly 20 questions with unique IDs.")
    required = {"id", "question", "category", "expected_docs", "key_facts", "should_escalate"}
    for item in questions:
        if not required <= item.keys() or type(item["should_escalate"]) is not bool:
            raise ValueError(f"Invalid question: {item.get('id', '?')}")
    return questions


def evaluate(questions, retriever, *, tag, only_retrieval=False, ask_fn=None, judge_fn=None):
    """Injectable boundaries let integration tests use fake search/answer/judge calls."""
    rows = []
    for position, item in enumerate(questions, 1):
        print(f"[{position}/{len(questions)}] {item['id']} ({item['category']}): {item['question']}", flush=True)
        row = {
            **item, "answer": None, "escalated": None, "citations": [],
            "timings": {}, "total_latency_ms": None, "judge_latency_ms": None,
            "key_fact_recall": None, "citation_accuracy": None,
            "faithful": None, "faithfulness_reason": "not run",
            "correct_behaviour": None, "search_queries": [],
            "retrieved_chunk_ids": [], "generation_chunk_ids": [],
            "error": "", "failures": [],
        }
        for mode in MODES:
            row[f"{mode}_hit_at_5"] = row[f"{mode}_mrr"] = None
            row[f"{mode}_chunk_ids"] = []
        eligible = not item["should_escalate"] and bool(item["expected_docs"])
        if eligible:
            for mode in MODES:
                try:
                    hits = retriever.search(item["question"], mode=mode, k=5)
                    row[f"{mode}_chunk_ids"] = [hit["id"] for hit in hits]
                    row[f"{mode}_hit_at_5"] = hit_at_5(hits, item["expected_docs"])
                    row[f"{mode}_mrr"] = reciprocal_rank(hits, item["expected_docs"])
                    if not row[f"{mode}_hit_at_5"]:
                        row["failures"].append(f"{mode} retrieval missed expected docs in top 5")
                except Exception as exc:
                    row[f"{mode}_hit_at_5"] = row[f"{mode}_mrr"] = 0.0
                    row["failures"].append(f"{mode} retrieval error: {type(exc).__name__}: {exc}")
            print("  Retrieval: " + ", ".join(f"{m} hit@5={row[f'{m}_hit_at_5']:.0f}" for m in MODES), flush=True)
        else:
            print("  Retrieval scoring skipped (no answerable expected docs).", flush=True)

        if not only_retrieval:
            metadata = {"category": item["category"], "eval": True, "tag": tag}
            started = perf_counter()
            try:
                result = ask_fn(item["question"], run_metadata=metadata)
                row.update({
                    "answer": result["answer"], "escalated": result["escalated"],
                    "citations": result.get("citations", []), "timings": result.get("timings", {}),
                    "total_latency_ms": result.get("total_ms", (perf_counter() - started) * 1000),
                    "search_queries": result.get("search_queries", [item["question"]]),
                    "retrieved_chunk_ids": [doc["id"] for doc in result.get("closest_docs", result.get("candidates", []))],
                    "generation_chunk_ids": [doc["id"] for doc in result.get("docs", [])],
                    "correct_behaviour": result["escalated"] == item["should_escalate"],
                })
                row["key_fact_recall"] = key_fact_recall(result["answer"], item["key_facts"])
                # An escalation note is not a factual answer, even if it repeats keywords.
                if result["escalated"] and item["key_facts"]:
                    row["key_fact_recall"] = 0.0
                if not row["correct_behaviour"]:
                    row["failures"].append("unexpected escalation" if result["escalated"] else "should have escalated")
                if row["key_fact_recall"] is not None and row["key_fact_recall"] < 1:
                    missing = [fact for fact in item["key_facts"] if result["escalated"] or fact.casefold() not in result["answer"].casefold()]
                    row["failures"].append("missing key facts: " + ", ".join(missing))
                if result["escalated"]:
                    row["faithfulness_reason"] = "skipped: escalated answer"
                else:
                    row["citation_accuracy"] = citation_accuracy(row["citations"], item["expected_docs"])
                    if row["citation_accuracy"] is not None and row["citation_accuracy"] < 1:
                        row["failures"].append("missing citations or citations outside expected docs")
                    judge_started = perf_counter()
                    try:
                        verdict = parse_judgement(judge_fn(item["question"], result.get("docs", []), result["answer"], metadata))
                        row["faithful"] = verdict["faithful"]
                        row["faithfulness_reason"] = verdict["reason"]
                        if not verdict["faithful"]:
                            row["failures"].append("unfaithful: " + verdict["reason"])
                    except Exception as exc:
                        row["faithfulness_reason"] = f"judge failed: {type(exc).__name__}: {exc}"
                        row["failures"].append(row["faithfulness_reason"])
                    finally:
                        row["judge_latency_ms"] = (perf_counter() - judge_started) * 1000
                print(f"  Answer: escalated={row['escalated']}, faithful={row['faithful']}, latency={row['total_latency_ms']:.0f} ms", flush=True)
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
                row["correct_behaviour"] = False
                row["total_latency_ms"] = (perf_counter() - started) * 1000
                row["key_fact_recall"] = 0.0 if item["key_facts"] else None
                row["failures"].append("pipeline error: " + row["error"])
                print(f"  Pipeline error: {row['error']}", flush=True)
        rows.append(row)
    return rows


def average(values):
    values = [value for value in values if value is not None]
    return mean(values) if values else None


def summarize(rows, only_retrieval=False):
    retrieval = {
        mode: {
            "questions": sum(row[f"{mode}_hit_at_5"] is not None for row in rows),
            "hit@5": average([row[f"{mode}_hit_at_5"] for row in rows]),
            "MRR@5": average([row[f"{mode}_mrr"] for row in rows]),
        }
        for mode in MODES
    }
    metrics = {}
    nodes = defaultdict(list)
    if not only_retrieval:
        answerable = [row for row in rows if not row["should_escalate"]]
        should_escalate = [row for row in rows if row["should_escalate"]]
        answered = [row for row in rows if row["escalated"] is False and not row["error"]]
        latencies = [row["total_latency_ms"] for row in rows if row["total_latency_ms"] is not None]
        metrics = {
            "Resolution rate": average([row["escalated"] is False and not row["error"] for row in answerable]),
            "Correct escalation rate": average([row["escalated"] is True and not row["error"] for row in should_escalate]),
            "False escalation rate": average([row["escalated"] is True for row in answerable]),
            "Correct behaviour rate": average([row["correct_behaviour"] for row in rows]),
            "Mean key-fact recall": average([row["key_fact_recall"] for row in rows]),
            "Mean citation accuracy": average([row["citation_accuracy"] for row in rows]),
            "Mean faithfulness": average([row["faithful"] for row in rows]),
            "Judge coverage of non-escalated answers": average([row["faithful"] is not None for row in answered]),
            "p50 total latency (ms)": percentile(latencies, 50),
            "p95 total latency (ms)": percentile(latencies, 95),
            "Pipeline errors": sum(bool(row["error"]) for row in rows),
        }
        for row in rows:
            for node, elapsed in row["timings"].items():
                nodes[node].append(elapsed)
    return metrics, retrieval, {node: mean(values) for node, values in sorted(nodes.items())}


def display(value, percent=False):
    if value is None:
        return "—"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return f"{value:.1%}" if percent else f"{value:.2f}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def write_outputs(rows, tag, output_dir, only_retrieval=False):
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"results_{tag}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value for key, value in row.items()})
    metrics, retrieval, nodes = summarize(rows, only_retrieval)
    lines = [
        f"# DBA Assistant evaluation: {tag}", "",
        f"Mode: {'retrieval only' if only_retrieval else 'retrieval and end-to-end'}. Questions: {len(rows)}.", "",
        "## Summary", "", "| Metric | Value |", "| --- | ---: |",
    ]
    if metrics:
        for name, value in metrics.items():
            lines.append(f"| {name} | {display(value, percent='latency' not in name and name != 'Pipeline errors')} |")
    else:
        lines.append("| End-to-end metrics | Not run |")
    lines.extend(["", "## Retrieval comparison", "", "| Mode | Questions | Hit@5 | MRR@5 |", "| --- | ---: | ---: | ---: |"])
    for mode, values in retrieval.items():
        lines.append(f"| {mode} | {values['questions']} | {display(values['hit@5'], True)} | {display(values['MRR@5'])} |")
    lines.extend([
        "", "A retrieval hit means any expected document appears in the first five chunks. MRR uses the first relevant chunk in those same five results. Multi-document hits do not imply complete evidence coverage.",
        "", "## Per-question results", "",
        "| ID | Category | Escalated | Key-fact recall | Faithful | Latency (ms) |",
        "| --- | --- | --- | ---: | --- | ---: |",
    ])
    for row in rows:
        values = [row['id'], row['category'], display(row['escalated']), display(row['key_fact_recall'], True), display(row['faithful']), display(row['total_latency_ms'])]
        lines.append("| " + " | ".join(values) + " |")
    if nodes:
        lines.extend(["", "## Mean node latency", "", "| Node | Mean ms |", "| --- | ---: |"])
        lines.extend(f"| {node} | {elapsed:.2f} |" for node, elapsed in nodes.items())
    lines.extend([
        "", "## Scoring notes", "",
        "- The ambiguous question allows a short overview or clarification and has no key-fact or expected-document score.",
        "- Empty fact lists are unscored. Escalated answerable cases receive zero key-fact recall; drafted escalation notes do not count as factual answers.",
        "- Fact checks use literal case-insensitive substrings, so correct paraphrases may miss them. Expected documents are an explicit benchmark, not a semantic citation-support judge.",
        "- Citation accuracy counts distinct cited documents, on non-escalated answers with expected docs; missing citations score zero.",
        "- Faithfulness uses the main model and the actual generation sources. Escalations are skipped; judge errors are unscored and listed as failures. Judge coverage prevents hidden judge failures.",
        "- Faithfulness is an automated model judgement; review the listed reasons against the source documents before treating a flagged answer as an established defect.",
        "- Total latency covers ask(), excluding Part A and the separate faithfulness judge. Node means use only questions that executed the node; repeated-node times are accumulated by the pipeline.",
        "- Retrieval-only mode uses query embeddings for dense/hybrid search but makes no generative LLM calls.",
        "", "## Failures", "",
    ])
    failed = [row for row in rows if row["failures"]]
    if not failed:
        lines.append("None.")
    for row in failed:
        lines.extend([f"### {row['id']}: {row['question']}", "", display("; ".join(row["failures"])), ""])
        lines.append("Retrieved chunk IDs:")
        for mode in MODES:
            lines.append(f"- {mode}: {', '.join(row[f'{mode}_chunk_ids']) or '(not scored)'}")
        if not only_retrieval:
            lines.append(f"- Pipeline (all retrieval passes): {', '.join(row['retrieved_chunk_ids']) or '(none)'}")
            lines.append(f"- Generation sources: {', '.join(row['generation_chunk_ids']) or '(none)'}")
        lines.append("")
    report_path = output_dir / f"report_{tag}.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_path, report_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Evaluate DBA Assistant retrieval and grounded answers.")
    parser.add_argument("--tag", default="baseline")
    parser.add_argument("--only-retrieval", action="store_true", help="Skip generation/judging; dense and hybrid still call the embedding API.")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", args.tag):
        parser.error("--tag must contain only letters, digits, underscores, or hyphens.")

    from rag import config  # Load tracing environment before LangChain imports.
    from rag.retriever import HybridRetriever
    from langchain_core.tracers.langchain import wait_for_all_tracers

    try:
        questions = load_questions(ROOT_DIR / "eval/questions.json")
        retriever = HybridRetriever()
        ask_fn = judge_fn = None
        if not args.only_retrieval:
            from rag.graph import ask, response_text, sources_text
            from rag.llm import get_llm
            from rag.prompts import EVAL_FAITHFULNESS_PROMPT

            judge = get_llm()
            ask_fn = ask

            def judge_fn(question, docs, answer, metadata):
                response = judge.invoke([
                    ("system", EVAL_FAITHFULNESS_PROMPT),
                    ("human", f"Question: {question}\n\nSources:\n{sources_text(docs)}\n\nAnswer:\n{answer}"),
                ], config={"run_name": "dba-faithfulness-judge", "metadata": metadata})
                return response_text(response)

        rows = evaluate(questions, retriever, tag=args.tag, only_retrieval=args.only_retrieval, ask_fn=ask_fn, judge_fn=judge_fn)
        paths = write_outputs(rows, args.tag, ROOT_DIR / "eval/results", args.only_retrieval)
        for path in paths:
            print(f"Saved {path}")
    finally:
        wait_for_all_tracers()


if __name__ == "__main__":
    main()
