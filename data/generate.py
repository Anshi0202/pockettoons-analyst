#!/usr/bin/env python3
"""
generate.py - PocketToons synthetic dataset generator
=====================================================

Builds data/pockettoons.db (SQLite) with 6 months of activity (2026-04-01 -> 2026-09-30)
for a fictional freemium anime streaming app. Standard library only; deterministic via SEED.

    python data/generate.py

THE PLANTED STORY  (full answer key with numbers: data/story.md)
---------------------------------------------------------------
GM's question: "MAU is up 20% QoQ but revenue is flat."
Q2 = Apr-Jun 2026, Q3 = Jul-Sep 2026.

In Q3 the company ran an "efficient growth" push judged on MAU and CAC. Three decisions, each
defensible on its own, together explain why the dashboard shows users up and revenue flat:

  RC1  Acquisition mix shift (Jul 1). Paid spend was cut ~33% and moved from Google Search /
       Meta (US-heavy, high-intent, CAC ~$5-6) to TikTok + influencers (SEA/LatAm,
       low-intent, CAC ~$2-3). Blended CAC fell sharply and the signup count held up, but
       Google signups fell ~80%. The replacement users rarely pay and churn faster, so this
       cost revenue (mostly felt in future months) and did NOT add real MAU.

  RC2  Free limit raised from 5 to 8 episodes/day (Jul 1) to boost engagement. Hitting the
       daily cap was the main moment free users subscribed (or bought PPV). With a higher cap
       far fewer users hit it, so conversion fell for EVERY cohort, including the old
       high-intent US base. Engagement rose (more free episodes per day); retention barely
       moved. This is the largest single cause of the revenue gap.

  RC3  LatAm payment migration (Aug 1). Local methods (pix / oxxo / pse) moved to a new
       processor with high and *correlated* failure rates (if the first charge fails, the
       retries almost always fail too). Result: failed sign-ups and involuntary churn in
       LatAm - the region RC1 was pouring new users into.

DATA QUALITY ISSUES (injected deliberately; DQ2-DQ4 in section 6 near the bottom)
  DQ1  Bot installs. A new 'affiliate_network' channel (Jul 10+, paid per install) is ~80%
       fake accounts: 1-3 sessions of a few seconds, within 3 days of signup, never pay.
       They inflate MAU - about half of the reported 20% growth is bots.
  DQ2  Currency bug. The new processor writes pix amounts in BRL into amount_usd from Aug 1
       (49.90 instead of 9.99). This props up reported revenue: "flat" is really a decline,
       and LatAm revenue looks flat when it actually fell ~20%.
  DQ3  Stale subscription_status. Involuntary churners on the new processor never received
       a cancel webhook, so users.subscription_status still says 'active' (end date NULL).
  DQ4  Inconsistent country codes. Legacy web sign-ups (before 2026) stored 'USA' not 'US'.

RED HERRING
  RH1  A premium title ("Crimson Requiem") released May 22 caused a PPV spike in May-June, so
       PPV revenue falls in Q3. Tempting explanation, but the title also drove subscriptions
       that carried into Q3; its net effect on the Q2->Q3 gap is ~zero. A dead end.

Counterfactual attribution of each cause (re-running with it switched off, 12 seeds) is in
data/story.md - see the PT_DISABLE switches in section 0.

HOW THE SIMULATION WORKS (causal order, so the story falls out of the mechanics)
  1. content_catalog  - 80 titles, Zipf-ish popularity, new-release hype that decays.
  2. marketing_spend  - daily spend per channel -> impressions (CPM) -> clicks (CTR).
  3. users            - signups = clicks x channel CVR (+ organic/referral). Each user gets a
                        hidden 'intent' (engagement) drawn from a channel-specific Beta, and a
                        country 'willingness to pay' (wtp). Neither is stored in the DB.
  4. behaviour        - day-by-day per user: churn hazard -> active today? -> episode demand ->
                        free cap / premium wall -> subscribe / PPV decisions -> renewals.
  5. transactions     - every charge attempt (success AND failed), retries, refunds.
  6. DQ injection     - DQ1 is generated as bot behaviour; DQ2-DQ4 are applied as explicit
                        post-processing steps so a reader can see exactly what was corrupted.
  7. write SQLite + indexes; write ground_truth.json (answer-key numbers using the hidden flags).

Pre-window history: the app launched 2025-10-01. Users are simulated from launch so that the
April 2026 starting state (who is subscribed, who already churned) is realistic, but only
events dated 2026-04-01 or later are written to the activity tables.
"""

import bisect
import json
import math
import os
import random
import sqlite3
from datetime import date, timedelta

# =============================================================================
# 0. CONFIG - every planted effect is a named parameter here
# =============================================================================
SEED = int(os.environ.get("PT_SEED", 12))   # env override used only for robustness sweeps
R = random.Random(SEED)

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("PT_DB", os.path.join(HERE, "pockettoons.db"))
GROUND_TRUTH_PATH = os.path.join(os.path.dirname(DB_PATH),
                                 os.path.basename(DB_PATH).replace("pockettoons", "ground_truth").replace(".db", ".json"))

LAUNCH = date(2025, 10, 1)        # app went live; simulation starts here
DATA_START = date(2026, 4, 1)     # first date written to activity tables
DATA_END = date(2026, 9, 30)      # last date written (end of Q3)
N_DAYS = (DATA_END - LAUNCH).days + 1


