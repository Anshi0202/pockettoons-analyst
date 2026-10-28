#!/usr/bin/env python3
"""
test_offline.py - checks the agent without an API key or network.

    python agent/test_offline.py

1. Tool safety: read-only, single statement, timeout, row cap, readable errors.
2. The loop, using the real OpenAI SDK against a mock HTTP server that replays scripted
   Responses API replies. This checks that what we send back to the API (function calls,
   reasoning items, tool outputs) serializes correctly, plus budget handling and trace files.
"""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:                       # newer openai SDKs ship httpx2, older ones httpx
    import httpx2 as httpx  # noqa: E402
except ImportError:
    import httpx  # noqa: E402
from openai import OpenAI  # noqa: E402

from agent.agent import run_agent  # noqa: E402
from agent.tools import SQLTools  # noqa: E402

PASSED = []


def check(name, cond, detail=""):
    if not cond:
        raise AssertionError(f"FAILED: {name} {detail}")
    PASSED.append(name)
    print(f"  ok  {name}")


# ----------------------------------------------------------------------------- 1. tools
def test_tools():
    print("Tools")
    db = SQLTools()
    schema = db.get_schema()
    for t in ("users", "sessions", "content_views", "transactions", "content_catalog", "marketing_spend"):
        check(f"schema lists {t}", f"## {t}" in schema)
    check("schema shows date coverage", "2026-04-01 to 2026-09-30" in schema)

    out, m = db.run_sql("SELECT substr(date,1,7) AS month, COUNT(DISTINCT user_id) AS mau "
                        "FROM sessions GROUP BY 1 ORDER BY 1")
    check("basic query", m["ok"] and m["rows"] == 6 and "| 2026-08 | 5389 |" in out, out)

    for label, q in [("INSERT blocked", "INSERT INTO users(user_id) VALUES (1)"),
                     ("DROP after comment blocked", "-- x\n/* y */ DROP TABLE users"),
                     ("PRAGMA blocked", "PRAGMA writable_schema = 1"),
                     ("WITH ... DELETE blocked by read-only file", "WITH x AS (SELECT 1) DELETE FROM users"),
                     ("two statements blocked", "SELECT 1; SELECT 2")]:
        out, m = db.run_sql(q)
        check(label, not m["ok"], out)
    check("users table untouched", "20708" in db.run_sql("SELECT COUNT(*) FROM users")[0])

    out, m = db.run_sql("SELECT nope FROM users")
    check("bad column -> readable error", not m["ok"] and "no such column: nope" in out)
    out, m = db.run_sql("SELECT user_id FROM users")
    check("row cap", m["rows"] == 100 and m["truncated"] and "first 100 rows" in out)
    out, m = db.run_sql("SELECT * FROM users WHERE country = 'Narnia'")
    check("empty result explained", m["ok"] and "0 rows" in out)

    slow = SQLTools(timeout_s=1)
    out, m = slow.run_sql("WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) SELECT COUNT(*) FROM c")
    check("timeout cancels runaway query", m["error"] == "timeout", out)
    check("connection usable after timeout", slow.run_sql("SELECT 1")[1]["ok"])
    db.close()
    slow.close()


# ----------------------------------------------------------------------------- 2. loop
def _response(rid, output, inp=1000, out=200, reasoning=50):
    return {
        "id": rid, "object": "response", "created_at": 0, "status": "completed", "model": "mock",
        "output": output, "parallel_tool_calls": True, "tool_choice": "auto", "tools": [],
        "error": None, "incomplete_details": None, "instructions": None, "metadata": {},
        "text": {"format": {"type": "text"}},
        "usage": {"input_tokens": inp, "output_tokens": out, "total_tokens": inp + out,
                  "input_tokens_details": {"cached_tokens": 0},
                  "output_tokens_details": {"reasoning_tokens": reasoning}},
    }


def _call(n, name, args):
    return {"type": "function_call", "id": f"fc_{n}", "call_id": f"call_{n}", "name": name,
            "arguments": json.dumps(args), "status": "completed"}


def _reasoning(n):
    return {"type": "reasoning", "id": f"rs_{n}", "summary": []}


