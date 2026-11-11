"""Offline checks for process-wide retrieval and provider client reuse."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["LANGSMITH_TRACING"] = "false"
os.environ["NEBIUS_API_KEY"] = "offline-test-key"

import numpy as np

from rag import graph, llm, retriever


class SingletonTests(unittest.TestCase):
    def setUp(self):
        self.clear_caches()
        self.addCleanup(self.clear_caches)

    @staticmethod
    def clear_caches():
        retriever.get_retriever.cache_clear()
        llm.get_embeddings.cache_clear()
        llm._get_llm.cache_clear()

    def test_provider_clients_are_shared_across_call_styles_and_graphs(self):
        with (
            patch.object(llm.config, "EMBED_MODEL", "embedding-model"),
            patch.object(llm.config, "LLM_MODEL", "main-model"),
            patch.object(llm.config, "FAST_LLM_MODEL", "fast-model"),
            patch.object(llm, "OpenAIEmbeddings") as embeddings,
            patch.object(llm, "ChatOpenAI") as chat,
        ):
            graph.build_graph()
            embeddings.assert_not_called()
            chat.assert_not_called()
            self.assertIs(llm.get_embeddings(), llm.get_embeddings())
            self.assertIs(llm.get_llm(), llm.get_llm(False))
            self.assertIs(llm.get_llm(fast=False), graph.get_model(False))
            self.assertIs(llm.get_llm(True), llm.get_llm(fast=True))
            self.assertIs(llm.get_llm(True), graph.get_model(True))
            embeddings.assert_called_once()
            self.assertEqual(chat.call_count, 2)
            self.assertEqual([c.kwargs["model"] for c in chat.call_args_list],
                             ["main-model", "fast-model"])

    def test_default_adapters_and_graph_share_one_index_and_bm25(self):
        constructor = retriever.HybridRetriever
        with tempfile.TemporaryDirectory() as temp:
            index = Path(temp)
            (index / "chunks.jsonl").write_text(json.dumps({
                "id": "runbook#0", "text": "slot approval", "metadata": {},
            }) + "\n")
            np.save(index / "embeddings.npy", np.array([[1., 0.]], dtype=np.float32))
            with (
                patch.object(retriever, "HybridRetriever", side_effect=lambda: constructor(index)) as build,
                patch.object(retriever, "BM25Okapi", wraps=retriever.BM25Okapi) as bm25,
            ):
                graph.build_graph()
                build.assert_not_called()
                first = retriever.DBARetriever(mode="bm25")
                second = retriever.DBARetriever(mode="bm25")
                self.assertIs(first.hybrid_retriever, second.hybrid_retriever)
                self.assertIs(first.hybrid_retriever, graph.get_retriever())
                self.assertEqual(first.invoke("slot")[0].metadata["id"], "runbook#0")
                second.invoke("approval")
                build.assert_called_once()
                bm25.assert_called_once()
                self.assertIsNone(first.hybrid_retriever._embedding_client)


if __name__ == "__main__":
    unittest.main()
