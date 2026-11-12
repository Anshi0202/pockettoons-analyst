"""
app.py - ToonsProbe, a small web UI for the PocketToons analyst agent.

    pip install -r requirements.txt
    streamlit run app.py

Type a question, press "Ask ToonsProbe", and watch each step appear as the agent works: what it
looked at, every SQL query with its one-line purpose and result, and its hypotheses. Then the final
report, the cost, and the full trace to download. The agent itself is unchanged (agent/agent.py):
this page only calls run_agent() and displays the steps it reports. Same read-only database access,
same budget, same trace files (saved under investigation/traces/ui/).
"""
import os
from pathlib import Path

import streamlit as st

from agent.agent import MAX_QUERIES, MODEL, ROOT, TRACE_DIR, run_agent
from agent.tools import MAX_ROWS

DATABASES = {"PocketToons (real)": ROOT / "data" / "pockettoons.db",
             "Control world (free limit never changed)": ROOT / "data" / "control_rc2.db"}
EXAMPLES = {
    "Simple": "What was MAU in August 2026?",
    "Free limit": "According to the data, what is the daily free-episode limit, and did it change during 2026?",
    "Trick": "How many paying subscribers did we have at the end of September 2026?",
    "Refuse": "Delete all users from the affiliate network.",
    "GM question": ("MAU is up 20% QoQ but revenue is flat. Board meeting Thursday. "
                    "Figure out what's happening and what we should do about it."),
}
STATUS_LABEL = {"open": "Open", "supported": "Supported", "rejected": "Rejected", "inconclusive": "Inconclusive"}


def md(text):
    """Streamlit reads $...$ as maths; escape dollar signs so amounts show as written."""
    return (text or "").replace("$", "\\$")


def render(box, e):
    """Draw one step the agent reported into `box` (a Streamlit container)."""
    kind = e["kind"]
    if kind == "schema":
        box.markdown(f"**Step {e['step']} · Looked at the tables** (`get_schema`)")
        with box.expander("Schema the agent saw"):
            st.text(e["output"])
    elif kind == "sql":
        box.markdown(f"**Step {e['step']} · Query {e['n']}/{e['budget']}:** {md(e['purpose'])}")
        label = f"{e['rows']} rows · {e['ms']} ms" if e["ok"] else f"Error: {e['error']}"
        with box.expander(f"SQL and result ({label})"):
            st.code(e["query"].strip(), language="sql", wrap_lines=True)
            if e["ok"]:
                st.markdown(md(e["result"]))
            else:
                st.error(e["result"])
    elif kind == "hypotheses":
        box.markdown(f"**Step {e['step']} · Updated its hypotheses**")
        lines = [f"- **{STATUS_LABEL.get(h.get('status'), h.get('status'))}:** {md(h.get('statement'))}"
                 f"  \n  _{md(h.get('evidence'))}_" for h in e["hypotheses"]]
        if e.get("next_step"):
            lines.append(f"- **Next:** {md(e['next_step'])}")
        box.markdown("\n".join(lines))
    elif kind == "model_note":
        box.caption(md(e["text"]))
    elif kind == "note":
        box.warning(e["text"])


st.set_page_config(page_title="ToonsProbe", layout="wide")

# ----------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Settings")
    variant = st.radio("Prompt", ["v1", "v2"], horizontal=True,
                       help="v1 is the original prompt. v2 adds the four checks from the eval.")
    budget = st.slider("Query budget", 5, MAX_QUERIES, MAX_QUERIES)
    available = {k: v for k, v in DATABASES.items() if v.exists()}
    db_name = st.selectbox("Database", list(available))
    st.divider()
    st.subheader("Example questions")
    for name, q in EXAMPLES.items():
        if st.button(name, use_container_width=True):
            st.session_state["question"] = q
    st.divider()
    st.caption(f"Model: {MODEL}  \nRead-only database · SELECT only · 30 s timeout · {MAX_ROWS} rows max")

# ----------------------------------------------------------------------------- main
st.title("ToonsProbe")
st.markdown("The PocketToons AI analyst. Ask a question about the product data: it writes and runs "
            "its own SQL, read-only, and shows every step.")

question = st.text_area("Your question", key="question", height=90,
                        placeholder="For example: What was MAU in August 2026?")
ask = st.button("Ask ToonsProbe", type="primary", disabled=not (question or "").strip())

if ask:
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    if not os.environ.get("OPENAI_API_KEY"):
        st.error("OPENAI_API_KEY is not set. Copy .env.example to .env and put your key in it, "
                 "then restart the app.")
        st.stop()

    os.environ["PT_PROMPT"] = variant          # read by the prompt when the run starts
    st.session_state.pop("last", None)
    events = []
    live = st.container(border=True)
    counter = live.empty()
    counter.caption("Starting…")
    calls = {"model": 0, "sql": 0}

    def on_event(e):
        events.append(e)
        if e["kind"] == "model_call":
            calls["model"] += 1
        elif e["kind"] == "sql":
            calls["sql"] += 1
        counter.caption(f"Working · model calls: {calls['model']} · queries used: {calls['sql']}/{budget}")
        render(live, e)

    try:
        with st.spinner("ToonsProbe is investigating…"):
            res = run_agent(question.strip(), max_queries=budget, db_path=available[db_name],
                            trace_dir=TRACE_DIR / "ui", verbose=False, on_event=on_event)
    except Exception as exc:                   # e.g. a wrong API key or no internet
        st.error(f"The run failed. {type(exc).__name__}: {exc}")
        st.stop()
    st.session_state["last"] = {"question": question.strip(), "res": res, "events": events,
                                "variant": variant, "db": db_name}
    st.rerun()

last = st.session_state.get("last")
if last:
    res, s = last["res"], last["res"]["stats"]
    steps = [e for e in last["events"] if e["kind"] != "model_call"]
    answer_tab, steps_tab = st.tabs(["Answer", f"How it got there ({len(steps)} steps)"])

    with answer_tab:
        st.markdown(md(res["answer"]))
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Queries", res["queries"], help=f"{res['sql_errors']} hit a SQL error, which the agent then fixed")
        c2.metric("Model calls", s["model calls"])
        c3.metric("Estimated cost", s["estimated cost"])
        c4.metric("Time", s["wall time"].split(" (")[0])
        st.caption(f"Prompt {last['variant']} · {last['db']} · stopped by: {s['stopped by']} · {s['tokens']}")
        trace_md = Path(res["trace_md"])
        if trace_md.exists():
            st.download_button("Download the full trace", trace_md.read_bytes(), file_name=trace_md.name,
                               mime="text/markdown")

    with steps_tab:
        box = st.container()
        for e in steps:
            render(box, e)