def _message(text):
    return {"type": "message", "id": "msg_1", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": text, "annotations": []}]}


def mock_client(script):
    """script: list of functions(request_body) -> response dict, consumed in order."""
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        step = script[min(len(requests), len(script)) - 1]
        return httpx.Response(200, json=step(body))

    client = OpenAI(api_key="test-key", base_url="https://mock.invalid/v1", max_retries=0,
                    http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    return client, requests


FINAL = "## Answer\nMAU in August 2026 was 5,389.\n\n## Definition and scope\nDistinct users with a session."


def test_happy_path(tmp):
    print("Loop: normal run")
    script = [
        lambda b: _response("r1", [_reasoning(1), _call(1, "get_schema", {})]),
        lambda b: _response("r2", [_reasoning(2), _call(2, "run_sql", {
            "query": "SELECT COUNT(DISTINCT user_id) AS mau FROM sessions WHERE substr(date,1,7)='2026-08'",
            "purpose": "MAU for August"})]),
        lambda b: _response("r3", [_call(3, "run_sql", {"query": "SELECT bogus FROM sessions",
                                                         "purpose": "deliberately bad column"})]),
        lambda b: _response("r4", [_call(4, "update_hypotheses", {
            "hypotheses": [{"statement": "August MAU is ~5.4K", "status": "supported", "evidence": "5,389"}],
            "next_step": "write answer"})]),
        lambda b: _response("r5", [_reasoning(5), _message(FINAL)]),
    ]
    client, reqs = mock_client(script)
    res = run_agent("What was MAU in August 2026?", client=client, trace_dir=tmp, verbose=False, model="mock")

    check("final answer returned", res["answer"].startswith("## Answer"))
    check("5 model calls", len(reqs) == 5, len(reqs))
    check("tools sent with strict schemas", {t["name"] for t in reqs[0]["tools"]} ==
          {"get_schema", "run_sql", "update_hypotheses"} and all(t["strict"] for t in reqs[0]["tools"]))
    check("system prompt sent as instructions", "senior product analyst" in reqs[0]["instructions"])
    second = reqs[1]["input"]
    check("reasoning item echoed back", any(i.get("type") == "reasoning" and i.get("id") == "rs_1" for i in second))
    check("function_call echoed back", any(i.get("type") == "function_call" and i.get("call_id") == "call_1" for i in second))
    outs = [i for i in reqs[2]["input"] if i.get("type") == "function_call_output"]
    check("tool outputs paired by call_id", [o["call_id"] for o in outs] == ["call_1", "call_2"])
    check("SQL result reaches the model", "5389" in outs[1]["output"] and "budget: 1/40" in outs[1]["output"])
    err = [i for i in reqs[3]["input"] if i.get("type") == "function_call_output"][-1]["output"]
    check("SQL error reaches the model", "no such column: bogus" in err)
    check("no tool_choice=none in a normal run", all("tool_choice" not in r for r in reqs))
    check("stats count queries and errors", res["queries"] == 2 and res["sql_errors"] == 1)

    md = Path(res["trace_md"]).read_text(encoding="utf-8")
    for part in ("**Question:** What was MAU", "get_schema", "**Purpose:** MAU for August", "| 5389 |",
                 "no such column: bogus", "| August MAU is ~5.4K | **supported** |", "## Final answer", "## Run stats"):
        check(f"trace has {part[:40]!r}", part in md)
    kinds = [json.loads(l)["kind"] for l in Path(res["trace_jsonl"]).read_text(encoding="utf-8").splitlines()]
    check("jsonl has start, tool, final events", kinds[0] == "start" and "tool" in kinds and kinds[-1] == "final")
    check("cost estimated", res["cost_usd"] > 0)


def test_budget(tmp):
    print("Loop: query budget runs out")

    def greedy(b):
        if b.get("tool_choice") == "none":
            return _response("rf", [_message("## Answer\nPartial answer.\n\n## Confidence and open questions\nBudget ran out.")])
        n = len(b["input"])
        return _response(f"r{n}", [_call(n, "run_sql", {"query": "SELECT 1", "purpose": f"probe {n}"})])

    client, reqs = mock_client([greedy])
    res = run_agent("Why did revenue change?", client=client, trace_dir=tmp, verbose=False,
                    model="mock", max_queries=2)
    check("stops at the query budget", res["queries"] == 2)
    check("last call disables tools", reqs[-1].get("tool_choice") == "none")
    check("model told to finish", "full query budget" in json.dumps(reqs[-1]["input"]))
    check("partial answer kept", "Partial answer" in res["answer"])
    check("stop reason recorded", res["stats"]["stopped by"] == "query budget")

    print("Loop: empty reply, then answer")
    script = [lambda b: _response("e1", [_reasoning(1)]), lambda b: _response("e2", [_message(FINAL)])]
    client, reqs = mock_client(script)
    res = run_agent("MAU in August?", client=client, trace_dir=tmp, verbose=False, model="mock")
    check("empty reply nudged and recovered", res["answer"].startswith("## Answer") and len(reqs) == 2)


if __name__ == "__main__":
    test_tools()
    with tempfile.TemporaryDirectory() as tmp:
        test_happy_path(tmp)
        test_budget(tmp)
    print(f"\nAll {len(PASSED)} checks passed.")
