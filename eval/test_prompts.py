"""Offline checks for the prompt variants in agent/prompts.py (no API key needed).

    python eval/test_prompts.py

- v1 (the default) is exactly the Phase 3 prompt.
- v2 changes only what V2_EDITS lists, and every edit applies exactly once.
- The text v2 adds is generic: none of the planted story's specifics appear in it.
"""
import difflib
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.pop("PT_PROMPT", None)
from agent import prompts  # noqa: E402

failures = 0


def expect(label, ok, extra=""):
    global failures
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {label}{(': ' + extra) if extra and not ok else ''}")


v1 = prompts.system_prompt(40, 100)
expect("default is v1", v1 == prompts.SYSTEM_PROMPT.format(max_queries=40, max_rows=100))
expect("explicit v1 equals default", prompts.system_prompt(40, 100, "v1") == v1)
os.environ["PT_PROMPT"] = "v2"
v2 = prompts.system_prompt(40, 100)
os.environ.pop("PT_PROMPT")
expect("PT_PROMPT=v2 changes the prompt", v2 != v1)
expect("v2 formats the budget", "40 run_sql calls" in v2 and "{max_queries}" not in v2)
expect("v2 adds step 9", "\n9. For an open-ended" in v2)
try:
    prompts.system_prompt(40, 100, "v3")
    expect("unknown variant rejected", False)
except ValueError:
    expect("unknown variant rejected", True)

# What v2 adds, word by word
added = " ".join(w for w in difflib.ndiff(v1.split(), v2.split()) if w.startswith("+ ")).replace("+ ", "")
removed = [w[2:] for w in difflib.ndiff(v1.split(), v2.split()) if w.startswith("- ")]
expect("v2 removes almost nothing", len(removed) <= 15, f"{len(removed)} words removed")
story_terms = ["pix", "oxxo", "pse", "brl", "real", "currency", "bot", "affiliate", "fraud", "tiktok", "google",
               "meta", "influencer", "crimson", "ppv", "pay-per-view", "episode", "free", "subscription",
               "latam", "latin", "brazil", "mexico", "colombia", "processor", "payment", "\\b5\\b", "\\b8\\b",
               "july", "august", "september", "june", "q2", "q3", "2026", "cap", "paywall"]
checked = re.sub(r"\bsteps? \d+(-\d+)?", " ", added)       # step references are not story numbers
hits = [t for t in story_terms if re.search(rf"\b{t}\b" if t.isalpha() else t, checked, re.I)]
expect("v2 additions contain no story-specific terms", not hits, f"found {hits}")
print(f"\nv2 adds {len(added.split())} words.")

print(f"\n{'All checks passed.' if not failures else f'{failures} check(s) failed.'}")
sys.exit(1 if failures else 0)
