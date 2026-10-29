"""Grading functions for the PocketToons agent eval (no API calls; imported by run_eval.py).

Each grade_* function takes one item from eval/questions.yaml and the agent's final report text,
and returns a dict: status ('pass' | 'fail' | 'trap'), score (0..1), flagged (bool or None), detail.
"""
import re

_DATE = re.compile(r"\b\d{4}-\d{2}(-\d{2})?\b")
_NUM = re.compile(r"(?<![\w.])[-−]?\$?\d[\d,]*(?:\.\d+)?")
_PCT = re.compile(r"([-−])?\s?(\d+(?:\.\d+)?)\s?%")
_DOWN = re.compile(r"(down|fell|fall|declin\w*|lower|drop\w*|decrease\w*)\W{0,3}(\w+\W{1,3}){0,3}$", re.I)


def numbers(text):
    """All numbers in the text as floats; dates are removed first, '$', ',' and '%' ignored."""
    text = _DATE.sub(" ", text)
    out = []
    for m in _NUM.finditer(text):
        s = m.group(0).replace("−", "-").replace("$", "").replace(",", "")
        try:
            out.append(float(s))
        except ValueError:
            pass
    return out


def _close(n, target, tol=None, rtol=None):
    if rtol is not None:
        return abs(abs(n) - target) <= rtol * abs(target)
    return abs(abs(n) - target) <= (tol or 0)


def _flagged(item, text):
    pats = item.get("flags")
    if not pats:
        return None
    return any(re.search(p, text, re.I) for p in pats)


def grade_number(item, text):
    nums = numbers(text)
    tol, rtol = item.get("tol"), item.get("rtol")
    hit = [a for a in item["accept"] if any(_close(n, a, tol, rtol) for n in nums)]
    trap_hit = [t for t in item.get("trap", [])
                if any(_close(n, t, item.get("trap_tol"), item.get("trap_rtol")) for n in nums)]
    if hit:
        status = "pass"
    elif trap_hit:
        status = "trap"
    else:
        status = "fail"
    flagged = _flagged(item, text)
    if flagged is not None and hit and trap_hit:
        flagged = True   # gave both the right value and the trap value: it contrasted them
    return {"status": status, "score": 1.0 if hit else 0.0, "flagged": flagged,
            "detail": {"matched": hit, "trap_matched": trap_hit}}


def _patterns_ok(spec, text):
    all_ok = all(re.search(p, text, re.I) for p in spec.get("all", []))
    any_list = spec.get("any", [])
    any_ok = (not any_list) or any(re.search(p, text, re.I) for p in any_list)
    return all_ok and any_ok


def grade_text(item, text):
    ok = _patterns_ok(item, text)
    return {"status": "pass" if ok else "fail", "score": 1.0 if ok else 0.0,
            "flagged": _flagged(item, text), "detail": {}}


def _pcts(text):
    """Percentages with their sign: negative if written with a minus or after 'down', 'fell', etc."""
    out = []
    for m in _PCT.finditer(text):
        val = float(m.group(2))
        neg = bool(m.group(1)) or bool(_DOWN.search(text[max(0, m.start() - 40):m.start()]))
        out.append(-val if neg else val)
    return out


def check(spec, text):
    if "pct_between" in spec:
        lo, hi = spec["pct_between"]
        return any(lo <= abs(p) <= hi for p in _pcts(text))
    if "neg_pct_between" in spec:
        lo, hi = spec["neg_pct_between"]
        return any(p < 0 and lo <= -p <= hi for p in _pcts(text))
    return _patterns_ok(spec, text)


def grade_investigation(item, text):
    hits = {name: check(spec, text) for name, spec in item["checks"].items()}
    score = sum(hits.values()) / len(hits)
    return {"status": "pass" if score >= 0.5 else "fail", "score": round(score, 3),
            "flagged": None, "detail": {"checks": hits}}


def grade(item, text):
    kind = item["type"]
    if kind == "number":
        return grade_number(item, text)
    if kind in ("text", "decline"):
        return grade_text(item, text)
    if kind == "investigation":
        return grade_investigation(item, text)
    raise ValueError(f"unknown type {kind!r} in {item['id']}")
