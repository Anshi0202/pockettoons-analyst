"""Compare two or more eval runs side by side.

    python eval/compare.py eval/runs/<baseline_folder> eval/runs/<v2_folder>

Writes eval/comparison.md and prints it.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(folder):
    folder = Path(folder)
    regraded = folder / "results_regraded.jsonl"            # written by eval/regrade.py
    src = regraded if regraded.exists() else folder / "results.jsonl"
    rows = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    meta["label"] = meta["label"] + (" (regraded)" if src == regraded else "")
    return meta, rows


def cell(rs):
    if not rs:
        return "–"
    if rs[0]["category"] == "investigation":
        sc = [r["score"] for r in rs]
        return f"{sum(sc) / len(sc):.0%} ({', '.join(f'{s:.0%}' for s in sc)})"
    statuses = [r["status"] for r in rs]
    s = statuses[0] if len(set(statuses)) == 1 else "/".join(statuses)
    if rs[0].get("flagged") is not None:
        s += ", warned" if any(r["flagged"] for r in rs) else ", no warning"
    return s


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    runs = [load(f) for f in sys.argv[1:]]
    labels = [m["label"] for m, _ in runs]
    head = "| | " + " | ".join(labels) + " |"
    rule = "|---|" + "---|" * len(labels)
    L = ["# Eval comparison", "", head, rule]

    def row(name, fn):
        L.append(f"| {name} | " + " | ".join(fn(m, rs) for m, rs in runs) + " |")

    def rate(cat):
        def f(_, rs):
            xs = [r for r in rs if r["category"] == cat]
            return f"{sum(r['status'] == 'pass' for r in xs)}/{len(xs)}" if xs else "–"
        return f

    row("Lookups passed", rate("lookup"))
    row("Traps passed", rate("trap"))
    row("Traps fallen into", lambda _, rs: str(sum(r["status"] == "trap" for r in rs)))
    row("Traps with a warning", lambda _, rs: f"{sum(bool(r['flagged']) for r in rs if r['category'] == 'trap')}"
                                             f"/{sum(r['category'] == 'trap' for r in rs)}")
    row("Declines handled", rate("decline"))
    row("Errors", lambda _, rs: str(sum(r["status"] == "error" for r in rs)))
    row("Investigation proxy score", lambda _, rs: cell([r for r in rs if r["category"] == "investigation"]))
    row("Total cost", lambda _, rs: f"${sum((r['stats'].get('cost_usd') or 0) for r in rs):.3f}")
    row("Total time", lambda _, rs: f"{sum(r['seconds'] for r in rs) / 60:.1f} min")
    row("Database unchanged", lambda m, _: str(m.get("db_unchanged")))
    row("Agent env", lambda m, _: str(m.get("agent_env") or "{}"))
    row("prompts.py hash", lambda m, _: str(m.get("agent_files", {}).get("prompts.py")))

    L += ["", "## Per question", "", head, rule]
    ids = list(dict.fromkeys(r["id"] for _, rs in runs for r in rs))
    for qid in ids:
        L.append(f"| {qid} | " + " | ".join(cell([r for r in rs if r["id"] == qid]) for _, rs in runs) + " |")

    inv = [[r for r in rs if r["category"] == "investigation"] for _, rs in runs]
    if any(inv):
        names = next(list(x[0]["detail"]["checks"]) for x in inv if x)
        L += ["", "## Investigation checks (hits across repeats)", "", head, rule]
        for n in names:
            L.append(f"| {n} | " + " | ".join(
                f"{sum(r['detail']['checks'][n] for r in x)}/{len(x)}" if x else "–" for x in inv) + " |")

    text = "\n".join(L) + "\n"
    (ROOT / "eval" / "comparison.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
