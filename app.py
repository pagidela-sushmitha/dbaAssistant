"""Streamlit chat: uv run streamlit run app.py."""

import logging
from uuid import uuid4

import streamlit as st

from rag import config  # Load tracing settings before importing the graph.
from rag.graph import ask
from rag.retriever import get_retriever


EXAMPLES = [
    "What does SQLSTATE 40P01 mean and is it a DBA page?",
    "What is the RTO for an unplanned failover?",
    "pg-billing is throwing 53300 after a deploy — what happened last time and what should I check?",
    "It's 2am and an inactive replication slot is filling the disk — what approvals do I need?",
    "How do I configure MongoDB sharding?",
]


def apply_style():
    st.html("""
    <style>
    .stMainBlockContainer {max-width: 960px; padding-top: 5rem;}
    h1 {letter-spacing: -.045em; font-weight: 650 !important;}
    [data-testid="stSidebar"] {border-right: 1px solid rgba(128,148,151,.16);}
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap: .65rem;}
    .workspace-brand {font-size: .7rem; font-weight: 700; letter-spacing: .18em;
        color: #59b9ac; margin: .5rem 0 .75rem;}
    .workspace-note {font-size: .85rem; opacity: .65; line-height: 1.6;}
    [data-testid="stBaseButton-secondary"] {border-radius: 12px;
        border-color: rgba(128,148,151,.25); transition: background .15s, border-color .15s;}
    [data-testid="stBaseButton-secondary"]:hover,
    [data-testid="stBaseButton-secondary"]:focus-visible {
        color: var(--text-color); border-color: #59b9ac; background: rgba(89,185,172,.08);}
    [class*="st-key-history_"] [data-testid="stButton"] button {
        border-color: transparent; background: transparent; text-align: left;
        justify-content: flex-start; min-height: 2.75rem; padding: .65rem .75rem;}
    [class*="st-key-history_active_"] [data-testid="stButton"] button {
        background: rgba(89,185,172,.12); border-color: rgba(89,185,172,.22);}
    [class*="st-key-history_"] [data-testid="stButton"] button p {
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: .85rem;}
    [class*="st-key-history_"] [data-testid="stPopover"] button {border: 0; background: transparent;}
    .st-key-new_chat button {
        color: var(--text-color); background: rgba(89,185,172,.12);
        border: 1px solid rgba(89,185,172,.3);}
    .st-key-suggestions button {text-align: left; justify-content: flex-start;
        padding: 1rem 1.15rem; min-height: 4.5rem; box-shadow: 0 3px 14px rgba(0,0,0,.035);}
    [data-testid="stChatMessage"] {border-radius: 16px; padding: 1.25rem;
        border: 1px solid rgba(128,148,151,.12);}
    [data-testid="stChatInput"] {border-radius: 16px; border-color: rgba(89,185,172,.35);
        box-shadow: 0 6px 28px rgba(0,0,0,.06);}
    [data-testid="stExpander"] {border-radius: 12px; border-color: rgba(128,148,151,.2);}
    .st-key-chunk_count [data-testid="stMetricValue"] {font-size: 1.25rem;}
    @media (max-width: 640px) {.stMainBlockContainer {padding-top: 4.5rem;}}
    </style>
    """)


@st.cache_resource
def load_retriever():
    """Warm the same process-wide retriever used by ask()."""
    return get_retriever()


@st.cache_data(ttl=300, show_spinner=False)
def langsmith_project_url(project_name: str):
    """Resolve the actual project URL, without making tracing a UI dependency."""
    if not config.LANGSMITH_API_KEY:
        return None
    from langsmith import Client
    from urllib3.util import Retry

    try:
        with Client(timeout_ms=2000, retry_config=Retry(total=0)) as client:
            return client.read_project(project_name=project_name).url
    except Exception:
        return None


def new_chat():
    """Clear the current view while retaining saved conversations."""
    st.session_state.active_chat = None
    st.session_state.messages = []


def open_chat(chat_id: str):
    st.session_state.active_chat = chat_id
    st.session_state.messages = st.session_state.chats[chat_id]["messages"]


def delete_chat(chat_id: str):
    st.session_state.chats.pop(chat_id, None)
    if st.session_state.active_chat == chat_id:
        new_chat()


def clear_history():
    """Delete all saved conversations and clear the current view."""
    st.session_state.chats = {}
    new_chat()


def render_answer(result: dict):
    if result.get("escalated"):
        st.error("Escalated to on-call DBA")
        answer, separator, note = result["answer"].partition("Draft escalation note:")
        st.markdown(answer)
        if separator:
            with st.expander("Draft escalation note"):
                st.text(note.strip())
    else:
        confidence = result.get("confidence", "medium")
        color = "green" if confidence == "high" else "orange"
        st.markdown(f":{color}-badge[{confidence.capitalize()} confidence]")
        st.markdown(result["answer"])

    if result.get("stale_warning"):
        st.warning("Some cited documents were last reviewed more than 180 days ago. Verify they are still current.")

    with st.expander("Sources"):
        chunks = {doc["id"]: doc for doc in result.get("docs", [])}
        citations = result.get("citations", [])
        if not citations:
            st.caption("No cited sources.")
        for citation in citations:
            st.text(f"[{citation['n']}] {citation['title']} > {citation['section']}")
            st.caption(citation["chunk_id"])
            st.text(chunks.get(citation["chunk_id"], {}).get("text", "Chunk text unavailable."))

    with st.expander("Retrieval trace"):
        for n, query in enumerate(result.get("search_queries", []), 1):
            st.text(f"Search {n}: {query}")
        st.caption("Final retrieval pass. Kept means selected as generation context, including for answers that later escalated.")
        kept = {doc["id"] for doc in result.get("docs", [])}
        rows = [{
            "chunk id": doc["id"],
            "bm25_rank": doc.get("bm25_rank"),
            "dense_rank": doc.get("dense_rank"),
            "grade score": doc.get("grade_score"),
            "kept": "yes" if doc["id"] in kept else "no",
        } for doc in result.get("candidates", [])]
        if rows:
            st.dataframe(rows, hide_index=True, width="stretch")
        else:
            st.caption("No candidates retrieved.")
        st.caption("Latency in milliseconds; repeated node timings are accumulated. Missing grades indicate a grading fallback.")
        timings = [{"node": node, "latency (ms)": round(elapsed, 1)}
                   for node, elapsed in result.get("timings", {}).items()]
        timings.append({"node": "Total", "latency (ms)": round(result.get("total_ms", 0), 1)})
        st.dataframe(timings, hide_index=True, width="stretch")


