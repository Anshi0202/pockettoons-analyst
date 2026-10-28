#!/usr/bin/env python3
"""
validate.py - checks that the planted story is present AND discoverable with SQL alone.

    python data/validate.py

Every number here comes from plain SQL against pockettoons.db (no hidden generator flags),
so it doubles as the reference answer for the eval set and for the board analysis.
Compare with data/ground_truth.json, which uses the generator's hidden flags.
"""
import os
import sqlite3

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pockettoons.db")
con = sqlite3.connect(DB)

Q = """CASE WHEN {col} < '2026-07-01' THEN 'Q2' ELSE 'Q3' END"""
BRL_RATE = 49.90 / 9.99

# Heuristic bot definition an analyst could arrive at from the data (DQ1):
# affiliate users whose total session time is under 2 minutes and who were only seen
# in the first 3 days after signup.
BOTS = """
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
    widths = [max(len(str(c)), *(len(f'{r[i]}') for r in rows)) for i, c in enumerate(cols)] if rows else [len(c) for c in cols]
    print("  ".join(str(c).ljust(w) for c, w in zip(cols, widths)))
    for r in rows:
        print("  ".join(f"{v}".ljust(w) for v, w in zip(r, widths)))
    return rows


# ---------------------------------------------------------------- headline
run("H1  MAU by month (reported vs excluding heuristic bots)", f"""
WITH bots AS ({BOTS})
SELECT substr(date,1,7) AS month,
       COUNT(DISTINCT user_id) AS mau_reported,
       COUNT(DISTINCT CASE WHEN user_id NOT IN (SELECT user_id FROM bots) THEN user_id END) AS mau_ex_bots
FROM sessions GROUP BY 1 ORDER BY 1""")

run("H2  Quarterly avg MAU", f"""
WITH bots AS ({BOTS}),
m AS (SELECT substr(date,1,7) AS month,
             COUNT(DISTINCT user_id) AS mau,
             COUNT(DISTINCT CASE WHEN user_id NOT IN (SELECT user_id FROM bots) THEN user_id END) AS mau_real
      FROM sessions GROUP BY 1)
SELECT CASE WHEN month < '2026-07' THEN 'Q2' ELSE 'Q3' END AS qtr,
       ROUND(AVG(mau)) AS avg_mau, ROUND(AVG(mau_real)) AS avg_mau_ex_bots
FROM m GROUP BY 1""")

run("H3  Net revenue by month: reported vs corrected for BRL bug", f"""
SELECT substr(date,1,7) AS month,
       ROUND(SUM(amount_usd),0) AS reported,
       ROUND(SUM(CASE WHEN payment_method='pix' AND date>='2026-08-01'
                      THEN amount_usd/{BRL_RATE} ELSE amount_usd END),0) AS corrected,
       ROUND(SUM(CASE WHEN type='subscription' THEN amount_usd END),0) AS sub_rep,
       ROUND(SUM(CASE WHEN type='ppv' THEN amount_usd END),0) AS ppv_rep,
       ROUND(SUM(CASE WHEN type='refund' THEN amount_usd END),0) AS refunds
FROM transactions WHERE status='success' GROUP BY 1 ORDER BY 1""")

run("H4  Quarterly net revenue", f"""
SELECT {Q.format(col='date')} AS qtr,
       ROUND(SUM(amount_usd),0) AS reported,
       ROUND(SUM(CASE WHEN payment_method='pix' AND date>='2026-08-01'
                      THEN amount_usd/{BRL_RATE} ELSE amount_usd END),0) AS corrected
FROM transactions WHERE status='success' GROUP BY 1""")

# ---------------------------------------------------------------- RC1
run("RC1a Signups by month and source", """
SELECT substr(signup_date,1,7) AS month, acquisition_source AS src, COUNT(*) AS signups
FROM users WHERE signup_date >= '2026-04-01' GROUP BY 1,2 ORDER BY 1,2""")

run("RC1b Spend & CAC by quarter and channel", f"""
WITH s AS (SELECT {Q.format(col='date')} AS qtr, channel, SUM(spend_usd) AS spend FROM marketing_spend GROUP BY 1,2),
     n AS (SELECT {Q.format(col='signup_date')} AS qtr, acquisition_source AS channel, COUNT(*) AS signups
           FROM users WHERE signup_date >= '2026-04-01' GROUP BY 1,2)
SELECT s.qtr, s.channel, ROUND(s.spend) AS spend, n.signups, ROUND(s.spend*1.0/n.signups,2) AS cac
FROM s JOIN n USING (qtr, channel) ORDER BY 1,2""")

run("RC1c 30-day free->paid conversion by signup quarter and source", f"""
WITH first_sub AS (SELECT user_id, MIN(date) AS d FROM transactions
                   WHERE type='subscription' AND status='success' GROUP BY 1)
