# DBA Assistant

Run the chat UI after configuring `.env` and building the index:

```bash
uv run python -m rag.ingest
uv run streamlit run app.py
```

Answers include confidence, source excerpts, freshness warnings, and a retrieval trace.
Escalations show a draft note for contacting the on-call DBA.

Run offline checks with `uv run python -m unittest discover -s tests`.