def main():
    st.set_page_config(page_title="DBA Assistant", page_icon="🗄️", layout="centered")
    apply_style()
    st.title("DBA Assistant")
    st.caption("Answers from the Northwind DBA knowledge base — escalates when it isn't sure.")
    try:
        retriever = load_retriever()
    except Exception:
        logging.exception("Unable to load DBA index")
        st.error("Could not load the knowledge base. Build the index with `uv run python -m rag.ingest`, then reload.")
        st.stop()

    st.session_state.setdefault("messages", [])
    if "chats" not in st.session_state:
        st.session_state.chats = {}
        st.session_state.active_chat = None
        # Preserve a conversation already open when this UI update is loaded.
        if st.session_state.messages:
            chat_id = uuid4().hex
            title = next((m["content"] for m in st.session_state.messages if m["role"] == "user"), "Chat")
            st.session_state.chats[chat_id] = {"title": title, "messages": st.session_state.messages}
            st.session_state.active_chat = chat_id
    question = None
    with st.sidebar:
        st.html('<div class="workspace-brand">NORTHWIND</div>')
        st.button("New chat", key="new_chat", icon=":material/add:", on_click=new_chat, width="stretch")
        st.caption("CONVERSATIONS")
        if not st.session_state.chats:
            st.caption("Your conversations will appear here. Start with a question below.")
        for chat_id, chat in reversed(list(st.session_state.chats.items())):
            title = chat["title"]
            active = chat_id == st.session_state.active_chat
            with st.container(key=f"history_{'active_' if active else ''}{chat_id}"):
                item, menu = st.columns([6, 1], gap="small", vertical_alignment="center")
                with item:
                    st.button(
                        title if len(title) <= 60 else title[:57] + "…",
                        key=f"chat_{chat_id}", help=title, on_click=open_chat, args=(chat_id,),
                        type="secondary", width="stretch",
                    )
                with menu:
                    with st.popover("", icon=":material/more_horiz:", help="Conversation options"):
                        st.button("Delete chat", key=f"delete_{chat_id}", icon=":material/delete:",
                                  on_click=delete_chat, args=(chat_id,), width="stretch")
        if st.session_state.chats:
            with st.popover("Manage history", icon=":material/tune:"):
                st.caption("Remove all conversations from this session.")
                st.button("Delete history", key="clear_history", on_click=clear_history, width="stretch")
        st.caption("History is saved for this browser session.")
        st.divider()
        with st.expander("Explore questions", icon=":material/chat_bubble_outline:"):
            for i, example in enumerate(EXAMPLES):
                if st.button(example, key=f"example_{i}", width="stretch"):
                    question = example
        with st.expander("About this assistant", expanded=False, icon=":material/info:"):
            with st.container(key="chunk_count"):
                st.metric("Chunks indexed", len(retriever.chunks), width="content")
            st.caption("  \n".join(f"{label}: {model or 'Not configured'}" for label, model in (
                ("Answer", config.LLM_MODEL),
                ("Fast / grading", config.FAST_LLM_MODEL),
                ("Embedding", config.EMBED_MODEL),
            )))
            url = langsmith_project_url(config.LANGSMITH_PROJECT)
            st.link_button(f"LangSmith: {config.LANGSMITH_PROJECT}", url or "https://smith.langchain.com")
            if not url:
                st.caption("Open the configured project from LangSmith's project list.")

    examples = st.empty()
    if not st.session_state.messages and not question:
        with examples.container():
            st.write("")
            st.subheader("What can we help you resolve?")
            st.caption("Explore a runbook, check a policy, or investigate an incident.")
            with st.container(key="suggestions"):
                for i, example in enumerate(EXAMPLES):
                    if st.button(example, key=f"main_example_{i}", width="stretch"):
                        question = example

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.markdown(message["content"])
            elif "result" in message:
                render_answer(message["result"])
            else:
                st.error(message["content"])

    typed_question = st.chat_input("Ask a DBA question")
    question = typed_question or question
    if question and question.strip():
        examples.empty()
        if st.session_state.active_chat is None:
            chat_id = uuid4().hex
            st.session_state.chats[chat_id] = {"title": question, "messages": st.session_state.messages}
            st.session_state.active_chat = chat_id
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            try:
                with st.spinner("Searching the DBA knowledge base…"):
                    result = ask(question, run_metadata={"interface": "streamlit"})
            except Exception:
                logging.exception("DBA query failed")
                error = "The request failed. Check the service configuration and try again."
                st.error(error)
                st.session_state.messages.append({"role": "assistant", "content": error})
            else:
                st.session_state.messages.append({"role": "assistant", "result": result})
                render_answer(result)
        st.rerun()


if __name__ == "__main__":
    main()
