#!/usr/bin/env python3
"""
followup_checks.py - plain-SQL checks behind the figures added to the board deck on 3 Nov 2026.

    python investigation/followup_checks.py > investigation/followup_checks_output.txt

The original deck (29 Oct) used only run 2's findings. On 3 Nov, three things were added:
  1. the free-episode limit change (5 -> 8 on 1 July), which the agent found when asked
     directly (eval question T6, both prompt versions) and in one v2 investigation run;
  2. MAU excluding bot-like accounts (a follow-up to run 2's "805 session-only user-months");
  3. the monthly revenue run-rate (the v2 prompt's monthly view).
Every new number on the deck comes from a query in this file. Pix amounts are re-priced
49.90 -> 9.99, 9.90 -> 1.99, 14.90 -> 2.99 (refunds likewise), so the monthly figures add up
to the deck's Q3 total.

Revenue re-pricing: every unusual Pix amount is about 5x a normal USD price (49.90/9.99,
9.90/1.99 and 14.90/2.99 are all ~5.0), so each is mapped back to that price. Run 2 priced the
$9.90 pay-per-view rows at $2.99, which gave $19,085; this mapping gives $19,070.
"""
import os
import sqlite3

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "pockettoons.db")
con = sqlite3.connect(f"file:{os.path.abspath(DB)}?mode=ro", uri=True)

# Run 2's re-pricing of the unusual Pix amounts (sign kept for refunds).
REPRICED = """CASE WHEN payment_method='pix' AND ABS(amount_usd) IN (49.90, 9.90, 14.90)
                   THEN (CASE ABS(amount_usd) WHEN 49.90 THEN 9.99 WHEN 9.90 THEN 1.99 ELSE 2.99 END)
                        * (CASE WHEN amount_usd < 0 THEN -1 ELSE 1 END)
                   ELSE amount_usd END"""

# Bot-like accounts: affiliate signups with under 2 minutes of total session time,
# never seen more than 3 days after signup.
BOT_LIKE = """
SELECT u.user_id FROM users u JOIN sessions s USING (user_id)
WHERE u.acquisition_source = 'affiliate_network'
GROUP BY u.user_id
HAVING SUM(s.duration_sec) < 120
   AND MAX(julianday(s.date) - julianday(u.signup_date)) <= 3
"""


def run(title, sql):
    cur = con.execute(sql)
    cols = [c[0] for c in cur.description]
    rows = cur.fetchall()
    print(f"\n=== {title} ===")
    widths = [max(len(str(c)), *(len(f"{r[i]}") for r in rows)) if rows else len(c) for i, c in enumerate(cols)]
    print("  ".join(str(c).ljust(w) for c, w in zip(cols, widths)))
    for r in rows:
        print("  ".join(f"{v}".ljust(w) for v, w in zip(r, widths)))
    return rows


# ------------------------------------------------------------------ users
run("U1  Bot-like accounts", f"""
SELECT (SELECT COUNT(*) FROM users WHERE acquisition_source='affiliate_network') AS affiliate_signups,
       (SELECT COUNT(*) FROM ({BOT_LIKE})) AS bot_like,
       (SELECT COUNT(*) FROM transactions WHERE status='success'
          AND user_id IN ({BOT_LIKE})) AS successful_payments_by_bot_like""")

run("U2  MAU by month: all users vs excluding bot-like accounts", f"""
WITH b AS ({BOT_LIKE})
SELECT substr(date,1,7) AS month,
       COUNT(DISTINCT user_id) AS mau,
       COUNT(DISTINCT CASE WHEN user_id NOT IN (SELECT user_id FROM b) THEN user_id END) AS mau_ex_bot_like,
       COUNT(DISTINCT CASE WHEN user_id IN (SELECT user_id FROM b) THEN user_id END) AS bot_like_active
FROM sessions GROUP BY 1 ORDER BY 1""")

run("U3  Quarterly average MAU and growth", f"""
WITH b AS ({BOT_LIKE}),
m AS (SELECT substr(date,1,7) AS month,
             COUNT(DISTINCT user_id) AS mau,
             COUNT(DISTINCT CASE WHEN user_id NOT IN (SELECT user_id FROM b) THEN user_id END) AS mau_real
      FROM sessions GROUP BY 1),
q AS (SELECT CASE WHEN month < '2026-07' THEN 'Q2' ELSE 'Q3' END AS qtr, AVG(mau) AS mau, AVG(mau_real) AS real
      FROM m GROUP BY 1)
SELECT q2.mau AS q2_mau, q3.mau AS q3_mau, ROUND(100*(q3.mau/q2.mau-1),1) AS mau_growth_pct,
       q2.real AS q2_real, q3.real AS q3_real, ROUND(100*(q3.real/q2.real-1),1) AS real_growth_pct
FROM q q2, q q3 WHERE q2.qtr='Q2' AND q3.qtr='Q3'""")

