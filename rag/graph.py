"""Bounded, source-grounded LangGraph query pipeline."""

import json
import re
from functools import wraps
from pathlib import Path
from time import perf_counter
from typing import Any

from typing_extensions import TypedDict

from rag import config  # Initialize tracing before importing LangGraph.

from langgraph.graph import END, START, StateGraph

from rag.prompts import GENERATE_PROMPT, GRADE_PROMPT, GROUNDING_PROMPT, REWRITE_PROMPT
from rag.retriever import get_retriever


class QueryInput(TypedDict):
    """Keep the root trace input focused on the user's query."""

    question: str
    search_query: str


class State(QueryInput):
    candidates: list[dict]
    docs: list[dict]
    attempts: int
    answer: str
    citations: list[dict]
    confidence: str
    escalated: bool
    grounded: bool
    stale_warning: bool
    timings: dict[str, float]
    # Retain both passes for a useful escalation note.
    search_queries: list[str]
    closest_docs: list[dict]


def parse_json(text: str, expected_type: type) -> Any:
    """Accept plain JSON, Markdown fences, or JSON surrounded by commentary."""
    text = re.sub(r"```(?:json)?\s*|```", "", text.strip(), flags=re.I)
    try:
        value = json.loads(text)
        if isinstance(value, expected_type):
            return value
    except json.JSONDecodeError:
        pass
    # Find possible JSON starts, then decode structurally so nested data and
    # brackets inside strings do not confuse a greedy regular expression.
    decoder = json.JSONDecoder()
    opening = r"\[" if expected_type is list else r"\{"
    for match in re.finditer(opening, text):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
            if isinstance(value, expected_type):
                return value
        except json.JSONDecodeError:
            continue
    raise ValueError("Model did not return the required JSON structure.")


def response_text(response: Any) -> str:
    """Handle both ordinary chat strings and LangChain text content blocks."""
    content = response.content
    if isinstance(content, str):
        return content.strip()
    return "\n".join(
        block if isinstance(block, str) else block.get("text", "")
        for block in content
        if isinstance(block, (str, dict))
    ).strip()


def sources_text(docs: list[dict], limit: int | None = None) -> str:
    sources = []
    for n, doc in enumerate(docs, 1):
        metadata = doc["metadata"]
        text = doc["text"] if limit is None else doc["text"][:limit]
        sources.append(
            f"[{n}] {metadata.get('title', doc['id'])} > {metadata.get('section', '')}\n"
            f"Source: {metadata.get('source', '')}; chunk: {doc['id']}; "
            f"last_reviewed: {metadata.get('last_reviewed', '')}; "
            f"stale: {metadata.get('stale', False)}\n{text}"
        )
    return "\n\n".join(sources)


def cited_numbers(answer: str) -> list[int]:
    return list(dict.fromkeys(int(n) for n in re.findall(r"\[(\d+)\]", answer)))


def timed(node):
    """Accumulate elapsed milliseconds when retrieve/grade run a second time."""
    @wraps(node)
    def wrapped(state: State) -> dict:
        start = perf_counter()
        update = node(state)
        timings = dict(state.get("timings", {}))
        timings[node.__name__] = timings.get(node.__name__, 0.0) + (perf_counter() - start) * 1000
        return {**update, "timings": timings}
    return wrapped


def get_model(fast: bool):
    from rag.llm import get_llm

    return get_llm(fast=fast)


def route_after_grade(state: State) -> str:
    if state["docs"]:
        return "generate"
    return "rewrite" if state["attempts"] < 1 else "escalate"


def route_after_check(state: State) -> str:
    if state["answer"].strip() == "INSUFFICIENT_CONTEXT" or not state["grounded"]:
        return "escalate"
    return "finalize"