def d2i(d):
    return (d - LAUNCH).days


def i2s(i):
    return (LAUNCH + timedelta(days=i)).isoformat()


DS, DE = d2i(DATA_START), d2i(DATA_END)

# --- Event dates ---------------------------------------------------------------
HIT_RELEASE = d2i(date(2026, 5, 22))         # RH1: premium hit title released
GROWTH_PUSH = d2i(date(2026, 7, 1))          # RC1 + RC2 start
AFFILIATE_LAUNCH = d2i(date(2026, 7, 10))    # DQ1 start
PROCESSOR_MIGRATION = d2i(date(2026, 8, 1))  # RC3 + DQ2 + DQ3 start

# --- Pricing -------------------------------------------------------------------
SUB_PRICE = 9.99
PPV_PRICE = 1.99
PPV_PRICE_HIT = 2.99
FREE_LIMIT_OLD, FREE_LIMIT_NEW = 5, 8        # RC2

# --- Countries: region, willingness-to-pay multiplier, platform mix (ios, android, web) ---
COUNTRIES = {
    "US": ("NA",    1.00, (0.55, 0.30, 0.15)),
    "ID": ("SEA",   0.35, (0.08, 0.88, 0.04)),
    "PH": ("SEA",   0.45, (0.12, 0.83, 0.05)),
    "VN": ("SEA",   0.30, (0.08, 0.88, 0.04)),
    "TH": ("SEA",   0.45, (0.15, 0.80, 0.05)),
    "BR": ("LATAM", 0.95, (0.15, 0.75, 0.10)),
    "MX": ("LATAM", 0.90, (0.20, 0.70, 0.10)),
    "CO": ("LATAM", 0.75, (0.15, 0.75, 0.10)),
}

# Probability a user with a failed local payment falls back to a credit card
CARD_FALLBACK = {"NA": 0.60, "SEA": 0.20, "LATAM": 0.25}

# --- Acquisition channels ----------------------------------------------------------
# spend = $/day (before Jul 1, from Jul 1). Signups/day = spend / CPM * 1000 * CTR * CVR.
# intent = Beta(a, b) for the hidden engagement trait. mix = country distribution.
PAID_CHANNELS = {
    "google_search": dict(spend=(55, 8), cpm=12.0, ctr=0.050, cvr=0.040, intent=(5.0, 2.5),
                          mix={"US": .72, "BR": .07, "MX": .07, "PH": .05, "ID": .04, "TH": .03, "CO": .02}),
    "meta_ads":      dict(spend=(40, 18), cpm=4.0, ctr=0.012, cvr=0.067, intent=(3.0, 3.5),
                          mix={"US": .43, "BR": .15, "MX": .12, "PH": .09, "ID": .08, "TH": .06, "VN": .04, "CO": .03}),
    "tiktok_ads":    dict(spend=(12.5, 30), cpm=1.25, ctr=0.016, cvr=0.039, intent=(1.3, 5.0),
                          mix={"ID": .22, "PH": .18, "BR": .17, "MX": .13, "VN": .10, "TH": .08, "CO": .06, "US": .06}),
    "influencer":    dict(spend=(5, 13), cpm=1.5, ctr=0.009, cvr=0.055, intent=(1.8, 4.5),
                          mix={"BR": .25, "ID": .20, "PH": .17, "MX": .15, "TH": .08, "VN": .07, "CO": .08}),
}
# DQ1: cost-per-install affiliate network, launched mid-Q3. Mostly bots.
AFFILIATE = dict(installs_per_day=18, cpi=0.25, click_to_install=0.30, bot_share=0.80,
                 intent=(1.1, 6.0), mix={"ID": .45, "PH": .35, "VN": .20})

# Unpaid channels: signups/day at DATA_START, growing linearly to `end` at DATA_END.
ORGANIC = dict(start=18.0, end=20.0, intent=(3.5, 3.0),
               mix={"US": .38, "BR": .15, "MX": .10, "PH": .10, "ID": .09, "TH": .07, "VN": .06, "CO": .05})
REFERRAL = dict(start=3.0, end=3.5, intent=(4.0, 2.5),
                mix={"US": .45, "BR": .12, "MX": .10, "PH": .10, "ID": .09, "TH": .06, "VN": .04, "CO": .04})
# Pre-window signups/day (launch to Mar 31) = STEADY + BURST * exp(-day / BURST_DAYS):
# a launch-marketing burst that settles to a steady level, using a Q2-like channel mix.
PRE_WINDOW = dict(steady=45.0, burst=75.0, burst_days=30.0)

# --- Behaviour -------------------------------------------------------------------
P_ACTIVE_BASE, P_ACTIVE_INTENT, P_ACTIVE_SUB_BONUS = 0.08, 0.22, 0.15
HAZARD_EARLY = (0.015, 0.12)      # daily churn hazard right after signup: a + b*(1-intent)
HAZARD_LATE = (0.0012, 0.010)     # long-run daily hazard:                 a + b*(1-intent)
HAZARD_DECAY_DAYS = 10
HAZARD_SUBSCRIBED = 0.003        # subscribers rarely "leave the app" (they cancel at renewal)
CAP_FRUSTRATION_CHURN = 0.02     # chance a free user who hits the cap and doesn't pay gives up
DEMAND_MEAN = (1.2, 4.0)         # episodes wanted per active day ~ Geometric(mean a + b*intent)
SUB_DEMAND_BONUS = 1.0