SELECT {Q.format(col='u.signup_date')} AS cohort, u.acquisition_source AS src, COUNT(*) AS users,
       ROUND(100.0*SUM(CASE WHEN julianday(f.d)-julianday(u.signup_date) <= 30 THEN 1 ELSE 0 END)/COUNT(*),2) AS conv30_pct
FROM users u LEFT JOIN first_sub f USING (user_id)
WHERE u.signup_date BETWEEN '2026-04-01' AND '2026-08-31'
GROUP BY 1,2 ORDER BY 2,1""")

run("RC1d 30-day conversion by signup quarter and region", f"""
WITH first_sub AS (SELECT user_id, MIN(date) AS d FROM transactions
                   WHERE type='subscription' AND status='success' GROUP BY 1)
SELECT {Q.format(col='u.signup_date')} AS cohort,
       CASE WHEN u.country IN ('US','USA') THEN 'US' WHEN u.country IN ('BR','MX','CO') THEN 'LATAM' ELSE 'SEA' END AS region,
       COUNT(*) AS users,
       ROUND(100.0*SUM(CASE WHEN julianday(f.d)-julianday(u.signup_date) <= 30 THEN 1 ELSE 0 END)/COUNT(*),2) AS conv30_pct
FROM users u LEFT JOIN first_sub f USING (user_id)
WHERE u.signup_date BETWEEN '2026-04-01' AND '2026-08-31' AND u.acquisition_source <> 'affiliate_network'
GROUP BY 1,2 ORDER BY 2,1""")

run("RC1e Channel economics: 60-day corrected revenue per signup vs CAC (Apr-May vs Jul cohorts)", f"""
WITH cohort AS (
  SELECT user_id, acquisition_source AS channel, signup_date,
         CASE WHEN signup_date < '2026-06-01' THEN 'Apr-May' ELSE 'Jul' END AS cohort
  FROM users WHERE (signup_date BETWEEN '2026-04-01' AND '2026-05-31')
                OR (signup_date BETWEEN '2026-07-01' AND '2026-07-31')),
rev AS (
  SELECT c.user_id, SUM(CASE WHEN t.payment_method='pix' AND t.date>='2026-08-01'
                             THEN t.amount_usd/{BRL_RATE} ELSE t.amount_usd END) AS rev60
  FROM cohort c JOIN transactions t ON t.user_id=c.user_id AND t.status='success'
   AND julianday(t.date)-julianday(c.signup_date) BETWEEN 0 AND 60
  GROUP BY 1),
spend AS (
  SELECT channel, CASE WHEN date < '2026-06-01' THEN 'Apr-May' ELSE 'Jul' END AS cohort, SUM(spend_usd) AS spend
  FROM marketing_spend WHERE (date BETWEEN '2026-04-01' AND '2026-05-31') OR (date BETWEEN '2026-07-01' AND '2026-07-31')
  GROUP BY 1,2)
SELECT c.cohort, c.channel, COUNT(*) AS signups,
       ROUND(SUM(COALESCE(r.rev60,0))*1.0/COUNT(*),2) AS rev60_per_signup,
       ROUND(s.spend*1.0/COUNT(*),2) AS cac
FROM cohort c LEFT JOIN rev r USING (user_id) LEFT JOIN spend s ON s.channel=c.channel AND s.cohort=c.cohort
GROUP BY 1,2 ORDER BY 2,1""")

# ---------------------------------------------------------------- RC2
run("RC2a Share of free-viewing user-days that hit the daily free limit", """
WITH d AS (SELECT user_id, date, COUNT(*) AS free_eps FROM content_views
           WHERE view_type='free' GROUP BY 1,2)
SELECT substr(date,1,7) AS month, COUNT(*) AS free_user_days,
       ROUND(100.0*AVG(CASE WHEN free_eps >= CASE WHEN date < '2026-07-01' THEN 5 ELSE 8 END THEN 1 ELSE 0 END),1) AS pct_at_limit,
       MAX(free_eps) AS max_free_eps_in_a_day
FROM d GROUP BY 1 ORDER BY 1""")

# Note: April is left-censored (renewals of subscriptions that started before the data window look
# like new starts), so this starts in May - a trap the agent should also respect.
run("RC2b New subscription starts per month, old base vs newer users (May onward)", """
WITH first_in_month AS (
  SELECT t.user_id, substr(t.date,1,7) AS month FROM transactions t
  WHERE t.type='subscription' AND t.status='success'
    AND NOT EXISTS (SELECT 1 FROM transactions p WHERE p.user_id=t.user_id AND p.type='subscription'
                    AND p.status='success' AND p.date < t.date AND julianday(t.date)-julianday(p.date) <= 35)
  GROUP BY 1,2)
