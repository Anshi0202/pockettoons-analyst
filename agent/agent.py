#!/usr/bin/env python3
"""
agent.py - PocketToons analyst agent (a plain loop, no agent framework)

    python agent/agent.py "MAU is up 20% QoQ but revenue is flat. What is going on?"
    python agent/agent.py --max-queries 10 "What was MAU in August 2026?"
    python agent/agent.py                      (asks for the question)

How it works
  1. The model gets a generic analyst method (prompts.py) and three tools:
       get_schema, run_sql   - read-only database access (tools.py)
       update_hypotheses     - the model's working notes: candidate explanations and their status
  2. Each turn the model either calls tools or writes its final report. We run the tool calls,
     append the results to the conversation, and call the model again.
  3. Hard limits keep cost and runaway loops in check: MAX_QUERIES run_sql calls (the model sees
     its remaining budget after every query) and MAX_TURNS model calls. When either runs out we
     tell the model and switch tools off (tool_choice="none"), so it must report what it has.
  4. Every step (purpose, SQL, result, hypothesis board, model notes, tokens, cost, latency) is
     written as it happens to investigation/traces/<timestamp>_<slug>.md (for people) and .jsonl
     (for the eval script). A crash still leaves a usable trace.

Provider: OpenAI Responses API. The model name is MODEL below (one line to swap, or set PT_MODEL).
The API key is read from OPENAI_API_KEY (environment variable or the project's .env file).
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if __package__ in (None, ""):          # allow `python agent/agent.py` as well as `python -m agent.agent`
    sys.path.insert(0, str(ROOT))

from agent.prompts import EMPTY_REPLY_NUDGE, FORCE_FINAL_MESSAGE, system_prompt  # noqa: E402
from agent.tools import MAX_ROWS, TOOL_SPECS, SQLTools  # noqa: E402

# ----------------------------------------------------------------------------- config
MODEL = os.environ.get("PT_MODEL", "gpt-6-luna")
PRICE_PER_1M_USD = {"input": 0.10, "output": 0.50}   # gpt-6-luna list price, Oct 2026. Cache discounts
                                                     # are ignored, so the cost shown is an upper bound.
MAX_QUERIES = 40          # run_sql calls per question
MAX_TURNS = 60            # model calls per question (safety net; queries usually run out first)
MAX_TOOL_OUTPUT_CHARS = 12_000
TRACE_DIR = ROOT / "investigation" / "traces"

HYPOTHESIS_TOOL = {
    "name": "update_hypotheses",
    "description": (
        "Record your current hypotheses (the full list each time, not just changes) and what you will "
        "check next. Use it to plan, to track which explanations the data supports or rejects, and to "
        "decide where to dig. It does not query the data."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "hypotheses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "statement": {"type": "string", "description": "A testable explanation."},
                        "status": {"type": "string", "enum": ["open", "supported", "rejected", "inconclusive"]},
                        "evidence": {"type": "string", "description": "Numbers so far, or what would test it."},
                    },
                    "required": ["statement", "status", "evidence"],
                    "additionalProperties": False,
                },
            },
            "next_step": {"type": "string", "description": "What you will check next and why."},
        },
        "required": ["hypotheses", "next_step"],
        "additionalProperties": False,
    },
}


def openai_tools():
    return [
        {"type": "function", "name": t["name"], "description": t["description"],
         "parameters": t["parameters"], "strict": True}
        for t in TOOL_SPECS + [HYPOTHESIS_TOOL]
    ]


def make_client():
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set. Copy .env.example to .env and put your key in it.")
    from openai import OpenAI
    return OpenAI(max_retries=3, timeout=180)


# ----------------------------------------------------------------------------- trace
def _slug(text, n=40):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:n].strip("-") or "question"


def _cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def _md_result(output):
    """Blank lines around the table so Markdown viewers render it; budget line in italics."""
    head, _, rest = output.partition("\n")
    rest = re.sub(r"\n?\[run_sql budget: ([^\]]+)\]$", r"\n\n_run_sql budget: \1_", rest)
    return f"{head}\n\n{rest}" if rest else head


class Trace:
    """Writes a human-readable .md and a machine-readable .jsonl, appending as the run goes."""

    def __init__(self, question, model, max_queries, trace_dir=TRACE_DIR):
        trace_dir = Path(trace_dir)
        trace_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{datetime.now():%Y%m%d_%H%M%S}_{_slug(question)}"
        self.md_path = trace_dir / f"{stem}.md"
        self.jsonl_path = trace_dir / f"{stem}.jsonl"
        self.step = 0
        self._md(
            f"# Agent trace\n\n**Question:** {question}\n\n"
            f"- Started: {datetime.now():%Y-%m-%d %H:%M:%S}\n- Model: `{model}`\n"
            f"- Query budget: {max_queries} run_sql calls\n\n---\n"
        )
        self.event("start", question=question, model=model, max_queries=max_queries)

    def _md(self, text):
        with open(self.md_path, "a", encoding="utf-8") as f:
            f.write(text + "\n")

    def event(self, kind, **data):
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": datetime.now().isoformat(timespec="seconds"), "kind": kind, **data},
                               ensure_ascii=False, default=str) + "\n")

    def model_note(self, text):
        self._md(f"\n> **Model note:** {text.strip()}\n")
        self.event("model_note", text=text)

    def get_schema(self, output):
        self.step += 1
        self._md(f"\n### Step {self.step} · get_schema\n\n<details><summary>Schema returned to the model"
                 f"</summary>\n\n```\n{output}\n```\n</details>\n")
        self.event("tool", step=self.step, name="get_schema", chars=len(output))

    def run_sql(self, purpose, query, output, meta, used, budget):
        self.step += 1
        status = "ok" if meta.get("ok") else f"error: {meta.get('error')}"
        self._md(
            f"\n### Step {self.step} · run_sql ({used}/{budget}, {meta.get('ms', 0)} ms, {status})\n\n"
            f"**Purpose:** {purpose}\n\n```sql\n{query.strip()}\n```\n\n{_md_result(output)}\n"
        )
        self.event("tool", step=self.step, name="run_sql", purpose=purpose, query=query, output=output, **meta)

    def hypotheses(self, hyps, next_step):
        self.step += 1
        rows = "\n".join(f"| {i} | {_cell(h.get('statement'))} | **{_cell(h.get('status'))}** | "
                         f"{_cell(h.get('evidence'))} |" for i, h in enumerate(hyps, 1))
        self._md(f"\n### Step {self.step} · update_hypotheses\n\n| # | Hypothesis | Status | Evidence |\n"
                 f"|---|---|---|---|\n{rows}\n\n**Next:** {next_step}\n")
        self.event("tool", step=self.step, name="update_hypotheses", hypotheses=hyps, next_step=next_step)

    def note(self, text):
        self._md(f"\n> _{text}_\n")
        self.event("note", text=text)

    def final(self, answer, stats):
        nested = re.sub(r"^(#{1,5}) ", r"#\1 ", answer, flags=re.M)   # model's ## -> ### under the heading
        self._md(f"\n---\n\n## Final answer\n\n{nested}\n\n---\n\n## Run stats\n")
        self._md("\n".join(f"- {k}: {v}" for k, v in stats.items()))
        self.event("final", answer=answer, stats=stats)


# ----------------------------------------------------------------------------- loop
def _usage(resp):
    u = getattr(resp, "usage", None)
    if u is None:
        return 0, 0, 0
    details = getattr(u, "output_tokens_details", None)
    return (getattr(u, "input_tokens", 0) or 0, getattr(u, "output_tokens", 0) or 0,
            getattr(details, "reasoning_tokens", 0) or 0 if details else 0)


def _clip(text, n=MAX_TOOL_OUTPUT_CHARS):
    return text if len(text) <= n else text[:n] + f"\n...[cut at {n} characters; aggregate further]"


def run_agent(question, *, model=MODEL, max_queries=MAX_QUERIES, max_turns=MAX_TURNS,
              trace_dir=TRACE_DIR, client=None, db_path=None, verbose=True):
    """Answer one question. Returns a dict with answer, stats and trace paths."""
    say = print if verbose else (lambda *a, **k: None)
    client = client or make_client()
    db = SQLTools(db_path)
    trace = Trace(question, model, max_queries, trace_dir)
    instructions = system_prompt(max_queries, MAX_ROWS)
    tools = openai_tools()

    items = [{"role": "user", "content": question}]
    queries = sql_errors = turns = tok_in = tok_out = tok_reason = 0
    api_seconds = 0.0
    forced = False
    answer = None
    t_start = time.monotonic()

    try:
        while turns < max_turns:
            turns += 1
            if not forced and turns == max_turns:          # last allowed call: must answer now
                forced = True
                items.append({"role": "user", "content": FORCE_FINAL_MESSAGE})
                trace.note("Turn limit reached; tools switched off.")
            kwargs = dict(model=model, instructions=instructions, input=items, tools=tools)
            if forced:
                kwargs["tool_choice"] = "none"

            t0 = time.monotonic()
            resp = client.responses.create(**kwargs)
            dt = time.monotonic() - t0
            api_seconds += dt
            i, o, r = _usage(resp)
            tok_in, tok_out, tok_reason = tok_in + i, tok_out + o, tok_reason + r
            trace.event("model_call", turn=turns, seconds=round(dt, 2), input_tokens=i, output_tokens=o,
                        reasoning_tokens=r, status=getattr(resp, "status", None))

            items += resp.output                       # keep the model's own items (incl. reasoning)
            calls = [it for it in resp.output if getattr(it, "type", None) == "function_call"]
            text = (getattr(resp, "output_text", "") or "").strip()

            if not calls:
                if text:
                    answer = text
                    break
                trace.note(f"Empty reply (status={getattr(resp, 'status', None)}); nudging the model.")
                items.append({"role": "user", "content": EMPTY_REPLY_NUDGE})
                continue
            if text:
                trace.model_note(text)

            for call in calls:
                try:
                    args = json.loads(call.arguments or "{}")
                except json.JSONDecodeError:
                    args = None
                if args is None:
                    out = "Error: tool arguments were not valid JSON. Call the tool again."
                elif call.name == "get_schema":
                    out = db.get_schema()
                    trace.get_schema(out)
                    say(f"[{trace.step:>2}] get_schema")
                elif call.name == "run_sql":
                    query, purpose = args.get("query", ""), args.get("purpose", "")
                    if queries >= max_queries:
                        out = "Query budget exhausted. Do not call tools; write the final answer."
                        trace.note(f"Refused run_sql over budget: {purpose}")
                    else:
                        queries += 1
                        result, meta = db.run_sql(query)
                        sql_errors += 0 if meta["ok"] else 1
                        out = _clip(result) + f"\n[run_sql budget: {queries}/{max_queries} used]"
                        trace.run_sql(purpose, query, out, meta, queries, max_queries)
                        flag = f"{meta['rows']} rows" if meta["ok"] else f"ERROR {meta['error']}"
                        say(f"[{trace.step:>2}] sql {queries}/{max_queries}: {purpose[:90]} -> {flag} ({meta['ms']} ms)")
                elif call.name == "update_hypotheses":
                    hyps, nxt = args.get("hypotheses", []), args.get("next_step", "")
                    trace.hypotheses(hyps, nxt)
                    counts = {s: sum(h.get("status") == s for h in hyps)
                              for s in ("open", "supported", "rejected", "inconclusive")}
                    out = "Recorded. " + ", ".join(f"{v} {k}" for k, v in counts.items() if v)
                    say(f"[{trace.step:>2}] hypotheses: {out[10:]}")
                else:
                    out = f"Error: unknown tool '{call.name}'."
                items.append({"type": "function_call_output", "call_id": call.call_id, "output": out})

            if queries >= max_queries and not forced:
                forced = True
                items.append({"role": "user", "content": FORCE_FINAL_MESSAGE})
                trace.note("Query budget used up; tools switched off for the next call.")
                say("   query budget used up; asking for the final answer")
    finally:
        db.close()

    if answer is None:
        answer = "(The agent stopped without a final answer. See the trace for the steps it completed.)"
    cost = tok_in / 1e6 * PRICE_PER_1M_USD["input"] + tok_out / 1e6 * PRICE_PER_1M_USD["output"]
    stats = {
        "model": model,
        "model calls": turns,
        "run_sql calls": f"{queries} ({sql_errors} errors)",
        "tokens": f"{tok_in:,} in / {tok_out:,} out ({tok_reason:,} reasoning)",
        "estimated cost": f"${cost:.4f}",
        "wall time": f"{time.monotonic() - t_start:.0f} s (model {api_seconds:.0f} s)",
        "stopped by": "query budget" if forced and queries >= max_queries else
                      ("turn limit" if forced else "model finished"),
    }
    trace.final(answer, stats)
    return {"answer": answer, "stats": stats, "queries": queries, "sql_errors": sql_errors,
            "cost_usd": round(cost, 5), "trace_md": str(trace.md_path), "trace_jsonl": str(trace.jsonl_path)}


# ----------------------------------------------------------------------------- CLI
def main():
    for stream in (sys.stdout, sys.stderr):                 # Windows consoles default to cp1252
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass
    p = argparse.ArgumentParser(description="Ask the PocketToons analyst agent a question.")
    p.add_argument("question", nargs="*", help="the question (quotes optional)")
    p.add_argument("--max-queries", type=int, default=MAX_QUERIES)
    p.add_argument("--model", default=MODEL)
    p.add_argument("--trace-dir", default=str(TRACE_DIR))
    p.add_argument("--quiet", action="store_true", help="only print the final answer")
    a = p.parse_args()
    question = " ".join(a.question).strip() or input("Question: ").strip()
    if not question:
        sys.exit("No question given.")

    res = run_agent(question, model=a.model, max_queries=a.max_queries,
                    trace_dir=a.trace_dir, verbose=not a.quiet)
    print("\n" + "=" * 78 + "\n" + res["answer"] + "\n" + "=" * 78)
    print(" | ".join(f"{k}: {v}" for k, v in res["stats"].items()))
    print(f"Trace: {res['trace_md']}")


if __name__ == "__main__":
    main()