P_SUB_AT_CAP = 0.085              # x intent^1.5 x wtp  (the main conversion moment - RC2)
P_SUB_AT_PREMIUM_WALL = 0.025    # x intent x wtp
P_PPV_AT_PREMIUM_WALL = 0.05     # x intent x wtp  (still has free episodes left today)
P_PPV_AT_CAP = 0.10              # x intent x wtp  (out of free episodes -> buys a premium episode)
P_PPV_HIT_MULTIPLIER = 2.5       # fans of the hit title buy PPV more readily (RH1)
P_SUB_BASELINE_DAILY = 0.0015    # x intent x wtp
P_RESUB_FACTOR = 0.5             # past subscribers who lapsed are half as likely to come back
VOL_CHURN = (0.085, 0.12)         # monthly voluntary churn at renewal: a + b*(1-intent)
REFUND_FIRST, REFUND_RENEWAL = 0.04, 0.015

# --- Payments ---------------------------------------------------------------------
LOCAL_METHODS = {"pix", "oxxo", "pse"}
BASE_FAIL = {"apple_iap": .03, "google_play": .04, "card": .07, "paypal": .04,
             "ewallet": .08, "pix": .06, "oxxo": .07, "pse": .07}
RETRY_FAIL = 0.45                        # P(retry fails | previous attempt failed), normal
MIGRATED_FAIL, MIGRATED_RETRY_FAIL = 0.60, 0.90   # RC3: local methods from Aug 1
BRL_PRICE = {9.99: 49.90, 1.99: 9.90, 2.99: 14.90}  # DQ2: what the buggy processor writes

# --- Counterfactual switches (answer key only) --------------------------------------
# PT_DISABLE=rc1,rc2,rc3,dq1,rh1 re-runs the world with those causes switched off, which is
# how data/story.md attributes the revenue gap to each cause. Never set for the real DB.
_DISABLE = set(filter(None, os.environ.get("PT_DISABLE", "").split(",")))
if "rc1" in _DISABLE:                      # keep the Q2 budget split in Q3
    for _cfg in PAID_CHANNELS.values():
        _cfg["spend"] = (_cfg["spend"][0], _cfg["spend"][0])
if "rc2" in _DISABLE:                      # keep the free limit at 5
    FREE_LIMIT_NEW = FREE_LIMIT_OLD
if "rc3" in _DISABLE:                      # no processor migration (also removes DQ2/DQ3)
    PROCESSOR_MIGRATION = N_DAYS + 30
if "dq1" in _DISABLE:                      # no affiliate network
    AFFILIATE["installs_per_day"] = 0
if "rh1" in _DISABLE:                      # the hit title is never released
    HIT_RELEASE = N_DAYS + 30

# =============================================================================
# 1. CONTENT CATALOG
# =============================================================================
GENRES = ["action", "fantasy", "isekai", "romance", "comedy",
          "slice_of_life", "horror", "sports", "mecha", "mystery"]
GENRE_W = [18, 14, 12, 12, 10, 9, 7, 6, 5, 7]
ADJ = ["Silent", "Crimson", "Hollow", "Neon", "Eternal", "Paper", "Iron", "Velvet", "Last",
       "Shattered", "Midnight", "Golden", "Wandering", "Frozen", "Burning", "Hidden",
       "Lunar", "Distant", "Little", "Seventh", "Azure", "Restless", "Copper", "Gentle"]
NOUN = ["Lantern", "Blade", "Garden", "Signal", "Academy", "Tides", "Kingdom", "Orbit",
        "Requiem", "Harbor", "Cipher", "Bloom", "Frontier", "Echo", "Covenant", "Rooftop",
        "Spiral", "Archive", "Summit", "Canvas", "Circuit", "Festival", "Shrine", "Voyage"]


class Title:
    __slots__ = ("cid", "name", "genre", "eps", "release", "tier", "dur", "pop", "hype", "hype_days")


def build_catalog():
    cat, used = [], set()
    # 30 titles in the launch library, 20 added before the data window, 30 added during it.
    releases = sorted([0] * 30 + [R.randint(1, DS - 1) for _ in range(20)] +
                      [R.randint(DS, DE - 5) for _ in range(30)])
    for i, rel in enumerate(releases):
        t = Title()
        t.cid = i + 1
        while True:
            name = f"{R.choice(ADJ)} {R.choice(NOUN)}"
            if name not in used and name != "Crimson Requiem":
                used.add(name)
                break
        t.name = name
        t.genre = R.choices(GENRES, GENRE_W)[0]
        t.eps = R.choice([12, 12, 12, 13, 24, 24, 25, 26, 36, 48])
        t.release = rel
        t.tier = "premium" if R.random() < 0.25 else "free"
        t.dur = R.randint(420, 720) if R.random() < 0.15 else R.randint(1320, 1500)
        t.pop = math.exp(R.gauss(0, 0.8))
        t.hype, t.hype_days = 3.0, 30.0
        cat.append(t)
    # RH1: the planted premium hit
    hit = Title()
    hit.cid, hit.name, hit.genre, hit.eps = len(cat) + 1, "Crimson Requiem", "action", 24
    hit.release, hit.tier, hit.dur = HIT_RELEASE, "premium", 1440
    hit.pop, hit.hype, hit.hype_days = 2.0, 12.0, 10.0
    cat.append(hit)
    return cat


