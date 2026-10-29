"""Re-grade an existing eval run with the current rules in eval/questions.yaml (no agent calls, no cost).

    python eval/regrade.py eval/runs/<run folder>

Reads the saved console output in <run folder>/raw/, grades it again, and writes
results_regraded.jsonl and summary_regraded.md next to the originals (which are left untouched).
compare.py uses the regraded results when they exist. Prints which items changed.
"""
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grade import grade  # noqa: E402
from run_eval import ROOT, answer_excerpt, parse_output, write_summary  # noqa: E402


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    folder = Path(sys.argv[1]).resolve()
    items = {it["id"]: it for it in
             yaml.safe_load((ROOT / "eval" / "questions.yaml").read_text(encoding="utf-8"))["questions"]}
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    old_rows = [json.loads(l) for l in (folder / "results.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

    rows, changed = [], []
    for old in old_rows:
        row = dict(old)
        raw = folder / "raw" / f"{old['id']}_r{old['repeat']}.txt"
        if old["status"] != "error" and raw.exists():
            report, _, _ = parse_output(raw.read_text(encoding="utf-8").split("\n--- stderr ---\n")[0])
            row.update(grade(items[old["id"]], report))
            row["excerpt"] = answer_excerpt(report)
        rows.append(row)
        before = old["score"] if old["category"] == "investigation" else old["status"]
        after = row["score"] if row["category"] == "investigation" else row["status"]
        if before != after or old.get("flagged") != row.get("flagged"):
            diff = ""
            if row["category"] == "investigation":
                diff = ", ".join(f"{k} {'+' if v else '-'}" for k, v in row["detail"]["checks"].items()
                                 if v != old["detail"]["checks"].get(k))
            changed.append(f"{old['id']} run {old['repeat']}: {before} -> {after} {diff}".rstrip())

    with open(folder / "results_regraded.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    write_summary(folder, meta, rows, list(items.values()), filename="summary_regraded.md",
                  note="Re-graded with the current rules in eval/questions.yaml (see its change log). "
                       "The original grades are in summary.md.")
    print("Changed:" if changed else "No grades changed.")
    for c in changed:
        print("  " + c)
    print(f"Wrote {(folder / 'summary_regraded.md').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
