"""Independent SQL check of the numbers in run 2's report (trace 20261029_044042).

Usage (from the project folder):  python investigation/verify_run2.py
Prints each number the report states next to what plain SQL on data/pockettoons.db gives.
"""
import os
import sqlite3
from pathlib import Path

DB = os.path.join(os.path.dirname(__file__), "..", "data", "pockettoons.db")
con = sqlite3.connect(Path(DB).resolve().as_uri() + "?mode=ro", uri=True)


def q(sql):
    return con.execute(sql).fetchall()


def one(sql):
    return q(sql)[0][0]


Q = "CASE WHEN {c} < '2026-07-01' THEN 'Q2' ELSE 'Q3' END"
rows = []


def check(label, claimed, actual, note=""):
    rows.append((label, claimed, actual, note))


# ---- 1. MAU -------------------------------------------------------------------------
um = """CREATE TEMP TABLE um AS SELECT DISTINCT user_id, substr(date,1,7) AS m FROM sessions"""
con.execute(um)
vm = """CREATE TEMP TABLE vm AS SELECT DISTINCT user_id, substr(date,1,7) AS m FROM content_views"""
con.execute(vm)
con.execute("CREATE INDEX ix_um ON um(user_id, m)")
con.execute("CREATE INDEX ix_vm ON vm(user_id, m)")
mau = dict(q("SELECT CASE WHEN m < '2026-07' THEN 'Q2' ELSE 'Q3' END, COUNT(*)/3.0 FROM um GROUP BY 1"))
vmau = dict(q("SELECT CASE WHEN m < '2026-07' THEN 'Q2' ELSE 'Q3' END, COUNT(*)/3.0 FROM vm GROUP BY 1"))
check("Session MAU Q2 -> Q3", "4,449 -> 5,328 (+19.8%)",
      f"{mau['Q2']:,.0f} -> {mau['Q3']:,.0f} ({mau['Q3']/mau['Q2']-1:+.1%})")
check("Content-view MAU Q2 -> Q3", "4,448 -> 5,060 (+13.8%)",
      f"{vmau['Q2']:,.0f} -> {vmau['Q3']:,.0f} ({vmau['Q3']/vmau['Q2']-1:+.1%})")
so = dict(q("""SELECT CASE WHEN um.m < '2026-07' THEN 'Q2' ELSE 'Q3' END, COUNT(*)
               FROM um LEFT JOIN vm ON vm.user_id = um.user_id AND vm.m = um.m
               WHERE vm.user_id IS NULL GROUP BY 1"""))
check("Session-only user-months Q2 / Q3", "2 / 805", f"{so.get('Q2', 0)} / {so.get('Q3', 0)}")

# ---- 2. Revenue ---------------------------------------------------------------------
rev = dict(q(f"SELECT {Q.format(c='date')}, SUM(amount_usd) FROM transactions WHERE status='success' GROUP BY 1"))
check("Net revenue Q2 -> Q3", "$20,795 -> $20,302 (-2.4%)",
      f"${rev['Q2']:,.0f} -> ${rev['Q3']:,.0f} ({rev['Q3']/rev['Q2']-1:+.1%})")
gross = dict(q(f"SELECT {Q.format(c='date')}, SUM(amount_usd) FROM transactions GROUP BY 1"))
check("(trap) all rows incl. failed", "not used", f"${gross['Q2']:,.0f} -> ${gross['Q3']:,.0f}")
uam = dict(q("SELECT CASE WHEN m < '2026-07' THEN 'Q2' ELSE 'Q3' END, COUNT(*) FROM um GROUP BY 1"))
check("Revenue per active user-month", "$1.56 -> $1.27",
      f"${rev['Q2']/uam['Q2']:.2f} -> ${rev['Q3']/uam['Q3']:.2f}")

# payer conversion: active user-months with >=1 successful txn in that month
con.execute("""CREATE TEMP TABLE pm AS SELECT DISTINCT user_id, substr(date,1,7) AS m
               FROM transactions WHERE status='success'""")