# ------------------------------------------------------------------ revenue run-rate
run("R1  Net revenue by month: as recorded vs Pix re-priced", f"""
SELECT substr(date,1,7) AS month,
       ROUND(SUM(amount_usd),2) AS recorded,
       ROUND(SUM({REPRICED}),2) AS repriced
FROM transactions WHERE status='success' GROUP BY 1 ORDER BY 1""")

run("R2  Quarter totals and September vs June (re-priced)", f"""
WITH m AS (SELECT substr(date,1,7) AS month, SUM(amount_usd) AS rec, SUM({REPRICED}) AS rep
           FROM transactions WHERE status='success' GROUP BY 1)
SELECT ROUND((SELECT SUM(rep) FROM m WHERE month<'2026-07'),2) AS q2_repriced,
       ROUND((SELECT SUM(rep) FROM m WHERE month>='2026-07'),2) AS q3_repriced,
       ROUND(100*((SELECT SUM(rep) FROM m WHERE month>='2026-07')/(SELECT SUM(rep) FROM m WHERE month<'2026-07')-1),1) AS q3_vs_q2_pct,
       ROUND((SELECT rep FROM m WHERE month='2026-06'),2) AS jun,
       ROUND((SELECT rep FROM m WHERE month='2026-09'),2) AS sep,
       ROUND(100*((SELECT rep FROM m WHERE month='2026-09')/(SELECT rep FROM m WHERE month='2026-06')-1),1) AS sep_vs_jun_pct,
       ROUND(100*((SELECT rec FROM m WHERE month='2026-09')/(SELECT rec FROM m WHERE month='2026-06')-1),1) AS sep_vs_jun_recorded_pct""")

# ------------------------------------------------------------------ free limit
run("F1  Free episodes per user-day: maximum and share at that month's maximum", """
WITH d AS (SELECT user_id, date, COUNT(*) AS free_eps FROM content_views
           WHERE view_type='free' GROUP BY 1,2),
mx AS (SELECT substr(date,1,7) AS month, MAX(free_eps) AS max_eps FROM d GROUP BY 1)
SELECT mx.month, mx.max_eps,
       (SELECT COUNT(*) FROM d WHERE substr(d.date,1,7)=mx.month) AS free_user_days,
       ROUND(100.0*(SELECT AVG(CASE WHEN free_eps>=mx.max_eps THEN 1 ELSE 0 END) FROM d
                    WHERE substr(d.date,1,7)=mx.month),1) AS pct_days_at_max
FROM mx ORDER BY 1""")

run("F2  First and last day the maximum was 5 / 8", """
WITH d AS (SELECT date, user_id, COUNT(*) AS n FROM content_views WHERE view_type='free' GROUP BY 1,2),
day AS (SELECT date, MAX(n) AS mx FROM d GROUP BY 1)
SELECT MAX(CASE WHEN mx>5 THEN NULL ELSE date END) AS last_day_max_le_5,
       MIN(CASE WHEN mx>5 THEN date END) AS first_day_above_5,
       (SELECT MAX(mx) FROM day WHERE date<'2026-07-01') AS max_before_jul,
       (SELECT MAX(mx) FROM day WHERE date>='2026-07-01') AS max_from_jul,
       (SELECT MIN(mx) FROM day WHERE date>='2026-07-01') AS min_daily_max_from_jul
FROM day""")

run("F3  Share of free user-days at the limit, by quarter", """
WITH d AS (SELECT user_id, date, COUNT(*) AS n FROM content_views WHERE view_type='free' GROUP BY 1,2)
SELECT CASE WHEN date<'2026-07-01' THEN 'Q2 (limit 5)' ELSE 'Q3 (limit 8)' END AS qtr,
       COUNT(*) AS free_user_days,
       ROUND(100.0*AVG(CASE WHEN n >= CASE WHEN date<'2026-07-01' THEN 5 ELSE 8 END THEN 1 ELSE 0 END),1) AS pct_at_limit
FROM d GROUP BY 1""")

