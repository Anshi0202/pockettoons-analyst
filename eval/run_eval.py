"""Run the PocketToons agent on every question in eval/questions.yaml and grade it.

From the project folder, venv active:

    python eval/run_eval.py --label baseline --dry-run        # list what would run, no API calls
    python eval/run_eval.py --label baseline                  # full eval (~20 min, ~$0.25)
    python eval/run_eval.py --label v2 --env PT_PROMPT=v2     # same, with an env var for the agent
    python eval/run_eval.py --label quick --only L1_signups_aug T1_paying_subs_sep

The agent is run exactly as from the command line (python agent/agent.py "<question>"), one
process per question, and its console output is parsed: the report between the two '=====' lines,
the stats line and the 'Trace:' path. Each run's trace files are moved into the eval run folder.

Output: eval/runs/<timestamp>_<label>/ with results.jsonl, summary.md, meta.json, raw/ (console
output per run) and traces/. Compare runs with eval/compare.py.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grade import grade  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SEP = re.compile(r"^={20,}\s*$", re.M)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_output(out):
    """Split the agent's console output into report, stats and trace path."""
    parts = SEP.split(out)
    if len(parts) >= 3:
        report, tail = parts[1].strip(), parts[2]
    else:  # no separator lines: drop the progress lines and keep the rest
        report = "\n".join(l for l in out.splitlines() if not re.match(r"^\[\s*\d+\]", l)).strip()
        tail = out
    stats = {}
    line = next((l for l in tail.splitlines() if "model calls:" in l), "")
    for key, pat, cast in [("model_calls", r"model calls:\s*(\d+)", int),
                           ("sql_calls", r"run_sql calls:\s*(\d+)", int),
                           ("sql_errors", r"\((\d+) errors?\)", int),
                           ("cost_usd", r"estimated cost:\s*\$([\d.]+)", float),
                           ("wall_s", r"wall time:\s*(\d+)", int),
                           ("stopped_by", r"stopped by:\s*(.+)$", str)]:
        m = re.search(pat, line)
        stats[key] = cast(m.group(1).strip()) if m else None
    m = re.search(r"^Trace:\s*(.+?)\s*$", out, re.M)
    return report, stats, (m.group(1) if m else None)


def answer_excerpt(report, n=160):
    m = re.search(r"#+\s*Answer\s*\n+([\s\S]+?)(\n\s*\n|\n#|$)", report)
    text = m.group(1) if m else report
    text = re.sub(r"\s+", " ", text.replace("**", "")).strip().replace("|", "/")
    return text[:n] + ("…" if len(text) > n else "")


def run_agent(agent, question, env, timeout):
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, str(agent), question], cwd=ROOT, env=env, timeout=timeout,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        return p.stdout, p.stderr, p.returncode, round(time.time() - t0, 1)
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        return out, f"TIMEOUT after {timeout}s", -1, round(time.time() - t0, 1)