con.execute("CREATE INDEX ix_pm ON pm(user_id, m)")
pc = dict(q("""SELECT CASE WHEN um.m < '2026-07' THEN 'Q2' ELSE 'Q3' END,
                      1.0*SUM(pm.user_id IS NOT NULL)/COUNT(*)
               FROM um LEFT JOIN pm ON pm.user_id = um.user_id AND pm.m = um.m GROUP BY 1"""))
check("Active-user payer conversion", "20.5% -> 14.3%", f"{pc['Q2']:.1%} -> {pc['Q3']:.1%}",
      "report's definition: any successful txn, refunds included (purchases only gives 20.4%)")

# ---- 3. Pix anomaly -----------------------------------------------------------------
std = "(9.99, 1.99, 2.99, -9.99, -1.99, -2.99)"
pix = q(f"""SELECT status, COUNT(*), MIN(date) FROM transactions
            WHERE payment_method='pix' AND amount_usd NOT IN {std} GROUP BY status""")
check("Nonstandard pix rows (success / failed)", "49 / 136",
      " / ".join(f"{s}:{n} (first {d})" for s, n, d in pix))
norm = one(f"""SELECT SUM(amount_usd - CASE amount_usd WHEN 49.90 THEN 9.99 WHEN -49.90 THEN -9.99
                                      WHEN 9.90 THEN 2.99 WHEN 14.90 THEN 2.99 ELSE amount_usd END)
             FROM transactions WHERE status='success' AND payment_method='pix'""")
check("Pix normalisation effect on Q3", "-$1,217 -> $19,085 (-8.2%)",
      f"-${norm:,.0f} -> ${rev['Q3']-norm:,.0f} ({(rev['Q3']-norm)/rev['Q2']-1:+.1%})",
      "report prices all odd PPV at $2.99; story.md (true /5 ratio): -$1,232 -> $19,070 (-8.3%)")

# ---- 4. Failure rates ---------------------------------------------------------------
fr = q(f"""SELECT payment_method, {Q.format(c='date')} AS qq, ROUND(100.0*AVG(status='failed'),1)
           FROM transactions WHERE payment_method IN ('pix','oxxo','pse') GROUP BY 1,2 ORDER BY 1,2""")
check("Failure rate pix/oxxo/pse Q2 -> Q3", "6.3/13.5/7.3% -> 56.4/58.9/62.7%",
      "; ".join(f"{m} {qq} {r}%" for m, qq, r in fr))
frm = q("""SELECT substr(date,1,7), ROUND(100.0*AVG(status='failed'),1) FROM transactions
           WHERE payment_method IN ('pix','oxxo','pse') GROUP BY 1""")
check("(not in report) local-method failure by month", "-", ", ".join(f"{m[5:]}:{r}%" for m, r in frm),
      "onset is Aug 1, not Jul 1")
other = q(f"""SELECT {Q.format(c='date')}, ROUND(100.0*AVG(status='failed'),1) FROM transactions
              WHERE payment_method NOT IN ('pix','oxxo','pse') GROUP BY 1""")
check("(not in report) other methods failure", "-", ", ".join(f"{a} {b}%" for a, b in other))
f3 = one("""SELECT COUNT(*) FROM transactions WHERE status='failed' AND date >= '2026-07-01'
            AND payment_method IN ('pix','oxxo','pse') AND type IN ('subscription','ppv')""")
check("Q3 failed sub/PPV attempts on local rails", "257 observed", f"{f3}")

# ---- 5. Acquisition -----------------------------------------------------------------
con.execute("""CREATE TEMP TABLE umx AS SELECT um.*, u.acquisition_source AS src,
               CASE u.country WHEN 'USA' THEN 'US' ELSE u.country END AS ctry,
               CASE WHEN um.m < '2026-07' THEN 'Q2' ELSE 'Q3' END AS qq
               FROM um JOIN users u USING(user_id)""")
src = {(s, qq): n for s, qq, n in q("SELECT src, qq, COUNT(*) FROM umx GROUP BY 1,2")}
srcpay = {(s, qq): n for s, qq, n in q("""SELECT src, qq, COUNT(*) FROM umx JOIN pm
                                          ON pm.user_id = umx.user_id AND pm.m = umx.m GROUP BY 1,2""")}
