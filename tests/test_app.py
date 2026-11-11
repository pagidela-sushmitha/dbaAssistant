"""Offline Streamlit interaction checks, without model or tracing requests."""

import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ["LANGSMITH_TRACING"] = "false"
os.environ["NEBIUS_API_KEY"] = "offline-test-key"

import streamlit as st
from streamlit.testing.v1 import AppTest

from rag import config


class AppTests(unittest.TestCase):
    def test_chat_sources_trace_escalation_and_history(self):
        doc = {"id": "runbook#1", "text": "Source evidence", "grade_score": 3,
               "bm25_rank": 2, "dense_rank": 1}
        result = {
            "answer": "Approved answer [1]", "confidence": "high", "escalated": False,
            "stale_warning": True, "docs": [doc], "candidates": [doc],
            "citations": [{"n": 1, "title": "Runbook", "section": "Recovery", "chunk_id": doc["id"]}],
            "timings": {"retrieve": 12.3}, "total_ms": 15.0,
            "search_queries": ["Question"],
        }
        escalation = {**result, "escalated": True, "confidence": "none",
                      "stale_warning": False, "citations": [], "docs": [],
                      "answer": "Cannot answer.\n\nDraft escalation note:\nQuestion: MongoDB"}
        st.cache_resource.clear()
        st.cache_data.clear()
        self.addCleanup(st.cache_resource.clear)
        self.addCleanup(st.cache_data.clear)
        with (
            patch("rag.retriever.get_retriever", return_value=SimpleNamespace(chunks=[doc])) as load,
            patch("rag.graph.ask", side_effect=[result, escalation, RuntimeError("provider failure")]) as ask,
            patch.object(config, "LANGSMITH_API_KEY", ""),
        ):
            app = AppTest.from_file(
                str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=15,
            ).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.sidebar.button(key="new_chat").label, "New chat")
            app.chat_input[0].set_value("Question").run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.chat_message), 2)
            self.assertIn(":green-badge[High confidence]", [m.value for m in app.markdown])
            self.assertEqual(len(app.warning), 1)
            self.assertIn("Source evidence", [t.value for t in app.text])
            self.assertEqual(app.dataframe[0].value.iloc[0]["kept"], "yes")
            app.sidebar.button(key="example_4").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.chat_message), 4)
            self.assertEqual(app.error[0].value, "Escalated to on-call DBA")
            self.assertIn("Draft escalation note", [e.label for e in app.expander])
            self.assertIn("Question: MongoDB", [t.value for t in app.text])
            self.assertEqual(ask.call_args.args[0], "How do I configure MongoDB sharding?")
            with self.assertLogs(level="ERROR"):
                app.chat_input[0].set_value("Try again").run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.chat_message), 6)
            self.assertIn("The request failed", app.error[-1].value)
            load.assert_called_once()

    def test_new_chat_and_reopening_history_preserve_answers(self):
        result = {"answer": "First answer", "confidence": "medium", "total_ms": 1}
        st.cache_resource.clear()
        st.cache_data.clear()
        self.addCleanup(st.cache_resource.clear)
        self.addCleanup(st.cache_data.clear)
        with (
            patch("rag.retriever.get_retriever", return_value=SimpleNamespace(chunks=[])),
            patch("rag.graph.ask", side_effect=[result, {**result, "answer": "Second answer"}]) as ask,
            patch.object(config, "LANGSMITH_API_KEY", ""),
        ):
            app = AppTest.from_file(
                str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=15,
            ).run()
            app.chat_input[0].set_value("First question").run()
            first_id = app.session_state["active_chat"]
            app.sidebar.button(key="new_chat").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.chat_message), 0)
            self.assertEqual(len(app.session_state["chats"]), 1)
            self.assertEqual(len([b for b in app.main.button if b.key.startswith("main_example_")]), 5)
            app.sidebar.button(key="new_chat").click().run()
            self.assertEqual(len(app.session_state["chats"]), 1)
            app.chat_input[0].set_value("Second question").run()
            second_id = app.session_state["active_chat"]
            self.assertNotEqual(first_id, second_id)
            self.assertEqual(len(app.session_state["chats"]), 2)
            app.sidebar.button(key=f"chat_{first_id}").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.chat_message), 2)
            self.assertIn("First answer", [m.value for m in app.markdown])
            self.assertNotIn("Second answer", [m.value for m in app.markdown])
            app.sidebar.button(key=f"chat_{second_id}").click().run()
            self.assertIn("Second answer", [m.value for m in app.markdown])
            self.assertEqual(app.sidebar.button(key=f"chat_{second_id}").proto.type, "secondary")
            app.sidebar.button(key="new_chat").click().run()
            self.assertEqual(len(app.chat_message), 0)
            self.assertEqual(len(app.session_state["chats"]), 2)
            app.sidebar.button(key=f"chat_{second_id}").click().run()
            app.sidebar.button(key=f"delete_{first_id}").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["active_chat"], second_id)
            self.assertEqual(len(app.session_state["chats"]), 1)
            self.assertIn("Second answer", [m.value for m in app.markdown])
            app.sidebar.button(key=f"delete_{second_id}").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.chat_message), 0)
            self.assertEqual(len(app.session_state["chats"]), 0)
            self.assertEqual(ask.call_count, 2)

    def test_sidebar_new_chat_and_clear_history(self):
        st.cache_resource.clear()
        st.cache_data.clear()
        self.addCleanup(st.cache_resource.clear)
        self.addCleanup(st.cache_data.clear)
        with (
            patch("rag.retriever.get_retriever", return_value=SimpleNamespace(chunks=[])),
            patch("rag.graph.ask", return_value={"answer": "Answer", "confidence": "high"}) as ask,
            patch.object(config, "LANGSMITH_API_KEY", ""),
        ):
            app = AppTest.from_file(
                str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=15,
            ).run()
            app.chat_input[0].set_value("First question").run()
            self.assertFalse(any(b.label == "New chat" for b in app.main.button))
            app.sidebar.button(key="new_chat").click().run()
            self.assertEqual(len(app.chat_message), 0)
            app.chat_input[0].set_value("Second question").run()
            self.assertEqual(len(app.session_state["chats"]), 2)
            app.sidebar.button(key="clear_history").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.session_state["chats"]), 0)
            self.assertIsNone(app.session_state["active_chat"])
            self.assertEqual(len(app.chat_message), 0)
            app.run()
            self.assertEqual(len(app.session_state["chats"]), 0)
            self.assertEqual(ask.call_count, 2)


if __name__ == "__main__":
    unittest.main()