# A "new start" is a successful subscription payment with no successful subscription payment in
# the previous 35 days. April is skipped: renewals of pre-April subscriptions would look new.
run("F4  New subscription starts per month: users who signed up before April vs newer users", """
WITH starts AS (
  SELECT DISTINCT t.user_id, substr(t.date,1,7) AS month FROM transactions t
  WHERE t.type='subscription' AND t.status='success'
    AND NOT EXISTS (SELECT 1 FROM transactions p WHERE p.user_id=t.user_id AND p.type='subscription'
                    AND p.status='success' AND p.date < t.date
                    AND julianday(t.date)-julianday(p.date) <= 35))
SELECT s.month,
       SUM(CASE WHEN u.signup_date < '2026-04-01' THEN 1 ELSE 0 END) AS signed_up_before_april,
       SUM(CASE WHEN u.signup_date >= '2026-04-01' THEN 1 ELSE 0 END) AS signed_up_from_april
FROM starts s JOIN users u USING (user_id) WHERE s.month >= '2026-05' GROUP BY 1 ORDER BY 1""")

run("F5  Payer conversion among users who signed up before April and were active in both quarters", """
WITH act AS (SELECT DISTINCT user_id, CASE WHEN date<'2026-07-01' THEN 'Q2' ELSE 'Q3' END AS q FROM sessions),
both_q AS (SELECT a.user_id FROM act a JOIN users u USING (user_id)
           WHERE u.signup_date < '2026-04-01' GROUP BY 1 HAVING COUNT(DISTINCT q)=2),
paid AS (SELECT DISTINCT user_id, CASE WHEN date<'2026-07-01' THEN 'Q2' ELSE 'Q3' END AS q
         FROM transactions WHERE status='success' AND type IN ('subscription','ppv'))
SELECT (SELECT COUNT(*) FROM both_q) AS users,
       ROUND(100.0*(SELECT COUNT(*) FROM paid WHERE q='Q2' AND user_id IN (SELECT user_id FROM both_q))
             /(SELECT COUNT(*) FROM both_q),2) AS pct_paid_q2,
       ROUND(100.0*(SELECT COUNT(*) FROM paid WHERE q='Q3' AND user_id IN (SELECT user_id FROM both_q))
             /(SELECT COUNT(*) FROM both_q),2) AS pct_paid_q3""")

# ------------------------------------------------------------------ LatAm payments
run("P1  Payment failure rate by month: Pix/Oxxo/PSE vs all other methods", """
SELECT substr(date,1,7) AS month,
       ROUND(100.0*AVG(CASE WHEN payment_method IN ('pix','oxxo','pse') THEN (status='failed') END),1) AS local_latam_fail_pct,
       ROUND(100.0*AVG(CASE WHEN payment_method NOT IN ('pix','oxxo','pse') THEN (status='failed') END),1) AS other_fail_pct
FROM transactions WHERE type IN ('subscription','ppv') GROUP BY 1 ORDER BY 1""")

run("P2  Paying subscribers (paid in the last 30 days), June 30 vs Sept 30, by region", """
WITH paid AS (SELECT user_id, date FROM transactions WHERE type='subscription' AND status='success'),
r AS (SELECT user_id, CASE WHEN country IN ('US','USA') THEN 'US' WHEN country IN ('BR','MX','CO') THEN 'LatAm' ELSE 'SEA' END AS region FROM users)
SELECT r.region,
       COUNT(DISTINCT CASE WHEN p.date > '2026-05-31' AND p.date <= '2026-06-30' THEN p.user_id END) AS jun_30,
       COUNT(DISTINCT CASE WHEN p.date > '2026-08-31' AND p.date <= '2026-09-30' THEN p.user_id END) AS sep_30
FROM paid p JOIN r USING (user_id) GROUP BY 1 ORDER BY 1""")

# ------------------------------------------------------------------ acquisition
run("A1  Spend by channel and quarter", """
SELECT channel,
       ROUND(SUM(CASE WHEN date<'2026-07-01' THEN spend_usd ELSE 0 END),2) AS q2,
       ROUND(SUM(CASE WHEN date>='2026-07-01' THEN spend_usd ELSE 0 END),2) AS q3
FROM marketing_spend GROUP BY 1
UNION ALL
SELECT 'ALL', ROUND(SUM(CASE WHEN date<'2026-07-01' THEN spend_usd ELSE 0 END),2),
       ROUND(SUM(CASE WHEN date>='2026-07-01' THEN spend_usd ELSE 0 END),2) FROM marketing_spend""")