srcrev = {(s, qq): v for s, qq, v in q(f"""SELECT u.acquisition_source, {Q.format(c='t.date')}, SUM(t.amount_usd)
                                           FROM transactions t JOIN users u USING(user_id)
                                           WHERE t.status='success' GROUP BY 1,2""")}
check("Affiliate Q3: user-months / payer-months / revenue", "1,486 / 2 / $19.98",
      f"{src[('affiliate_network','Q3')]:,} / {srcpay.get(('affiliate_network','Q3'),0)} / "
      f"${srcrev.get(('affiliate_network','Q3'),0):.2f}")
check("TikTok: user-month change / payer-months Q2 -> Q3", "+871 / 38 -> 29",
      f"{src[('tiktok_ads','Q3')]-src[('tiktok_ads','Q2')]:+,} / "
      f"{srcpay[('tiktok_ads','Q2')]} -> {srcpay[('tiktok_ads','Q3')]}")
tot = uam["Q3"] - uam["Q2"]
share = (src[('affiliate_network', 'Q3')] + src[('tiktok_ads', 'Q3')] - src[('tiktok_ads', 'Q2')]) / tot
check("Affiliate + TikTok share of user-month increase", "~89%", f"{share:.1%} of {tot:+,}")
deltas = ", ".join(f"{s} {src.get((s,'Q3'),0)-src.get((s,'Q2'),0):+,}" for s in
                   ["organic", "referral", "google_search", "meta_ads", "tiktok_ads", "influencer", "affiliate_network"])
check("(context) user-month change by source", "-", deltas)
sp = {(c, qq): v for c, qq, v in q(f"SELECT channel, {Q.format(c='date')}, SUM(spend_usd) FROM marketing_spend GROUP BY 1,2")}
check("Spend TikTok / Google Q2 -> Q3", "$1,127 -> $2,707 / $5,008 -> $883",
      f"${sp[('tiktok_ads','Q2')]:,.0f} -> ${sp[('tiktok_ads','Q3')]:,.0f} / "
      f"${sp[('google_search','Q2')]:,.0f} -> ${sp[('google_search','Q3')]:,.0f}")
tsp = {qq: v for qq, v in q(f"SELECT {Q.format(c='date')}, SUM(spend_usd) FROM marketing_spend GROUP BY 1")}
check("(not in report) total paid spend", "-", f"${tsp['Q2']:,.0f} -> ${tsp['Q3']:,.0f} ({tsp['Q3']/tsp['Q2']-1:+.0%})")

ctry = {(c, qq): n for c, qq, n in q("SELECT ctry, qq, COUNT(*) FROM umx GROUP BY 1,2")}
crev = {(c, qq): v for c, qq, v in q(f"""SELECT CASE u.country WHEN 'USA' THEN 'US' ELSE u.country END,
                                         {Q.format(c='t.date')}, SUM(t.amount_usd)
                                         FROM transactions t JOIN users u USING(user_id)
                                         WHERE t.status='success' GROUP BY 1,2""")}
sea = ["ID", "PH", "VN"]
check("ID+PH+VN: user-month change / Q3 revenue / revenue change", "+2,220 / ~$66",
      f"{sum(ctry[(c,'Q3')]-ctry[(c,'Q2')] for c in sea):+,} / ${sum(crev[(c,'Q3')] for c in sea):,.0f} / "
      f"{sum(crev[(c,'Q3')]-crev[(c,'Q2')] for c in sea):+,.0f}")
usrev = dict(q(f"""SELECT {Q.format(c='t.date')}, SUM(t.amount_usd)
                   FROM transactions t JOIN users u USING(user_id)
                   JOIN um ON um.user_id = t.user_id AND um.m = substr(t.date,1,7)
                   WHERE t.status='success' AND u.country IN ('US','USA') GROUP BY 1"""))