CATALOG = build_catalog()
HIT_CID = CATALOG[-1].cid

# Daily cumulative popularity weights -> fast weighted sampling with bisect.
CUM = []
for d in range(N_DAYS):
    acc, row = 0.0, []
    for t in CATALOG:
        if t.release <= d:
            age = d - t.release
            acc += t.pop * (1.0 + t.hype * math.exp(-age / t.hype_days))
        row.append(acc)
    CUM.append(row)


def pick_title(d, favs, free_only=False, tier=None):
    """Popularity-weighted pick, biased toward the user's two favourite genres."""
    tier = "free" if free_only else tier
    cum = CUM[d]
    total = cum[-1]
    t = None
    for _ in range(20):
        t = CATALOG[bisect.bisect_right(cum, R.random() * total)]
        if tier and t.tier != tier:
            continue
        if t.genre in favs or R.random() < 0.35:
            return t
    return t if (t and (not tier or t.tier == tier)) else None


# =============================================================================
# 2. MARKETING SPEND  ->  signups per paid channel per day
# =============================================================================
def weekday_factor(i):
    return 1.12 if (LAUNCH + timedelta(days=i)).weekday() >= 5 else 0.95


def poisson(lam):
    # Knuth for small lambda, normal approximation for large
    if lam <= 0:
        return 0
    if lam > 30:
        return max(0, int(round(R.gauss(lam, math.sqrt(lam)))))
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= R.random()
        if p <= L:
            return k
        k += 1


marketing_rows = []           # (date, channel, spend, impressions, clicks)
signup_plan = []              # (day_idx, source, is_affiliate)

for d in range(DS, DE + 1):
    for ch, cfg in PAID_CHANNELS.items():
        base = cfg["spend"][0] if d < GROWTH_PUSH else cfg["spend"][1]
        # one-week ramp into the new budget so the change isn't a perfect step
        if GROWTH_PUSH <= d < GROWTH_PUSH + 7:
            w = (d - GROWTH_PUSH + 1) / 7
            base = cfg["spend"][0] * (1 - w) + cfg["spend"][1] * w
        spend = max(0.0, base * weekday_factor(d) * R.uniform(0.85, 1.15))
        cpm = cfg["cpm"] * R.uniform(0.9, 1.1)
        impressions = int(spend / cpm * 1000)
        clicks = int(impressions * cfg["ctr"] * R.uniform(0.9, 1.1))
        signups = poisson(clicks * cfg["cvr"])
        marketing_rows.append((i2s(d), ch, round(spend, 2), impressions, clicks))
        signup_plan += [(d, ch, False)] * signups
    if d >= AFFILIATE_LAUNCH:
        installs = poisson(AFFILIATE["installs_per_day"] * weekday_factor(d))
        clicks = int(installs / AFFILIATE["click_to_install"])
        # affiliate networks report clicks/installs, not impressions -> NULL (real-world gap)
        marketing_rows.append((i2s(d), "affiliate_network", round(installs * AFFILIATE["cpi"], 2), None, clicks))
        signup_plan += [(d, "affiliate_network", True)] * installs
    frac = (d - DS) / (DE - DS)
    for src, cfg in (("organic", ORGANIC), ("referral", REFERRAL)):
        lam = (cfg["start"] + (cfg["end"] - cfg["start"]) * frac) * weekday_factor(d)
        signup_plan += [(d, src, False)] * poisson(lam)

# Pre-window users (Oct 2025 - Mar 2026): Q2-like channel mix, no marketing rows exported.
PRE_MIX = {"organic": 0.38, "google_search": 0.20, "meta_ads": 0.17, "tiktok_ads": 0.14,
           "referral": 0.06, "influencer": 0.05}
for d in range(0, DS):
    lam = PRE_WINDOW["steady"] + PRE_WINDOW["burst"] * math.exp(-d / PRE_WINDOW["burst_days"])
    for _ in range(poisson(lam * weekday_factor(d))):
        signup_plan.append((d, R.choices(list(PRE_MIX), list(PRE_MIX.values()))[0], False))

signup_plan.sort(key=lambda x: x[0])


# =============================================================================
# 3. USERS (with hidden traits)
# =============================================================================
class User:
    __slots__ = ("uid", "signup", "country", "region", "source", "intent", "wtp", "platform",
                 "method", "favs", "is_bot", "spells", "ever_sub")


def pick(mix):
    return R.choices(list(mix), list(mix.values()))[0]


def pay_method(country, platform):
    region = COUNTRIES[country][0]
    if platform == "ios":
        return "apple_iap"
    if platform == "android":
        opts = {"US": {"google_play": .8, "card": .2},
                "BR": {"google_play": .30, "pix": .60, "card": .10},
                "MX": {"google_play": .30, "oxxo": .55, "card": .15},
                "CO": {"google_play": .40, "pse": .45, "card": .15}}.get(
            country, {"google_play": .55, "ewallet": .30, "card": .15})
        return pick(opts)
    opts = {"US": {"card": .7, "paypal": .3}, "BR": {"pix": .7, "card": .3},
            "MX": {"oxxo": .5, "card": .5}, "CO": {"pse": .5, "card": .5}}.get(
        country, {"card": .6, "ewallet": .4} if region == "SEA" else {"card": 1.0})
    return pick(opts)