def build_graph(retriever=None, fast_llm=None, llm=None):
    """Optional injected clients support offline tests without provider requests."""
    def call_model(prompt: str, content: str, fast: bool, max_tokens: int) -> str:
        client = fast_llm if fast else llm
        if client is None:
            client = get_model(fast)
        return response_text(client.invoke(
            [("system", prompt), ("human", content)], max_tokens=max_tokens,
        ))

    @timed
    def retrieve(state: State) -> dict:
        engine = retriever if retriever is not None else get_retriever()
        candidates = engine.search(state["search_query"], mode="hybrid", k=8)
        history = {doc["id"]: doc for doc in state.get("closest_docs", [])}
        history.update({doc["id"]: doc for doc in candidates})
        return {
            "candidates": candidates,
            "attempts": state.get("attempts", 0),
            "search_queries": [*state.get("search_queries", []), state["search_query"]],
            "closest_docs": list(history.values()),
        }

    @timed
    def grade(state: State) -> dict:
        candidates = state["candidates"]
        if not candidates:
            return {"docs": []}
        raw = call_model(
            GRADE_PROMPT,
            f"Question: {state['question']}\n\nExcerpts:\n{sources_text(candidates, limit=700)}",
            fast=True,
            max_tokens=300,
        )
        try:
            grades = parse_json(raw, list)
            scores = {}
            for entry in grades:
                n, score = entry["id"], entry["score"]
                if (
                    type(n) is not int or not 1 <= n <= len(candidates)
                    or n in scores or type(score) is not int or not 0 <= score <= 3
                ):
                    raise ValueError("Invalid grade entry.")
                scores[n] = score
            if len(scores) != len(candidates):
                raise ValueError("Missing candidate grades.")
            order = sorted((n for n in scores if scores[n] >= 2), key=lambda n: (-scores[n], n))[:4]
            candidates = [{**doc, "grade_score": scores[n]} for n, doc in enumerate(candidates, 1)]
            docs = [{**candidates[n - 1], "grade_score": scores[n]} for n in order]
        except (ValueError, TypeError, KeyError):
            # Retrieval order is fused rank. A fallback cannot claim grade 3.
            candidates = [{**doc, "grade_score": None} for doc in candidates]
            docs = [{**doc, "grade_score": None} for doc in candidates[:3]]
        return {"docs": docs, "candidates": candidates}

    @timed
    def rewrite(state: State) -> dict:
        query = call_model(
            REWRITE_PROMPT,
            f"Question: {state['question']}\nPrevious search: {state['search_query']}",
            fast=True,
            max_tokens=60,
        )
        # Enforce the prompt's word budget and remove repeated terms even when
        # the model ignores it. Preserve technical tokens and their first spelling.
        words = {}
        for word in (query.strip() or state["question"]).split():
            term = word.casefold().strip(".,;:!?\"'`")
            if term:
                words.setdefault(term, word)
        query = " ".join(list(words.values())[:20])
        return {"search_query": query, "attempts": state["attempts"] + 1}

    @timed
    def generate(state: State) -> dict:
        answer = call_model(
            GENERATE_PROMPT,
            f"Question: {state['question']}\n\nSources:\n{sources_text(state['docs'])}",
            fast=False,
            max_tokens=500,
        )
        return {"answer": answer}

    @timed
    def check_grounding(state: State) -> dict:
        raw = call_model(
            GROUNDING_PROMPT,
            f"Question: {state['question']}\n\nSources:\n{sources_text(state['docs'])}\n\n"
            f"Answer to audit:\n{state['answer']}",
            fast=True,
            max_tokens=150,
        )
        try:
            verdict = parse_json(raw, dict)
            grounded = (
                verdict.get("grounded") is True
                and isinstance(verdict.get("unsupported"), str)
                and not verdict["unsupported"].strip()
            )
        except ValueError:
            grounded = False
        numbers = cited_numbers(state["answer"])
        # Missing/unknown citations cannot pass merely because a model says yes.
        valid_citations = bool(numbers) and all(1 <= n <= len(state["docs"]) for n in numbers)
        return {"grounded": grounded and valid_citations and bool(state["answer"].strip())}

    @timed
    def escalate(state: State) -> dict:
        closest = state["closest_docs"][:5]
        titles = "; ".join(
            f"{doc['metadata'].get('title', doc['id'])} > {doc['metadata'].get('section', '')} ({doc['id']})"
            for doc in closest
        ) or "none"
        answer = (
            "I couldn't find a reliable answer in the DBA knowledge base.\n\n"
            "For non-urgent help, contact #dba-help. For an urgent production issue, "
            "page PagerDuty DBA-Primary or use /page dba.\n\n"
            f"Draft escalation note:\nQuestion: {state['question']}\n"
            f"Search queries tried: {'; '.join(state['search_queries'])}\n"
            f"Closest docs found: {titles}"
        ).lstrip()
        return {
            "answer": answer, "escalated": True, "confidence": "none",
            "citations": [], "grounded": False, "stale_warning": False,
        }

    @timed
    def finalize(state: State) -> dict:
        citations = []
        stale = False
        for n in sorted(cited_numbers(state["answer"])):
            doc = state["docs"][n - 1]
            metadata = doc["metadata"]
            citations.append({
                "n": n, "title": metadata.get("title", ""),
                "section": metadata.get("section", ""), "source": metadata.get("source", ""),
                "chunk_id": doc["id"],
            })
            stale = stale or metadata.get("stale") is True
        return {
            "citations": citations,
            "confidence": "high" if state["docs"][0].get("grade_score") == 3 and state["grounded"] else "medium",
            "stale_warning": stale, "escalated": False,
        }

    builder = StateGraph(State, input_schema=QueryInput)
    for node in (retrieve, grade, rewrite, generate, check_grounding, escalate, finalize):
        builder.add_node(node.__name__, node)
    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "grade")
    builder.add_conditional_edges("grade", route_after_grade, {
        "generate": "generate", "rewrite": "rewrite", "escalate": "escalate",
    })
    builder.add_edge("rewrite", "retrieve")
    builder.add_edge("generate", "check_grounding")
    builder.add_conditional_edges("check_grounding", route_after_check, {
        "escalate": "escalate", "finalize": "finalize",
    })
    builder.add_edge("escalate", END)
    builder.add_edge("finalize", END)
    return builder.compile()


# Compilation does not initialize models or load the index; diagram export is offline.
graph = build_graph()


def ask(question: str, run_metadata: dict | None = None) -> dict:
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a nonempty string.")
    question = question.strip()
    state: QueryInput = {"question": question, "search_query": question}
    start = perf_counter()
    # Keep internal placeholders such as confidence="none" out of trace input:
    # LangSmith's automatic table preview may select them instead of the question.
    # Nodes initialize working state; the returned state includes the final answer.
    result = graph.invoke(input=state, config={"run_name": "dba-assistant", "metadata": run_metadata or {}})
    result["total_ms"] = (perf_counter() - start) * 1000
    return result


def export_graph(path: str | Path | None = None) -> Path:
    path = Path(path) if path is not None else Path(__file__).resolve().parent.parent / "docs/graph.mmd"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(graph.get_graph().draw_mermaid() + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    print(export_graph())