check("US (incl. USA): user-month change / revenue change", "-218 / -$564",
      f"{ctry[('US','Q3')]-ctry[('US','Q2')]:+,} / {usrev['Q3']-usrev['Q2']:+,.0f}",
      f"report counts revenue in active user-months only; all US revenue gives "
      f"{crev[('US','Q3')]-crev[('US','Q2')]:+,.0f}")

# ---- 6. Premium content / PPV -------------------------------------------------------
rel = q(f"""SELECT {Q.format(c='release_date')}, COUNT(*), SUM(total_episodes) FROM content_catalog
            WHERE content_tier='premium' AND release_date >= '2026-04-01' GROUP BY 1""")
check("Premium releases Q2 / Q3 (titles, episodes)", "7, 173 / 1, 25", " / ".join(f"{a}: {b}, {c}" for a, b, c in rel))
vw = {(qq, vt, tier): n for qq, vt, tier, n in q(f"""SELECT {Q.format(c='v.date')}, v.view_type, c.content_tier, COUNT(*)
                                                      FROM content_views v JOIN content_catalog c USING(content_id)
                                                      GROUP BY 1,2,3""")}
pp = {qq: vw.get((qq, 'sub', 'premium'), 0) + vw.get((qq, 'ppv', 'premium'), 0) for qq in ("Q2", "Q3")}
fv = {qq: sum(n for (a, vt, _), n in vw.items() if a == qq and vt == 'free') for qq in ("Q2", "Q3")}
ppv = {qq: sum(n for (a, vt, _), n in vw.items() if a == qq and vt == 'ppv') for qq in ("Q2", "Q3")}
check("Paid-premium views Q2 -> Q3", "30,826 -> 25,569 (-17%)", f"{pp['Q2']:,} -> {pp['Q3']:,} ({pp['Q3']/pp['Q2']-1:+.0%})")
check("Free views Q2 -> Q3", "156,554 -> 200,911", f"{fv['Q2']:,} -> {fv['Q3']:,}")
check("PPV views change", "-41.6%", f"{ppv['Q2']:,} -> {ppv['Q3']:,} ({ppv['Q3']/ppv['Q2']-1:+.1%})")
ppvrev = dict(q(f"SELECT {Q.format(c='date')}, SUM(amount_usd) FROM transactions WHERE status='success' AND type='ppv' GROUP BY 1"))
check("Raw PPV sales change", "-$721", f"${ppvrev['Q2']:,.0f} -> ${ppvrev['Q3']:,.0f} ({ppvrev['Q3']-ppvrev['Q2']:+,.0f})")

# ---- 7. Free limit (what the agent didn't check) ------------------------------------
mx = q("""SELECT substr(date,1,7), MAX(n), ROUND(100.0*AVG(n = CASE WHEN date < '2026-07-01' THEN 5 ELSE 8 END),1)
          FROM (SELECT user_id, date, COUNT(*) n FROM content_views WHERE view_type='free' GROUP BY 1,2)
          GROUP BY 1""")
check("(not in report) max free eps per user-day by month; % of free user-days at max",
      "agent: 'no day exceeded 8'", "; ".join(f"{m[5:]}: max {a}, {b}% at max" for m, a, b in mx))
ns = q("""SELECT substr(t.date,1,7), COUNT(DISTINCT t.user_id) FROM transactions t JOIN users u USING(user_id)
          WHERE t.type='subscription' AND t.status='success' AND u.signup_date < '2026-04-01'
            AND NOT EXISTS (SELECT 1 FROM transactions p WHERE p.user_id = t.user_id AND p.type='subscription'
                            AND p.status='success' AND p.date < t.date AND p.date >= date(t.date,'-40 days'))
          GROUP BY 1""")
check("(not in report) new sub starts, pre-April signups, by month", "-", ", ".join(f"{m[5:]}:{n}" for m, n in ns),
      "story.md: 96/94 (May/Jun) -> 47/30/18")

for label, claimed, actual, note in rows:
    print(f"{label}\n    report: {claimed}\n    SQL:    {actual}" + (f"\n    note:   {note}" if note else ""))