def channel_cfg(src):
    if src in PAID_CHANNELS:
        return PAID_CHANNELS[src]
    return {"organic": ORGANIC, "referral": REFERRAL, "affiliate_network": AFFILIATE}[src]


users = []
for uid, (d, src, is_aff) in enumerate(signup_plan, start=1):
    cfg = channel_cfg(src)
    u = User()
    u.uid, u.signup, u.source = uid, d, src
    u.country = pick(cfg["mix"])
    u.region, u.wtp, pmix = COUNTRIES[u.country]
    u.platform = R.choices(["ios", "android", "web"], pmix)[0]
    u.is_bot = is_aff and R.random() < AFFILIATE["bot_share"]
    if u.is_bot:
        u.platform = "android"
    u.intent = R.betavariate(*cfg["intent"])
    u.method = pay_method(u.country, u.platform)
    u.favs = set(R.sample(GENRES, 2))
    u.spells = []          # list of [start, end_or_None, end_reason, method_at_end]
    u.ever_sub = False
    users.append(u)

# =============================================================================
# 4-5. BEHAVIOUR + TRANSACTIONS
# =============================================================================
sessions = []      # (user_id, date, duration_sec, platform)
views = []         # (user_id, content_id, episode, date, watch_sec, content_sec, view_type)
txns = []          # (user_id, date, type, amount, method, status)
diag = {"cap_hits": [0, 0], "free_active_days": [0, 0],   # [Q2, Q3] internal diagnostics
        "subs_by_trigger": {}}


def add_txn(u, d, ttype, amount, method, status):
    if DS <= d <= DE:
        txns.append((u.uid, d, ttype, amount, method, status))


def fail_probs(method, d):
    if method in LOCAL_METHODS and d >= PROCESSOR_MIGRATION:
        return MIGRATED_FAIL, MIGRATED_RETRY_FAIL
    return BASE_FAIL[method], RETRY_FAIL


def charge_new(u, d, ttype, amount):
    """User-initiated purchase (new subscription or PPV). The user may retry once, then may
    fall back to a card. Returns True if it eventually succeeds (same day)."""
    p1, pr = fail_probs(u.method, d)
    if R.random() >= p1:
        add_txn(u, d, ttype, amount, u.method, "success")
        return True
    add_txn(u, d, ttype, amount, u.method, "failed")
    if R.random() < 0.45:
        if R.random() >= pr:
            add_txn(u, d, ttype, amount, u.method, "success")
            return True
        add_txn(u, d, ttype, amount, u.method, "failed")
    if u.method not in ("card", "apple_iap") and R.random() < CARD_FALLBACK[u.region]:
        if R.random() >= BASE_FAIL["card"]:
            u.method = "card"
            add_txn(u, d, ttype, amount, "card", "success")
            return True
        add_txn(u, d, ttype, amount, "card", "failed")
    return False


def charge_renewal(u, d):
    """Automatic renewal with dunning retries on d+1 and d+3. Returns (ok, day_resolved)."""
    p1, pr = fail_probs(u.method, d)
    if R.random() >= p1:
        add_txn(u, d, "subscription", SUB_PRICE, u.method, "success")
        return True, d
    add_txn(u, d, "subscription", SUB_PRICE, u.method, "failed")
    for off in (1, 3):
        p1, pr = fail_probs(u.method, d + off)
        if R.random() >= pr:
            add_txn(u, d + off, "subscription", SUB_PRICE, u.method, "success")
            return True, d + off
        add_txn(u, d + off, "subscription", SUB_PRICE, u.method, "failed")
    return False, d + 3


def geometric(mean):
    p = 1.0 / mean
    return 1 + int(math.log(1.0 - R.random()) / math.log(1.0 - p))


def simulate_bot(u):
    """DQ1: fake install. 1-3 near-empty sessions within 3 days, maybe one 'view' of seconds."""
    n = R.choice([1, 1, 1, 2, 2, 3])
    for k in range(n):
        d = u.signup + (0 if k == 0 else R.randint(0, 2))
        if d > DE:
            continue
        sessions.append((u.uid, d, R.randint(2, 45), "android"))
        if k == 0 and R.random() < 0.30:
            t = pick_title(d, u.favs, free_only=True)
            if t:
                views.append((u.uid, t.cid, 1, d, R.randint(3, 25), t.dur, "free"))


