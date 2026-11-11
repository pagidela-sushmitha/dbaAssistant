"""Clean and index the corpus: uv run python -m rag.ingest."""

import html
import json
import re
import sys
from datetime import date
from pathlib import Path

from rag import config  # Initialize tracing before importing LangChain.

import numpy as np
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

METADATA_FIELDS = ("title", "doc_type", "owner", "last_reviewed", "status")
ROOT_DIR = Path(__file__).resolve().parent.parent


def parse_document(path: Path, today: date) -> Document:
    """Parse the corpus's flat front matter without adding a YAML dependency."""
    text = path.read_text(encoding="utf-8-sig")
    metadata = dict.fromkeys(METADATA_FIELDS, "")
    front_matter = re.match(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", text, re.S)
    if front_matter:
        for line in front_matter.group(1).splitlines():
            key, separator, value = line.partition(":")
            if separator and key.strip() in metadata:
                metadata[key.strip()] = value.strip().strip("\"'")
        text = text[front_matter.end():]

    metadata["title"] = metadata["title"] or path.stem
    metadata["status"] = metadata["status"] or "current"
    metadata["source"] = path.name
    reviewed = metadata["last_reviewed"]
    try:
        stale = bool(reviewed) and (today - date.fromisoformat(reviewed)).days > 180
    except ValueError as exc:
        raise ValueError(f"{path.name}: invalid last_reviewed date {reviewed!r}") from exc
    metadata["stale"] = stale
    return Document(page_content=text, metadata=metadata)


def clean_text(text: str) -> str:
    """Remove export artifacts while retaining Markdown headings and SQL."""
    text = html.unescape(text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    # Require a tag name immediately after '<'; preserve SQL such as '< 10'.
    text = re.sub(r"</?[A-Za-z][A-Za-z0-9:-]*(?:\s+[^<>]*?)?\s*/?>", "", text)
    text = re.sub(r"^.*Northwind Data · Confidential.*$", "", text, flags=re.M)
    text = re.sub(r"^[ \t]*---[ \t]*\r?$", "", text, flags=re.M)
    text = re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", text)
    return text.strip()


def chunk_document(document: Document) -> list[dict]:
    """Keep level-two sections separate and label every resulting chunk."""
    text = clean_text(document.page_content)
    title = html.unescape(str(document.metadata["title"]))
    sections = re.split(r"^##[ \t]+(.+?)[ \t]*\r?$", text, flags=re.M)
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = []
    # The content before the first section is the document overview.
    named_sections = [("Overview", sections[0])]
    named_sections.extend(zip(sections[1::2], sections[2::2]))
    for section, content in named_sections:
        section = section.strip()
        for piece in splitter.split_text(content):
            metadata = {**document.metadata, "title": title, "section": section}
            chunks.append({
                "id": f"{Path(str(metadata['source'])).stem}#{len(chunks)}",
                "text": f"[{title} > {section}]\n{piece}",
                "metadata": metadata,
            })
    return chunks


def ingest(corpus_dir: Path, index_dir: Path) -> None:
    from rag.llm import get_embeddings

    paths = sorted(p for p in corpus_dir.rglob("*") if p.is_file() and p.suffix.lower() in {".md", ".txt"})
    if not paths:
        raise ValueError(f"No .md or .txt documents found in {corpus_dir}")
    # Chunk IDs use stems; reject ambiguous inputs instead of overwriting IDs.
    if len({p.stem for p in paths}) != len(paths):
        raise ValueError("Corpus filenames must have unique stems for stable chunk IDs.")

    loaded = skipped = 0
    chunks = []
    today = date.today()
    for path in paths:
        document = parse_document(path, today)
        if document.metadata["status"] == "deprecated":
            print(f"Skipping deprecated document: {path.name}", flush=True)
            skipped += 1
            continue
        loaded += 1
        chunks.extend(chunk_document(document))
    if not chunks:
        raise ValueError("No indexable chunks remain after filtering and cleaning.")

    embeddings = get_embeddings()
    batches = []
    dimension = None
    for start in range(0, len(chunks), 32):
        batch = chunks[start:start + 32]
        print(f"Embedding chunks {start + 1}-{start + len(batch)} of {len(chunks)}", flush=True)
        vectors = np.asarray(embeddings.embed_documents([c["text"] for c in batch]), dtype=np.float32)
        if vectors.ndim != 2 or vectors.shape[0] != len(batch) or vectors.shape[1] == 0:
            raise ValueError("Provider returned an invalid embedding batch shape.")
        if dimension is not None and vectors.shape[1] != dimension:
            raise ValueError("Embedding dimension changed between batches.")
        dimension = vectors.shape[1]
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        if not np.isfinite(vectors).all() or not np.isfinite(norms).all() or (norms == 0).any():
            raise ValueError("Provider returned non-finite or zero-length embeddings.")
        batches.append(vectors / norms)

    # Row n in embeddings.npy corresponds to line n in chunks.jsonl.
    matrix = np.concatenate(batches, axis=0)
    index_dir.mkdir(parents=True, exist_ok=True)
    with (index_dir / "chunks.jsonl").open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    np.save(index_dir / "embeddings.npy", matrix, allow_pickle=False)
    average = sum(len(c["text"]) for c in chunks) / len(chunks)
    print(f"\nDocs loaded: {loaded}\nDocs skipped: {skipped}\nChunks created: {len(chunks)}")
    print(f"Average chunk length: {average:.1f} characters")
    print(f"Index saved to {index_dir}")


def main() -> None:
    ingest(ROOT_DIR / "data" / "corpus", ROOT_DIR / "index")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        sys.exit(1)
