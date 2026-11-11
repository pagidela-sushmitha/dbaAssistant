# DBA Assistant — Project Plan

## One-liner
DBA Assistant helps on-call DBAs and application engineers answer database incident, runbook and policy questions from the DBA team's ~25-doc internal knowledge base in a Streamlit chat, with ≥90% faithfulness, ≥85% retrieval hit@5 and <10s answers — and escalates to the on-call DBA when it can't answer.

## RAG framework
| Field | Decision |
|---|---|
| Use case | On-call DBAs / app engineers ask "how do I fix X / what's the policy for Y" in a chat UI |
| Corpus | 25 synthetic markdown docs for fictional Northwind Data: runbooks, policies, postmortems, error-code reference, FAQ (data/corpus) |
| Ingestion + cleaning | Parse front-matter; html.unescape; strip HTML comments/tags and confidential footer; skip status: deprecated |
| Freshness | Re-ingest on every docs change; docs with last_reviewed > 180 days flagged stale and warned in answers |
| Chunking + embedding | Split on ## headers, then 1000 chars / 150 overlap; "[title > section]" prefix; Qwen/Qwen3-Embedding-8B (4096-dim) |
| Retrieve | Local NumPy vector store + BM25; hybrid via Reciprocal Rank Fusion (top 20 each, k=8); LLM batch rerank keeps top 4 |

## Stack
uv · LangChain + LangGraph · Nebius Token Factory (embeddings: Qwen3-Embedding-8B; main LLM: Qwen3-235B-A22B-Instruct-2507; fast LLM: Qwen3-30B-A3B-Instruct-2507) · LangSmith tracing · Streamlit

## Graph
retrieve → grade (batched LLM rerank) → [generate | rewrite once → retrieve | escalate] → check_grounding → [finalize | escalate]

## Rules
- Answers only from retrieved sources, inline [n] citations
- Never answer from general knowledge; escalate instead (#dba-help or PagerDuty DBA-Primary)
- All prompts are original (do not copy course solution kit)
- All commands use `uv run`

## Status
- [x] Corpus (25 docs, 1 deprecated)
- [x] Ingest (24 docs, 101 chunks, avg 473 chars)
- [x] Hybrid retriever
- [x] LangGraph pipeline + CLI
- [x] 20-question eval + report
- [x] Streamlit UI