def simulate_user(u):
    if u.is_bot:
        simulate_bot(u)
        return
    alive = True
    sub = None                 # dict(start, next, refund_day)
    progress = {}              # cid -> next episode
    current = None             # cid currently being binged
    purchased = set()          # (cid, ep) bought via PPV
    hz_e = HAZARD_EARLY[0] + HAZARD_EARLY[1] * (1 - u.intent)
    hz_l = HAZARD_LATE[0] + HAZARD_LATE[1] * (1 - u.intent)
    p_vol = VOL_CHURN[0] + VOL_CHURN[1] * (1 - u.intent)
    p_act_free = P_ACTIVE_BASE + P_ACTIVE_INTENT * u.intent
    dmean = DEMAND_MEAN[0] + DEMAND_MEAN[1] * u.intent
    pay_mult = u.intent * u.wtp

    def start_sub(d, trigger):
        nonlocal sub
        ok = charge_new(u, d, "subscription", SUB_PRICE)
        if ok and DS <= d <= DE:
            key = ("Q2" if d < GROWTH_PUSH else "Q3") + "_" + trigger
            diag["subs_by_trigger"][key] = diag["subs_by_trigger"].get(key, 0) + 1
        if ok:
            sub = {"start": d, "next": d + 30, "refund_day": None}
            if R.random() < REFUND_FIRST:
                sub["refund_day"] = d + R.randint(1, 6)
            u.spells.append([d, None, None, u.method])
            u.ever_sub = True
        return ok

    def end_sub(d, reason):
        nonlocal sub
        u.spells[-1][1], u.spells[-1][2], u.spells[-1][3] = d, reason, u.method
        sub = None

    def resub_factor():
        return P_RESUB_FACTOR if u.ever_sub else 1.0

    for d in range(u.signup, N_DAYS):
        # ---- subscription lifecycle -------------------------------------------------
        if sub is not None:
            if sub["refund_day"] == d:
                add_txn(u, d, "refund", -SUB_PRICE, u.method, "success")
                end_sub(d, "refund")
            elif sub["next"] == d:
                if not alive or R.random() < p_vol:
                    end_sub(d, "voluntary")
                else:
                    ok, dd = charge_renewal(u, d)
                    if ok:
                        sub["next"] = dd + 30
                        if R.random() < REFUND_RENEWAL:
                            sub["refund_day"] = dd + R.randint(1, 6)
                    else:
                        end_sub(dd, "involuntary")
        if not alive:
            if sub is None:
                break
            continue

        # ---- churn hazard (leave the app for good) ------------------------------------
        age = d - u.signup
        if sub is not None:
            h = HAZARD_SUBSCRIBED
        else:
            h = hz_l + (hz_e - hz_l) * math.exp(-age / HAZARD_DECAY_DAYS)
        if R.random() < h:
            alive = False
            continue

        # ---- active today? ------------------------------------------------------------
        p_act = p_act_free + (P_ACTIVE_SUB_BONUS if sub is not None else 0.0)
        if age > 0 and R.random() > p_act:
            continue

        # tiny baseline chance to subscribe without hitting any wall
        if sub is None and R.random() < P_SUB_BASELINE_DAILY * pay_mult * resub_factor():
            start_sub(d, "baseline")

        limit = FREE_LIMIT_OLD if d < GROWTH_PUSH else FREE_LIMIT_NEW
        was_free = sub is None
        demand = geometric(dmean + (SUB_DEMAND_BONUS if sub is not None else 0.0))
        free_used, today, hit_cap = 0, [], False
        q = 0 if d < GROWTH_PUSH else 1
        k = 0
        while k < demand:
            # choose what to watch: keep bingeing the current series most of the time
            if current is not None and R.random() < 0.75 and progress.get(current, 1) <= CATALOG[current - 1].eps:
                t = CATALOG[current - 1]
            else:
                t = pick_title(d, u.favs)
                if t is None:
                    break
                current = t.cid
            ep = progress.get(t.cid, 1)
            if ep > t.eps:                       # finished this series; pick another
                current = None
                k += 1
                continue

            if sub is not None:
                vtype = "sub"
            elif t.tier == "premium":
                if (t.cid, ep) in purchased:
                    vtype = "ppv"
                else:
                    r = R.random()
                    p_s = P_SUB_AT_PREMIUM_WALL * pay_mult * resub_factor()
                    p_p = P_PPV_AT_PREMIUM_WALL * pay_mult * (P_PPV_HIT_MULTIPLIER if t.cid == HIT_CID else 1.0)
                    if r < p_s and start_sub(d, "premium_wall"):
                        vtype = "sub"
                    elif r < p_s + p_p and charge_new(u, d, "ppv", PPV_PRICE_HIT if t.cid == HIT_CID else PPV_PRICE):
                        purchased.add((t.cid, ep))
                        vtype = "ppv"
                    else:
                        # declined the premium wall -> fall back to a free title
                        t = pick_title(d, u.favs, free_only=True)
                        if t is None:
                            break
                        current = t.cid
                        ep = progress.get(t.cid, 1)
                        if ep > t.eps:
                            k += 1
                            continue
                        vtype = None
            else:
                vtype = None

            if vtype is None:                    # free-tier episode for a non-subscriber
                if free_used >= limit:
                    hit_cap = True
                    # RC2: the cap is the main monetisation moment - subscribe, buy a premium
                    # episode instead, or stop for the day (and sometimes give up on the app).
                    r = R.random()
                    p_s = P_SUB_AT_CAP * (u.intent ** 1.5) * u.wtp * resub_factor()
                    p_p = P_PPV_AT_CAP * pay_mult
                    if r < p_s and start_sub(d, "cap"):
                        vtype = "sub"
                    else:
                        if p_s <= r < p_s + p_p:
                            pt = pick_title(d, u.favs, tier="premium")
                            if pt is not None:
                                pep = progress.get(pt.cid, 1)
                                price = PPV_PRICE_HIT if pt.cid == HIT_CID else PPV_PRICE
                                if pep <= pt.eps and charge_new(u, d, "ppv", price):
                                    purchased.add((pt.cid, pep))
                                    comp = min(1.0, max(0.05, R.betavariate(6, 1.5)))
                                    today.append((pt.cid, pep, int(pt.dur * comp), pt.dur, "ppv"))
                                    progress[pt.cid] = pep + 1
                        elif R.random() < CAP_FRUSTRATION_CHURN:
                            alive = False
                        break
                else:
                    vtype = "free"
                    free_used += 1

            completion = min(1.0, max(0.05, R.betavariate(6, 1.5)))
            today.append((t.cid, ep, int(t.dur * completion), t.dur, vtype))
            progress[t.cid] = ep + 1
            k += 1

        if DS <= d <= DE and was_free:
            diag["free_active_days"][q] += 1
            diag["cap_hits"][q] += int(hit_cap)

        if not (DS <= d <= DE):
            continue
        # ---- write sessions + views ----------------------------------------------------
        n_sess = 1 + (R.random() < 0.35) + (R.random() < 0.10)
        buckets = [[] for _ in range(n_sess)]
        for v in today:
            buckets[R.randrange(n_sess)].append(v)
        for b in buckets:
            plat = u.platform if R.random() < 0.9 else R.choice(["ios", "android", "web"])
            watch = sum(v[2] for v in b)
            sessions.append((u.uid, d, watch + R.randint(30, 400), plat))
            for (cid, ep, w, dur, vt) in b:
                views.append((u.uid, cid, ep, d, w, dur, vt))