SELECT f.month,
       SUM(CASE WHEN u.signup_date < '2026-04-01' THEN 1 ELSE 0 END) AS new_subs_old_base,
       SUM(CASE WHEN u.signup_date >= '2026-04-01' THEN 1 ELSE 0 END) AS new_subs_new_users
FROM first_in_month f JOIN users u USING (user_id) WHERE f.month >= '2026-05' GROUP BY 1 ORDER BY 1""")

run("RC2c Free views per active free user-day", """
SELECT substr(date,1,7) AS month, ROUND(COUNT(*)*1.0/COUNT(DISTINCT user_id||date),2) AS free_eps_per_user_day
FROM content_views WHERE view_type='free' GROUP BY 1 ORDER BY 1""")

# ---------------------------------------------------------------- RC3
run("RC3a Payment failure rate by method group and month", """
SELECT substr(date,1,7) AS month,
       CASE WHEN payment_method IN ('pix','oxxo','pse') THEN 'latam_local' ELSE 'other' END AS grp,
       COUNT(*) AS attempts,
       ROUND(100.0*AVG(CASE WHEN status='failed' THEN 1 ELSE 0 END),1) AS fail_pct
FROM transactions WHERE type IN ('subscription','ppv') GROUP BY 1,2 ORDER BY 2,1""")

run("RC3b Paying subscribers at month end by region (from transactions, not users.status)", """
WITH months(m_end) AS (VALUES ('2026-04-30'),('2026-05-31'),('2026-06-30'),('2026-07-31'),('2026-08-31'),('2026-09-30')),
paid AS (SELECT user_id, date FROM transactions WHERE type='subscription' AND status='success')
SELECT m.m_end,
       CASE WHEN u.country IN ('US','USA') THEN 'US' WHEN u.country IN ('BR','MX','CO') THEN 'LATAM' ELSE 'SEA' END AS region,
       COUNT(DISTINCT p.user_id) AS paying_subs
FROM months m JOIN paid p ON p.date > date(m.m_end,'-30 days') AND p.date <= m.m_end
JOIN users u USING (user_id)
GROUP BY 1,2 ORDER BY 2,1""")

# ---------------------------------------------------------------- DQ
run("DQ1 Heuristic bots vs affiliate signups", f"""
SELECT (SELECT COUNT(*) FROM users WHERE acquisition_source='affiliate_network') AS affiliate_users,
       (SELECT COUNT(*) FROM ({BOTS})) AS heuristic_bots""")

run("DQ2 Subscription amounts that aren't 9.99 (should be none)", """
SELECT payment_method, amount_usd, COUNT(*) AS n, MIN(date) AS first_seen
FROM transactions WHERE type='subscription' AND amount_usd <> 9.99 GROUP BY 1,2""")

run("DQ3 users.status='active' but no successful sub payment in last 35 days", """
SELECT COUNT(*) AS stale_active FROM users u
WHERE subscription_status='active'
  AND NOT EXISTS (SELECT 1 FROM transactions t WHERE t.user_id=u.user_id AND t.type='subscription'
                  AND t.status='success' AND t.date > '2026-08-26')""")

run("DQ4 Country codes", "SELECT country, COUNT(*) AS n FROM users GROUP BY 1 ORDER BY 2 DESC")

# ---------------------------------------------------------------- RH1
run("RH1a PPV revenue by month (transactions)", f"""
SELECT substr(date,1,7) AS month,
       ROUND(SUM(CASE WHEN payment_method='pix' AND date>='2026-08-01' THEN amount_usd/{BRL_RATE} ELSE amount_usd END)) AS ppv_rev_corrected,
       COUNT(*) AS ppv_txns
FROM transactions WHERE type='ppv' AND status='success' GROUP BY 1 ORDER BY 1""")

# transactions have no content_id, so attribute PPV to titles through content_views
run("RH1b PPV episode views by month: the hit title vs everything else", """
SELECT substr(v.date,1,7) AS month,
       SUM(CASE WHEN c.title='Crimson Requiem' THEN 1 ELSE 0 END) AS hit_ppv_views,
       SUM(CASE WHEN c.title<>'Crimson Requiem' THEN 1 ELSE 0 END) AS other_ppv_views
FROM content_views v JOIN content_catalog c USING (content_id)
WHERE v.view_type='ppv' GROUP BY 1 ORDER BY 1""")

run("Sizes", """
SELECT (SELECT COUNT(*) FROM users) users, (SELECT COUNT(*) FROM sessions) sessions,
       (SELECT COUNT(*) FROM content_views) views, (SELECT COUNT(*) FROM transactions) txns""")