def move_traces(trace_md, dest, prefix):
    moved = []
    if not trace_md:
        return moved
    src = Path(trace_md)
    for f in (src, src.with_suffix(".jsonl")):
        if f.exists():
            target = dest / f"{prefix}_{f.name}"
            try:
                shutil.move(str(f), target)
            except OSError:
                shutil.copy2(f, target)
            moved.append(str(target.relative_to(ROOT)))
    return moved


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, timeout=10).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def write_summary(out_dir, meta, rows, items):
    by_id = {it["id"]: it for it in items}
    L = [f"# Eval run: {meta['label']}", "",
         "| Field | Value |", "|---|---|"]
    for k in ("started", "finished", "agent_env", "git_commit", "agent_files", "db_unchanged"):
        L.append(f"| {k} | {meta.get(k)} |")
    tot_cost = sum((r["stats"].get("cost_usd") or 0) for r in rows)
    tot_time = sum(r["seconds"] for r in rows)
    L.append(f"| total cost / time | ${tot_cost:.3f} / {tot_time / 60:.1f} min |")

    L += ["", "## Score by category", "", "| Category | Runs | Pass | Rate | Notes |", "|---|---|---|---|---|"]
    for cat in ("lookup", "trap", "decline"):
        rs = [r for r in rows if r["category"] == cat]
        if not rs:
            continue
        p = sum(r["status"] == "pass" for r in rs)
        note = ""
        if cat == "trap":
            note = (f"fell into trap: {sum(r['status'] == 'trap' for r in rs)}; "
                    f"warned about the data issue: {sum(bool(r['flagged']) for r in rs)}/{len(rs)}")
        L.append(f"| {cat} | {len(rs)} | {p} | {p / len(rs):.0%} | {note} |")
    inv = [r for r in rows if r["category"] == "investigation"]
    if inv:
        sc = [r["score"] for r in inv]
        L.append(f"| investigation | {len(inv)} | – | mean {sum(sc) / len(sc):.0%} "
                 f"(min {min(sc):.0%}, max {max(sc):.0%}) | proxy checklist, not the hand rubric |")

    L += ["", "## Per run", "", "| Question | Run | Status | Warned | Queries | Cost | Time (s) | Stopped by | Answer (start) |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        s = r["stats"]
        warned = "" if r["flagged"] is None else ("yes" if r["flagged"] else "no")
        status = r["status"] if r["category"] != "investigation" else f"{r['score']:.0%}"
        cost = "" if s.get("cost_usd") is None else "${:.4f}".format(s["cost_usd"])
        L.append(f"| {r['id']} | {r['repeat']} | {status} | {warned} | {s.get('sql_calls')} | "
                 f"{cost} | {r['seconds']} | {s.get('stopped_by') or ''} | {r['excerpt']} |")

    if inv:
        names = list(by_id[inv[0]["id"]]["checks"])
        L += ["", "## Investigation checks (hits across repeats)", "", "| Check | Hits |", "|---|---|"]
        for n in names:
            L.append(f"| {n} | {sum(r['detail']['checks'][n] for r in inv)}/{len(inv)} |")
    (out_dir / "summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", required=True, help="name for this run, e.g. baseline or v2")
    ap.add_argument("--env", nargs="*", default=[], metavar="KEY=VALUE", help="extra env vars for the agent")
    ap.add_argument("--only", nargs="*", help="question ids to run (default: all)")
    ap.add_argument("--repeats", type=int, default=1, help="runs per non-investigation question")
    ap.add_argument("--investigation-repeats", type=int, default=3, help="runs of the GM question")
    ap.add_argument("--agent", default="agent/agent.py", help="agent script, relative to the project folder")
    ap.add_argument("--timeout", type=int, default=1200, help="seconds per agent run")
    ap.add_argument("--dry-run", action="store_true", help="list what would run and exit")
    args = ap.parse_args()

    items = yaml.safe_load((ROOT / "eval" / "questions.yaml").read_text(encoding="utf-8"))["questions"]
    if args.only:
        unknown = set(args.only) - {it["id"] for it in items}
        if unknown:
            sys.exit(f"unknown question id(s): {', '.join(sorted(unknown))}")
        items = [it for it in items if it["id"] in args.only]
    plan = [(it, k + 1) for it in items
            for k in range(args.investigation_repeats if it["type"] == "investigation" else args.repeats)]

    extra_env = dict(kv.split("=", 1) for kv in args.env)
    print(f"{len(plan)} agent runs, label '{args.label}', env {extra_env or '{}'}")
    if args.dry_run:
        for it, k in plan:
            print(f"  {it['id']:<24} run {k}: {it['question'][:70]}")
        return

    agent = ROOT / args.agent
    db = ROOT / "data" / "pockettoons.db"
    if not agent.exists():
        sys.exit(f"agent not found: {agent}")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "eval" / "runs" / f"{stamp}_{re.sub(r'[^A-Za-z0-9_-]', '_', args.label)}"
    (out_dir / "raw").mkdir(parents=True)
    (out_dir / "traces").mkdir()
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", **extra_env}
    meta = {"label": args.label, "started": datetime.now().isoformat(timespec="seconds"),
            "agent_env": extra_env, "git_commit": git_commit(), "python": sys.version.split()[0],
            "agent_files": {p.name: sha256(p)[:12] for p in sorted((ROOT / "agent").glob("*.py"))},
            "db_sha256_before": sha256(db) if db.exists() else None}

    rows = []
    with open(out_dir / "results.jsonl", "w", encoding="utf-8") as fout:
        for n, (it, k) in enumerate(plan, 1):
            print(f"[{n}/{len(plan)}] {it['id']} run {k} ...", end=" ", flush=True)
            out, err, code, secs = run_agent(agent, it["question"], env, args.timeout)
            prefix = f"{it['id']}_r{k}"
            (out_dir / "raw" / f"{prefix}.txt").write_text(out + ("\n--- stderr ---\n" + err if err else ""),
                                                           encoding="utf-8")
            report, stats, trace = parse_output(out)
            if code != 0 or not report:
                g = {"status": "error", "score": 0.0, "flagged": None,
                     "detail": {"returncode": code, "stderr_tail": err[-500:]}}
            else:
                g = grade(it, report)
            row = {"id": it["id"], "category": it["category"], "repeat": k, "question": it["question"],
                   **g, "stats": stats, "seconds": secs, "excerpt": answer_excerpt(report) if report else "",
                   "traces": move_traces(trace, out_dir / "traces", prefix)}
            rows.append(row)
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
            fout.flush()
            label = f"{g['score']:.0%}" if it["type"] == "investigation" else g["status"]
            print(f"{label} ({secs:.0f} s, {stats.get('sql_calls')} queries)")

    meta["finished"] = datetime.now().isoformat(timespec="seconds")
    meta["db_sha256_after"] = sha256(db) if db.exists() else None
    meta["db_unchanged"] = meta["db_sha256_before"] == meta["db_sha256_after"]
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    write_summary(out_dir, meta, rows, items)
    print(f"\nDone. Database unchanged: {meta['db_unchanged']}. Summary: {out_dir.relative_to(ROOT) / 'summary.md'}")


if __name__ == "__main__":
    main()