for u in users:
    simulate_user(u)

# =============================================================================
# 6. DATA-QUALITY INJECTION (explicit post-processing so the corruption is visible)
# =============================================================================
# DQ2 - currency bug: the new processor writes pix amounts in BRL into amount_usd.
dq2_rows = 0
for i, (uid, d, ttype, amt, method, status) in enumerate(txns):
    if method == "pix" and d >= PROCESSOR_MIGRATION:
        sign = -1 if amt < 0 else 1
        txns[i] = (uid, d, ttype, sign * BRL_PRICE[round(abs(amt), 2)], method, status)
        dq2_rows += 1


# Snapshot of the users table as of DATA_END.
def user_snapshot(u):
    if not u.spells:
        return "free", None, None
    start, end, reason, method = u.spells[-1]
    if end is None or end > DE:
        return "active", i2s(start), None
    # DQ3 - stale status: no cancel webhook from the new processor for failed renewals.
    if reason == "involuntary" and method in LOCAL_METHODS and end >= PROCESSOR_MIGRATION:
        return "active", i2s(start), None
    return "cancelled", i2s(start), i2s(end)


dq3_users = sum(1 for u in users if u.spells and u.spells[-1][2] == "involuntary"
                and u.spells[-1][3] in LOCAL_METHODS and u.spells[-1][1] is not None
                and PROCESSOR_MIGRATION <= u.spells[-1][1] <= DE)


# DQ4 - legacy web sign-up form (before 2026) stored 'USA' for ~6% of US users.
def country_label(u):
    if u.country == "US" and u.signup < d2i(date(2026, 1, 1)) and R.random() < 0.06:
        return "USA"
    return u.country


# =============================================================================
# 7. WRITE SQLITE
# =============================================================================
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
con = sqlite3.connect(DB_PATH)
cur = con.cursor()
cur.executescript("""
CREATE TABLE content_catalog (
    content_id      INTEGER PRIMARY KEY,
    title           TEXT NOT NULL,
    genre           TEXT NOT NULL,
    total_episodes  INTEGER NOT NULL,
    release_date    TEXT NOT NULL,      -- date the title was added to PocketToons
    content_tier    TEXT NOT NULL       -- 'free' (counts toward daily free limit) | 'premium'
);
CREATE TABLE marketing_spend (
    date         TEXT NOT NULL,
    channel      TEXT NOT NULL,
    spend_usd    REAL NOT NULL,
    impressions  INTEGER,               -- NULL for affiliate_network (reports clicks/installs only)
    clicks       INTEGER
);
CREATE TABLE users (
    user_id              INTEGER PRIMARY KEY,
    signup_date          TEXT NOT NULL,
    country              TEXT NOT NULL,
    acquisition_source   TEXT NOT NULL,
    subscription_status  TEXT NOT NULL, -- snapshot as of 2026-09-30: active | cancelled | free
    subscription_start   TEXT,          -- start of the most recent subscription
    subscription_end     TEXT           -- end of the most recent subscription (NULL if active)
);
CREATE TABLE sessions (
    session_id    INTEGER PRIMARY KEY,
    user_id       INTEGER NOT NULL,
    date          TEXT NOT NULL,
    duration_sec  INTEGER NOT NULL,
    platform      TEXT NOT NULL         -- ios | android | web
);
CREATE TABLE content_views (
    view_id               INTEGER PRIMARY KEY,
    user_id               INTEGER NOT NULL,
    content_id            INTEGER NOT NULL,
    episode_number        INTEGER NOT NULL,
    date                  TEXT NOT NULL,
    watch_duration_sec    INTEGER NOT NULL,
    content_duration_sec  INTEGER NOT NULL,
    view_type             TEXT NOT NULL  -- free | sub | ppv
);
CREATE TABLE transactions (
    txn_id          INTEGER PRIMARY KEY,
    user_id         INTEGER NOT NULL,
    date            TEXT NOT NULL,
    type            TEXT NOT NULL,       -- subscription | ppv | refund
    amount_usd      REAL NOT NULL,       -- refunds are negative
    payment_method  TEXT NOT NULL,
    status          TEXT NOT NULL        -- success | failed (failed attempts are logged too)
);
""")

