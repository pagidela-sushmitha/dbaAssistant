"""Pure evaluation helpers; importing this module never loads API clients."""

import json
import re
from pathlib import Path
from statistics import mean


def doc_stem(result: dict) -> str:
    source = result.get("metadata", {}).get("source") or result.get("source")
    return Path(source).stem if source else result.get("id", result.get("chunk_id", "")).split("#")[0]


def hit_at_5(results: list[dict], expected_docs: list[str]) -> float:
    return float(any(doc_stem(result) in expected_docs for result in results[:5]))


def reciprocal_rank(results: list[dict], expected_docs: list[str]) -> float:
    for rank, result in enumerate(results, 1):
        if doc_stem(result) in expected_docs:
            return 1.0 / rank
    return 0.0


def key_fact_recall(answer: str, key_facts: list[str]) -> float | None:
    if not key_facts:
        return None  # Ambiguous and out-of-scope questions have no fact score.
    return mean(fact.casefold() in answer.casefold() for fact in key_facts)


def citation_accuracy(citations: list[dict], expected_docs: list[str]) -> float | None:
    if not expected_docs:
        return None
    cited = {doc_stem(citation) for citation in citations}
    return sum(stem in expected_docs for stem in cited) / len(cited) if cited else 0.0


def percentile(values: list[float], p: float) -> float | None:
    """Linear interpolation, equivalent to NumPy's default percentile method."""
    if not 0 <= p <= 100:
        raise ValueError("Percentile must be between 0 and 100.")
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * p / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def parse_json(text: str) -> dict:
    """Extract a JSON object from plain text, code fences, or model commentary."""
    text = re.sub(r"```(?:json)?\s*|```", "", text.strip(), flags=re.I)
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            continue
    raise ValueError("Judge response contains no valid JSON object.")


def parse_judgement(text: str) -> dict:
    result = parse_json(text)
    if type(result.get("faithful")) is not bool or not isinstance(result.get("reason"), str):
        raise ValueError("Judge must return a boolean faithful and a string reason.")
    return result
