"""Offline integration tests: uv run python -m unittest discover -s tests."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Tests must not send traces or call a provider.
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["NEBIUS_API_KEY"] = "offline-test-key"

from rag import graph as pipeline
from langchain_core.tracers.context import collect_runs


def candidate(n, stale=False):
    return {
        "id": f"runbook#{n}", "text": f"Evidence {n}: an approved DBA operation.",
        "score": 1 / (60 + n), "bm25_rank": n, "dense_rank": n,
        "metadata": {
            "title": f"Runbook {n}", "section": "Recovery", "source": "runbook.md",
            "stale": stale, "last_reviewed": "2026-09-01",
        },
    }


def grades(*scores):
    return json.dumps([{"id": i, "score": score} for i, score in enumerate(scores, 1)])


class ScriptedModel:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []
        self.options = []

    def invoke(self, messages, **kwargs):
        self.calls.append(messages)
        self.options.append(kwargs)
        return SimpleNamespace(content=next(self.responses))


class PipelineTests(unittest.TestCase):
    def run_pipeline(self, batches, fast_responses, answer="Follow the approved operation. [1]"):
        retriever = MagicMock()
        retriever.search.side_effect = batches
        fast = ScriptedModel(*fast_responses)
        main = ScriptedModel(answer)
        compiled = pipeline.build_graph(retriever=retriever, fast_llm=fast, llm=main)
        with patch.object(pipeline, "graph", compiled):
            result = pipeline.ask("How do I recover?", {"case": self.id()})
        return result, retriever, fast, main

    def test_batched_grade_sort_citations_confidence_and_freshness(self):
        docs = [candidate(1, stale=True), candidate(2), candidate(3)]
        result, retriever, fast, main = self.run_pipeline(
            [docs], [grades(2, 3, 3), '{"grounded": true, "unsupported": ""}'],
            "Follow the approved operation. [1] Repeat its validation. [1]",
        )
        self.assertEqual([d["id"] for d in result["docs"]], ["runbook#2", "runbook#3", "runbook#1"])
        self.assertEqual([d["grade_score"] for d in result["candidates"]], [2, 3, 3])
        self.assertEqual(result["confidence"], "high")
        self.assertEqual(result["citations"], [{
            "n": 1, "title": "Runbook 2", "section": "Recovery",
            "source": "runbook.md", "chunk_id": "runbook#2",
        }])
        self.assertFalse(result["stale_warning"])  # The stale source was not cited.
        self.assertFalse(result["escalated"])
        self.assertTrue(result["grounded"])
        self.assertEqual(len(fast.calls), 2)  # One batch grade, one grounding call.
        self.assertEqual(len(main.calls), 1)
        self.assertEqual(main.options, [{"max_tokens": 500}])
        self.assertEqual(fast.options, [{"max_tokens": 300}, {"max_tokens": 150}])
        retriever.search.assert_called_once_with("How do I recover?", mode="hybrid", k=8)
        self.assertEqual(set(result["timings"]), {"retrieve", "grade", "generate", "check_grounding", "finalize"})
        self.assertTrue(all(t >= 0 for t in result["timings"].values()))
        self.assertGreaterEqual(result["total_ms"], sum(result["timings"].values()))

    def test_conflicting_sources_prompt_requires_explicit_rules_and_stricter_recommendation(self):
        docs = [candidate(1), candidate(2)]
        docs[0]["text"] = (
            "Disk runbook: dropping an inactive slot needs slot owner or on-call DBA lead approval."
        )
        docs[1]["text"] = (
            "Change policy: emergency changes require both on-call DBA lead and engineering "
            "manager approval. Complete the change ticket within 24 hours."
        )
        answer = (
            "The disk runbook permits slot owner or on-call DBA lead approval [1], but the "
            "change policy requires both on-call DBA lead and engineering manager approval "
            "for emergency changes [2]. These rules conflict; follow the stricter requirement "
            "and obtain both approvals [2]. Complete the ticket within 24 hours [2]."
        )
        result, _, _, main = self.run_pipeline(
            [docs], [grades(3, 3), '{"grounded": true, "unsupported": ""}'], answer,
        )
        prompt = main.calls[0][0][1]
        for rule in (
            "explicitly state the", "conflict", "each rule with its own source citation",
            "stricter requirement", "Do not silently merge conflicting rules",
        ):
            self.assertIn(rule, prompt)
        evidence = main.calls[0][1][1]
        for n, doc in enumerate(docs, 1):
            self.assertIn(f"[{n}]", evidence)
            self.assertIn(doc["text"], evidence)
        self.assertEqual(result["answer"], answer)
        self.assertEqual([c["n"] for c in result["citations"]], [1, 2])
        self.assertFalse(result["escalated"])

    def test_cited_stale_document_warns_and_grade_two_is_medium(self):
        result, *_ = self.run_pipeline(
            [[candidate(1, stale=True)]], [grades(2), '{"grounded": true, "unsupported": ""}'],
        )
        self.assertTrue(result["stale_warning"])
        self.assertEqual(result["confidence"], "medium")

    def test_citations_are_unique_sorted_and_only_include_cited_sources(self):
        result, *_ = self.run_pipeline(
            [[candidate(n) for n in range(1, 5)]],
            [grades(3, 3, 3, 3), '{"grounded": true, "unsupported": ""}'],
            "First point. [3] Second point. [1] Repeated support. [3]",
        )
        self.assertEqual([citation["n"] for citation in result["citations"]], [1, 3])
        self.assertEqual([citation["chunk_id"] for citation in result["citations"]], ["runbook#1", "runbook#3"])

    def test_exactly_one_rewrite_then_success(self):
        result, retriever, fast, _ = self.run_pipeline(
            [[candidate(1)], [candidate(2)]],
            [grades(0), "WAL disk capacity pg_replication_slots", grades(3), '{"grounded": true, "unsupported": ""}'],
        )
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(retriever.search.call_count, 2)
        self.assertEqual(result["search_queries"], ["How do I recover?", "WAL disk capacity pg_replication_slots"])
        self.assertIn("rewrite", result["timings"])
        self.assertEqual(len(fast.calls), 4)
        self.assertEqual(fast.options, [
            {"max_tokens": 300}, {"max_tokens": 60},
            {"max_tokens": 300}, {"max_tokens": 150},
        ])
        self.assertEqual(result["confidence"], "high")

    def test_rewrite_is_one_line_with_at_most_twenty_unique_terms(self):
        terms = ["WAL", "wal,", "pg-orders", "PG-ORDERS", "pg_stat_activity", "40P01"]
        terms.extend(f"term_{n}" for n in range(25))
        result, retriever, fast, _ = self.run_pipeline(
            [[candidate(1)], [candidate(2)]],
            [grades(0), "\n".join(terms), grades(3), '{"grounded": true, "unsupported": ""}'],
        )
        rewritten = result["search_query"]
        self.assertEqual(len(rewritten.split()), 20)
        self.assertNotIn("\n", rewritten)
        self.assertEqual(rewritten.split()[:4], ["WAL", "pg-orders", "pg_stat_activity", "40P01"])
        normalized = [term.casefold().strip(".,;:!?\"'`") for term in rewritten.split()]
        self.assertEqual(len(normalized), len(set(normalized)))
        self.assertEqual(retriever.search.call_args_list[1].args[0], rewritten)
        self.assertIn("at most 20 words", fast.calls[1][0][1])

    def test_empty_rewrite_fallback_also_obeys_word_limit(self):
        question = " ".join(f"term_{n}" for n in range(30))
        engine = MagicMock()
        engine.search.return_value = []
        compiled = pipeline.build_graph(retriever=engine, fast_llm=ScriptedModel("  "))
        with patch.object(pipeline, "graph", compiled):
            result = pipeline.ask(question)
        self.assertEqual(result["search_query"], " ".join(question.split()[:20]))
        self.assertEqual(result["attempts"], 1)

    def test_two_empty_grades_escalate_with_both_searches(self):
        result, retriever, fast, main = self.run_pipeline(
            [[candidate(1)], [candidate(2)]], [grades(1), "rewritten query", grades(0)],
        )
        self.assertEqual(retriever.search.call_count, 2)
        self.assertEqual(result["attempts"], 1)
        self.assertTrue(result["escalated"])
        self.assertEqual(result["confidence"], "none")
        self.assertEqual(result["citations"], [])
        self.assertEqual(result["answer"].splitlines()[0], "I couldn't find a reliable answer in the DBA knowledge base.")
        for text in ("#dba-help", "PagerDuty DBA-Primary", "/page dba", "rewritten query", "runbook#1", "runbook#2"):
            self.assertIn(text, result["answer"])
        self.assertEqual(len(main.calls), 0)
        self.assertEqual(len(fast.calls), 3)
        self.assertEqual([d["grade_score"] for d in result["candidates"]], [0])

    def test_empty_retrieval_preserves_earlier_closest_documents(self):
        result, _, fast, _ = self.run_pipeline([[candidate(1)], []], [grades(0), "new search"])
        self.assertTrue(result["escalated"])
        self.assertIn("runbook#1", result["answer"])
        self.assertEqual(len(fast.calls), 2)

    def test_grade_parse_failure_uses_top_three_and_truncates_evidence(self):
        docs = [candidate(i) for i in range(1, 9)]
        docs[0]["text"] = "a" * 700 + "NEVER_SENT_TO_GRADER"
        result, _, fast, _ = self.run_pipeline(
            [docs], ["not valid JSON", '{"grounded": true, "unsupported": ""}'],
        )
        self.assertEqual([d["id"] for d in result["docs"]], ["runbook#1", "runbook#2", "runbook#3"])
        self.assertEqual(result["confidence"], "medium")
        self.assertNotIn("NEVER_SENT_TO_GRADER", fast.calls[0][1][1])
        self.assertTrue(all(d["grade_score"] is None for d in result["candidates"]))
        self.assertIn("[8]", fast.calls[0][1][1])

    def test_invalid_grades_fall_back_instead_of_crashing(self):
        for raw in ('[1]', '[{"id": true, "score": 3}]', '[{"id": 1, "score": 4}]', '[]'):
            with self.subTest(raw=raw):
                result, *_ = self.run_pipeline(
                    [[candidate(1)]], [raw, '{"grounded": true, "unsupported": ""}'],
                )
                self.assertEqual(result["confidence"], "medium")

    def test_insufficient_unsupported_malformed_and_bad_citations_escalate(self):
        cases = [
            ("INSUFFICIENT_CONTEXT", '{"grounded": true, "unsupported": ""}'),
            ("Invented procedure. [1]", '{"grounded": false, "unsupported": "invented"}'),
            ("Procedure. [1]", "not JSON"),
            ("Procedure. [1]", '{"grounded": "true", "unsupported": ""}'),
            ("Procedure. [1]", '{"grounded": true, "unsupported": "command not supported"}'),
            ("Procedure. [9]", '{"grounded": true, "unsupported": ""}'),
            ("Procedure without citation.", '{"grounded": true, "unsupported": ""}'),
        ]
        for answer, verdict in cases:
            with self.subTest(answer=answer, verdict=verdict):
                result, retriever, _, _ = self.run_pipeline([[candidate(1)]], [grades(3), verdict], answer)
                self.assertTrue(result["escalated"])
                self.assertFalse(result["grounded"])
                self.assertEqual(result["confidence"], "none")
                self.assertEqual(result["answer"].splitlines()[0], "I couldn't find a reliable answer in the DBA knowledge base.")
                self.assertEqual(retriever.search.call_count, 1)

    def test_json_code_fences_and_commentary_fallback(self):
        for text in ('```json\n[{"id": 1, "score": 3}]\n```', 'Here are the grades: [{"id": 1, "score": 3}] Done.'):
            self.assertEqual(pipeline.parse_json(text, list), [{"id": 1, "score": 3}])
        self.assertEqual(pipeline.parse_json('Audit: {"grounded": true, "unsupported": ""}', dict)["grounded"], True)

    def test_run_metadata_and_name_are_passed_to_invoke(self):
        fake = MagicMock()
        fake.invoke.return_value = {"answer": "test"}
        metadata = {"experiment": "offline"}
        with patch.object(pipeline, "graph", fake):
            result = pipeline.ask(" test question ", metadata)
        args, kwargs = fake.invoke.call_args
        self.assertEqual(kwargs["input"]["question"], "test question")
        self.assertEqual(kwargs["input"]["search_query"], "test question")
        self.assertEqual(set(kwargs["input"]), {"question", "search_query"})
        self.assertEqual(result["answer"], "test")
        self.assertEqual(kwargs["config"], {"run_name": "dba-assistant", "metadata": metadata})
        with self.assertRaises(ValueError):
            pipeline.ask(" ")

    def test_root_trace_records_question_search_query_and_final_answer(self):
        with collect_runs() as recorder:
            result, *_ = self.run_pipeline(
                [[candidate(1)]], [grades(3), '{"grounded": true, "unsupported": ""}'],
            )
        root = next(run for run in recorder.traced_runs if run.name == "dba-assistant")
        self.assertEqual(root.inputs["question"], "How do I recover?")
        self.assertEqual(root.inputs["search_query"], "How do I recover?")
        self.assertEqual(root.inputs, {
            "question": "How do I recover?", "search_query": "How do I recover?",
        })
        self.assertNotIn("confidence", root.inputs)
        self.assertEqual(root.outputs["answer"], result["answer"])
        self.assertEqual(root.outputs["answer"], "Follow the approved operation. [1]")

    def test_graph_accepts_query_only_input_and_returns_complete_state(self):
        compiled = pipeline.build_graph(
            retriever=MagicMock(search=MagicMock(return_value=[candidate(1)])),
            fast_llm=ScriptedModel(grades(3), '{"grounded": true, "unsupported": ""}'),
            llm=ScriptedModel("Follow the approved operation. [1]"),
        )
        self.assertEqual(set(compiled.get_input_jsonschema()["properties"]), {"question", "search_query"})
        result = compiled.invoke({"question": "How do I recover?", "search_query": "How do I recover?"})
        self.assertEqual(set(pipeline.State.__annotations__) | set(pipeline.QueryInput.__annotations__), set(result))
        self.assertEqual(result["attempts"], 0)
        self.assertEqual(result["search_queries"], ["How do I recover?"])
        self.assertEqual(result["answer"], "Follow the approved operation. [1]")

    def test_diagram_export_does_not_initialize_clients(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(pipeline, "get_model") as model, patch.object(pipeline, "get_retriever") as retriever:
            target = pipeline.export_graph(Path(temp) / "graph.mmd")
            diagram = target.read_text()
            for node in ("retrieve", "grade", "rewrite", "generate", "check_grounding", "escalate", "finalize"):
                self.assertIn(node, diagram)
            model.assert_not_called()
            retriever.assert_not_called()


if __name__ == "__main__":
    unittest.main()
