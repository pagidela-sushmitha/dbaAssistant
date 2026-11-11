"""Offline tests for evaluation arithmetic, parsing, and runner boundaries."""

import contextlib
import csv
import io
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import MagicMock

from eval.metrics import citation_accuracy, hit_at_5, key_fact_recall, parse_json, parse_judgement, percentile, reciprocal_rank
from eval.run_eval import ROOT_DIR, evaluate, load_questions, summarize, write_outputs


def chunk(source, n=0):
    return {"id": f"{source}#{n}", "text": "fake evidence", "metadata": {"source": f"{source}.md"}}


class EvalMetricTests(unittest.TestCase):
    def test_hit_at_five_respects_cutoff_and_any_expected_document(self):
        results = [chunk("unrelated", n) for n in range(5)] + [chunk("wanted")]
        self.assertEqual(hit_at_5(results, ["wanted"]), 0)
        self.assertEqual(hit_at_5([chunk("other"), chunk("wanted")], ["alternative", "wanted"]), 1)
        self.assertEqual(hit_at_5([], ["wanted"]), 0)

    def test_reciprocal_rank_uses_first_relevant_chunk(self):
        results = [chunk("other"), chunk("wanted", 1), chunk("wanted", 2)]
        self.assertEqual(reciprocal_rank(results, ["wanted"]), 0.5)
        self.assertEqual(reciprocal_rank(results, ["missing"]), 0)
        self.assertEqual(reciprocal_rank([], ["wanted"]), 0)

    def test_key_fact_recall_is_case_insensitive_and_empty_is_unscored(self):
        self.assertEqual(key_fact_recall("SQLSTATE 53300; use SHOW POOLS.", ["53300", "show pools", "rollback"]), 2 / 3)
        self.assertEqual(key_fact_recall("Nothing relevant.", ["53300"]), 0)
        self.assertIsNone(key_fact_recall("Any overview", []))

    def test_p95_uses_linear_interpolation(self):
        self.assertAlmostEqual(percentile([100, 200, 300, 400, 500], 95), 480)
        self.assertEqual(percentile([42], 95), 42)
        self.assertIsNone(percentile([], 95))
        self.assertEqual(percentile([3, 1, 2], 50), 2)
        with self.assertRaises(ValueError):
            percentile([1], 101)

    def test_json_parser_handles_fences_commentary_and_braces_in_strings(self):
        for raw in [
            '{"faithful": true, "reason": "supported"}',
            '```json\n{"faithful": true, "reason": "supported"}\n```',
            'Audit follows: {"faithful": true, "reason": "supported"} Done.',
        ]:
            self.assertTrue(parse_judgement(raw)["faithful"])
        self.assertEqual(parse_json('Note: {"reason": "literal { bracket }", "faithful": false}')["reason"], "literal { bracket }")
        for raw in ["not JSON", '{"faithful": "true", "reason": "bad type"}', '{"faithful": true}', '{"faithful": 1, "reason": "bad type"}']:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_judgement(raw)

    def test_citations_use_distinct_document_stems(self):
        self.assertEqual(citation_accuracy([{"source": "wanted.md"}, {"source": "wanted.md"}, {"chunk_id": "other#1"}], ["wanted"]), 0.5)
        self.assertEqual(citation_accuracy([], ["wanted"]), 0)
        self.assertIsNone(citation_accuracy([], []))

    def test_dataset_distribution_and_current_expected_docs(self):
        questions = load_questions(ROOT_DIR / "eval/questions.json")
        self.assertEqual(Counter(q["category"] for q in questions), {
            "single-doc": 9, "multi-doc": 4, "conflict": 1, "ambiguous": 1, "should-escalate": 5,
        })
        for question in questions:
            for stem in question["expected_docs"]:
                text = (ROOT_DIR / "data/corpus" / f"{stem}.md").read_text()
                self.assertIn("status: current", text)
            self.assertTrue(all(fact == fact.lower() for fact in question["key_facts"]))
            if question["category"] not in {"ambiguous", "should-escalate"}:
                self.assertIn(len(question["key_facts"]), (2, 3))

    def test_runner_writes_rows_skips_escalation_judge_and_passes_metadata(self):
        questions = [
            {"id": "answer", "question": "SQLSTATE?", "category": "single-doc", "expected_docs": ["wanted"], "key_facts": ["53300", "connections"], "should_escalate": False},
            {"id": "escalate", "question": "Outside KB?", "category": "should-escalate", "expected_docs": [], "key_facts": [], "should_escalate": True},
        ]
        retriever = MagicMock()
        retriever.search.return_value = [chunk("wanted")]
        ask = MagicMock(side_effect=[
            {"answer": "53300 means too many connections. [1]", "escalated": False, "citations": [{"source": "wanted.md"}], "docs": [chunk("wanted")], "candidates": [chunk("wanted")], "timings": {"retrieve": 2, "generate": 8}, "total_ms": 10},
            {"answer": "Please escalate.", "escalated": True, "citations": [], "docs": [], "timings": {"retrieve": 1, "escalate": 1}, "total_ms": 2},
        ])
        judge = MagicMock(return_value='```json\n{"faithful": true, "reason": "supported"}\n```')
        with contextlib.redirect_stdout(io.StringIO()):
            rows = evaluate(questions, retriever, tag="unit", ask_fn=ask, judge_fn=judge)
        self.assertEqual(judge.call_count, 1)
        self.assertEqual(ask.call_args_list[0].kwargs["run_metadata"], {"category": "single-doc", "eval": True, "tag": "unit"})
        self.assertEqual(judge.call_args.args[1], [chunk("wanted")])
        self.assertIsNone(rows[1]["faithful"])
        metrics, retrieval, nodes = summarize(rows)
        self.assertEqual(metrics["Resolution rate"], 1)
        self.assertEqual(metrics["Correct escalation rate"], 1)
        self.assertEqual(metrics["False escalation rate"], 0)
        self.assertEqual(retrieval["hybrid"]["hit@5"], 1)
        self.assertEqual(nodes["retrieve"], 1.5)
        with tempfile.TemporaryDirectory() as temp:
            csv_path, report_path = write_outputs(rows, "unit", Path(temp))
            with csv_path.open() as handle:
                saved = list(csv.DictReader(handle))
            self.assertEqual(len(saved), 2)
            self.assertEqual(json.loads(saved[0]["citations"]), [{"source": "wanted.md"}])
            self.assertIn("## Failures\n\nNone.", report_path.read_text())

    def test_retrieval_only_never_calls_answer_or_judge(self):
        question = {"id": "test", "question": "question", "category": "single-doc", "expected_docs": ["wanted"], "key_facts": ["fact"], "should_escalate": False}
        retriever = MagicMock()
        retriever.search.return_value = [chunk("other")]
        ask, judge = MagicMock(), MagicMock()
        with contextlib.redirect_stdout(io.StringIO()):
            rows = evaluate([question], retriever, tag="unit", only_retrieval=True, ask_fn=ask, judge_fn=judge)
        ask.assert_not_called()
        judge.assert_not_called()
        self.assertEqual(retriever.search.call_count, 3)
        self.assertEqual(len(rows[0]["failures"]), 3)
        with tempfile.TemporaryDirectory() as temp:
            _, report = write_outputs(rows, "unit", Path(temp), only_retrieval=True)
            self.assertIn("other#0", report.read_text())

    def test_judge_parse_error_is_visible_and_not_a_faithfulness_success(self):
        question = {"id": "test", "question": "question", "category": "single-doc", "expected_docs": ["wanted"], "key_facts": ["fact"], "should_escalate": False}
        retriever = MagicMock(search=MagicMock(return_value=[chunk("wanted")]))
        ask = MagicMock(return_value={"answer": "fact [1]", "escalated": False, "citations": [{"source": "wanted.md"}], "docs": [chunk("wanted")]})
        judge = MagicMock(return_value="not JSON")
        with contextlib.redirect_stdout(io.StringIO()):
            rows = evaluate([question], retriever, tag="unit", ask_fn=ask, judge_fn=judge)
        self.assertIsNone(rows[0]["faithful"])
        self.assertIn("judge failed", rows[0]["faithfulness_reason"])
        self.assertEqual(summarize(rows)[0]["Judge coverage of non-escalated answers"], 0)


if __name__ == "__main__":
    unittest.main()