run("A2  Signups by channel and quarter", """
SELECT acquisition_source AS channel,
       SUM(CASE WHEN signup_date BETWEEN '2026-04-01' AND '2026-06-30' THEN 1 ELSE 0 END) AS q2,
       SUM(CASE WHEN signup_date >= '2026-07-01' THEN 1 ELSE 0 END) AS q3
FROM users GROUP BY 1 ORDER BY 1""")

run("A3  Affiliate network: spend vs successful revenue (re-priced)", f"""
SELECT (SELECT ROUND(SUM(spend_usd),2) FROM marketing_spend WHERE channel='affiliate_network') AS spend,
       (SELECT ROUND(SUM({REPRICED}),2) FROM transactions t JOIN users u USING (user_id)
        WHERE t.status='success' AND u.acquisition_source='affiliate_network') AS revenue""")

run("A4  Revenue per signup in the first 60 days vs cost per signup (Apr-May signups; affiliate: Jul)", f"""
WITH c AS (
  SELECT user_id, acquisition_source AS channel, signup_date,
         CASE WHEN signup_date < '2026-06-01' THEN 'Apr-May' ELSE 'Jul' END AS cohort
  FROM users
  WHERE (signup_date BETWEEN '2026-04-01' AND '2026-05-31' AND acquisition_source <> 'affiliate_network')
     OR (signup_date BETWEEN '2026-07-01' AND '2026-07-31' AND acquisition_source = 'affiliate_network')),
r AS (SELECT c.user_id, SUM({REPRICED}) AS rev FROM c JOIN transactions t
        ON t.user_id = c.user_id AND t.status = 'success'
       AND julianday(t.date) - julianday(c.signup_date) BETWEEN 0 AND 60 GROUP BY 1),
s AS (SELECT channel, CASE WHEN date < '2026-06-01' THEN 'Apr-May' ELSE 'Jul' END AS cohort,
             SUM(spend_usd) AS spend FROM marketing_spend
      WHERE date BETWEEN '2026-04-01' AND '2026-05-31' OR date BETWEEN '2026-07-01' AND '2026-07-31'
      GROUP BY 1, 2)
SELECT c.channel, c.cohort, COUNT(*) AS signups,
       ROUND(SUM(COALESCE(r.rev, 0)) / COUNT(*), 2) AS rev60_per_signup,
       ROUND(s.spend / COUNT(*), 2) AS cost_per_signup,
       ROUND(100 * SUM(COALESCE(r.rev, 0)) / s.spend, 0) AS pct_recovered
FROM c LEFT JOIN r USING (user_id) JOIN s ON s.channel = c.channel AND s.cohort = c.cohort
GROUP BY 1, 2 ORDER BY 4 DESC""")

run("Q   Quarter revenue as recorded (for the Pix adjustment)", f"""
SELECT ROUND(SUM(CASE WHEN date>='2026-07-01' THEN amount_usd END),2) AS q3_recorded,
       ROUND(SUM(CASE WHEN date>='2026-07-01' THEN {REPRICED} END),2) AS q3_repriced,
       ROUND(SUM(CASE WHEN date>='2026-07-01' THEN amount_usd - ({REPRICED}) END),2) AS pix_overstatement,
       (SELECT COUNT(*) FROM transactions WHERE status='success' AND payment_method='pix'
          AND ABS(amount_usd) IN (49.90, 9.90, 14.90)) AS repriced_rows
FROM transactions WHERE status='success'""")

# Why the "fewer premium releases" finding was dropped from the deck: pay-per-view purchases
# fell only on days the user had reached the free limit.
run("F6  Successful pay-per-view purchases: on days the user reached the free limit vs other days", """
WITH fd AS (SELECT user_id, date, COUNT(*) AS n FROM content_views WHERE view_type='free' GROUP BY 1,2),
p AS (SELECT user_id, date FROM transactions WHERE type='ppv' AND status='success')
SELECT CASE WHEN p.date<'2026-07-01' THEN 'Q2' ELSE 'Q3' END AS qtr, COUNT(*) AS ppv_purchases,
       SUM(CASE WHEN fd.n >= CASE WHEN p.date<'2026-07-01' THEN 5 ELSE 8 END THEN 1 ELSE 0 END) AS on_limit_days,
       SUM(CASE WHEN fd.n >= CASE WHEN p.date<'2026-07-01' THEN 5 ELSE 8 END THEN 0 ELSE 1 END) AS other_days
FROM p LEFT JOIN fd USING (user_id, date) GROUP BY 1""")
