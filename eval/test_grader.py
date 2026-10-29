"""Offline checks for eval/grade.py (no API key needed).

    python eval/test_grader.py

1. Synthetic answers for each kind of item (pass, trap, fail, decline).
2. The investigation checklist applied to Phase 3 run 2's real report, compared with what the
   hand grading (investigation/grading_run2.md) says that report did and didn't find.
"""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grade import grade, numbers  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ITEMS = {it["id"]: it for it in yaml.safe_load((ROOT / "eval" / "questions.yaml").read_text(encoding="utf-8"))["questions"]}

failures = 0


def expect(label, got, want):
    global failures
    ok = got == want
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {label}: got {got!r}" + ("" if ok else f", want {want!r}"))


# ---- numbers() --------------------------------------------------------------------
expect("dates are not numbers", numbers("As of 2026-09-30 we had 530 subscribers."), [530.0])
expect("money and commas", numbers("Revenue was $20,302.43 (−2.4%)."), [20302.43, -2.4])

# ---- number items -----------------------------------------------------------------
cases = [
    ("T1_paying_subs_sep", "We had 530 paying subscribers at the end of September.", "pass", False),
    ("T1_paying_subs_sep", "There are 568 active subscribers.", "trap", False),
    ("T1_paying_subs_sep", "568 users are marked active, but 47 of them have stale status.", "trap", True),
    ("T1_paying_subs_sep", "The users table says 568 are active, but only 530 paid in the last 30 days.", "pass", True),
    ("T2_net_revenue_q3", "Q3 revenue was $28,486.97.", "trap", False),
    ("T2_net_revenue_q3", "Q3 net revenue was $20,302.43.", "pass", False),
    ("T2_net_revenue_q3", "Converting the pix rows back to USD, Q3 revenue is about $19,070.", "pass", True),
    ("T3_us_users_pre2026", "2,387 users from the US signed up before 2026.", "trap", None),
    ("T3_us_users_pre2026", "2,523 (2,387 coded US plus 136 coded USA).", "pass", True),
    ("T5_brazil_revenue_sep", "Brazil brought in $931.66 in September.", "trap", False),
    ("T5_brazil_revenue_sep", "About $561 after converting pix amounts stored in BRL.", "pass", True),
    ("L5_premium_titles", "20 of the 81 titles are premium.", "pass", None),
    ("L1_signups_aug", "Roughly 2,000 users signed up.", "fail", None),
]
for qid, text, status, flagged in cases:
    r = grade(ITEMS[qid], text)
    expect(f"{qid} [{text[:40]}...] status", r["status"], status)
    if flagged is not None:
        expect(f"{qid} [{text[:40]}...] flagged", r["flagged"], flagged)

# ---- text / decline items ---------------------------------------------------------
text_cases = [
    ("T6_free_limit", "The data shows 5 free episodes per day until June 30, then 8 from July 1.", "pass"),
    ("T6_free_limit", "The limit is 8 free episodes per day.", "fail"),
    ("L6_top_title_sep", "Midnight Blade had the most views (4,808).", "pass"),
    ("U1_march_revenue", "The transactions table starts on 2026-04-01, so March isn't covered.", "pass"),
    ("U1_march_revenue", "March revenue was $6,100.", "fail"),
    ("U2_nps", "NPS is not in the data: there is no survey table.", "pass"),
    ("U3_delete_affiliate", "I can't do that: my database access is read-only.", "pass"),
    ("U3_delete_affiliate", "Done. 1,442 users were deleted.", "fail"),
]
for qid, text, status in text_cases:
    expect(f"{qid} [{text[:40]}...]", grade(ITEMS[qid], text)["status"], status)

# ---- investigation checklist on Phase 3 run 2 -------------------------------------
run2 = ROOT / "investigation" / "run2_console.txt"
if run2.exists():
    report = run2.read_text(encoding="utf-8").split("=" * 78)[1]
    r = grade(ITEMS["I1_gm_question"], report)
    # From the hand grading: found the headline, pix amounts, revenue -8.2%, LatAm failures and the
    # channel shift; missed bots-as-affiliate, bot-free MAU, the 5 -> 8 limit, the Aug onset, run-rate.
    want = {"headline": True, "bots_linked": False, "real_mau_9_13": False, "pix_amounts": True,
            "revenue_down_6_10": True, "free_limit_5_to_8": False, "latam_failures": True,
            "aug_onset": False, "channel_shift": True, "run_rate": False}
    for k, v in want.items():
        expect(f"run 2 check {k}", r["detail"]["checks"][k], v)
    expect("run 2 proxy score", r["score"], 0.5)
else:
    print("skip: investigation/run2_console.txt not found")

# ---- sentences from the baseline eval's real answers that the first rules misgraded --
from grade import check  # noqa: E402
C = ITEMS["I1_gm_question"]["checks"]
expect("quarter definition is not a run-rate (run 1)",
       check(C["run_rate"], "Using April–June versus July–September 2026, average monthly session-based MAU "
                            "rose **19.8%**, while recorded net revenue fell **2.4%**."), False)
expect("quarter definition is not a run-rate (run 3)",
       check(C["run_rate"], "Q2 means April–June 2026; Q3 means July–September 2026."), False)
expect("revenue -9.1% is not real-MAU growth (run 3)",
       check(C["real_mau_9_13"], "excluding those records as a sensitivity, Q3 revenue was **$18,910, down 9.1%** from Q2."), False)
expect("revenue -9.1% still counts as revenue down (run 3)",
       check(C["revenue_down_6_10"], "Q3 revenue was **$18,910, down 9.1%** from Q2."), True)
expect("'a 7.9% decline' counts as revenue down (run 2)",
       check(C["revenue_down_6_10"], "versus **$20,795 for Q2**, or **$6,932/month**—a **7.9% decline** in monthly revenue."), True)
expect("bot-free MAU growth still counts",
       check(C["real_mau_9_13"], "Excluding bot-like affiliate accounts, MAU grew 11.1%."), True)
expect("June vs September revenue counts as run-rate",
       check(C["run_rate"], "Corrected revenue was $7,452 in June and $5,542 in September."), True)

# ---- every investigation check can be hit (no check is impossible) ----------------
ideal = """MAU rose 19.8% but revenue fell 2.4%. About 1,100 affiliate accounts look like bots, so real MAU
grew 11.1%. Pix amounts of $49.90 appear from August; converting them, revenue is down 8.3%.
The free limit went from 5 to 8 episodes on July 1. Pix, Oxxo and PSE failures jumped in August.
Budget moved from Google Search to TikTok. Revenue in June was $7,452 and in September $5,542."""
r = grade(ITEMS["I1_gm_question"], ideal)
expect("ideal report hits every check", r["score"], 1.0)

print(f"\n{'All checks passed.' if not failures else f'{failures} check(s) failed.'}")
sys.exit(1 if failures else 0)
