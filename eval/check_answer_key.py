"""Re-run the SQL behind every expected answer in eval/questions.yaml and compare.

    python eval/check_answer_key.py

Prints OK or MISMATCH per question. Run it after regenerating the database to confirm the
answer key still matches the data.
"""
import os
import sqlite3
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DB = Path(os.environ.get("PT_DB", ROOT / "data" / "pockettoons.db"))


def main():
    items = yaml.safe_load((ROOT / "eval" / "questions.yaml").read_text(encoding="utf-8"))["questions"]
    con = sqlite3.connect(DB.resolve().as_uri() + "?mode=ro", uri=True)
    bad = 0
    for it in items:
        sql = it.get("sql")
        if not sql:
            print(f"{it['id']:<24} -        (no SQL: {it['type']})")
            continue
        got = con.execute(sql).fetchone()[0]
        if it["type"] == "number":
            want = it["accept"][0]
            ok = abs(float(got) - want) <= max(it.get("tol") or 0, (it.get("rtol") or 0) * abs(want), 0.01)
        elif it["type"] == "text" and it.get("any") and "all" not in it:
            import re
            ok = any(re.search(p, str(got), re.I) for p in it["any"])
        else:
            ok = True   # reference value only (decline / free-limit items): printed for the reader
        bad += not ok
        print(f"{it['id']:<24} {'OK      ' if ok else 'MISMATCH'} {got}")
    print("\nAnswer key matches the database." if not bad else f"\n{bad} mismatch(es).")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