cur.executemany("INSERT INTO content_catalog VALUES (?,?,?,?,?,?)",
                [(t.cid, t.name, t.genre, t.eps, i2s(t.release), t.tier) for t in CATALOG])
cur.executemany("INSERT INTO marketing_spend VALUES (?,?,?,?,?)", marketing_rows)
cur.executemany("INSERT INTO users VALUES (?,?,?,?,?,?,?)",
                [(u.uid, i2s(u.signup), country_label(u), u.source, *user_snapshot(u)) for u in users])

sessions.sort(key=lambda s: (s[1], s[0]))
cur.executemany("INSERT INTO sessions (user_id, date, duration_sec, platform) VALUES (?,?,?,?)",
                [(s[0], i2s(s[1]), s[2], s[3]) for s in sessions])
views.sort(key=lambda v: (v[3], v[0]))
cur.executemany("INSERT INTO content_views (user_id, content_id, episode_number, date, watch_duration_sec, "
                "content_duration_sec, view_type) VALUES (?,?,?,?,?,?,?)",
                [(v[0], v[1], v[2], i2s(v[3]), v[4], v[5], v[6]) for v in views])
txns.sort(key=lambda t: (t[1], t[0]))
cur.executemany("INSERT INTO transactions (user_id, date, type, amount_usd, payment_method, status) "
                "VALUES (?,?,?,?,?,?)",
                [(t[0], i2s(t[1]), t[2], t[3], t[4], t[5]) for t in txns])

cur.executescript("""
CREATE INDEX ix_sessions_user ON sessions(user_id);
CREATE INDEX ix_sessions_date ON sessions(date);
CREATE INDEX ix_views_user ON content_views(user_id);
CREATE INDEX ix_txn_user ON transactions(user_id);
CREATE INDEX ix_txn_date ON transactions(date);
CREATE INDEX ix_users_signup ON users(signup_date);
""")
con.commit()
con.execute("VACUUM")
con.close()

# =============================================================================
# 8. GROUND TRUTH (uses hidden flags; NOT in the DB - this is the answer key)
# =============================================================================
bot_ids = {u.uid for u in users if u.is_bot}


def month_of(i):
    return i2s(i)[:7]


mau, mau_real = {}, {}
for uid, d, _, _ in sessions:
    m = month_of(d)
    mau.setdefault(m, set()).add(uid)
    if uid not in bot_ids:
        mau_real.setdefault(m, set()).add(uid)


def q_avg(dct, months):
    return sum(len(dct.get(m, ())) for m in months) / len(months)


Q2M, Q3M = ["2026-04", "2026-05", "2026-06"], ["2026-07", "2026-08", "2026-09"]
rev_rep, rev_true = [0.0, 0.0], [0.0, 0.0]
rev_true_month = {}
for uid, d, ttype, amt, method, status in txns:
    if status != "success":
        continue
    q = 0 if d < GROWTH_PUSH else 1
    rev_rep[q] += amt
    true_amt = amt / (BRL_PRICE[9.99] / 9.99) if (method == "pix" and d >= PROCESSOR_MIGRATION) else amt
    rev_true[q] += true_amt
    rev_true_month[month_of(d)] = rev_true_month.get(month_of(d), 0.0) + true_amt

gt = {
    "mau_reported": {"Q2": round(q_avg(mau, Q2M)), "Q3": round(q_avg(mau, Q3M))},
    "mau_excluding_bots": {"Q2": round(q_avg(mau_real, Q2M)), "Q3": round(q_avg(mau_real, Q3M))},
    "net_revenue_reported_usd": {"Q2": round(rev_rep[0], 2), "Q3": round(rev_rep[1], 2)},
    "net_revenue_true_usd": {"Q2": round(rev_true[0], 2), "Q3": round(rev_true[1], 2)},
    "true_revenue_by_month_usd": {m: round(v, 2) for m, v in sorted(rev_true_month.items())},
    "bot_accounts": len(bot_ids),
    "dq2_pix_rows_in_brl": dq2_rows,
    "dq3_stale_active_users": dq3_users,
    "cap_hit_rate_free_active_days": {
        "Q2": round(diag["cap_hits"][0] / max(1, diag["free_active_days"][0]), 4),
        "Q3": round(diag["cap_hits"][1] / max(1, diag["free_active_days"][1]), 4)},
    "new_subs_by_trigger": dict(sorted(diag["subs_by_trigger"].items())),
    "row_counts": {"users": len(users), "sessions": len(sessions), "content_views": len(views),
                   "transactions": len(txns), "marketing_spend": len(marketing_rows),
                   "content_catalog": len(CATALOG)},
}
for k in ("mau_reported", "mau_excluding_bots", "net_revenue_reported_usd", "net_revenue_true_usd"):
    gt[k]["QoQ_change"] = f"{(gt[k]['Q3'] / gt[k]['Q2'] - 1) * 100:+.1f}%"

with open(GROUND_TRUTH_PATH, "w") as f:
    json.dump(gt, f, indent=2)

print(json.dumps(gt, indent=2))
print(f"\nWrote {DB_PATH} ({os.path.getsize(DB_PATH) / 1e6:.1f} MB)")
