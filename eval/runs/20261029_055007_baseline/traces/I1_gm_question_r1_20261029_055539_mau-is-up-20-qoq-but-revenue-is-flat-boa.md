# Agent trace

**Question:** MAU is up 20% QoQ but revenue is flat. Board meeting Thursday. Figure out what's happening and what we should do about it.

- Started: 2026-10-29 05:55:39
- Model: `gpt-6-luna`
- Query budget: 40 run_sql calls

---


### Step 1 · get_schema

<details><summary>Schema returned to the model</summary>

```
Database: SQLite file pockettoons.db. Dates are TEXT 'YYYY-MM-DD'.
Column notes after '--' come from the table definitions.

## content_catalog  (81 rows; release_date: 2025-10-01 to 2026-09-23)
CREATE TABLE content_catalog (
    content_id      INTEGER PRIMARY KEY,
    title           TEXT NOT NULL,
    genre           TEXT NOT NULL,
    total_episodes  INTEGER NOT NULL,
    release_date    TEXT NOT NULL,      -- date the title was added to PocketToons
    content_tier    TEXT NOT NULL       -- 'free' (counts toward daily free limit) | 'premium'
)

## content_views  (564,780 rows; date: 2026-04-01 to 2026-09-30)
CREATE TABLE content_views (
    view_id               INTEGER PRIMARY KEY,
    user_id               INTEGER NOT NULL,
    content_id            INTEGER NOT NULL,
    episode_number        INTEGER NOT NULL,
    date                  TEXT NOT NULL,
    watch_duration_sec    INTEGER NOT NULL,
    content_duration_sec  INTEGER NOT NULL,
    view_type             TEXT NOT NULL  -- free | sub | ppv
)

## marketing_spend  (815 rows; date: 2026-04-01 to 2026-09-30)
CREATE TABLE marketing_spend (
    date         TEXT NOT NULL,
    channel      TEXT NOT NULL,
    spend_usd    REAL NOT NULL,
    impressions  INTEGER,               -- NULL for affiliate_network (reports clicks/installs only)
    clicks       INTEGER
)

## sessions  (232,354 rows; date: 2026-04-01 to 2026-09-30)
CREATE TABLE sessions (
    session_id    INTEGER PRIMARY KEY,
    user_id       INTEGER NOT NULL,
    date          TEXT NOT NULL,
    duration_sec  INTEGER NOT NULL,
    platform      TEXT NOT NULL         -- ios | android | web
)

## transactions  (5,965 rows; date: 2026-04-01 to 2026-09-30)
CREATE TABLE transactions (
    txn_id          INTEGER PRIMARY KEY,
    user_id         INTEGER NOT NULL,
    date            TEXT NOT NULL,
    type            TEXT NOT NULL,       -- subscription | ppv | refund
    amount_usd      REAL NOT NULL,       -- refunds are negative
    payment_method  TEXT NOT NULL,
    status          TEXT NOT NULL        -- success | failed (failed attempts are logged too)
)

## users  (20,708 rows; signup_date: 2025-10-01 to 2026-09-30)
CREATE TABLE users (
    user_id              INTEGER PRIMARY KEY,
    signup_date          TEXT NOT NULL,
    country              TEXT NOT NULL,
    acquisition_source   TEXT NOT NULL,
    subscription_status  TEXT NOT NULL, -- snapshot as of 2026-09-30: active | cancelled | free
    subscription_start   TEXT,          -- start of the most recent subscription
    subscription_end     TEXT           -- end of the most recent subscription (NULL if active)
)
```
</details>


### Step 2 · run_sql (1/40, 1983 ms, ok)

**Purpose:** Establish monthly session-based MAU, revenue and payer/transaction components to verify the stated QoQ pattern and identify its timing.

```sql
WITH m AS (SELECT substr(s.date,1,7) month, COUNT(DISTINCT s.user_id) mau, COUNT(*) sessions, (SELECT COUNT(DISTINCT v.user_id) FROM content_views v WHERE substr(v.date,1,7)=substr(s.date,1,7)) view_users, (SELECT SUM(CASE WHEN t.status='success' THEN t.amount_usd ELSE 0 END) FROM transactions t WHERE substr(t.date,1,7)=substr(s.date,1,7)) net_revenue, (SELECT SUM(CASE WHEN t.status='success' AND t.amount_usd>0 THEN t.amount_usd ELSE 0 END) FROM transactions t WHERE substr(t.date,1,7)=substr(s.date,1,7)) positive_revenue, (SELECT SUM(CASE WHEN t.status='success' AND t.amount_usd<0 THEN t.amount_usd ELSE 0 END) FROM transactions t WHERE substr(t.date,1,7)=substr(s.date,1,7)) refunds, (SELECT COUNT(DISTINCT t.user_id) FROM transactions t WHERE substr(t.date,1,7)=substr(s.date,1,7) AND t.status='success' AND t.amount_usd>0) paying_users, (SELECT COUNT(*) FROM transactions t WHERE substr(t.date,1,7)=substr(s.date,1,7) AND t.status='success') successful_txns, (SELECT COUNT(*) FROM transactions t WHERE substr(t.date,1,7)=substr(s.date,1,7) AND t.status='failed') failed_txns FROM sessions s GROUP BY substr(s.date,1,7)) SELECT * FROM m ORDER BY month
```

6 rows (1983 ms)

| month | mau | sessions | view_users | net_revenue | positive_revenue | refunds | paying_users | successful_txns | failed_txns |
|---|---|---|---|---|---|---|---|---|---|
| 2026-04 | 4243 | 34001 | 4243 | 6335.32 | 6475.18 | -139.86 | 837 | 896 | 54 |
| 2026-05 | 4510 | 37341 | 4509 | 7007.56 | 7127.44 | -119.88 | 899 | 968 | 60 |
| 2026-06 | 4594 | 38120 | 4593 | 7451.74 | 7671.52 | -219.78 | 990 | 1070 | 61 |
| 2026-07 | 5123 | 40963 | 4915 | 7336.12 | 7426.03 | -89.91 | 850 | 906 | 66 |
| 2026-08 | 5389 | 41677 | 5087 | 7053.84 | 7253.64 | -199.8 | 753 | 813 | 226 |
| 2026-09 | 5473 | 40252 | 5178 | 5912.47 | 6112.17 | -199.7 | 687 | 715 | 130 |

_run_sql budget: 1/40 used_


### Step 3 · update_hypotheses

| # | Hypothesis | Status | Evidence |
|---|---|---|---|
| 1 | Revenue per active user fell because the expanding audience converted to payers less often or spent less per payer. | **open** | Session MAU averages 4,449 in Apr–Jun and 5,328 in Jul–Sep (+19.8%); net successful transaction revenue is $20,794.62 vs $20,302.43 (-2.4%). |
| 2 | A payment-processing or checkout issue drove down successful revenue, especially in August and September. | **open** | Failed transaction attempts rise from 54–66/month in Apr–Jul to 226 in August and 130 in September, while paying users and successful transaction counts fall. |
| 3 | The MAU increase is partly a measurement or low-intent activity shift rather than monetizable audience growth. | **open** | Session MAU and view-user counts match nearly exactly through June, but by September sessions report 5,473 MAU versus 5,178 view users; need to assess audience quality and sessions/platform/source. |
| 4 | Product mix, country, acquisition source or cohort shift explains weaker monetization per active user. | **open** | Not yet segmented. |
| 5 | Refunds, price anomalies, or status-data inconsistencies materially explain the flat revenue. | **open** | Monthly refunds remain around $90–$220; transaction outcomes, prices and statuses need validation. |

**Next:** Check transaction types/statuses/payment methods and price/refund distributions, then decompose quarterly revenue, payer conversion and ARPPU by subscription versus PPV; compare active-user quality and segments.


### Step 4 · run_sql (2/40, 14 ms, ok)

**Purpose:** Validate transaction outcome categories, payment methods and amount/sign behavior to determine whether reported revenue should exclude failed attempts and how refunds contribute.

```sql
SELECT type,status,payment_method,COUNT(*) txn_count,COUNT(DISTINCT user_id) users,ROUND(SUM(amount_usd),2) amount,ROUND(AVG(amount_usd),2) avg_amount,MIN(amount_usd) min_amount,MAX(amount_usd) max_amount FROM transactions GROUP BY type,status,payment_method ORDER BY type,status,payment_method
```

38 rows (14 ms)

| type | status | payment_method | txn_count | users | amount | avg_amount | min_amount | max_amount |
|---|---|---|---|---|---|---|---|---|
| ppv | failed | apple_iap | 25 | 20 | 55.75 | 2.23 | 1.99 | 2.99 |
| ppv | failed | card | 23 | 17 | 48.77 | 2.12 | 1.99 | 2.99 |
| ppv | failed | ewallet | 2 | 2 | 3.98 | 1.99 | 1.99 | 1.99 |
| ppv | failed | google_play | 28 | 24 | 60.72 | 2.17 | 1.99 | 2.99 |
| ppv | failed | oxxo | 35 | 23 | 71.65 | 2.05 | 1.99 | 2.99 |
| ppv | failed | pix | 28 | 21 | 242.65 | 8.67 | 1.99 | 14.9 |
| ppv | failed | pse | 7 | 5 | 15.93 | 2.28 | 1.99 | 2.99 |
| ppv | success | apple_iap | 612 | 437 | 1302.88 | 2.13 | 1.99 | 2.99 |
| ppv | success | card | 267 | 205 | 571.33 | 2.14 | 1.99 | 2.99 |
| ppv | success | ewallet | 42 | 40 | 86.58 | 2.06 | 1.99 | 2.99 |
| ppv | success | google_play | 400 | 313 | 868 | 2.17 | 1.99 | 2.99 |
| ppv | success | oxxo | 52 | 45 | 109.48 | 2.11 | 1.99 | 2.99 |
| ppv | success | paypal | 36 | 29 | 77.64 | 2.16 | 1.99 | 2.99 |
| ppv | success | pix | 95 | 78 | 358.43 | 3.77 | 1.99 | 14.9 |
| ppv | success | pse | 23 | 17 | 51.77 | 2.25 | 1.99 | 2.99 |
| refund | success | apple_iap | 38 | 38 | -379.62 | -9.99 | -9.99 | -9.99 |
| refund | success | card | 11 | 11 | -109.89 | -9.99 | -9.99 | -9.99 |
| refund | success | ewallet | 1 | 1 | -9.99 | -9.99 | -9.99 | -9.99 |
| refund | success | google_play | 25 | 25 | -249.75 | -9.99 | -9.99 | -9.99 |
| refund | success | oxxo | 4 | 4 | -39.96 | -9.99 | -9.99 | -9.99 |
| refund | success | pix | 9 | 9 | -169.73 | -18.86 | -49.9 | -9.99 |
| refund | success | pse | 1 | 1 | -9.99 | -9.99 | -9.99 | -9.99 |
| subscription | failed | apple_iap | 69 | 43 | 689.31 | 9.99 | 9.99 | 9.99 |
| subscription | failed | card | 64 | 35 | 639.36 | 9.99 | 9.99 | 9.99 |
| subscription | failed | ewallet | 15 | 8 | 149.85 | 9.99 | 9.99 | 9.99 |
| subscription | failed | google_play | 78 | 45 | 779.22 | 9.99 | 9.99 | 9.99 |
| subscription | failed | oxxo | 64 | 24 | 639.36 | 9.99 | 9.99 | 9.99 |
| subscription | failed | paypal | 3 | 1 | 29.97 | 9.99 | 9.99 | 9.99 |
| subscription | failed | pix | 128 | 52 | 5788.55 | 45.22 | 9.99 | 49.9 |
| subscription | failed | pse | 28 | 10 | 279.72 | 9.99 | 9.99 | 9.99 |
| subscription | success | apple_iap | 1588 | 495 | 15864.12 | 9.99 | 9.99 | 9.99 |
| subscription | success | card | 674 | 232 | 6733.26 | 9.99 | 9.99 | 9.99 |
| subscription | success | ewallet | 111 | 39 | 1108.89 | 9.99 | 9.99 | 9.99 |
| subscription | success | google_play | 944 | 313 | 9430.56 | 9.99 | 9.99 | 9.99 |
| subscription | success | oxxo | 105 | 44 | 1048.95 | 9.99 | 9.99 | 9.99 |
| subscription | success | paypal | 82 | 23 | 819.18 | 9.99 | 9.99 | 9.99 |
| subscription | success | pix | 215 | 83 | 3305.24 | 15.37 | 9.99 | 49.9 |
| subscription | success | pse | 33 | 12 | 329.67 | 9.99 | 9.99 | 9.99 |

_run_sql budget: 2/40 used_


### Step 5 · run_sql (3/40, 562 ms, ok)

**Purpose:** Inventory actual category values for key user, activity and content dimensions before filtering and segmentation.

```sql
SELECT 'country' dimension,country value,COUNT(*) n FROM users GROUP BY country UNION ALL SELECT 'acquisition_source',acquisition_source,COUNT(*) FROM users GROUP BY acquisition_source UNION ALL SELECT 'subscription_status',subscription_status,COUNT(*) FROM users GROUP BY subscription_status UNION ALL SELECT 'platform',platform,COUNT(*) FROM sessions GROUP BY platform UNION ALL SELECT 'view_type',view_type,COUNT(*) FROM content_views GROUP BY view_type UNION ALL SELECT 'content_tier',content_tier,COUNT(*) FROM content_catalog GROUP BY content_tier ORDER BY dimension,value
```

27 rows (562 ms)

| dimension | value | n |
|---|---|---|
| acquisition_source | affiliate_network | 1442 |
| acquisition_source | google_search | 3093 |
| acquisition_source | influencer | 1037 |
| acquisition_source | meta_ads | 2856 |
| acquisition_source | organic | 7631 |
| acquisition_source | referral | 1277 |
| acquisition_source | tiktok_ads | 3372 |
| content_tier | free | 61 |
| content_tier | premium | 20 |
| country | BR | 2784 |
| country | CO | 901 |
| country | ID | 2790 |
| country | MX | 2084 |
| country | PH | 2567 |
| country | TH | 1239 |
| country | US | 6902 |
| country | USA | 136 |
| country | VN | 1305 |
| platform | android | 126011 |
| platform | ios | 76526 |
| platform | web | 29817 |
| subscription_status | active | 568 |
| subscription_status | cancelled | 1054 |
| subscription_status | free | 19086 |
| view_type | free | 357465 |
| view_type | ppv | 1527 |
| view_type | sub | 205788 |

_run_sql budget: 3/40 used_


### Step 6 · run_sql (4/40, 1000 ms, ok)

**Purpose:** Test whether the MAU growth is accompanied by content consumption, and check for anomalous session or view records that could inflate activity.

```sql
WITH activity AS (SELECT substr(date,1,7) month,COUNT(DISTINCT user_id) session_users,COUNT(*) sessions,COUNT(DISTINCT CASE WHEN duration_sec<=0 THEN user_id END) zero_duration_users,ROUND(AVG(duration_sec),1) avg_session_sec FROM sessions GROUP BY substr(date,1,7)), views AS (SELECT substr(date,1,7) month,COUNT(DISTINCT user_id) view_users,COUNT(*) views,ROUND(AVG(CASE WHEN content_duration_sec>0 THEN watch_duration_sec*1.0/content_duration_sec END),3) avg_watch_share,COUNT(CASE WHEN watch_duration_sec>content_duration_sec THEN 1 END) overlong_views FROM content_views GROUP BY substr(date,1,7)) SELECT a.*,v.view_users,v.views,v.avg_watch_share,v.overlong_views FROM activity a JOIN views v USING(month) ORDER BY month
```

6 rows (1000 ms)

| month | session_users | sessions | zero_duration_users | avg_session_sec | view_users | views | avg_watch_share | overlong_views |
|---|---|---|---|---|---|---|---|---|
| 2026-04 | 4243 | 34001 | 0 | 2863.1 | 4243 | 80295 | 0.8 | 0 |
| 2026-05 | 4510 | 37341 | 0 | 2854.7 | 4509 | 88207 | 0.8 | 0 |
| 2026-06 | 4594 | 38120 | 0 | 2852.7 | 4593 | 90638 | 0.8 | 0 |
| 2026-07 | 5123 | 40963 | 0 | 2910.4 | 4915 | 103152 | 0.799 | 0 |
| 2026-08 | 5389 | 41677 | 0 | 2910.2 | 5087 | 103776 | 0.799 | 0 |
| 2026-09 | 5473 | 40252 | 0 | 2874.1 | 5178 | 98712 | 0.799 | 0 |

_run_sql budget: 4/40 used_


### Step 7 · run_sql (5/40, 15 ms, ok)

**Purpose:** Trace revenue and failed transaction volume by month and product type to locate when and where transaction performance changed.

```sql
WITH tx AS (SELECT substr(date,1,7) month,type,status,COUNT(*) n,ROUND(SUM(amount_usd),2) amount FROM transactions GROUP BY substr(date,1,7),type,status) SELECT * FROM tx ORDER BY month,type,status
```

30 rows (15 ms)

| month | type | status | n | amount |
|---|---|---|---|---|
| 2026-04 | ppv | failed | 14 | 27.86 |
| 2026-04 | ppv | success | 292 | 581.08 |
| 2026-04 | refund | success | 14 | -139.86 |
| 2026-04 | subscription | failed | 40 | 399.6 |
| 2026-04 | subscription | success | 590 | 5894.1 |
| 2026-05 | ppv | failed | 21 | 48.79 |
| 2026-05 | ppv | success | 313 | 703.87 |
| 2026-05 | refund | success | 12 | -119.88 |
| 2026-05 | subscription | failed | 39 | 389.61 |
| 2026-05 | subscription | success | 643 | 6423.57 |
| 2026-06 | ppv | failed | 21 | 44.79 |
| 2026-06 | ppv | success | 359 | 788.41 |
| 2026-06 | refund | success | 22 | -219.78 |
| 2026-06 | subscription | failed | 40 | 399.6 |
| 2026-06 | subscription | success | 689 | 6883.11 |
| 2026-07 | ppv | failed | 15 | 31.85 |
| 2026-07 | ppv | success | 196 | 423.04 |
| 2026-07 | refund | success | 9 | -89.91 |
| 2026-07 | subscription | failed | 51 | 509.49 |
| 2026-07 | subscription | success | 701 | 7002.99 |
| 2026-08 | ppv | failed | 39 | 169.62 |
| 2026-08 | ppv | success | 194 | 471.43 |
| 2026-08 | refund | success | 20 | -199.8 |
| 2026-08 | subscription | failed | 187 | 4821.47 |
| 2026-08 | subscription | success | 599 | 6782.21 |
| 2026-09 | ppv | failed | 38 | 176.54 |
| 2026-09 | ppv | success | 173 | 458.28 |
| 2026-09 | refund | success | 12 | -199.7 |
| 2026-09 | subscription | failed | 92 | 2475.57 |
| 2026-09 | subscription | success | 530 | 5653.89 |

_run_sql budget: 5/40 used_


### Step 8 · update_hypotheses

| # | Hypothesis | Status | Evidence |
|---|---|---|---|
| 1 | Revenue per active user fell because the expanding audience converted to payers less often or spent less per payer. | **open** | MAU rose ~19.8% quarterly while revenue fell ~2.4%; successful paying users fell from monthly 2,726 across Q2 to 2,290 across Q3, but need quarterly distinct users and segment-adjusted conversion. |
| 2 | A payment-processing or checkout issue drove down successful revenue, especially in August and September. | **supported** | Failed attempts jump from 54–66 per month pre-August to 226 in August and 130 in September; subscription failures rise from 39–51 to 187 and 92. Failed values are not revenue; Pix failure amounts have unusual outliers, so quantify reliable lost opportunity before claiming impact. |
| 3 | The MAU increase is partly a measurement or low-intent activity shift rather than monetizable audience growth. | **open** | After June, session MAU exceeds view-user MAU (difference 208 in July, 302 in August, 295 in September), but aggregate views still rise from 259,140 in Q2 to 305,640 in Q3 and watch share is stable ~80%. |
| 4 | Product mix, country, acquisition source or cohort shift explains weaker monetization per active user. | **open** | Subscription successful sales are $19,200.78 in Q2 vs $19,439.09 in Q3 (+1.2%), while PPV drops $2,073.36 to $1,352.75 (-34.7%); need segment attribution. |
| 5 | Refunds, price anomalies, or status-data inconsistencies materially explain the flat revenue. | **open** | Refunds are $479.52 in Q2 and $489.41 in Q3; failed attempts must be excluded. Pix successful amounts include $49.90 subscriptions and $14.90 PPV, beyond standard listed prices; assess materiality and timing. |

**Next:** Compare quarterly actives, paying users, revenue and PPV/subscription mix by country and acquisition source; assess monthly activity and monetization by user cohort/platform, then isolate failed-payment spike by method and validate anomalous Pix amounts.


### Step 9 · run_sql (6/40, 640 ms, ok)

**Purpose:** Determine whether monetization deterioration is concentrated in particular countries, accounting for each country's active audience, payer rate, revenue per active and product line.

```sql
WITH active AS (SELECT CASE WHEN substr(s.date,1,7) BETWEEN '2026-04' AND '2026-06' THEN 'Q2' ELSE 'Q3' END q,u.country,COUNT(DISTINCT s.user_id) actives FROM sessions s JOIN users u USING(user_id) GROUP BY q,u.country), rev AS (SELECT CASE WHEN substr(t.date,1,7) BETWEEN '2026-04' AND '2026-06' THEN 'Q2' ELSE 'Q3' END q,u.country,COUNT(DISTINCT CASE WHEN t.status='success' AND t.amount_usd>0 THEN t.user_id END) payers,ROUND(SUM(CASE WHEN t.status='success' THEN t.amount_usd ELSE 0 END),2) revenue,ROUND(SUM(CASE WHEN t.status='success' AND t.type='subscription' THEN t.amount_usd ELSE 0 END),2) subs,ROUND(SUM(CASE WHEN t.status='success' AND t.type='ppv' THEN t.amount_usd ELSE 0 END),2) ppv,COUNT(CASE WHEN t.status='failed' THEN 1 END) failed_attempts FROM transactions t JOIN users u USING(user_id) GROUP BY q,u.country) SELECT a.q,a.country,a.actives,COALESCE(r.payers,0) payers,ROUND(COALESCE(r.payers,0)*100.0/a.actives,1) payer_rate,COALESCE(r.revenue,0) revenue,ROUND(COALESCE(r.revenue,0)/a.actives,2) revenue_per_active,COALESCE(r.subs,0) subscription_revenue,COALESCE(r.ppv,0) ppv_revenue,COALESCE(r.failed_attempts,0) failed_attempts FROM active a LEFT JOIN rev r ON a.q=r.q AND a.country=r.country ORDER BY a.country,a.q
```

18 rows (640 ms)

| q | country | actives | payers | payer_rate | revenue | revenue_per_active | subscription_revenue | ppv_revenue | failed_attempts |
|---|---|---|---|---|---|---|---|---|---|
| Q2 | BR | 960 | 231 | 24.1 | 2924.95 | 3.05 | 2717.28 | 307.57 | 22 |
| Q3 | BR | 1067 | 175 | 16.4 | 3542.03 | 3.32 | 3345.2 | 316.61 | 155 |
| Q2 | CO | 285 | 53 | 18.6 | 675.06 | 2.37 | 629.37 | 75.66 | 6 |
| Q3 | CO | 366 | 45 | 12.3 | 524.31 | 1.43 | 489.51 | 44.79 | 36 |
| Q2 | ID | 673 | 66 | 9.8 | 667.05 | 0.99 | 589.41 | 77.64 | 3 |
| Q3 | ID | 1461 | 55 | 3.8 | 819.01 | 0.56 | 779.22 | 49.78 | 9 |
| Q2 | MX | 742 | 162 | 21.8 | 2108.16 | 2.84 | 1938.06 | 200.07 | 31 |
| Q3 | MX | 816 | 127 | 15.6 | 1680.83 | 2.06 | 1598.4 | 132.38 | 98 |
| Q2 | PH | 617 | 80 | 13 | 1083.59 | 1.76 | 1008.99 | 84.59 | 17 |
| Q3 | PH | 1290 | 59 | 4.6 | 1001.84 | 0.78 | 989.01 | 42.8 | 18 |
| Q2 | TH | 409 | 53 | 13 | 556.23 | 1.36 | 539.46 | 56.73 | 3 |
| Q3 | TH | 500 | 43 | 8.6 | 532.31 | 1.06 | 489.51 | 42.8 | 10 |
| Q2 | US | 2901 | 921 | 31.7 | 12014.55 | 4.14 | 11038.95 | 1215.36 | 90 |
| Q3 | US | 2606 | 739 | 28.4 | 11513.82 | 4.42 | 11048.94 | 714.63 | 86 |
| Q2 | USA | 37 | 21 | 56.8 | 384.52 | 10.39 | 369.63 | 24.88 | 1 |
| Q3 | USA | 23 | 14 | 60.9 | 311.68 | 13.55 | 309.69 | 1.99 | 3 |
| Q2 | VN | 312 | 32 | 10.3 | 380.51 | 1.22 | 369.63 | 30.86 | 2 |
| Q3 | VN | 698 | 20 | 2.9 | 376.6 | 0.54 | 389.61 | 6.97 | 7 |

_run_sql budget: 6/40 used_


### Step 10 · run_sql (7/40, 687 ms, ok)

**Purpose:** Test whether changing acquisition mix or within-channel monetization explains MAU growth without revenue growth.

```sql
WITH active AS (SELECT CASE WHEN substr(s.date,1,7) BETWEEN '2026-04' AND '2026-06' THEN 'Q2' ELSE 'Q3' END q,u.acquisition_source,COUNT(DISTINCT s.user_id) actives FROM sessions s JOIN users u USING(user_id) GROUP BY q,u.acquisition_source), rev AS (SELECT CASE WHEN substr(t.date,1,7) BETWEEN '2026-04' AND '2026-06' THEN 'Q2' ELSE 'Q3' END q,u.acquisition_source,COUNT(DISTINCT CASE WHEN t.status='success' AND t.amount_usd>0 THEN t.user_id END) payers,ROUND(SUM(CASE WHEN t.status='success' THEN t.amount_usd ELSE 0 END),2) revenue,ROUND(SUM(CASE WHEN t.status='success' AND t.type='subscription' THEN t.amount_usd ELSE 0 END),2) subs,ROUND(SUM(CASE WHEN t.status='success' AND t.type='ppv' THEN t.amount_usd ELSE 0 END),2) ppv,COUNT(CASE WHEN t.status='failed' THEN 1 END) failed_attempts FROM transactions t JOIN users u USING(user_id) GROUP BY q,u.acquisition_source) SELECT a.q,a.acquisition_source,a.actives,COALESCE(r.payers,0) payers,ROUND(COALESCE(r.payers,0)*100.0/a.actives,1) payer_rate,COALESCE(r.revenue,0) revenue,ROUND(COALESCE(r.revenue,0)/a.actives,2) revenue_per_active,COALESCE(r.subs,0) subscription_revenue,COALESCE(r.ppv,0) ppv_revenue,COALESCE(r.failed_attempts,0) failed_attempts FROM active a LEFT JOIN rev r ON a.q=r.q AND a.acquisition_source=r.acquisition_source ORDER BY a.acquisition_source,a.q
```

13 rows (687 ms)

| q | acquisition_source | actives | payers | payer_rate | revenue | revenue_per_active | subscription_revenue | ppv_revenue | failed_attempts |
|---|---|---|---|---|---|---|---|---|---|
| Q3 | affiliate_network | 1402 | 2 | 0.1 | 19.98 | 0.01 | 19.98 | 0 | 0 |
| Q2 | google_search | 1600 | 601 | 37.6 | 8172.77 | 5.11 | 7562.43 | 850.1 | 71 |
| Q3 | google_search | 1056 | 442 | 41.9 | 7515.68 | 7.12 | 7272.47 | 403 | 107 |
| Q2 | influencer | 202 | 9 | 4.5 | 120.84 | 0.6 | 109.89 | 10.95 | 0 |
| Q3 | influencer | 427 | 10 | 2.3 | 119.75 | 0.28 | 99.9 | 19.85 | 1 |
| Q2 | meta_ads | 1100 | 218 | 19.8 | 2674.43 | 2.43 | 2497.5 | 246.86 | 30 |
| Q3 | meta_ads | 856 | 146 | 17.1 | 2490.62 | 2.91 | 2397.4 | 143.17 | 73 |
| Q2 | organic | 2769 | 606 | 21.9 | 7709.63 | 2.78 | 7122.87 | 716.63 | 65 |
| Q3 | organic | 3103 | 530 | 17.1 | 7805.9 | 2.52 | 7411.83 | 603.81 | 205 |
| Q2 | referral | 519 | 159 | 30.6 | 1840.33 | 3.55 | 1658.34 | 221.95 | 8 |
| Q3 | referral | 583 | 126 | 21.6 | 2040.26 | 3.5 | 1977.87 | 132.32 | 30 |
| Q2 | tiktok_ads | 746 | 26 | 3.5 | 276.62 | 0.37 | 249.75 | 26.87 | 1 |
| Q3 | tiktok_ads | 1400 | 21 | 1.5 | 310.24 | 0.22 | 259.64 | 50.6 | 6 |

_run_sql budget: 7/40 used_


### Step 11 · run_sql (8/40, 15 ms, ok)

**Purpose:** Locate the failed-attempt spike by method and product and identify when unusual Pix prices first appear among successes or failures.

```sql
SELECT substr(t.date,1,7) month,t.payment_method,t.type,t.status,COUNT(*) attempts,COUNT(DISTINCT t.user_id) users,ROUND(SUM(t.amount_usd),2) amount,ROUND(AVG(t.amount_usd),2) avg_amount,MIN(t.amount_usd) min_amount,MAX(t.amount_usd) max_amount FROM transactions t GROUP BY month,t.payment_method,t.type,t.status ORDER BY month,t.payment_method,t.type,t.status
```

100 rows (15 ms)

| month | payment_method | type | status | attempts | users | amount | avg_amount | min_amount | max_amount |
|---|---|---|---|---|---|---|---|---|---|
| 2026-04 | apple_iap | ppv | failed | 4 | 4 | 7.96 | 1.99 | 1.99 | 1.99 |
| 2026-04 | apple_iap | ppv | success | 126 | 112 | 250.74 | 1.99 | 1.99 | 1.99 |
| 2026-04 | apple_iap | refund | success | 9 | 9 | -89.91 | -9.99 | -9.99 | -9.99 |
| 2026-04 | apple_iap | subscription | failed | 12 | 8 | 119.88 | 9.99 | 9.99 | 9.99 |
| 2026-04 | apple_iap | subscription | success | 241 | 240 | 2407.59 | 9.99 | 9.99 | 9.99 |
| 2026-04 | card | ppv | failed | 3 | 2 | 5.97 | 1.99 | 1.99 | 1.99 |
| 2026-04 | card | ppv | success | 50 | 46 | 99.5 | 1.99 | 1.99 | 1.99 |
| 2026-04 | card | refund | success | 2 | 2 | -19.98 | -9.99 | -9.99 | -9.99 |
| 2026-04 | card | subscription | failed | 8 | 4 | 79.92 | 9.99 | 9.99 | 9.99 |
| 2026-04 | card | subscription | success | 104 | 104 | 1038.96 | 9.99 | 9.99 | 9.99 |
| 2026-04 | ewallet | ppv | success | 9 | 9 | 17.91 | 1.99 | 1.99 | 1.99 |
| 2026-04 | ewallet | subscription | failed | 1 | 1 | 9.99 | 9.99 | 9.99 | 9.99 |
| 2026-04 | ewallet | subscription | success | 12 | 12 | 119.88 | 9.99 | 9.99 | 9.99 |
| 2026-04 | google_play | ppv | failed | 3 | 3 | 5.97 | 1.99 | 1.99 | 1.99 |
| 2026-04 | google_play | ppv | success | 69 | 67 | 137.31 | 1.99 | 1.99 | 1.99 |
| 2026-04 | google_play | refund | success | 2 | 2 | -19.98 | -9.99 | -9.99 | -9.99 |
| 2026-04 | google_play | subscription | failed | 14 | 10 | 139.86 | 9.99 | 9.99 | 9.99 |
| 2026-04 | google_play | subscription | success | 150 | 150 | 1498.5 | 9.99 | 9.99 | 9.99 |
| 2026-04 | oxxo | ppv | failed | 3 | 2 | 5.97 | 1.99 | 1.99 | 1.99 |
| 2026-04 | oxxo | ppv | success | 11 | 11 | 21.89 | 1.99 | 1.99 | 1.99 |
| 2026-04 | oxxo | subscription | success | 24 | 24 | 239.76 | 9.99 | 9.99 | 9.99 |
| 2026-04 | paypal | ppv | success | 5 | 5 | 9.95 | 1.99 | 1.99 | 1.99 |
| 2026-04 | paypal | subscription | success | 13 | 13 | 129.87 | 9.99 | 9.99 | 9.99 |
| 2026-04 | pix | ppv | failed | 1 | 1 | 1.99 | 1.99 | 1.99 | 1.99 |
| 2026-04 | pix | ppv | success | 22 | 21 | 43.78 | 1.99 | 1.99 | 1.99 |
| 2026-04 | pix | refund | success | 1 | 1 | -9.99 | -9.99 | -9.99 | -9.99 |
| 2026-04 | pix | subscription | failed | 3 | 2 | 29.97 | 9.99 | 9.99 | 9.99 |
| 2026-04 | pix | subscription | success | 40 | 40 | 399.6 | 9.99 | 9.99 | 9.99 |
| 2026-04 | pse | subscription | failed | 2 | 1 | 19.98 | 9.99 | 9.99 | 9.99 |
| 2026-04 | pse | subscription | success | 6 | 6 | 59.94 | 9.99 | 9.99 | 9.99 |
| 2026-05 | apple_iap | ppv | failed | 5 | 4 | 11.95 | 2.39 | 1.99 | 2.99 |
| 2026-05 | apple_iap | ppv | success | 121 | 110 | 272.79 | 2.25 | 1.99 | 2.99 |
| 2026-05 | apple_iap | refund | success | 3 | 3 | -29.97 | -9.99 | -9.99 | -9.99 |
| 2026-05 | apple_iap | subscription | failed | 12 | 7 | 119.88 | 9.99 | 9.99 | 9.99 |
| 2026-05 | apple_iap | subscription | success | 260 | 254 | 2597.4 | 9.99 | 9.99 | 9.99 |
| 2026-05 | card | ppv | failed | 5 | 4 | 12.95 | 2.59 | 1.99 | 2.99 |
| 2026-05 | card | ppv | success | 56 | 52 | 125.44 | 2.24 | 1.99 | 2.99 |
| 2026-05 | card | subscription | failed | 11 | 6 | 109.89 | 9.99 | 9.99 | 9.99 |
| 2026-05 | card | subscription | success | 111 | 110 | 1108.89 | 9.99 | 9.99 | 9.99 |
| 2026-05 | ewallet | ppv | success | 7 | 7 | 14.93 | 2.13 | 1.99 | 2.99 |
| 2026-05 | ewallet | subscription | failed | 1 | 1 | 9.99 | 9.99 | 9.99 | 9.99 |
| 2026-05 | ewallet | subscription | success | 20 | 18 | 199.8 | 9.99 | 9.99 | 9.99 |
| 2026-05 | google_play | ppv | failed | 7 | 5 | 15.93 | 2.28 | 1.99 | 2.99 |
| 2026-05 | google_play | ppv | success | 85 | 77 | 191.15 | 2.25 | 1.99 | 2.99 |
| 2026-05 | google_play | refund | success | 5 | 5 | -49.95 | -9.99 | -9.99 | -9.99 |
| 2026-05 | google_play | subscription | failed | 10 | 6 | 99.9 | 9.99 | 9.99 | 9.99 |
| 2026-05 | google_play | subscription | success | 159 | 156 | 1588.41 | 9.99 | 9.99 | 9.99 |
| 2026-05 | oxxo | ppv | failed | 2 | 2 | 3.98 | 1.99 | 1.99 | 1.99 |
| 2026-05 | oxxo | ppv | success | 11 | 11 | 21.89 | 1.99 | 1.99 | 1.99 |
| 2026-05 | oxxo | refund | success | 2 | 2 | -19.98 | -9.99 | -9.99 | -9.99 |
| 2026-05 | oxxo | subscription | failed | 1 | 1 | 9.99 | 9.99 | 9.99 | 9.99 |
| 2026-05 | oxxo | subscription | success | 21 | 20 | 209.79 | 9.99 | 9.99 | 9.99 |
| 2026-05 | paypal | ppv | success | 8 | 8 | 18.92 | 2.37 | 1.99 | 2.99 |
| 2026-05 | paypal | subscription | success | 14 | 13 | 139.86 | 9.99 | 9.99 | 9.99 |
| 2026-05 | pix | ppv | failed | 1 | 1 | 1.99 | 1.99 | 1.99 | 1.99 |
| 2026-05 | pix | ppv | success | 20 | 19 | 46.8 | 2.34 | 1.99 | 2.99 |
| 2026-05 | pix | refund | success | 2 | 2 | -19.98 | -9.99 | -9.99 | -9.99 |
| 2026-05 | pix | subscription | failed | 4 | 2 | 39.96 | 9.99 | 9.99 | 9.99 |
| 2026-05 | pix | subscription | success | 51 | 48 | 509.49 | 9.99 | 9.99 | 9.99 |
| 2026-05 | pse | ppv | failed | 1 | 1 | 1.99 | 1.99 | 1.99 | 1.99 |
| 2026-05 | pse | ppv | success | 5 | 5 | 11.95 | 2.39 | 1.99 | 2.99 |
| 2026-05 | pse | subscription | success | 7 | 7 | 69.93 | 9.99 | 9.99 | 9.99 |
| 2026-06 | apple_iap | ppv | failed | 3 | 3 | 5.97 | 1.99 | 1.99 | 1.99 |
| 2026-06 | apple_iap | ppv | success | 138 | 125 | 300.62 | 2.18 | 1.99 | 2.99 |
| 2026-06 | apple_iap | refund | success | 5 | 5 | -49.95 | -9.99 | -9.99 | -9.99 |
| 2026-06 | apple_iap | subscription | failed | 9 | 6 | 89.91 | 9.99 | 9.99 | 9.99 |
| 2026-06 | apple_iap | subscription | success | 278 | 278 | 2777.22 | 9.99 | 9.99 | 9.99 |
| 2026-06 | card | ppv | failed | 3 | 3 | 5.97 | 1.99 | 1.99 | 1.99 |
| 2026-06 | card | ppv | success | 50 | 46 | 111.5 | 2.23 | 1.99 | 2.99 |
| 2026-06 | card | refund | success | 5 | 5 | -49.95 | -9.99 | -9.99 | -9.99 |
| 2026-06 | card | subscription | failed | 13 | 7 | 129.87 | 9.99 | 9.99 | 9.99 |
| 2026-06 | card | subscription | success | 119 | 119 | 1188.81 | 9.99 | 9.99 | 9.99 |
| 2026-06 | ewallet | ppv | success | 9 | 9 | 17.91 | 1.99 | 1.99 | 1.99 |
| 2026-06 | ewallet | subscription | failed | 1 | 1 | 9.99 | 9.99 | 9.99 | 9.99 |
| 2026-06 | ewallet | subscription | success | 23 | 23 | 229.77 | 9.99 | 9.99 | 9.99 |
| 2026-06 | google_play | ppv | failed | 9 | 8 | 19.91 | 2.21 | 1.99 | 2.99 |
| 2026-06 | google_play | ppv | success | 109 | 96 | 241.91 | 2.22 | 1.99 | 2.99 |
| 2026-06 | google_play | refund | success | 8 | 8 | -79.92 | -9.99 | -9.99 | -9.99 |
| 2026-06 | google_play | subscription | failed | 8 | 5 | 79.92 | 9.99 | 9.99 | 9.99 |
| 2026-06 | google_play | subscription | success | 175 | 175 | 1748.25 | 9.99 | 9.99 | 9.99 |
| 2026-06 | oxxo | ppv | failed | 3 | 3 | 6.97 | 2.32 | 1.99 | 2.99 |
| 2026-06 | oxxo | ppv | success | 14 | 13 | 32.86 | 2.35 | 1.99 | 2.99 |
| 2026-06 | oxxo | subscription | failed | 7 | 3 | 69.93 | 9.99 | 9.99 | 9.99 |
| 2026-06 | oxxo | subscription | success | 20 | 20 | 199.8 | 9.99 | 9.99 | 9.99 |
| 2026-06 | paypal | ppv | success | 8 | 7 | 16.92 | 2.12 | 1.99 | 2.99 |
| 2026-06 | paypal | subscription | success | 16 | 16 | 159.84 | 9.99 | 9.99 | 9.99 |
| 2026-06 | pix | ppv | failed | 3 | 2 | 5.97 | 1.99 | 1.99 | 1.99 |
| 2026-06 | pix | ppv | success | 21 | 19 | 43.79 | 2.09 | 1.99 | 2.99 |
| 2026-06 | pix | refund | success | 3 | 3 | -29.97 | -9.99 | -9.99 | -9.99 |
| 2026-06 | pix | subscription | failed | 2 | 2 | 19.98 | 9.99 | 9.99 | 9.99 |
| 2026-06 | pix | subscription | success | 49 | 49 | 489.51 | 9.99 | 9.99 | 9.99 |
| 2026-06 | pse | ppv | success | 10 | 8 | 22.9 | 2.29 | 1.99 | 2.99 |
| 2026-06 | pse | refund | success | 1 | 1 | -9.99 | -9.99 | -9.99 | -9.99 |
| 2026-06 | pse | subscription | success | 9 | 9 | 89.91 | 9.99 | 9.99 | 9.99 |
| 2026-07 | apple_iap | ppv | failed | 5 | 3 | 10.95 | 2.19 | 1.99 | 2.99 |
| 2026-07 | apple_iap | ppv | success | 70 | 62 | 154.3 | 2.2 | 1.99 | 2.99 |
| 2026-07 | apple_iap | refund | success | 4 | 4 | -39.96 | -9.99 | -9.99 | -9.99 |
| 2026-07 | apple_iap | subscription | failed | 12 | 7 | 119.88 | 9.99 | 9.99 | 9.99 |
| 2026-07 | apple_iap | subscription | success | 302 | 289 | 3016.98 | 9.99 | 9.99 | 9.99 |
| 2026-07 | card | ppv | failed | 5 | 3 | 9.95 | 1.99 | 1.99 | 1.99 |
Showing the first 100 rows only; the query returned more. Aggregate further or add ORDER BY + LIMIT.

_run_sql budget: 8/40 used_


### Step 12 · run_sql (9/40, 796 ms, ok)

**Purpose:** Check whether the additional session-based MAU is concentrated on a platform and compare platform-level activity quality over time.

```sql
WITH act AS (SELECT substr(s.date,1,7) month,s.platform,COUNT(DISTINCT s.user_id) active_users,COUNT(*) sessions,ROUND(AVG(s.duration_sec),1) avg_session_sec FROM sessions s GROUP BY month,s.platform), v AS (SELECT substr(date,1,7) month,view_type,COUNT(*) views,COUNT(DISTINCT user_id) users FROM content_views GROUP BY month,view_type) SELECT act.month,act.platform,act.active_users,act.sessions,act.avg_session_sec FROM act ORDER BY act.month,act.platform
```

18 rows (796 ms)

| month | platform | active_users | sessions | avg_session_sec |
|---|---|---|---|---|
| 2026-04 | android | 2861 | 18129 | 2766.9 |
| 2026-04 | ios | 2007 | 11479 | 2985.9 |
| 2026-04 | web | 1293 | 4393 | 2939 |
| 2026-05 | android | 3013 | 19715 | 2763.2 |
| 2026-05 | ios | 2103 | 12668 | 2960.9 |
| 2026-05 | web | 1372 | 4958 | 2947.4 |
| 2026-06 | android | 3146 | 20258 | 2775.3 |
| 2026-06 | ios | 2165 | 12871 | 2962.7 |
| 2026-06 | web | 1421 | 4991 | 2883.5 |
| 2026-07 | android | 3662 | 22129 | 2787 |
| 2026-07 | ios | 2215 | 13745 | 3087.7 |
| 2026-07 | web | 1487 | 5089 | 2967.6 |
| 2026-08 | android | 3952 | 23157 | 2748.4 |
| 2026-08 | ios | 2172 | 13237 | 3166.7 |
| 2026-08 | web | 1497 | 5283 | 2976.8 |
| 2026-09 | android | 4006 | 22623 | 2712.7 |
| 2026-09 | ios | 2176 | 12526 | 3119.2 |
| 2026-09 | web | 1538 | 5103 | 2988.2 |

_run_sql budget: 9/40 used_


### Step 13 · run_sql (10/40, 15 ms, ok)

**Purpose:** Quantify month-by-month payment failures by method and distinguish actual unusual-price rows from ordinary failed-attempt counts.

```sql
SELECT substr(date,1,7) month,payment_method,type,status,COUNT(*) attempts,COUNT(DISTINCT user_id) users,ROUND(SUM(amount_usd),2) recorded_amount,COUNT(CASE WHEN (type='subscription' AND amount_usd<>9.99 AND type<>'refund') OR (type='ppv' AND amount_usd NOT IN (1.99,2.99)) THEN 1 END) unusual_price_rows,COUNT(CASE WHEN amount_usd>CASE WHEN type='subscription' THEN 9.99 WHEN type='ppv' THEN 2.99 ELSE 0 END AND type<>'refund' THEN 1 END) above_list_price_rows FROM transactions GROUP BY month,payment_method,type,status ORDER BY month,payment_method,type,status LIMIT 100
```

100 rows (15 ms)

| month | payment_method | type | status | attempts | users | recorded_amount | unusual_price_rows | above_list_price_rows |
|---|---|---|---|---|---|---|---|---|
| 2026-04 | apple_iap | ppv | failed | 4 | 4 | 7.96 | 0 | 0 |
| 2026-04 | apple_iap | ppv | success | 126 | 112 | 250.74 | 0 | 0 |
| 2026-04 | apple_iap | refund | success | 9 | 9 | -89.91 | 0 | 0 |
| 2026-04 | apple_iap | subscription | failed | 12 | 8 | 119.88 | 0 | 0 |
| 2026-04 | apple_iap | subscription | success | 241 | 240 | 2407.59 | 0 | 0 |
| 2026-04 | card | ppv | failed | 3 | 2 | 5.97 | 0 | 0 |
| 2026-04 | card | ppv | success | 50 | 46 | 99.5 | 0 | 0 |
| 2026-04 | card | refund | success | 2 | 2 | -19.98 | 0 | 0 |
| 2026-04 | card | subscription | failed | 8 | 4 | 79.92 | 0 | 0 |
| 2026-04 | card | subscription | success | 104 | 104 | 1038.96 | 0 | 0 |
| 2026-04 | ewallet | ppv | success | 9 | 9 | 17.91 | 0 | 0 |
| 2026-04 | ewallet | subscription | failed | 1 | 1 | 9.99 | 0 | 0 |
| 2026-04 | ewallet | subscription | success | 12 | 12 | 119.88 | 0 | 0 |
| 2026-04 | google_play | ppv | failed | 3 | 3 | 5.97 | 0 | 0 |
| 2026-04 | google_play | ppv | success | 69 | 67 | 137.31 | 0 | 0 |
| 2026-04 | google_play | refund | success | 2 | 2 | -19.98 | 0 | 0 |
| 2026-04 | google_play | subscription | failed | 14 | 10 | 139.86 | 0 | 0 |
| 2026-04 | google_play | subscription | success | 150 | 150 | 1498.5 | 0 | 0 |
| 2026-04 | oxxo | ppv | failed | 3 | 2 | 5.97 | 0 | 0 |
| 2026-04 | oxxo | ppv | success | 11 | 11 | 21.89 | 0 | 0 |
| 2026-04 | oxxo | subscription | success | 24 | 24 | 239.76 | 0 | 0 |
| 2026-04 | paypal | ppv | success | 5 | 5 | 9.95 | 0 | 0 |
| 2026-04 | paypal | subscription | success | 13 | 13 | 129.87 | 0 | 0 |
| 2026-04 | pix | ppv | failed | 1 | 1 | 1.99 | 0 | 0 |
| 2026-04 | pix | ppv | success | 22 | 21 | 43.78 | 0 | 0 |
| 2026-04 | pix | refund | success | 1 | 1 | -9.99 | 0 | 0 |
| 2026-04 | pix | subscription | failed | 3 | 2 | 29.97 | 0 | 0 |
| 2026-04 | pix | subscription | success | 40 | 40 | 399.6 | 0 | 0 |
| 2026-04 | pse | subscription | failed | 2 | 1 | 19.98 | 0 | 0 |
| 2026-04 | pse | subscription | success | 6 | 6 | 59.94 | 0 | 0 |
| 2026-05 | apple_iap | ppv | failed | 5 | 4 | 11.95 | 0 | 0 |
| 2026-05 | apple_iap | ppv | success | 121 | 110 | 272.79 | 0 | 0 |
| 2026-05 | apple_iap | refund | success | 3 | 3 | -29.97 | 0 | 0 |
| 2026-05 | apple_iap | subscription | failed | 12 | 7 | 119.88 | 0 | 0 |
| 2026-05 | apple_iap | subscription | success | 260 | 254 | 2597.4 | 0 | 0 |
| 2026-05 | card | ppv | failed | 5 | 4 | 12.95 | 0 | 0 |
| 2026-05 | card | ppv | success | 56 | 52 | 125.44 | 0 | 0 |
| 2026-05 | card | subscription | failed | 11 | 6 | 109.89 | 0 | 0 |
| 2026-05 | card | subscription | success | 111 | 110 | 1108.89 | 0 | 0 |
| 2026-05 | ewallet | ppv | success | 7 | 7 | 14.93 | 0 | 0 |
| 2026-05 | ewallet | subscription | failed | 1 | 1 | 9.99 | 0 | 0 |
| 2026-05 | ewallet | subscription | success | 20 | 18 | 199.8 | 0 | 0 |
| 2026-05 | google_play | ppv | failed | 7 | 5 | 15.93 | 0 | 0 |
| 2026-05 | google_play | ppv | success | 85 | 77 | 191.15 | 0 | 0 |
| 2026-05 | google_play | refund | success | 5 | 5 | -49.95 | 0 | 0 |
| 2026-05 | google_play | subscription | failed | 10 | 6 | 99.9 | 0 | 0 |
| 2026-05 | google_play | subscription | success | 159 | 156 | 1588.41 | 0 | 0 |
| 2026-05 | oxxo | ppv | failed | 2 | 2 | 3.98 | 0 | 0 |
| 2026-05 | oxxo | ppv | success | 11 | 11 | 21.89 | 0 | 0 |
| 2026-05 | oxxo | refund | success | 2 | 2 | -19.98 | 0 | 0 |
| 2026-05 | oxxo | subscription | failed | 1 | 1 | 9.99 | 0 | 0 |
| 2026-05 | oxxo | subscription | success | 21 | 20 | 209.79 | 0 | 0 |
| 2026-05 | paypal | ppv | success | 8 | 8 | 18.92 | 0 | 0 |
| 2026-05 | paypal | subscription | success | 14 | 13 | 139.86 | 0 | 0 |
| 2026-05 | pix | ppv | failed | 1 | 1 | 1.99 | 0 | 0 |
| 2026-05 | pix | ppv | success | 20 | 19 | 46.8 | 0 | 0 |
| 2026-05 | pix | refund | success | 2 | 2 | -19.98 | 0 | 0 |
| 2026-05 | pix | subscription | failed | 4 | 2 | 39.96 | 0 | 0 |
| 2026-05 | pix | subscription | success | 51 | 48 | 509.49 | 0 | 0 |
| 2026-05 | pse | ppv | failed | 1 | 1 | 1.99 | 0 | 0 |
| 2026-05 | pse | ppv | success | 5 | 5 | 11.95 | 0 | 0 |
| 2026-05 | pse | subscription | success | 7 | 7 | 69.93 | 0 | 0 |
| 2026-06 | apple_iap | ppv | failed | 3 | 3 | 5.97 | 0 | 0 |
| 2026-06 | apple_iap | ppv | success | 138 | 125 | 300.62 | 0 | 0 |
| 2026-06 | apple_iap | refund | success | 5 | 5 | -49.95 | 0 | 0 |
| 2026-06 | apple_iap | subscription | failed | 9 | 6 | 89.91 | 0 | 0 |
| 2026-06 | apple_iap | subscription | success | 278 | 278 | 2777.22 | 0 | 0 |
| 2026-06 | card | ppv | failed | 3 | 3 | 5.97 | 0 | 0 |
| 2026-06 | card | ppv | success | 50 | 46 | 111.5 | 0 | 0 |
| 2026-06 | card | refund | success | 5 | 5 | -49.95 | 0 | 0 |
| 2026-06 | card | subscription | failed | 13 | 7 | 129.87 | 0 | 0 |
| 2026-06 | card | subscription | success | 119 | 119 | 1188.81 | 0 | 0 |
| 2026-06 | ewallet | ppv | success | 9 | 9 | 17.91 | 0 | 0 |
| 2026-06 | ewallet | subscription | failed | 1 | 1 | 9.99 | 0 | 0 |
| 2026-06 | ewallet | subscription | success | 23 | 23 | 229.77 | 0 | 0 |
| 2026-06 | google_play | ppv | failed | 9 | 8 | 19.91 | 0 | 0 |
| 2026-06 | google_play | ppv | success | 109 | 96 | 241.91 | 0 | 0 |
| 2026-06 | google_play | refund | success | 8 | 8 | -79.92 | 0 | 0 |
| 2026-06 | google_play | subscription | failed | 8 | 5 | 79.92 | 0 | 0 |
| 2026-06 | google_play | subscription | success | 175 | 175 | 1748.25 | 0 | 0 |
| 2026-06 | oxxo | ppv | failed | 3 | 3 | 6.97 | 0 | 0 |
| 2026-06 | oxxo | ppv | success | 14 | 13 | 32.86 | 0 | 0 |
| 2026-06 | oxxo | subscription | failed | 7 | 3 | 69.93 | 0 | 0 |
| 2026-06 | oxxo | subscription | success | 20 | 20 | 199.8 | 0 | 0 |
| 2026-06 | paypal | ppv | success | 8 | 7 | 16.92 | 0 | 0 |
| 2026-06 | paypal | subscription | success | 16 | 16 | 159.84 | 0 | 0 |
| 2026-06 | pix | ppv | failed | 3 | 2 | 5.97 | 0 | 0 |
| 2026-06 | pix | ppv | success | 21 | 19 | 43.79 | 0 | 0 |
| 2026-06 | pix | refund | success | 3 | 3 | -29.97 | 0 | 0 |
| 2026-06 | pix | subscription | failed | 2 | 2 | 19.98 | 0 | 0 |
| 2026-06 | pix | subscription | success | 49 | 49 | 489.51 | 0 | 0 |
| 2026-06 | pse | ppv | success | 10 | 8 | 22.9 | 0 | 0 |
| 2026-06 | pse | refund | success | 1 | 1 | -9.99 | 0 | 0 |
| 2026-06 | pse | subscription | success | 9 | 9 | 89.91 | 0 | 0 |
| 2026-07 | apple_iap | ppv | failed | 5 | 3 | 10.95 | 0 | 0 |
| 2026-07 | apple_iap | ppv | success | 70 | 62 | 154.3 | 0 | 0 |
| 2026-07 | apple_iap | refund | success | 4 | 4 | -39.96 | 0 | 0 |
| 2026-07 | apple_iap | subscription | failed | 12 | 7 | 119.88 | 0 | 0 |
| 2026-07 | apple_iap | subscription | success | 302 | 289 | 3016.98 | 0 | 0 |
| 2026-07 | card | ppv | failed | 5 | 3 | 9.95 | 0 | 0 |

_run_sql budget: 10/40 used_


### Step 14 · run_sql (11/40, 2171 ms, ok)

**Purpose:** Assess whether recent acquisition cohorts, especially the newly observed affiliate source, account for Q3 audience growth but contribute little revenue.

```sql
SELECT substr(u.signup_date,1,7) signup_month,u.acquisition_source,COUNT(*) signups,COUNT(DISTINCT CASE WHEN s.date BETWEEN '2026-07-01' AND '2026-09-30' THEN u.user_id END) q3_actives,COUNT(DISTINCT CASE WHEN t.date BETWEEN '2026-07-01' AND '2026-09-30' AND t.status='success' AND t.amount_usd>0 THEN u.user_id END) q3_payers,ROUND(SUM(CASE WHEN t.date BETWEEN '2026-07-01' AND '2026-09-30' AND t.status='success' THEN t.amount_usd ELSE 0 END),2) q3_revenue FROM users u LEFT JOIN sessions s ON s.user_id=u.user_id LEFT JOIN transactions t ON t.user_id=u.user_id GROUP BY signup_month,u.acquisition_source ORDER BY signup_month,u.acquisition_source
```

75 rows (2171 ms)

| signup_month | acquisition_source | signups | q3_actives | q3_payers | q3_revenue |
|---|---|---|---|---|---|
| 2025-10 | google_search | 35850 | 117 | 63 | 107149.32 |
| 2025-10 | influencer | 401 | 7 | 0 | 0 |
| 2025-10 | meta_ads | 8140 | 48 | 16 | 20556.24 |
| 2025-10 | organic | 31183 | 144 | 50 | 85077.86 |
| 2025-10 | referral | 8646 | 30 | 19 | 33261.52 |
| 2025-10 | tiktok_ads | 988 | 13 | 1 | 499.5 |
| 2025-11 | google_search | 19743 | 67 | 32 | 67297.95 |
| 2025-11 | influencer | 725 | 3 | 1 | 2457.54 |
| 2025-11 | meta_ads | 7294 | 33 | 11 | 17308.88 |
| 2025-11 | organic | 22511 | 107 | 41 | 79872.15 |
| 2025-11 | referral | 4789 | 18 | 10 | 14912.04 |
| 2025-11 | tiktok_ads | 1233 | 13 | 2 | 2653.04 |
| 2025-12 | google_search | 19177 | 65 | 34 | 66048.95 |
| 2025-12 | influencer | 428 | 6 | 0 | 0 |
| 2025-12 | meta_ads | 8017 | 40 | 12 | 23518.9 |
| 2025-12 | organic | 21951 | 97 | 39 | 66767.33 |
| 2025-12 | referral | 3836 | 15 | 8 | 24368.2 |
| 2025-12 | tiktok_ads | 1088 | 17 | 1 | 97.51 |
| 2026-01 | google_search | 26372 | 98 | 51 | 88022.59 |
| 2026-01 | influencer | 572 | 6 | 2 | 884.65 |
| 2026-01 | meta_ads | 7306 | 34 | 11 | 21887.41 |
| 2026-01 | organic | 20023 | 114 | 36 | 63597.13 |
| 2026-01 | referral | 3680 | 23 | 7 | 9344.07 |
| 2026-01 | tiktok_ads | 962 | 14 | 1 | 699.3 |
| 2026-02 | google_search | 20956 | 94 | 44 | 74504.09 |
| 2026-02 | influencer | 410 | 7 | 0 | 0 |
| 2026-02 | meta_ads | 6275 | 33 | 9 | 17909.24 |
| 2026-02 | organic | 21526 | 128 | 40 | 60335.25 |
| 2026-02 | referral | 5786 | 19 | 11 | 18937.45 |
| 2026-02 | tiktok_ads | 803 | 13 | 0 | 0 |
| 2026-03 | google_search | 21240 | 102 | 43 | 66324.61 |
| 2026-03 | influencer | 514 | 12 | 0 | 0 |
| 2026-03 | meta_ads | 11359 | 54 | 20 | 46582.62 |
| 2026-03 | organic | 17305 | 119 | 32 | 46358.95 |
| 2026-03 | referral | 5977 | 24 | 11 | 16782.91 |
| 2026-03 | tiktok_ads | 1307 | 23 | 0 | 0 |
| 2026-04 | google_search | 20918 | 103 | 45 | 67624.53 |
| 2026-04 | influencer | 672 | 7 | 1 | 1888.11 |
| 2026-04 | meta_ads | 4835 | 59 | 10 | 5576.56 |
| 2026-04 | organic | 22939 | 176 | 53 | 72126.69 |
| 2026-04 | referral | 4923 | 36 | 13 | 12247.13 |
| 2026-04 | tiktok_ads | 2808 | 40 | 5 | 6076.94 |
| 2026-05 | google_search | 15231 | 119 | 53 | 58546.82 |
| 2026-05 | influencer | 570 | 11 | 1 | 93.53 |
| 2026-05 | meta_ads | 7920 | 99 | 27 | 24906.93 |
| 2026-05 | organic | 18443 | 226 | 61 | 59115.25 |
| 2026-05 | referral | 3729 | 41 | 15 | 12489.64 |
| 2026-05 | tiktok_ads | 1472 | 39 | 1 | 1069.2 |
| 2026-06 | google_search | 9659 | 151 | 44 | 36179.65 |
| 2026-06 | influencer | 309 | 12 | 2 | 123.38 |
| 2026-06 | meta_ads | 4206 | 115 | 12 | 10148.16 |
| 2026-06 | organic | 12363 | 291 | 54 | 35503.87 |
| 2026-06 | referral | 3301 | 71 | 13 | 10082.92 |
| 2026-06 | tiktok_ads | 1428 | 63 | 1 | 1438.56 |
| 2026-07 | affiliate_network | 847 | 375 | 1 | 219.78 |
| 2026-07 | google_search | 1947 | 70 | 22 | 10006.1 |
| 2026-07 | influencer | 1022 | 113 | 2 | 1435.59 |
| 2026-07 | meta_ads | 1562 | 125 | 7 | 1617.22 |
| 2026-07 | organic | 9341 | 585 | 60 | 17664.88 |
| 2026-07 | referral | 1924 | 93 | 12 | 6759.19 |
| 2026-07 | tiktok_ads | 2360 | 353 | 4 | 2078.68 |
| 2026-08 | affiliate_network | 1222 | 529 | 0 | 0 |
| 2026-08 | google_search | 608 | 38 | 8 | 1790.58 |
| 2026-08 | influencer | 569 | 110 | 1 | 13.93 |
| 2026-08 | meta_ads | 857 | 115 | 7 | 145.27 |
| 2026-08 | organic | 5673 | 567 | 43 | 6196.93 |
| 2026-08 | referral | 1088 | 93 | 5 | 1755.85 |
| 2026-08 | tiktok_ads | 2098 | 406 | 3 | 207.41 |
| 2026-09 | affiliate_network | 954 | 498 | 1 | 119.88 |
| 2026-09 | google_search | 158 | 32 | 3 | 213.73 |
| 2026-09 | influencer | 454 | 133 | 0 | 0 |
| 2026-09 | meta_ads | 416 | 101 | 4 | 267.7 |
| 2026-09 | organic | 2330 | 549 | 21 | 1074.87 |
| 2026-09 | referral | 583 | 120 | 2 | 139.86 |
| 2026-09 | tiktok_ads | 1351 | 406 | 2 | 65.91 |

_run_sql budget: 11/40 used_


### Step 15 · run_sql (12/40, 296 ms, ok)

**Purpose:** Quantify the revenue bridge month by month through MAU conversion, revenue per payer, subscriptions, PPV, refunds and failure attempts.

```sql
WITH a AS (SELECT substr(s.date,1,7) month,COUNT(DISTINCT s.user_id) mau FROM sessions s GROUP BY month), t AS (SELECT substr(date,1,7) month,COUNT(DISTINCT CASE WHEN status='success' AND amount_usd>0 THEN user_id END) payers,ROUND(SUM(CASE WHEN status='success' THEN amount_usd ELSE 0 END),2) net_revenue,ROUND(SUM(CASE WHEN status='success' AND type='subscription' THEN amount_usd ELSE 0 END),2) subscription_revenue,ROUND(SUM(CASE WHEN status='success' AND type='ppv' THEN amount_usd ELSE 0 END),2) ppv_revenue,ROUND(SUM(CASE WHEN status='success' AND type='refund' THEN amount_usd ELSE 0 END),2) refunds,COUNT(CASE WHEN status='failed' THEN 1 END) failed_attempts,COUNT(CASE WHEN status='success' AND amount_usd>0 THEN 1 END) positive_txns FROM transactions GROUP BY month) SELECT a.month,a.mau,t.payers,ROUND(t.payers*100.0/a.mau,2) payer_conversion,ROUND(t.net_revenue/a.mau,2) revenue_per_mau,ROUND(t.net_revenue/t.payers,2) revenue_per_payer,t.subscription_revenue,t.ppv_revenue,t.refunds,t.failed_attempts,t.positive_txns FROM a JOIN t USING(month) ORDER BY a.month
```

6 rows (296 ms)

| month | mau | payers | payer_conversion | revenue_per_mau | revenue_per_payer | subscription_revenue | ppv_revenue | refunds | failed_attempts | positive_txns |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-04 | 4243 | 837 | 19.73 | 1.49 | 7.57 | 5894.1 | 581.08 | -139.86 | 54 | 882 |
| 2026-05 | 4510 | 899 | 19.93 | 1.55 | 7.79 | 6423.57 | 703.87 | -119.88 | 60 | 956 |
| 2026-06 | 4594 | 990 | 21.55 | 1.62 | 7.53 | 6883.11 | 788.41 | -219.78 | 61 | 1048 |
| 2026-07 | 5123 | 850 | 16.59 | 1.43 | 8.63 | 7002.99 | 423.04 | -89.91 | 66 | 897 |
| 2026-08 | 5389 | 753 | 13.97 | 1.31 | 9.37 | 6782.21 | 471.43 | -199.8 | 226 | 793 |
| 2026-09 | 5473 | 687 | 12.55 | 1.08 | 8.61 | 5653.89 | 458.28 | -199.7 | 130 | 703 |

_run_sql budget: 12/40 used_


### Step 16 · run_sql (13/40, 1375 ms, ok)

**Purpose:** Test whether PPV revenue decline corresponds to fewer PPV views/viewers or weaker content engagement.

```sql
SELECT substr(v.date,1,7) month,v.view_type,COUNT(*) views,COUNT(DISTINCT v.user_id) users,ROUND(AVG(v.watch_duration_sec*1.0/NULLIF(v.content_duration_sec,0)),3) avg_watch_share,COUNT(DISTINCT CASE WHEN v.view_type='ppv' THEN v.user_id END) ppv_viewers FROM content_views v GROUP BY month,v.view_type ORDER BY month,v.view_type
```

18 rows (1375 ms)

| month | view_type | views | users | avg_watch_share | ppv_viewers |
|---|---|---|---|---|---|
| 2026-04 | free | 49276 | 3830 | 0.8 | 0 |
| 2026-04 | ppv | 292 | 271 | 0.796 | 271 |
| 2026-04 | sub | 30727 | 661 | 0.8 | 0 |
| 2026-05 | free | 53332 | 4026 | 0.8 | 0 |
| 2026-05 | ppv | 313 | 287 | 0.792 | 287 |
| 2026-05 | sub | 34562 | 718 | 0.8 | 0 |
| 2026-06 | free | 53946 | 4082 | 0.8 | 0 |
| 2026-06 | ppv | 359 | 323 | 0.796 | 323 |
| 2026-06 | sub | 36333 | 768 | 0.799 | 0 |
| 2026-07 | free | 65253 | 4336 | 0.799 | 0 |
| 2026-07 | ppv | 196 | 176 | 0.808 | 176 |
| 2026-07 | sub | 37703 | 758 | 0.8 | 0 |
| 2026-08 | free | 67780 | 4572 | 0.798 | 0 |
| 2026-08 | ppv | 194 | 174 | 0.815 | 174 |
| 2026-08 | sub | 35802 | 726 | 0.801 | 0 |
| 2026-09 | free | 67878 | 4721 | 0.798 | 0 |
| 2026-09 | ppv | 173 | 163 | 0.811 | 163 |
| 2026-09 | sub | 30661 | 612 | 0.8 | 0 |

_run_sql budget: 13/40 used_


### Step 17 · run_sql (14/40, 0 ms, ok)

**Purpose:** Check marketing channel spend and timing, particularly whether the low-converting affiliate audience growth coincides with an acquisition push.

```sql
SELECT channel,substr(date,1,7) month,COUNT(*) daily_rows,ROUND(SUM(spend_usd),2) spend, SUM(impressions) impressions,SUM(clicks) clicks FROM marketing_spend GROUP BY channel,month ORDER BY channel,month
```

27 rows (0 ms)

| channel | month | daily_rows | spend | impressions | clicks |
|---|---|---|---|---|---|
| affiliate_network | 2026-07 | 22 | 97.25 | NULL | 1287 |
| affiliate_network | 2026-08 | 31 | 135.75 | NULL | 1801 |
| affiliate_network | 2026-09 | 30 | 127.5 | NULL | 1690 |
| google_search | 2026-04 | 30 | 1644.1 | 136175 | 6725 |
| google_search | 2026-05 | 31 | 1741.93 | 149564 | 7330 |
| google_search | 2026-06 | 30 | 1621.54 | 133860 | 6591 |
| google_search | 2026-07 | 31 | 393.68 | 32947 | 1615 |
| google_search | 2026-08 | 31 | 255.53 | 21182 | 1063 |
| google_search | 2026-09 | 30 | 233.53 | 19876 | 977 |
| influencer | 2026-04 | 30 | 146.23 | 97449 | 864 |
| influencer | 2026-05 | 31 | 154.26 | 101864 | 893 |
| influencer | 2026-06 | 30 | 150.17 | 100750 | 891 |
| influencer | 2026-07 | 31 | 370.25 | 247611 | 2216 |
| influencer | 2026-08 | 31 | 406.19 | 270294 | 2435 |
| influencer | 2026-09 | 30 | 393.73 | 259900 | 2307 |
| meta_ads | 2026-04 | 30 | 1175.5 | 294166 | 3458 |
| meta_ads | 2026-05 | 31 | 1243.79 | 311670 | 3752 |
| meta_ads | 2026-06 | 30 | 1168.67 | 297069 | 3493 |
| meta_ads | 2026-07 | 31 | 617.9 | 155311 | 1852 |
| meta_ads | 2026-08 | 31 | 564.01 | 144284 | 1713 |
| meta_ads | 2026-09 | 30 | 540.42 | 135201 | 1579 |
| tiktok_ads | 2026-04 | 30 | 374.18 | 295898 | 4684 |
| tiktok_ads | 2026-05 | 31 | 380.53 | 303176 | 4775 |
| tiktok_ads | 2026-06 | 30 | 371.86 | 298913 | 4687 |
| tiktok_ads | 2026-07 | 31 | 860.16 | 677986 | 10816 |
| tiktok_ads | 2026-08 | 31 | 959.87 | 754805 | 12059 |
| tiktok_ads | 2026-09 | 30 | 886.57 | 713362 | 11645 |

_run_sql budget: 14/40 used_


### Step 18 · run_sql (15/40, 375 ms, ok)

**Purpose:** Measure quarter-active users, newly acquired active users, active payers and revenue by source without join multiplication, so cohort and acquisition-mix effects can be estimated.

```sql
WITH q_users AS (SELECT CASE WHEN s.date BETWEEN '2026-04-01' AND '2026-06-30' THEN 'Q2' ELSE 'Q3' END q,s.user_id FROM sessions s WHERE s.date BETWEEN '2026-04-01' AND '2026-09-30' GROUP BY q,s.user_id), tx_u AS (SELECT CASE WHEN date BETWEEN '2026-04-01' AND '2026-06-30' THEN 'Q2' ELSE 'Q3' END q,user_id,COUNT(DISTINCT CASE WHEN status='success' AND amount_usd>0 THEN user_id END) payer,ROUND(SUM(CASE WHEN status='success' THEN amount_usd ELSE 0 END),2) revenue FROM transactions WHERE date BETWEEN '2026-04-01' AND '2026-09-30' GROUP BY q,user_id) SELECT qu.q,u.acquisition_source,COUNT(*) quarter_active_users,COUNT(CASE WHEN u.signup_date BETWEEN CASE WHEN qu.q='Q2' THEN '2026-04-01' ELSE '2026-07-01' END AND CASE WHEN qu.q='Q2' THEN '2026-06-30' ELSE '2026-09-30' END THEN 1 END) new_signup_actives,COUNT(CASE WHEN tx_u.payer=1 THEN 1 END) active_payers,ROUND(SUM(COALESCE(tx_u.revenue,0)),2) revenue FROM q_users qu JOIN users u USING(user_id) LEFT JOIN tx_u ON tx_u.q=qu.q AND tx_u.user_id=qu.user_id GROUP BY qu.q,u.acquisition_source ORDER BY u.acquisition_source,qu.q
```

13 rows (375 ms)

| q | acquisition_source | quarter_active_users | new_signup_actives | active_payers | revenue |
|---|---|---|---|---|---|
| Q3 | affiliate_network | 1402 | 1402 | 2 | 19.98 |
| Q2 | google_search | 1600 | 788 | 600 | 8162.78 |
| Q3 | google_search | 1056 | 140 | 442 | 7515.68 |
| Q2 | influencer | 202 | 113 | 9 | 120.84 |
| Q3 | influencer | 427 | 356 | 10 | 119.75 |
| Q2 | meta_ads | 1100 | 652 | 218 | 2674.43 |
| Q3 | meta_ads | 856 | 341 | 145 | 2480.63 |
| Q2 | organic | 2769 | 1587 | 606 | 7709.63 |
| Q3 | organic | 3103 | 1701 | 530 | 7805.9 |
| Q2 | referral | 519 | 302 | 159 | 1840.33 |
| Q3 | referral | 583 | 306 | 126 | 2040.26 |
| Q2 | tiktok_ads | 746 | 527 | 26 | 276.62 |
| Q3 | tiktok_ads | 1400 | 1165 | 21 | 310.24 |

_run_sql budget: 15/40 used_


### Step 19 · run_sql (16/40, 0 ms, ok)

**Purpose:** Compare Q2 versus Q3 failure rates by method/product and quantify successful price anomalies' effect on reported revenue.

```sql
WITH q AS (SELECT CASE WHEN date BETWEEN '2026-04-01' AND '2026-06-30' THEN 'Q2' ELSE 'Q3' END period,* FROM transactions WHERE date BETWEEN '2026-04-01' AND '2026-09-30') SELECT period,payment_method,type,COUNT(CASE WHEN status='success' AND amount_usd>0 THEN 1 END) successful_positive,COUNT(CASE WHEN status='failed' THEN 1 END) failed,ROUND(100.0*COUNT(CASE WHEN status='failed' THEN 1 END)/NULLIF(COUNT(*),0),1) failed_share_of_attempt_rows,COUNT(CASE WHEN status='success' AND type='subscription' AND amount_usd<>9.99 THEN 1 END) nonstandard_subscription_successes,ROUND(SUM(CASE WHEN status='success' AND type='subscription' AND amount_usd<>9.99 THEN amount_usd ELSE 0 END),2) nonstandard_subscription_success_revenue,COUNT(CASE WHEN status='success' AND type='ppv' AND amount_usd NOT IN (1.99,2.99) THEN 1 END) nonstandard_ppv_successes,ROUND(SUM(CASE WHEN status='success' AND type='ppv' AND amount_usd NOT IN (1.99,2.99) THEN amount_usd ELSE 0 END),2) nonstandard_ppv_revenue FROM q GROUP BY period,payment_method,type ORDER BY period,payment_method,type
```

44 rows (0 ms)

| period | payment_method | type | successful_positive | failed | failed_share_of_attempt_rows | nonstandard_subscription_successes | nonstandard_subscription_success_revenue | nonstandard_ppv_successes | nonstandard_ppv_revenue |
|---|---|---|---|---|---|---|---|---|---|
| Q2 | apple_iap | ppv | 385 | 12 | 3 | 0 | 0 | 0 | 0 |
| Q2 | apple_iap | refund | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Q2 | apple_iap | subscription | 779 | 33 | 4.1 | 0 | 0 | 0 | 0 |
| Q2 | card | ppv | 156 | 11 | 6.6 | 0 | 0 | 0 | 0 |
| Q2 | card | refund | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Q2 | card | subscription | 334 | 32 | 8.7 | 0 | 0 | 0 | 0 |
| Q2 | ewallet | ppv | 25 | 0 | 0 | 0 | 0 | 0 | 0 |
| Q2 | ewallet | subscription | 55 | 3 | 5.2 | 0 | 0 | 0 | 0 |
| Q2 | google_play | ppv | 263 | 19 | 6.7 | 0 | 0 | 0 | 0 |
| Q2 | google_play | refund | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Q2 | google_play | subscription | 484 | 32 | 6.2 | 0 | 0 | 0 | 0 |
| Q2 | oxxo | ppv | 36 | 8 | 18.2 | 0 | 0 | 0 | 0 |
| Q2 | oxxo | refund | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Q2 | oxxo | subscription | 65 | 8 | 11 | 0 | 0 | 0 | 0 |
| Q2 | paypal | ppv | 21 | 0 | 0 | 0 | 0 | 0 | 0 |
| Q2 | paypal | subscription | 43 | 0 | 0 | 0 | 0 | 0 | 0 |
| Q2 | pix | ppv | 63 | 5 | 7.4 | 0 | 0 | 0 | 0 |
| Q2 | pix | refund | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Q2 | pix | subscription | 140 | 9 | 6 | 0 | 0 | 0 | 0 |
| Q2 | pse | ppv | 15 | 1 | 6.3 | 0 | 0 | 0 | 0 |
| Q2 | pse | refund | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Q2 | pse | subscription | 22 | 2 | 8.3 | 0 | 0 | 0 | 0 |
| Q3 | apple_iap | ppv | 227 | 13 | 5.4 | 0 | 0 | 0 | 0 |
| Q3 | apple_iap | refund | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Q3 | apple_iap | subscription | 809 | 36 | 4.3 | 0 | 0 | 0 | 0 |
| Q3 | card | ppv | 111 | 12 | 9.8 | 0 | 0 | 0 | 0 |
| Q3 | card | refund | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Q3 | card | subscription | 340 | 32 | 8.6 | 0 | 0 | 0 | 0 |
| Q3 | ewallet | ppv | 17 | 2 | 10.5 | 0 | 0 | 0 | 0 |
| Q3 | ewallet | refund | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Q3 | ewallet | subscription | 56 | 12 | 17.6 | 0 | 0 | 0 | 0 |
| Q3 | google_play | ppv | 137 | 9 | 6.2 | 0 | 0 | 0 | 0 |
| Q3 | google_play | refund | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Q3 | google_play | subscription | 460 | 46 | 9.1 | 0 | 0 | 0 | 0 |
| Q3 | oxxo | ppv | 16 | 27 | 62.8 | 0 | 0 | 0 | 0 |
| Q3 | oxxo | refund | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Q3 | oxxo | subscription | 40 | 56 | 58.3 | 0 | 0 | 0 | 0 |
| Q3 | paypal | ppv | 15 | 0 | 0 | 0 | 0 | 0 | 0 |
| Q3 | paypal | subscription | 39 | 3 | 7.1 | 0 | 0 | 0 | 0 |
| Q3 | pix | ppv | 32 | 23 | 41.8 | 0 | 0 | 18 | 193.2 |
| Q3 | pix | refund | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Q3 | pix | subscription | 75 | 119 | 61.3 | 29 | 1447.1 | 0 | 0 |
| Q3 | pse | ppv | 8 | 6 | 42.9 | 0 | 0 | 0 | 0 |
| Q3 | pse | subscription | 11 | 26 | 70.3 | 0 | 0 | 0 | 0 |

_run_sql budget: 16/40 used_


### Step 20 · run_sql (17/40, 16 ms, ok)

**Purpose:** Determine whether the Q3 failed-payment spike is geographically concentrated and whether it is driven by a specific local payment method or unusual accounts.

```sql
SELECT u.country,t.payment_method,t.type,t.status,COUNT(*) n,COUNT(DISTINCT t.user_id) users,ROUND(SUM(t.amount_usd),2) amount,MIN(t.amount_usd) min_amount,MAX(t.amount_usd) max_amount FROM transactions t JOIN users u USING(user_id) WHERE t.date BETWEEN '2026-07-01' AND '2026-09-30' GROUP BY u.country,t.payment_method,t.type,t.status ORDER BY n DESC LIMIT 60
```

60 rows (16 ms)

| country | payment_method | type | status | n | users | amount | min_amount | max_amount |
|---|---|---|---|---|---|---|---|---|
| US | apple_iap | subscription | success | 654 | 301 | 6533.46 | 9.99 | 9.99 |
| US | card | subscription | success | 210 | 93 | 2097.9 | 9.99 | 9.99 |
| US | google_play | subscription | success | 203 | 100 | 2027.97 | 9.99 | 9.99 |
| US | apple_iap | ppv | success | 191 | 153 | 403.09 | 1.99 | 2.99 |
| BR | pix | subscription | failed | 119 | 49 | 5698.64 | 9.99 | 49.9 |
| BR | pix | subscription | success | 75 | 51 | 1906.64 | 9.99 | 49.9 |
| US | google_play | ppv | success | 70 | 61 | 151.3 | 1.99 | 2.99 |
| US | card | ppv | success | 61 | 50 | 128.39 | 1.99 | 2.99 |
| MX | oxxo | subscription | failed | 56 | 22 | 559.44 | 9.99 | 9.99 |
| MX | apple_iap | subscription | success | 54 | 22 | 539.46 | 9.99 | 9.99 |
| BR | google_play | subscription | success | 50 | 22 | 499.5 | 9.99 | 9.99 |
| BR | apple_iap | subscription | success | 48 | 20 | 479.52 | 9.99 | 9.99 |
| PH | google_play | subscription | success | 47 | 19 | 469.53 | 9.99 | 9.99 |
| BR | card | subscription | success | 46 | 21 | 459.54 | 9.99 | 9.99 |
| MX | google_play | subscription | success | 40 | 17 | 399.6 | 9.99 | 9.99 |
| MX | oxxo | subscription | success | 40 | 27 | 399.6 | 9.99 | 9.99 |
| US | paypal | subscription | success | 39 | 17 | 389.61 | 9.99 | 9.99 |
| ID | google_play | subscription | success | 34 | 16 | 339.66 | 9.99 | 9.99 |
| BR | pix | ppv | success | 32 | 28 | 224.06 | 1.99 | 14.9 |
| US | apple_iap | subscription | failed | 29 | 17 | 289.71 | 9.99 | 9.99 |
| VN | google_play | subscription | success | 28 | 12 | 279.72 | 9.99 | 9.99 |
| ID | ewallet | subscription | success | 27 | 11 | 269.73 | 9.99 | 9.99 |
| MX | oxxo | ppv | failed | 27 | 17 | 54.73 | 1.99 | 2.99 |
| TH | google_play | subscription | success | 27 | 13 | 269.73 | 9.99 | 9.99 |
| CO | google_play | subscription | success | 26 | 11 | 259.74 | 9.99 | 9.99 |
| CO | pse | subscription | failed | 26 | 9 | 259.74 | 9.99 | 9.99 |
| MX | card | subscription | success | 26 | 17 | 259.74 | 9.99 | 9.99 |
| BR | pix | ppv | failed | 23 | 17 | 232.7 | 9.9 | 14.9 |
| BR | google_play | ppv | success | 20 | 16 | 39.8 | 1.99 | 1.99 |
| PH | card | subscription | success | 20 | 9 | 199.8 | 9.99 | 9.99 |
| US | card | subscription | failed | 20 | 14 | 199.8 | 9.99 | 9.99 |
| MX | card | ppv | success | 19 | 17 | 41.81 | 1.99 | 2.99 |
| PH | ewallet | subscription | success | 19 | 8 | 189.81 | 9.99 | 9.99 |
| US | apple_iap | refund | success | 18 | 18 | -179.82 | -9.99 | -9.99 |
| USA | apple_iap | subscription | success | 18 | 7 | 179.82 | 9.99 | 9.99 |
| BR | card | ppv | success | 16 | 15 | 32.84 | 1.99 | 2.99 |
| MX | oxxo | ppv | success | 16 | 15 | 32.84 | 1.99 | 2.99 |
| MX | google_play | ppv | success | 15 | 11 | 32.85 | 1.99 | 2.99 |
| US | paypal | ppv | success | 15 | 12 | 31.85 | 1.99 | 2.99 |
| PH | apple_iap | subscription | success | 13 | 5 | 129.87 | 9.99 | 9.99 |
| US | google_play | subscription | failed | 13 | 7 | 129.87 | 9.99 | 9.99 |
| ID | card | subscription | success | 12 | 6 | 119.88 | 9.99 | 9.99 |
| MX | apple_iap | ppv | success | 12 | 8 | 24.88 | 1.99 | 2.99 |
| TH | card | subscription | success | 12 | 5 | 119.88 | 9.99 | 9.99 |
| CO | pse | subscription | success | 11 | 9 | 109.89 | 9.99 | 9.99 |
| ID | google_play | ppv | success | 11 | 11 | 25.89 | 1.99 | 2.99 |
| PH | google_play | subscription | failed | 11 | 5 | 109.89 | 9.99 | 9.99 |
| US | apple_iap | ppv | failed | 11 | 8 | 23.89 | 1.99 | 2.99 |
| BR | apple_iap | ppv | success | 9 | 8 | 19.91 | 1.99 | 2.99 |
| CO | pse | ppv | success | 8 | 5 | 16.92 | 1.99 | 2.99 |
| PH | google_play | ppv | success | 8 | 8 | 16.92 | 1.99 | 2.99 |
| TH | google_play | ppv | success | 8 | 8 | 17.92 | 1.99 | 2.99 |
| USA | card | subscription | success | 8 | 4 | 79.92 | 9.99 | 9.99 |
| CO | apple_iap | subscription | success | 7 | 5 | 69.93 | 9.99 | 9.99 |
| ID | ewallet | ppv | success | 7 | 7 | 14.93 | 1.99 | 2.99 |
| ID | google_play | subscription | failed | 7 | 4 | 69.93 | 9.99 | 9.99 |
| TH | ewallet | subscription | success | 7 | 5 | 69.93 | 9.99 | 9.99 |
| US | card | ppv | failed | 7 | 5 | 13.93 | 1.99 | 1.99 |
| VN | apple_iap | subscription | success | 7 | 3 | 69.93 | 9.99 | 9.99 |
| CO | apple_iap | ppv | success | 6 | 5 | 11.94 | 1.99 | 1.99 |

_run_sql budget: 17/40 used_


### Step 21 · run_sql (18/40, 1405 ms, ok)

**Purpose:** Audit user acquisition cohort sizes and Q3 actives/payers using deduplicated date records, avoiding inflated counts from joining raw event logs.

```sql
SELECT u.acquisition_source,substr(u.signup_date,1,7) signup_month,COUNT(*) users,COUNT(DISTINCT CASE WHEN s.date BETWEEN '2026-07-01' AND '2026-09-30' THEN u.user_id END) q3_active_users,COUNT(DISTINCT CASE WHEN t.date BETWEEN '2026-07-01' AND '2026-09-30' AND t.status='success' AND t.amount_usd>0 THEN u.user_id END) q3_payers FROM users u LEFT JOIN (SELECT DISTINCT user_id,date FROM sessions) s USING(user_id) LEFT JOIN (SELECT DISTINCT user_id,date,status,amount_usd FROM transactions) t USING(user_id) GROUP BY u.acquisition_source,signup_month ORDER BY signup_month,u.acquisition_source
```

75 rows (1405 ms)

| acquisition_source | signup_month | users | q3_active_users | q3_payers |
|---|---|---|---|---|
| google_search | 2025-10 | 24753 | 117 | 63 |
| influencer | 2025-10 | 317 | 7 | 0 |
| meta_ads | 2025-10 | 5770 | 48 | 16 |
| organic | 2025-10 | 21755 | 144 | 50 |
| referral | 2025-10 | 6004 | 30 | 19 |
| tiktok_ads | 2025-10 | 782 | 13 | 1 |
| google_search | 2025-11 | 13383 | 67 | 32 |
| influencer | 2025-11 | 558 | 3 | 1 |
| meta_ads | 2025-11 | 5044 | 33 | 11 |
| organic | 2025-11 | 15558 | 107 | 41 |
| referral | 2025-11 | 3307 | 18 | 10 |
| tiktok_ads | 2025-11 | 922 | 13 | 2 |
| google_search | 2025-12 | 13151 | 65 | 34 |
| influencer | 2025-12 | 308 | 6 | 0 |
| meta_ads | 2025-12 | 5568 | 40 | 12 |
| organic | 2025-12 | 15313 | 97 | 39 |
| referral | 2025-12 | 2740 | 15 | 8 |
| tiktok_ads | 2025-12 | 812 | 17 | 1 |
| google_search | 2026-01 | 18121 | 98 | 51 |
| influencer | 2026-01 | 423 | 6 | 2 |
| meta_ads | 2026-01 | 5092 | 34 | 11 |
| organic | 2026-01 | 13728 | 114 | 36 |
| referral | 2026-01 | 2558 | 23 | 7 |
| tiktok_ads | 2026-01 | 718 | 14 | 1 |
| google_search | 2026-02 | 14304 | 94 | 44 |
| influencer | 2026-02 | 303 | 7 | 0 |
| meta_ads | 2026-02 | 4303 | 33 | 9 |
| organic | 2026-02 | 14850 | 128 | 40 |
| referral | 2026-02 | 3897 | 19 | 11 |
| tiktok_ads | 2026-02 | 589 | 13 | 0 |
| google_search | 2026-03 | 14546 | 102 | 43 |
| influencer | 2026-03 | 367 | 12 | 0 |
| meta_ads | 2026-03 | 7905 | 54 | 20 |
| organic | 2026-03 | 11714 | 119 | 32 |
| referral | 2026-03 | 4160 | 24 | 11 |
| tiktok_ads | 2026-03 | 921 | 23 | 0 |
| google_search | 2026-04 | 14331 | 103 | 45 |
| influencer | 2026-04 | 458 | 7 | 1 |
| meta_ads | 2026-04 | 3203 | 59 | 10 |
| organic | 2026-04 | 15798 | 176 | 53 |
| referral | 2026-04 | 3282 | 36 | 13 |
| tiktok_ads | 2026-04 | 1949 | 40 | 5 |
| google_search | 2026-05 | 10230 | 119 | 53 |
| influencer | 2026-05 | 400 | 11 | 1 |
| meta_ads | 2026-05 | 5345 | 99 | 27 |
| organic | 2026-05 | 12384 | 226 | 61 |
| referral | 2026-05 | 2593 | 41 | 15 |
| tiktok_ads | 2026-05 | 1041 | 39 | 1 |
| google_search | 2026-06 | 6532 | 151 | 44 |
| influencer | 2026-06 | 203 | 12 | 2 |
| meta_ads | 2026-06 | 2873 | 115 | 12 |
| organic | 2026-06 | 8473 | 291 | 54 |
| referral | 2026-06 | 2176 | 71 | 13 |
| tiktok_ads | 2026-06 | 1013 | 63 | 1 |
| affiliate_network | 2026-07 | 663 | 375 | 1 |
| google_search | 2026-07 | 1346 | 70 | 22 |
| influencer | 2026-07 | 693 | 113 | 2 |
| meta_ads | 2026-07 | 1082 | 125 | 7 |
| organic | 2026-07 | 6345 | 585 | 60 |
| referral | 2026-07 | 1346 | 93 | 12 |
| tiktok_ads | 2026-07 | 1637 | 353 | 4 |
| affiliate_network | 2026-08 | 931 | 529 | 0 |
| google_search | 2026-08 | 421 | 38 | 8 |
| influencer | 2026-08 | 405 | 110 | 1 |
| meta_ads | 2026-08 | 604 | 115 | 7 |
| organic | 2026-08 | 3829 | 567 | 43 |
| referral | 2026-08 | 731 | 93 | 5 |
| tiktok_ads | 2026-08 | 1440 | 406 | 3 |
| affiliate_network | 2026-09 | 767 | 498 | 1 |
| google_search | 2026-09 | 107 | 32 | 3 |
| influencer | 2026-09 | 304 | 133 | 0 |
| meta_ads | 2026-09 | 298 | 101 | 4 |
| organic | 2026-09 | 1619 | 549 | 21 |
| referral | 2026-09 | 394 | 120 | 2 |
| tiktok_ads | 2026-09 | 946 | 406 | 2 |

_run_sql budget: 18/40 used_


### Step 22 · run_sql (19/40, 141 ms, ok)

**Purpose:** Correctly calculate Q3 active signups and monetization by signup cohort and source using one row per user and pre-aggregated transactions.

```sql
WITH q_users AS (SELECT 'Q3' q,s.user_id FROM sessions s WHERE s.date BETWEEN '2026-07-01' AND '2026-09-30' GROUP BY s.user_id), tx_u AS (SELECT user_id,COUNT(DISTINCT CASE WHEN status='success' AND amount_usd>0 THEN user_id END) payer,ROUND(SUM(CASE WHEN status='success' THEN amount_usd ELSE 0 END),2) revenue FROM transactions WHERE date BETWEEN '2026-07-01' AND '2026-09-30' GROUP BY user_id) SELECT substr(u.signup_date,1,7) signup_month,u.acquisition_source,COUNT(*) active_users,COUNT(CASE WHEN tx_u.payer=1 THEN 1 END) payers,ROUND(SUM(COALESCE(tx_u.revenue,0)),2) revenue FROM q_users JOIN users u USING(user_id) LEFT JOIN tx_u USING(user_id) GROUP BY signup_month,u.acquisition_source ORDER BY signup_month,u.acquisition_source
```

75 rows (141 ms)

| signup_month | acquisition_source | active_users | payers | revenue |
|---|---|---|---|---|
| 2025-10 | google_search | 117 | 63 | 1082.7 |
| 2025-10 | influencer | 7 | 0 | 0 |
| 2025-10 | meta_ads | 48 | 16 | 240.63 |
| 2025-10 | organic | 144 | 50 | 895.01 |
| 2025-10 | referral | 30 | 19 | 350.61 |
| 2025-10 | tiktok_ads | 13 | 1 | 9.99 |
| 2025-11 | google_search | 67 | 32 | 675.26 |
| 2025-11 | influencer | 3 | 1 | 29.97 |
| 2025-11 | meta_ads | 33 | 11 | 208.62 |
| 2025-11 | organic | 107 | 41 | 830.99 |
| 2025-11 | referral | 18 | 10 | 149.82 |
| 2025-11 | tiktok_ads | 13 | 2 | 31.96 |
| 2025-12 | google_search | 65 | 34 | 688.1 |
| 2025-12 | influencer | 6 | 0 | 0 |
| 2025-12 | meta_ads | 40 | 12 | 265.62 |
| 2025-12 | organic | 97 | 39 | 715.14 |
| 2025-12 | referral | 15 | 8 | 234.65 |
| 2025-12 | tiktok_ads | 17 | 1 | 1.99 |
| 2026-01 | google_search | 98 | 51 | 867.99 |
| 2026-01 | influencer | 6 | 2 | 11.98 |
| 2026-01 | meta_ads | 34 | 11 | 241.75 |
| 2026-01 | organic | 114 | 36 | 732.91 |
| 2026-01 | referral | 23 | 7 | 101.89 |
| 2026-01 | tiktok_ads | 14 | 1 | 9.99 |
| 2026-02 | google_search | 94 | 44 | 806.01 |
| 2026-02 | influencer | 7 | 0 | 0 |
| 2026-02 | meta_ads | 33 | 9 | 203.78 |
| 2026-02 | organic | 128 | 40 | 706.1 |
| 2026-02 | referral | 19 | 11 | 210.75 |
| 2026-02 | tiktok_ads | 13 | 0 | 0 |
| 2026-03 | google_search | 102 | 43 | 739.11 |
| 2026-03 | influencer | 12 | 0 | 0 |
| 2026-03 | meta_ads | 54 | 20 | 554.33 |
| 2026-03 | organic | 119 | 32 | 527.26 |
| 2026-03 | referral | 24 | 11 | 187.78 |
| 2026-03 | tiktok_ads | 23 | 0 | 0 |
| 2026-04 | google_search | 103 | 45 | 825.98 |
| 2026-04 | influencer | 7 | 1 | 29.97 |
| 2026-04 | meta_ads | 59 | 10 | 90.87 |
| 2026-04 | organic | 176 | 53 | 924.91 |
| 2026-04 | referral | 36 | 13 | 161.79 |
| 2026-04 | tiktok_ads | 40 | 5 | 83.85 |
| 2026-05 | google_search | 119 | 53 | 817.89 |
| 2026-05 | influencer | 11 | 1 | 1.99 |
| 2026-05 | meta_ads | 99 | 26 | 385.47 |
| 2026-05 | organic | 226 | 61 | 916.68 |
| 2026-05 | referral | 41 | 15 | 194.75 |
| 2026-05 | tiktok_ads | 39 | 1 | 19.8 |
| 2026-06 | google_search | 151 | 44 | 673.13 |
| 2026-06 | influencer | 12 | 2 | 3.98 |
| 2026-06 | meta_ads | 115 | 12 | 192.76 |
| 2026-06 | organic | 291 | 54 | 687.99 |
| 2026-06 | referral | 71 | 13 | 190.64 |
| 2026-06 | tiktok_ads | 63 | 1 | 29.97 |
| 2026-07 | affiliate_network | 375 | 1 | 9.99 |
| 2026-07 | google_search | 70 | 22 | 247.64 |
| 2026-07 | influencer | 113 | 2 | 39.87 |
| 2026-07 | meta_ads | 125 | 7 | 50.91 |
| 2026-07 | organic | 585 | 60 | 472.09 |
| 2026-07 | referral | 93 | 12 | 171.69 |
| 2026-07 | tiktok_ads | 353 | 4 | 95.83 |
| 2026-08 | affiliate_network | 529 | 0 | 0 |
| 2026-08 | google_search | 38 | 8 | 69.9 |
| 2026-08 | influencer | 110 | 1 | 1.99 |
| 2026-08 | meta_ads | 115 | 7 | 13.93 |
| 2026-08 | organic | 567 | 43 | 291.21 |
| 2026-08 | referral | 93 | 5 | 65.91 |
| 2026-08 | tiktok_ads | 406 | 3 | 14.88 |
| 2026-09 | affiliate_network | 498 | 1 | 9.99 |
| 2026-09 | google_search | 32 | 3 | 21.97 |
| 2026-09 | influencer | 133 | 0 | 0 |
| 2026-09 | meta_ads | 101 | 4 | 31.96 |
| 2026-09 | organic | 549 | 21 | 105.61 |
| 2026-09 | referral | 120 | 2 | 19.98 |
| 2026-09 | tiktok_ads | 406 | 2 | 11.98 |

_run_sql budget: 19/40 used_


### Step 23 · run_sql (20/40, 608 ms, ok)

**Purpose:** Separate geographic audience mix from within-country monetization changes and consolidate the USA/US spelling variants.

```sql
WITH a AS (SELECT CASE WHEN u.country='USA' THEN 'US' ELSE u.country END country,CASE WHEN s.date BETWEEN '2026-04-01' AND '2026-06-30' THEN 'Q2' ELSE 'Q3' END q,COUNT(DISTINCT s.user_id) active_users FROM sessions s JOIN users u USING(user_id) WHERE s.date BETWEEN '2026-04-01' AND '2026-09-30' GROUP BY country,q),r AS (SELECT CASE WHEN u.country='USA' THEN 'US' ELSE u.country END country,CASE WHEN t.date BETWEEN '2026-04-01' AND '2026-06-30' THEN 'Q2' ELSE 'Q3' END q,ROUND(SUM(CASE WHEN t.status='success' THEN t.amount_usd ELSE 0 END),2) revenue FROM transactions t JOIN users u USING(user_id) WHERE t.date BETWEEN '2026-04-01' AND '2026-09-30' GROUP BY country,q),x AS (SELECT a.country,a.q,a.active_users,COALESCE(r.revenue,0) revenue,COALESCE(r.revenue,0)*1.0/a.active_users rate FROM a LEFT JOIN r USING(country,q)),bridge AS (SELECT country,MAX(CASE WHEN q='Q2' THEN active_users END) q2_active,MAX(CASE WHEN q='Q3' THEN active_users END) q3_active,MAX(CASE WHEN q='Q2' THEN revenue END) q2_revenue,MAX(CASE WHEN q='Q3' THEN revenue END) q3_revenue,MAX(CASE WHEN q='Q2' THEN rate END) q2_rate,MAX(CASE WHEN q='Q3' THEN rate END) q3_rate FROM x GROUP BY country) SELECT country,q2_active,q3_active,ROUND(q2_revenue,2) q2_revenue,ROUND(q3_revenue,2) q3_revenue,ROUND(q2_rate,3) q2_revenue_per_active,ROUND(q3_rate,3) q3_revenue_per_active,ROUND((q3_active-q2_active)*q2_rate,2) mix_effect_usd,ROUND(q3_active*(q3_rate-q2_rate),2) within_country_effect_usd FROM bridge ORDER BY country
```

8 rows (608 ms)

| country | q2_active | q3_active | q2_revenue | q3_revenue | q2_revenue_per_active | q3_revenue_per_active | mix_effect_usd | within_country_effect_usd |
|---|---|---|---|---|---|---|---|---|
| BR | 960 | 1067 | 2924.95 | 3542.03 | 3.047 | 3.32 | 326.01 | 291.07 |
| CO | 285 | 366 | 675.06 | 524.31 | 2.369 | 1.433 | 191.86 | -342.61 |
| ID | 673 | 1461 | 667.05 | 819.01 | 0.991 | 0.561 | 781.03 | -629.07 |
| MX | 742 | 816 | 2108.16 | 1680.83 | 2.841 | 2.06 | 210.25 | -637.58 |
| PH | 617 | 1290 | 1083.59 | 1001.84 | 1.756 | 0.777 | 1181.94 | -1263.69 |
| TH | 409 | 500 | 556.23 | 532.31 | 1.36 | 1.065 | 123.76 | -147.68 |
| US | 2901 | 2606 | 12014.55 | 11513.82 | 324.718 | 500.601 | -95791.68 | 458351.89 |
| VN | 312 | 698 | 380.51 | 376.6 | 1.22 | 0.54 | 470.76 | -474.67 |

_run_sql budget: 20/40 used_


### Step 24 · run_sql (21/40, 16 ms, ok)

**Purpose:** Quantify Q2-to-Q3 marketing budget shifts across channels to relate investment changes to active-user growth and monetization quality.

```sql
SELECT CASE WHEN date BETWEEN '2026-04-01' AND '2026-06-30' THEN 'Q2' ELSE 'Q3' END q,channel,ROUND(SUM(spend_usd),2) spend, SUM(clicks) clicks,SUM(impressions) impressions FROM marketing_spend GROUP BY q,channel ORDER BY channel,q
```

9 rows (16 ms)

| q | channel | spend | clicks | impressions |
|---|---|---|---|---|
| Q3 | affiliate_network | 360.5 | 4778 | NULL |
| Q2 | google_search | 5007.57 | 20646 | 419599 |
| Q3 | google_search | 882.74 | 3655 | 74005 |
| Q2 | influencer | 450.66 | 2648 | 300063 |
| Q3 | influencer | 1170.17 | 6958 | 777805 |
| Q2 | meta_ads | 3587.96 | 10703 | 902905 |
| Q3 | meta_ads | 1722.33 | 5144 | 434796 |
| Q2 | tiktok_ads | 1126.57 | 14146 | 897987 |
| Q3 | tiktok_ads | 2706.6 | 34520 | 2146153 |

_run_sql budget: 21/40 used_


### Step 25 · run_sql (22/40, 0 ms, ok)

**Purpose:** Track timing, unique failed customers and successful purchases for Brazil's Pix, Mexico's Oxxo and Colombia's PSE local payment methods.

```sql
SELECT substr(date,1,7) month,payment_method,type,COUNT(CASE WHEN status='failed' THEN 1 END) failed_attempts,COUNT(DISTINCT CASE WHEN status='failed' THEN user_id END) failed_users,COUNT(CASE WHEN status='success' AND amount_usd>0 THEN 1 END) successful_sales,COUNT(DISTINCT CASE WHEN status='success' AND amount_usd>0 THEN user_id END) successful_users,ROUND(SUM(CASE WHEN status='success' THEN amount_usd ELSE 0 END),2) net_success_revenue FROM transactions WHERE payment_method IN ('pix','oxxo','pse') GROUP BY month,payment_method,type ORDER BY month,payment_method,type
```

44 rows (0 ms)

| month | payment_method | type | failed_attempts | failed_users | successful_sales | successful_users | net_success_revenue |
|---|---|---|---|---|---|---|---|
| 2026-04 | oxxo | ppv | 3 | 2 | 11 | 11 | 21.89 |
| 2026-04 | oxxo | subscription | 0 | 0 | 24 | 24 | 239.76 |
| 2026-04 | pix | ppv | 1 | 1 | 22 | 21 | 43.78 |
| 2026-04 | pix | refund | 0 | 0 | 0 | 0 | -9.99 |
| 2026-04 | pix | subscription | 3 | 2 | 40 | 40 | 399.6 |
| 2026-04 | pse | subscription | 2 | 1 | 6 | 6 | 59.94 |
| 2026-05 | oxxo | ppv | 2 | 2 | 11 | 11 | 21.89 |
| 2026-05 | oxxo | refund | 0 | 0 | 0 | 0 | -19.98 |
| 2026-05 | oxxo | subscription | 1 | 1 | 21 | 20 | 209.79 |
| 2026-05 | pix | ppv | 1 | 1 | 20 | 19 | 46.8 |
| 2026-05 | pix | refund | 0 | 0 | 0 | 0 | -19.98 |
| 2026-05 | pix | subscription | 4 | 2 | 51 | 48 | 509.49 |
| 2026-05 | pse | ppv | 1 | 1 | 5 | 5 | 11.95 |
| 2026-05 | pse | subscription | 0 | 0 | 7 | 7 | 69.93 |
| 2026-06 | oxxo | ppv | 3 | 3 | 14 | 13 | 32.86 |
| 2026-06 | oxxo | subscription | 7 | 3 | 20 | 20 | 199.8 |
| 2026-06 | pix | ppv | 3 | 2 | 21 | 19 | 43.79 |
| 2026-06 | pix | refund | 0 | 0 | 0 | 0 | -29.97 |
| 2026-06 | pix | subscription | 2 | 2 | 49 | 49 | 489.51 |
| 2026-06 | pse | ppv | 0 | 0 | 10 | 8 | 22.9 |
| 2026-06 | pse | refund | 0 | 0 | 0 | 0 | -9.99 |
| 2026-06 | pse | subscription | 0 | 0 | 9 | 9 | 89.91 |
| 2026-07 | oxxo | ppv | 2 | 1 | 8 | 7 | 15.92 |
| 2026-07 | oxxo | refund | 0 | 0 | 0 | 0 | -9.99 |
| 2026-07 | oxxo | subscription | 1 | 1 | 24 | 23 | 239.76 |
| 2026-07 | pix | ppv | 0 | 0 | 14 | 13 | 30.86 |
| 2026-07 | pix | refund | 0 | 0 | 0 | 0 | -9.99 |
| 2026-07 | pix | subscription | 6 | 3 | 46 | 45 | 459.54 |
| 2026-07 | pse | ppv | 0 | 0 | 5 | 2 | 9.95 |
| 2026-07 | pse | subscription | 0 | 0 | 7 | 7 | 69.93 |
| 2026-08 | oxxo | ppv | 14 | 10 | 4 | 4 | 8.96 |
| 2026-08 | oxxo | refund | 0 | 0 | 0 | 0 | -9.99 |
| 2026-08 | oxxo | subscription | 43 | 16 | 9 | 9 | 89.91 |
| 2026-08 | pix | ppv | 11 | 8 | 7 | 7 | 79.3 |
| 2026-08 | pix | subscription | 74 | 33 | 20 | 20 | 998 |
| 2026-08 | pse | ppv | 3 | 2 | 1 | 1 | 1.99 |
| 2026-08 | pse | subscription | 19 | 7 | 2 | 2 | 19.98 |
| 2026-09 | oxxo | ppv | 11 | 7 | 4 | 4 | 7.96 |
| 2026-09 | oxxo | subscription | 12 | 8 | 7 | 7 | 69.93 |
| 2026-09 | pix | ppv | 12 | 9 | 11 | 10 | 113.9 |
| 2026-09 | pix | refund | 0 | 0 | 0 | 0 | -99.8 |
| 2026-09 | pix | subscription | 39 | 20 | 9 | 9 | 449.1 |
| 2026-09 | pse | ppv | 3 | 2 | 2 | 2 | 4.98 |
| 2026-09 | pse | subscription | 7 | 3 | 2 | 2 | 19.98 |

_run_sql budget: 22/40 used_


### Step 26 · run_sql (23/40, 0 ms, ok)

**Purpose:** Inspect exact successful Pix amount values by month to quantify pricing/record anomalies and their contribution to Q3 revenue.

```sql
SELECT substr(date,1,7) month,payment_method,type,status,amount_usd,COUNT(*) rows,COUNT(DISTINCT user_id) users FROM transactions WHERE payment_method='pix' AND date>='2026-07-01' AND status='success' GROUP BY month,payment_method,type,status,amount_usd ORDER BY month,type,amount_usd
```

11 rows (0 ms)

| month | payment_method | type | status | amount_usd | rows | users |
|---|---|---|---|---|---|---|
| 2026-07 | pix | ppv | success | 1.99 | 11 | 11 |
| 2026-07 | pix | ppv | success | 2.99 | 3 | 2 |
| 2026-07 | pix | refund | success | -9.99 | 1 | 1 |
| 2026-07 | pix | subscription | success | 9.99 | 46 | 45 |
| 2026-08 | pix | ppv | success | 9.9 | 5 | 5 |
| 2026-08 | pix | ppv | success | 14.9 | 2 | 2 |
| 2026-08 | pix | subscription | success | 49.9 | 20 | 20 |
| 2026-09 | pix | ppv | success | 9.9 | 10 | 9 |
| 2026-09 | pix | ppv | success | 14.9 | 1 | 1 |
| 2026-09 | pix | refund | success | -49.9 | 2 | 2 |
| 2026-09 | pix | subscription | success | 49.9 | 9 | 9 |

_run_sql budget: 23/40 used_


### Step 27 · run_sql (24/40, 453 ms, ok)

**Purpose:** Recalculate the geographic mix versus within-country revenue bridge with deduplicated user-quarter activity and explicit country normalization.

```sql
WITH a0 AS (SELECT s.user_id,CASE WHEN s.date BETWEEN '2026-04-01' AND '2026-06-30' THEN 'Q2' ELSE 'Q3' END q,u.country FROM sessions s JOIN users u USING(user_id) WHERE s.date BETWEEN '2026-04-01' AND '2026-09-30' GROUP BY s.user_id,q), a AS (SELECT CASE WHEN country='USA' THEN 'US' ELSE country END country,q,COUNT(*) active_users FROM a0 GROUP BY CASE WHEN country='USA' THEN 'US' ELSE country END,q), r0 AS (SELECT t.user_id,CASE WHEN t.date BETWEEN '2026-04-01' AND '2026-06-30' THEN 'Q2' ELSE 'Q3' END q,SUM(CASE WHEN t.status='success' THEN t.amount_usd ELSE 0 END) revenue FROM transactions t WHERE t.date BETWEEN '2026-04-01' AND '2026-09-30' GROUP BY t.user_id,q), r AS (SELECT CASE WHEN u.country='USA' THEN 'US' ELSE u.country END country,r0.q,SUM(r0.revenue) revenue FROM r0 JOIN users u USING(user_id) GROUP BY CASE WHEN u.country='USA' THEN 'US' ELSE u.country END,r0.q), x AS (SELECT a.country,a.q,a.active_users,COALESCE(r.revenue,0) revenue,COALESCE(r.revenue,0)*1.0/a.active_users rate FROM a LEFT JOIN r ON a.country=r.country AND a.q=r.q), b AS (SELECT country,MAX(CASE WHEN q='Q2' THEN active_users END) q2_active,MAX(CASE WHEN q='Q3' THEN active_users END) q3_active,MAX(CASE WHEN q='Q2' THEN revenue END) q2_revenue,MAX(CASE WHEN q='Q3' THEN revenue END) q3_revenue,MAX(CASE WHEN q='Q2' THEN rate END) q2_rate,MAX(CASE WHEN q='Q3' THEN rate END) q3_rate FROM x GROUP BY country) SELECT country,q2_active,q3_active,ROUND(q2_revenue,2) q2_revenue,ROUND(q3_revenue,2) q3_revenue,ROUND(q2_rate,3) q2_revenue_per_active,ROUND(q3_rate,3) q3_revenue_per_active,ROUND((q3_active-q2_active)*q2_rate,2) mix_effect_usd,ROUND(q3_active*(q3_rate-q2_rate),2) within_country_effect_usd FROM b ORDER BY country
```

8 rows (453 ms)

| country | q2_active | q3_active | q2_revenue | q3_revenue | q2_revenue_per_active | q3_revenue_per_active | mix_effect_usd | within_country_effect_usd |
|---|---|---|---|---|---|---|---|---|
| BR | 960 | 1067 | 2924.95 | 3542.03 | 3.047 | 3.32 | 326.01 | 291.07 |
| CO | 285 | 366 | 675.06 | 524.31 | 2.369 | 1.433 | 191.86 | -342.61 |
| ID | 673 | 1461 | 667.05 | 819.01 | 0.991 | 0.561 | 781.03 | -629.07 |
| MX | 742 | 816 | 2108.16 | 1680.83 | 2.841 | 2.06 | 210.25 | -637.58 |
| PH | 617 | 1290 | 1083.59 | 1001.84 | 1.756 | 0.777 | 1181.94 | -1263.69 |
| TH | 409 | 500 | 556.23 | 532.31 | 1.36 | 1.065 | 123.76 | -147.68 |
| US | 2938 | 2629 | 12399.07 | 11825.5 | 4.22 | 4.498 | -1304.05 | 730.48 |
| VN | 312 | 698 | 380.51 | 376.6 | 1.22 | 0.54 | 470.76 | -474.67 |

_run_sql budget: 24/40 used_


### Step 28 · run_sql (25/40, 468 ms, ok)

**Purpose:** Attribute the stated average monthly active-user growth to acquisition sources and quantify how much comes from the new affiliate audience.

```sql
WITH m AS (SELECT substr(s.date,1,7) month,u.acquisition_source,COUNT(DISTINCT s.user_id) mau FROM sessions s JOIN users u USING(user_id) GROUP BY substr(s.date,1,7),u.acquisition_source) SELECT acquisition_source,ROUND(AVG(CASE WHEN month BETWEEN '2026-04' AND '2026-06' THEN mau END),1) q2_avg_monthly_mau,ROUND(AVG(CASE WHEN month BETWEEN '2026-07' AND '2026-09' THEN mau END),1) q3_avg_monthly_mau,ROUND(AVG(CASE WHEN month BETWEEN '2026-07' AND '2026-09' THEN mau END)-AVG(CASE WHEN month BETWEEN '2026-04' AND '2026-06' THEN mau END),1) change_mau FROM m GROUP BY acquisition_source ORDER BY change_mau DESC
```

7 rows (468 ms)

| acquisition_source | q2_avg_monthly_mau | q3_avg_monthly_mau | change_mau |
|---|---|---|---|
| tiktok_ads | 399 | 689.3 | 290.3 |
| organic | 1791 | 2057.3 | 266.3 |
| influencer | 121.3 | 213.3 | 92 |
| referral | 336 | 388.7 | 52.7 |
| meta_ads | 678.3 | 596.7 | -81.7 |
| google_search | 1123.3 | 887.7 | -235.7 |
| affiliate_network | NULL | 495.3 | NULL |

_run_sql budget: 25/40 used_


### Step 29 · run_sql (26/40, 15 ms, ok)

**Purpose:** Calculate raw and price-normalized revenue sensitivities for Q2/Q3 using explicit observed subscription and PPV price benchmarks, while separating refund anomalies.

```sql
WITH q AS (SELECT CASE WHEN date BETWEEN '2026-04-01' AND '2026-06-30' THEN 'Q2' ELSE 'Q3' END period,* FROM transactions WHERE date BETWEEN '2026-04-01' AND '2026-09-30'), sums AS (SELECT period,ROUND(SUM(CASE WHEN status='success' THEN amount_usd ELSE 0 END),2) raw_net_revenue,COUNT(CASE WHEN status='success' AND type='subscription' AND payment_method='pix' AND amount_usd<>9.99 THEN 1 END) nonstandard_pix_sub_rows,ROUND(SUM(CASE WHEN status='success' AND type='subscription' AND payment_method='pix' AND amount_usd<>9.99 THEN amount_usd-9.99 ELSE 0 END),2) pix_sub_excess_vs_9_99,COUNT(CASE WHEN status='success' AND type='ppv' AND payment_method='pix' AND amount_usd NOT IN (1.99,2.99) THEN 1 END) nonstandard_pix_ppv_rows,ROUND(SUM(CASE WHEN status='success' AND type='ppv' AND payment_method='pix' AND amount_usd NOT IN (1.99,2.99) THEN amount_usd-2.99 ELSE 0 END),2) pix_ppv_excess_vs_2_99,COUNT(CASE WHEN status='success' AND type='refund' AND payment_method='pix' AND amount_usd<>-9.99 THEN 1 END) nonstandard_pix_refunds,ROUND(SUM(CASE WHEN status='success' AND type='refund' AND payment_method='pix' AND amount_usd<>-9.99 THEN amount_usd+9.99 ELSE 0 END),2) refund_difference_vs_9_99 FROM q GROUP BY period) SELECT *,ROUND(raw_net_revenue-pix_sub_excess_vs_9_99-pix_ppv_excess_vs_2_99,2) corrected_positive_price_net,ROUND(raw_net_revenue-pix_sub_excess_vs_9_99-pix_ppv_excess_vs_2_99-refund_difference_vs_9_99,2) corrected_including_refund_normalization FROM sums ORDER BY period
```

2 rows (15 ms)

| period | raw_net_revenue | nonstandard_pix_sub_rows | pix_sub_excess_vs_9_99 | nonstandard_pix_ppv_rows | pix_ppv_excess_vs_2_99 | nonstandard_pix_refunds | refund_difference_vs_9_99 | corrected_positive_price_net | corrected_including_refund_normalization |
|---|---|---|---|---|---|---|---|---|---|
| Q2 | 20794.62 | 0 | 0 | 0 | 0 | 0 | 0 | 20794.62 | 20794.62 |
| Q3 | 20302.43 | 29 | 1157.39 | 18 | 139.38 | 2 | -79.82 | 19005.66 | 19085.48 |

_run_sql budget: 26/40 used_


### Step 30 · run_sql (27/40, 16 ms, ok)

**Purpose:** Confirm the timing and concentration of failures across local and mainstream payment methods to distinguish a broad processor issue from local-method failures.

```sql
WITH m AS (SELECT substr(date,1,7) month,payment_method,type,COUNT(CASE WHEN status='failed' THEN 1 END) failed,COUNT(CASE WHEN status='success' AND amount_usd>0 THEN 1 END) successful,COUNT(DISTINCT CASE WHEN status='failed' THEN user_id END) failed_users FROM transactions GROUP BY substr(date,1,7),payment_method,type) SELECT month,payment_method,SUM(failed) failed_attempts,SUM(successful) successful_sales,SUM(failed_users) method_type_failed_user_counts FROM m WHERE payment_method IN ('pix','oxxo','pse','apple_iap','google_play','card') GROUP BY month,payment_method ORDER BY month,payment_method
```

36 rows (16 ms)

| month | payment_method | failed_attempts | successful_sales | method_type_failed_user_counts |
|---|---|---|---|---|
| 2026-04 | apple_iap | 16 | 367 | 12 |
| 2026-04 | card | 11 | 154 | 6 |
| 2026-04 | google_play | 17 | 219 | 13 |
| 2026-04 | oxxo | 3 | 35 | 2 |
| 2026-04 | pix | 4 | 62 | 3 |
| 2026-04 | pse | 2 | 6 | 1 |
| 2026-05 | apple_iap | 17 | 381 | 11 |
| 2026-05 | card | 16 | 167 | 10 |
| 2026-05 | google_play | 17 | 244 | 11 |
| 2026-05 | oxxo | 3 | 32 | 3 |
| 2026-05 | pix | 5 | 71 | 3 |
| 2026-05 | pse | 1 | 12 | 1 |
| 2026-06 | apple_iap | 12 | 416 | 9 |
| 2026-06 | card | 16 | 169 | 10 |
| 2026-06 | google_play | 17 | 284 | 13 |
| 2026-06 | oxxo | 10 | 34 | 6 |
| 2026-06 | pix | 5 | 70 | 4 |
| 2026-06 | pse | 0 | 19 | 0 |
| 2026-07 | apple_iap | 17 | 372 | 10 |
| 2026-07 | card | 11 | 153 | 8 |
| 2026-07 | google_play | 20 | 220 | 14 |
| 2026-07 | oxxo | 3 | 32 | 2 |
| 2026-07 | pix | 6 | 60 | 3 |
| 2026-07 | pse | 0 | 12 | 0 |
| 2026-08 | apple_iap | 21 | 359 | 16 |
| 2026-08 | card | 16 | 153 | 11 |
| 2026-08 | google_play | 17 | 195 | 10 |
| 2026-08 | oxxo | 57 | 13 | 26 |
| 2026-08 | pix | 85 | 27 | 41 |
| 2026-08 | pse | 22 | 3 | 9 |
| 2026-09 | apple_iap | 11 | 305 | 5 |
| 2026-09 | card | 17 | 145 | 10 |
| 2026-09 | google_play | 18 | 182 | 9 |
| 2026-09 | oxxo | 23 | 11 | 15 |
| 2026-09 | pix | 51 | 20 | 29 |
| 2026-09 | pse | 10 | 4 | 5 |

_run_sql budget: 27/40 used_


### Step 31 · update_hypotheses

| # | Hypothesis | Status | Evidence |
|---|---|---|---|
| 1 | Revenue per active user fell because the expanding audience converted to payers less often. | **supported** | Monthly payer-months/MAU-months fell from 2,726/13,347=20.4% in Q2 to 2,290/15,985=14.3% in Q3; payer-months fell 16% while MAU-months rose 20%. Revenue per MAU-month fell from $1.56 to $1.27 raw. |
| 2 | A payment-processing or checkout issue drove down successful revenue, especially in August and September. | **supported** | Failed attempts rose from 175 in Q2 to 422 in Q3, concentrated in Pix (14 to 142), Oxxo (16 to 83) and PSE (3 to 32); failed attempts surged starting August. Treat as likely checkout/local-method issue, but transaction logs alone do not prove processor cause. |
| 3 | The MAU increase is partly a measurement or low-intent activity shift rather than monetizable audience growth. | **supported** | Engagement is real overall (views grew 18%, watch share stayed ~80%), but affiliate_network averaged 495 Q3 MAU with only 2 payers among 1,402 quarter-actives; this source contributed ~56% of the average monthly MAU increase. TikTok and influencer also grew while their quarter payer rates weakened. |
| 4 | Product mix, country, acquisition source or cohort shift explains weaker monetization per active user. | **supported** | Q3 expansion centered on ID/PH/VN and lower-monetizing channels; the raw country bridge is mix +$1,982 but within-country changes -$2,476, and PPV revenue/views fell about 35%/42%. Must re-evaluate Brazil contribution after correcting Pix price outliers. |
| 5 | Refunds, price anomalies, or status-data inconsistencies materially explain the flat revenue. | **supported** | Q3 contains 29 Pix subscriptions at non-$9.99 amounts and 18 Pix PPV sales outside the observed $1.99/$2.99 range; those positive-price excesses total $1,296.77. Normalizing them makes Q3 $19,005.66 vs Q2 $20,794.62 (-8.6%). Refunds are only $479.52 Q2 vs $489.41 Q3, so refund growth does not explain the headline. |

**Next:** Validate the Q3 Pix anomaly by country and recalculate the geographic bridge at standard observed prices; check premium/free content mix, payment retries/duplicate events, and monthly active-source trends before finalizing quantified recommendations.


### Step 32 · run_sql (28/40, 421 ms, ok)

**Purpose:** Re-estimate country-level mix and within-country drivers after normalizing the unusual Q3 Pix charges to the $9.99 subscription and observed PPV price range.

```sql
WITH act0 AS (SELECT s.user_id,CASE WHEN s.date BETWEEN '2026-04-01' AND '2026-06-30' THEN 'Q2' ELSE 'Q3' END q,u.country FROM sessions s JOIN users u USING(user_id) WHERE s.date BETWEEN '2026-04-01' AND '2026-09-30' GROUP BY s.user_id,q),act AS (SELECT CASE WHEN country='USA' THEN 'US' ELSE country END country,q,COUNT(*) active_users FROM act0 GROUP BY CASE WHEN country='USA' THEN 'US' ELSE country END,q),rev0 AS (SELECT t.user_id,CASE WHEN t.date BETWEEN '2026-04-01' AND '2026-06-30' THEN 'Q2' ELSE 'Q3' END q,SUM(CASE WHEN t.status='success' THEN t.amount_usd ELSE 0 END)-SUM(CASE WHEN t.status='success' AND t.payment_method='pix' AND t.type='subscription' AND t.amount_usd<>9.99 THEN t.amount_usd-9.99 WHEN t.status='success' AND t.payment_method='pix' AND t.type='ppv' AND t.amount_usd NOT IN (1.99,2.99) THEN t.amount_usd-2.99 ELSE 0 END) adjusted_revenue FROM transactions t WHERE t.date BETWEEN '2026-04-01' AND '2026-09-30' GROUP BY t.user_id,q),rev AS (SELECT CASE WHEN u.country='USA' THEN 'US' ELSE u.country END country,rev0.q,SUM(rev0.adjusted_revenue) revenue FROM rev0 JOIN users u USING(user_id) GROUP BY CASE WHEN u.country='USA' THEN 'US' ELSE u.country END,rev0.q),x AS (SELECT act.country,act.q,act.active_users,COALESCE(rev.revenue,0) revenue,COALESCE(rev.revenue,0)*1.0/act.active_users rate FROM act LEFT JOIN rev ON act.country=rev.country AND act.q=rev.q),b AS (SELECT country,MAX(CASE WHEN q='Q2' THEN active_users END) q2_active,MAX(CASE WHEN q='Q3' THEN active_users END) q3_active,MAX(CASE WHEN q='Q2' THEN revenue END) q2_revenue,MAX(CASE WHEN q='Q3' THEN revenue END) q3_adjusted_revenue,MAX(CASE WHEN q='Q2' THEN rate END) q2_rate,MAX(CASE WHEN q='Q3' THEN rate END) q3_rate FROM x GROUP BY country) SELECT country,q2_active,q3_active,ROUND(q2_revenue,2) q2_revenue,ROUND(q3_adjusted_revenue,2) q3_adjusted_revenue,ROUND((q3_active-q2_active)*q2_rate,2) mix_effect,ROUND(q3_active*(q3_rate-q2_rate),2) within_country_effect FROM b ORDER BY country
```

8 rows (421 ms)

| country | q2_active | q3_active | q2_revenue | q3_adjusted_revenue | mix_effect | within_country_effect |
|---|---|---|---|---|---|---|
| BR | 960 | 1067 | 2924.95 | 2245.26 | 326.01 | -1005.7 |
| CO | 285 | 366 | 675.06 | 524.31 | 191.86 | -342.61 |
| ID | 673 | 1461 | 667.05 | 819.01 | 781.03 | -629.07 |
| MX | 742 | 816 | 2108.16 | 1680.83 | 210.25 | -637.58 |
| PH | 617 | 1290 | 1083.59 | 1001.84 | 1181.94 | -1263.69 |
| TH | 409 | 500 | 556.23 | 532.31 | 123.76 | -147.68 |
| US | 2938 | 2629 | 12399.07 | 11825.5 | -1304.05 | 730.48 |
| VN | 312 | 698 | 380.51 | 376.6 | 470.76 | -474.67 |

_run_sql budget: 28/40 used_


### Step 33 · run_sql (29/40, 500 ms, ok)

**Purpose:** Quantify all source contributions to average monthly MAU growth, treating sources absent in Q2 as zero rather than missing.

```sql
WITH m AS (SELECT substr(s.date,1,7) month,u.acquisition_source,COUNT(DISTINCT s.user_id) mau FROM sessions s JOIN users u USING(user_id) GROUP BY substr(s.date,1,7),u.acquisition_source),sources AS (SELECT DISTINCT acquisition_source FROM users) SELECT sources.acquisition_source,ROUND(COALESCE(SUM(CASE WHEN m.month BETWEEN '2026-04' AND '2026-06' THEN m.mau ELSE 0 END),0)/3.0,1) q2_avg_mau,ROUND(COALESCE(SUM(CASE WHEN m.month BETWEEN '2026-07' AND '2026-09' THEN m.mau ELSE 0 END),0)/3.0,1) q3_avg_mau,ROUND((COALESCE(SUM(CASE WHEN m.month BETWEEN '2026-07' AND '2026-09' THEN m.mau ELSE 0 END),0)-COALESCE(SUM(CASE WHEN m.month BETWEEN '2026-04' AND '2026-06' THEN m.mau ELSE 0 END),0))/3.0,1) change_mau FROM sources LEFT JOIN m USING(acquisition_source) GROUP BY sources.acquisition_source ORDER BY change_mau DESC
```

7 rows (500 ms)

| acquisition_source | q2_avg_mau | q3_avg_mau | change_mau |
|---|---|---|---|
| affiliate_network | 0 | 495.3 | 495.3 |
| tiktok_ads | 399 | 689.3 | 290.3 |
| organic | 1791 | 2057.3 | 266.3 |
| influencer | 121.3 | 213.3 | 92 |
| referral | 336 | 388.7 | 52.7 |
| meta_ads | 678.3 | 596.7 | -81.7 |
| google_search | 1123.3 | 887.7 | -235.7 |

_run_sql budget: 29/40 used_


### Step 34 · run_sql (30/40, 1953 ms, ok)

**Purpose:** Check whether the monetization shift reflects less premium-content consumption or more free-tier usage, controlling for the actual catalog tier.

```sql
SELECT CASE WHEN v.date BETWEEN '2026-04-01' AND '2026-06-30' THEN 'Q2' ELSE 'Q3' END q,c.content_tier,v.view_type,COUNT(*) views,COUNT(DISTINCT v.user_id) users,COUNT(DISTINCT v.content_id) titles,ROUND(AVG(v.watch_duration_sec*1.0/NULLIF(v.content_duration_sec,0)),3) avg_watch_share FROM content_views v JOIN content_catalog c USING(content_id) WHERE v.date BETWEEN '2026-04-01' AND '2026-09-30' GROUP BY q,c.content_tier,v.view_type ORDER BY q,c.content_tier,v.view_type
```

8 rows (1953 ms)

| q | content_tier | view_type | views | users | titles | avg_watch_share |
|---|---|---|---|---|---|---|
| Q2 | free | free | 156554 | 6613 | 47 | 0.8 |
| Q2 | free | sub | 71760 | 1002 | 47 | 0.8 |
| Q2 | premium | ppv | 964 | 788 | 19 | 0.795 |
| Q2 | premium | sub | 29862 | 933 | 19 | 0.799 |
| Q3 | free | free | 200911 | 7618 | 61 | 0.798 |
| Q3 | free | sub | 79160 | 932 | 61 | 0.8 |
| Q3 | premium | ppv | 563 | 474 | 20 | 0.811 |
| Q3 | premium | sub | 25006 | 886 | 20 | 0.799 |

_run_sql budget: 30/40 used_


### Step 35 · run_sql (31/40, 30 ms, ok)

**Purpose:** Check transaction logs for exact repeated same-user same-day payment rows that might inflate sales, failures or revenue.

```sql
WITH dupe AS (SELECT user_id,date,type,payment_method,status,amount_usd,COUNT(*) n FROM transactions GROUP BY user_id,date,type,payment_method,status,amount_usd HAVING COUNT(*)>1) SELECT COUNT(*) duplicate_groups,SUM(n-1) extra_rows,COUNT(DISTINCT user_id) users_in_duplicate_groups,ROUND(SUM((n-1)*amount_usd),2) signed_duplicate_amount FROM dupe
```

1 row (30 ms)

| duplicate_groups | extra_rows | users_in_duplicate_groups | signed_duplicate_amount |
|---|---|---|---|
| 85 | 88 | 83 | 625.04 |

_run_sql budget: 31/40 used_


### Step 36 · run_sql (32/40, 250 ms, ok)

**Purpose:** Estimate directional Q3 media spend per newly acquired active user by source and identify channels where low cost may reflect low-quality or incentivized traffic.

```sql
WITH active_q AS (SELECT u.acquisition_source,COUNT(*) q3_new_active_users FROM users u JOIN (SELECT DISTINCT user_id FROM sessions WHERE date BETWEEN '2026-07-01' AND '2026-09-30') s USING(user_id) WHERE u.signup_date BETWEEN '2026-07-01' AND '2026-09-30' GROUP BY u.acquisition_source),spend AS (SELECT channel,SUM(spend_usd) q3_spend FROM marketing_spend WHERE date BETWEEN '2026-07-01' AND '2026-09-30' GROUP BY channel) SELECT a.acquisition_source,a.q3_new_active_users,ROUND(COALESCE(s.q3_spend,0),2) q3_spend,ROUND(COALESCE(s.q3_spend,0)/a.q3_new_active_users,2) spend_per_new_active FROM active_q a LEFT JOIN spend s ON a.acquisition_source=s.channel ORDER BY spend_per_new_active
```

7 rows (250 ms)

| acquisition_source | q3_new_active_users | q3_spend | spend_per_new_active |
|---|---|---|---|
| organic | 1701 | 0 | 0 |
| referral | 306 | 0 | 0 |
| affiliate_network | 1402 | 360.5 | 0.26 |
| tiktok_ads | 1165 | 2706.6 | 2.32 |
| influencer | 356 | 1170.17 | 3.29 |
| meta_ads | 341 | 1722.33 | 5.05 |
| google_search | 140 | 882.74 | 6.31 |

_run_sql budget: 32/40 used_


### Step 37 · run_sql (33/40, 46 ms, ok)

**Purpose:** Quantify the possible impact of exact repeated transaction signatures on Q2/Q3 revenue and separate successful sales from failed-attempt duplicates.

```sql
WITH numbered AS (SELECT t.*,CASE WHEN date BETWEEN '2026-04-01' AND '2026-06-30' THEN 'Q2' ELSE 'Q3' END q,ROW_NUMBER() OVER (PARTITION BY user_id,date,type,payment_method,status,amount_usd ORDER BY txn_id) rn FROM transactions t),d AS (SELECT * FROM numbered WHERE rn>1) SELECT q,type,status,payment_method,COUNT(*) extra_rows,COUNT(DISTINCT user_id) users,ROUND(SUM(amount_usd),2) signed_amount FROM d GROUP BY q,type,status,payment_method ORDER BY q,type,status,payment_method
```

29 rows (46 ms)

| q | type | status | payment_method | extra_rows | users | signed_amount |
|---|---|---|---|---|---|---|
| Q2 | ppv | failed | apple_iap | 1 | 1 | 1.99 |
| Q2 | ppv | failed | card | 2 | 2 | 4.98 |
| Q2 | ppv | failed | google_play | 3 | 3 | 5.97 |
| Q2 | ppv | failed | oxxo | 1 | 1 | 1.99 |
| Q2 | ppv | failed | pix | 1 | 1 | 1.99 |
| Q2 | ppv | success | apple_iap | 5 | 5 | 9.95 |
| Q2 | ppv | success | card | 5 | 5 | 10.95 |
| Q2 | ppv | success | google_play | 4 | 4 | 10.96 |
| Q2 | subscription | failed | apple_iap | 3 | 3 | 29.97 |
| Q2 | subscription | failed | card | 1 | 1 | 9.99 |
| Q2 | subscription | failed | google_play | 1 | 1 | 9.99 |
| Q3 | ppv | failed | apple_iap | 4 | 4 | 8.96 |
| Q3 | ppv | failed | card | 4 | 4 | 7.96 |
| Q3 | ppv | failed | google_play | 1 | 1 | 1.99 |
| Q3 | ppv | failed | oxxo | 9 | 9 | 17.91 |
| Q3 | ppv | failed | pix | 6 | 6 | 59.4 |
| Q3 | ppv | failed | pse | 2 | 2 | 4.98 |
| Q3 | ppv | success | apple_iap | 10 | 10 | 22.9 |
| Q3 | ppv | success | card | 2 | 1 | 3.98 |
| Q3 | ppv | success | google_play | 4 | 3 | 7.96 |
| Q3 | ppv | success | oxxo | 1 | 1 | 1.99 |
| Q3 | ppv | success | paypal | 1 | 1 | 1.99 |
| Q3 | ppv | success | pix | 1 | 1 | 2.99 |
| Q3 | ppv | success | pse | 2 | 1 | 3.98 |
| Q3 | subscription | failed | apple_iap | 1 | 1 | 9.99 |
| Q3 | subscription | failed | card | 1 | 1 | 9.99 |
| Q3 | subscription | failed | oxxo | 3 | 3 | 29.97 |
| Q3 | subscription | failed | pix | 6 | 6 | 299.4 |
| Q3 | subscription | failed | pse | 3 | 2 | 29.97 |

_run_sql budget: 33/40 used_


### Step 38 · run_sql (34/40, 0 ms, ok)

**Purpose:** Test whether fewer premium titles or episodes were released in Q3, which could explain weaker PPV and premium viewing.

```sql
SELECT CASE WHEN release_date BETWEEN '2026-04-01' AND '2026-06-30' THEN 'Q2' WHEN release_date BETWEEN '2026-07-01' AND '2026-09-30' THEN 'Q3' ELSE 'Other' END release_period,content_tier,COUNT(*) titles,SUM(total_episodes) episodes,MIN(release_date) first_release,MAX(release_date) last_release FROM content_catalog GROUP BY release_period,content_tier ORDER BY release_period,content_tier
```

6 rows (0 ms)

| release_period | content_tier | titles | episodes | first_release | last_release |
|---|---|---|---|---|---|
| Other | free | 38 | 927 | 2025-10-01 | 2026-03-21 |
| Other | premium | 12 | 317 | 2025-10-01 | 2026-03-27 |
| Q2 | free | 9 | 206 | 2026-04-05 | 2026-06-26 |
| Q2 | premium | 7 | 173 | 2026-04-16 | 2026-05-28 |
| Q3 | free | 14 | 314 | 2026-07-04 | 2026-09-23 |
| Q3 | premium | 1 | 25 | 2026-07-23 | 2026-07-23 |

_run_sql budget: 34/40 used_


### Step 39 · run_sql (35/40, 30 ms, ok)

**Purpose:** Estimate unique customer exposure to failed attempts and distinguish retries eventually recovered from customers with no successful matching payment.

```sql
WITH failed AS (SELECT CASE WHEN date BETWEEN '2026-04-01' AND '2026-06-30' THEN 'Q2' ELSE 'Q3' END q,user_id,payment_method,type FROM transactions WHERE status='failed' AND date BETWEEN '2026-04-01' AND '2026-09-30' GROUP BY q,user_id,payment_method,type),success AS (SELECT CASE WHEN date BETWEEN '2026-04-01' AND '2026-06-30' THEN 'Q2' ELSE 'Q3' END q,user_id,payment_method,type FROM transactions WHERE status='success' AND amount_usd>0 AND date BETWEEN '2026-04-01' AND '2026-09-30' GROUP BY q,user_id,payment_method,type) SELECT f.q,f.payment_method,f.type,COUNT(*) distinct_failed_users,COUNT(s.user_id) users_with_success_same_method_type,COUNT(*)-COUNT(s.user_id) failed_users_without_success_same_method_type FROM failed f LEFT JOIN success s ON f.q=s.q AND f.user_id=s.user_id AND f.payment_method=s.payment_method AND f.type=s.type GROUP BY f.q,f.payment_method,f.type ORDER BY f.q,f.payment_method,f.type
```

28 rows (30 ms)

| q | payment_method | type | distinct_failed_users | users_with_success_same_method_type | failed_users_without_success_same_method_type |
|---|---|---|---|---|---|
| Q2 | apple_iap | ppv | 11 | 5 | 6 |
| Q2 | apple_iap | subscription | 21 | 17 | 4 |
| Q2 | card | ppv | 9 | 5 | 4 |
| Q2 | card | subscription | 16 | 11 | 5 |
| Q2 | ewallet | subscription | 3 | 1 | 2 |
| Q2 | google_play | ppv | 16 | 7 | 9 |
| Q2 | google_play | subscription | 20 | 16 | 4 |
| Q2 | oxxo | ppv | 7 | 5 | 2 |
| Q2 | oxxo | subscription | 4 | 4 | 0 |
| Q2 | pix | ppv | 4 | 1 | 3 |
| Q2 | pix | subscription | 6 | 5 | 1 |
| Q2 | pse | ppv | 1 | 0 | 1 |
| Q2 | pse | subscription | 1 | 1 | 0 |
| Q3 | apple_iap | ppv | 9 | 2 | 7 |
| Q3 | apple_iap | subscription | 22 | 19 | 3 |
| Q3 | card | ppv | 8 | 1 | 7 |
| Q3 | card | subscription | 21 | 18 | 3 |
| Q3 | ewallet | ppv | 2 | 1 | 1 |
| Q3 | ewallet | subscription | 5 | 3 | 2 |
| Q3 | google_play | ppv | 8 | 3 | 5 |
| Q3 | google_play | subscription | 25 | 21 | 4 |
| Q3 | oxxo | ppv | 17 | 1 | 16 |
| Q3 | oxxo | subscription | 22 | 18 | 4 |
| Q3 | paypal | subscription | 1 | 0 | 1 |
| Q3 | pix | ppv | 17 | 3 | 14 |
| Q3 | pix | subscription | 49 | 35 | 14 |
| Q3 | pse | ppv | 4 | 0 | 4 |
| Q3 | pse | subscription | 9 | 7 | 2 |

_run_sql budget: 35/40 used_


### Step 40 · run_sql (36/40, 266 ms, ok)

**Purpose:** Verify the precise quarter-level monthly-average conversion and revenue-per-MAU calculation used in the executive summary.

```sql
WITH a AS (SELECT substr(date,1,7) month,COUNT(DISTINCT user_id) mau FROM sessions GROUP BY substr(date,1,7)),t AS (SELECT substr(date,1,7) month,COUNT(DISTINCT CASE WHEN status='success' AND amount_usd>0 THEN user_id END) payers,ROUND(SUM(CASE WHEN status='success' THEN amount_usd ELSE 0 END),2) net_revenue FROM transactions GROUP BY substr(date,1,7)) SELECT CASE WHEN a.month BETWEEN '2026-04' AND '2026-06' THEN 'Q2' ELSE 'Q3' END q,COUNT(*) months,SUM(a.mau) mau_months,SUM(t.payers) payer_months,ROUND(100.0*SUM(t.payers)/SUM(a.mau),2) payer_conversion,ROUND(SUM(t.net_revenue),2) net_revenue,ROUND(SUM(t.net_revenue)*1.0/SUM(a.mau),2) revenue_per_mau_month,ROUND(SUM(t.net_revenue)*1.0/SUM(t.payers),2) revenue_per_payer_month FROM a JOIN t USING(month) GROUP BY q ORDER BY q
```

2 rows (266 ms)

| q | months | mau_months | payer_months | payer_conversion | net_revenue | revenue_per_mau_month | revenue_per_payer_month |
|---|---|---|---|---|---|---|---|
| Q2 | 3 | 13347 | 2726 | 20.42 | 20794.62 | 1.56 | 7.63 |
| Q3 | 3 | 15985 | 2290 | 14.33 | 20302.43 | 1.27 | 8.87 |

_run_sql budget: 36/40 used_


### Step 41 · run_sql (37/40, 3655 ms, ok)

**Purpose:** Check whether source-level MAU growth represents users actually watching content or mostly non-viewing session activity, with payer conversion alongside.

```sql
WITH a AS (SELECT CASE WHEN s.date BETWEEN '2026-04-01' AND '2026-06-30' THEN 'Q2' ELSE 'Q3' END q,u.acquisition_source,COUNT(DISTINCT s.user_id) active_users FROM sessions s JOIN users u USING(user_id) WHERE s.date BETWEEN '2026-04-01' AND '2026-09-30' GROUP BY q,u.acquisition_source),v AS (SELECT CASE WHEN v.date BETWEEN '2026-04-01' AND '2026-06-30' THEN 'Q2' ELSE 'Q3' END q,u.acquisition_source,COUNT(DISTINCT v.user_id) viewers,COUNT(*) views,COUNT(DISTINCT CASE WHEN v.view_type='ppv' THEN v.user_id END) ppv_viewers FROM content_views v JOIN users u USING(user_id) WHERE v.date BETWEEN '2026-04-01' AND '2026-09-30' GROUP BY q,u.acquisition_source),t AS (SELECT CASE WHEN date BETWEEN '2026-04-01' AND '2026-06-30' THEN 'Q2' ELSE 'Q3' END q,u.acquisition_source,COUNT(DISTINCT CASE WHEN status='success' AND amount_usd>0 THEN user_id END) payers FROM transactions t JOIN users u USING(user_id) WHERE date BETWEEN '2026-04-01' AND '2026-09-30' GROUP BY q,u.acquisition_source) SELECT a.q,a.acquisition_source,a.active_users,COALESCE(v.viewers,0) viewers,ROUND(100.0*COALESCE(v.viewers,0)/a.active_users,1) active_viewer_rate,COALESCE(v.views,0) views,COALESCE(t.payers,0) quarter_payers,ROUND(100.0*COALESCE(t.payers,0)/a.active_users,1) payer_rate FROM a LEFT JOIN v USING(q,acquisition_source) LEFT JOIN t USING(q,acquisition_source) ORDER BY a.acquisition_source,a.q
```

13 rows (3655 ms)

| q | acquisition_source | active_users | viewers | active_viewer_rate | views | quarter_payers | payer_rate |
|---|---|---|---|---|---|---|---|
| Q3 | affiliate_network | 1402 | 612 | 43.7 | 1748 | 2 | 0.1 |
| Q2 | google_search | 1600 | 1600 | 100 | 90001 | 601 | 37.6 |
| Q3 | google_search | 1056 | 1055 | 99.9 | 88797 | 442 | 41.9 |
| Q2 | influencer | 202 | 202 | 100 | 3413 | 9 | 4.5 |
| Q3 | influencer | 427 | 427 | 100 | 5498 | 10 | 2.3 |
| Q2 | meta_ads | 1100 | 1100 | 100 | 32816 | 218 | 19.8 |
| Q3 | meta_ads | 856 | 856 | 100 | 35010 | 146 | 17.1 |
| Q2 | organic | 2769 | 2769 | 100 | 101840 | 606 | 21.9 |
| Q3 | organic | 3103 | 3103 | 100 | 130384 | 530 | 17.1 |
| Q2 | referral | 519 | 519 | 100 | 22596 | 159 | 30.6 |
| Q3 | referral | 583 | 583 | 100 | 30025 | 126 | 21.6 |
| Q2 | tiktok_ads | 746 | 746 | 100 | 8474 | 26 | 3.5 |
| Q3 | tiktok_ads | 1400 | 1400 | 100 | 14178 | 21 | 1.5 |

_run_sql budget: 37/40 used_


### Step 42 · run_sql (38/40, 16 ms, ok)

**Purpose:** Decompose Q2/Q3 volume and net revenue by subscription, PPV and refunds, isolating Pix price anomalies to quantify each source of the revenue change.

```sql
WITH x AS (SELECT CASE WHEN date BETWEEN '2026-04-01' AND '2026-06-30' THEN 'Q2' ELSE 'Q3' END q,type,status,payment_method,amount_usd FROM transactions WHERE date BETWEEN '2026-04-01' AND '2026-09-30') SELECT q,type,COUNT(CASE WHEN status='success' AND amount_usd>0 THEN 1 END) successful_sales,ROUND(SUM(CASE WHEN status='success' AND amount_usd>0 THEN amount_usd ELSE 0 END),2) gross_positive_revenue,COUNT(CASE WHEN status='success' AND type='refund' THEN 1 END) refunds,ROUND(SUM(CASE WHEN status='success' AND type='refund' THEN amount_usd ELSE 0 END),2) refunds_amount,ROUND(SUM(CASE WHEN status='success' AND type='subscription' AND payment_method='pix' AND amount_usd<>9.99 THEN amount_usd-9.99 WHEN status='success' AND type='ppv' AND payment_method='pix' AND amount_usd NOT IN (1.99,2.99) THEN amount_usd-2.99 ELSE 0 END),2) pix_positive_excess,ROUND(SUM(CASE WHEN status='success' THEN amount_usd ELSE 0 END)-SUM(CASE WHEN status='success' AND type='subscription' AND payment_method='pix' AND amount_usd<>9.99 THEN amount_usd-9.99 WHEN status='success' AND type='ppv' AND payment_method='pix' AND amount_usd NOT IN (1.99,2.99) THEN amount_usd-2.99 ELSE 0 END),2) adjusted_net_revenue FROM x GROUP BY q,type ORDER BY q,type
```

6 rows (16 ms)

| q | type | successful_sales | gross_positive_revenue | refunds | refunds_amount | pix_positive_excess | adjusted_net_revenue |
|---|---|---|---|---|---|---|---|
| Q2 | ppv | 964 | 2073.36 | 0 | 0 | 0 | 2073.36 |
| Q2 | refund | 0 | 0 | 48 | -479.52 | 0 | -479.52 |
| Q2 | subscription | 1922 | 19200.78 | 0 | 0 | 0 | 19200.78 |
| Q3 | ppv | 563 | 1352.75 | 0 | 0 | 139.38 | 1213.37 |
| Q3 | refund | 0 | 0 | 41 | -489.41 | 0 | -489.41 |
| Q3 | subscription | 1830 | 19439.09 | 0 | 0 | 1157.39 | 18281.7 |

_run_sql budget: 38/40 used_


### Step 43 · run_sql (39/40, 0 ms, ok)

**Purpose:** Estimate the Q3 count of customers with local-method failures and no successful same-method purchase, to set a cautious recovery opportunity ceiling.

```sql
WITH failed_users AS (SELECT user_id,payment_method,type FROM transactions WHERE date BETWEEN '2026-07-01' AND '2026-09-30' AND status='failed' AND payment_method IN ('pix','oxxo','pse') GROUP BY user_id,payment_method,type), success_users AS (SELECT user_id,payment_method,type FROM transactions WHERE date BETWEEN '2026-07-01' AND '2026-09-30' AND status='success' AND amount_usd>0 AND payment_method IN ('pix','oxxo','pse') GROUP BY user_id,payment_method,type), f AS (SELECT f.user_id,f.payment_method,f.type FROM failed_users f LEFT JOIN success_users s USING(user_id,payment_method,type) WHERE s.user_id IS NULL) SELECT type,COUNT(DISTINCT user_id) distinct_users_without_success,COUNT(*) user_method_type_records,CASE WHEN type='subscription' THEN ROUND(COUNT(*)*9.99,2) ELSE NULL END subscription_value_at_list_price FROM f GROUP BY type
```

2 rows (0 ms)

| type | distinct_users_without_success | user_method_type_records | subscription_value_at_list_price |
|---|---|---|---|
| ppv | 34 | 34 | NULL |
| subscription | 20 | 20 | 199.8 |

_run_sql budget: 39/40 used_


### Step 44 · run_sql (40/40, 171 ms, ok)

**Purpose:** Validate the link between PPV sales and premium episode viewing, and estimate lost PPV revenue from the lower Q3 sales volume at normalized prices.

```sql
WITH prem AS (SELECT CASE WHEN v.date BETWEEN '2026-04-01' AND '2026-06-30' THEN 'Q2' ELSE 'Q3' END q,v.view_type,COUNT(*) views,COUNT(DISTINCT v.user_id) users FROM content_views v JOIN content_catalog c USING(content_id) WHERE c.content_tier='premium' AND v.date BETWEEN '2026-04-01' AND '2026-09-30' GROUP BY q,v.view_type),ppv_tx AS (SELECT CASE WHEN date BETWEEN '2026-04-01' AND '2026-06-30' THEN 'Q2' ELSE 'Q3' END q,COUNT(*) sales,ROUND(SUM(amount_usd),2) raw_revenue,ROUND(SUM(amount_usd)-SUM(CASE WHEN payment_method='pix' AND amount_usd NOT IN (1.99,2.99) THEN amount_usd-2.99 ELSE 0 END),2) price_normalized_revenue FROM transactions WHERE type='ppv' AND status='success' AND date BETWEEN '2026-04-01' AND '2026-09-30' GROUP BY q) SELECT ppv_tx.q,ppv_tx.sales,ppv_tx.raw_revenue,ppv_tx.price_normalized_revenue,prem.views ppv_content_views,prem.users ppv_viewers FROM ppv_tx LEFT JOIN prem ON prem.q=ppv_tx.q AND prem.view_type='ppv' ORDER BY ppv_tx.q
```

2 rows (171 ms)

| q | sales | raw_revenue | price_normalized_revenue | ppv_content_views | ppv_viewers |
|---|---|---|---|---|---|
| Q2 | 964 | 2073.36 | 2073.36 | 964 | 788 |
| Q3 | 563 | 1352.75 | 1213.37 | 563 | 474 |

_run_sql budget: 40/40 used_


> _Query budget used up; tools switched off for the next call._


---

## Final answer

### Answer

The reported picture is **not simply “20% more users, same revenue.”** Using April–June versus July–September 2026, average monthly session-based MAU rose **19.8%**, while recorded net revenue fell **2.4%**. But Q3 includes unusual Brazil Pix charges: normalizing those to the $9.99 subscription price and the $1.99–$2.99 PPV prices observed elsewhere reduces Q3 revenue from **$20.3K to $19.0K**, an **8.6% decline** versus Q2. Separately, payer conversion fell and premium PPV activity dropped sharply.

For the board, present both the **reported** and **price-normalized** Q3 revenue until Finance verifies those Pix transactions. The growth is real in viewing overall, but a disproportionate share came from audiences that convert poorly; fewer premium releases and a sharp rise in local-payment failures are also consistent with weaker monetization.

### Definition and scope

- **Periods:** Q2 = April 1–June 30, 2026; Q3 = July 1–September 30, 2026, the latest complete quarter in the data.
- **MAU:** distinct users with at least one session in each calendar month; compared as the average of the three monthly counts. Q2 averaged **4,449** MAU; Q3 averaged **5,328**.
- **Net revenue:** successful transactions only, summing positive charges and negative refunds; failed attempts are excluded. This is transaction-log revenue, not audited accounting revenue.
- **Price-normalized sensitivity:** leaves refunds as logged, but adjusts Q3 Pix subscription charges that differ from **$9.99** to $9.99, and Pix PPV charges outside the observed **$1.99/$2.99** prices to $2.99. This is a sensitivity, not a confirmed accounting correction.

### Data quality

- **Pix price outliers materially change the headline.** Q3 has **29** Pix subscription charges outside $9.99, including $49.90 amounts, and **18** Pix PPV charges outside the $1.99/$2.99 range, including $9.90 and $14.90 amounts. Their excess over the stated/observed benchmarks is **$1,157.39** for subscriptions and **$139.38** for PPV. Subtracting **$1,296.77** from Q3 net revenue changes it from **$20,302.43** to **$19,005.66**; the Q2 comparison changes from **−2.4%** to **−8.6%**. These amounts appear in Brazil Pix activity; validate against gateway receipts and any localized pricing or bundle rules before treating the sensitivity as the true revenue figure.
- **Refunds do not explain the flat headline.** Refunds were **−$479.52** in Q2 and **−$489.41** in Q3. There are also two Q3 Pix refunds of **−$49.90**; if those should instead be −$9.99, Q3 would be **$79.82** higher than the price-normalized figure. I have not assumed that correction.
- **Failed attempts are not revenue.** Failed records rose from **175** in Q2 to **422** in Q3. Some failed Pix rows also have unusual amounts, so their recorded amounts are not a reliable estimate of lost revenue.
- **Activity is not entirely a session-tracking artifact.** Q3 monthly session MAU exceeded view-user counts by **208–302** per month, whereas they nearly matched in Q2. Still, total content views rose from **259,140** to **305,640** and average watch share remained about **80%**. The audience grew, but not all session activity represents content viewing.
- **Other checks:** USA/US country labels were consolidated for country comparisons. Exact repeated transaction signatures exist, but repeated successful charges were only about **$31.86** in Q2 and **$45.79** in Q3; they do not explain the headline. The data has no explicit test-user flag, so I could not rule out incentivized or otherwise non-human acquisition.

### Findings

1. **Fewer active users paid, despite more MAU.** MAU-months rose from **13,347** to **15,985**, but payer-months fell from **2,726** to **2,290**. Payer conversion fell from **20.42%** to **14.33%**; recorded revenue per MAU-month fell from **$1.56** to **$1.27**. This is the clearest explanation for why audience growth did not translate into revenue growth.

2. **A large part of the audience increase came from a very weakly monetizing affiliate source.** Affiliate contributed an average **495** MAU per month in Q3, about **56%** of the net average-MAU increase, and had **1,402** Q3 active users but only **2** payers. Only **612** of those users viewed content; that is a **43.7%** active-viewer rate, versus essentially all active users in the other sources. Among affiliate viewers, just **2** paid. TikTok also grew, from **746** to **1,400** quarter-active users, while its payer rate fell from **3.5%** to **1.5%**; influencer rose from **202** to **427** actives while its payer rate fell from **4.5%** to **2.3%**.

3. **Premium PPV volume fell as premium release supply slowed.** Q3 added **1 premium title with 25 episodes**, versus **7 titles with 173 episodes** in Q2. Premium PPV views—which match successful PPV sales in both quarters—fell from **964** to **563**; PPV viewers fell from **788** to **474**. After the Pix price normalization, PPV revenue fell from **$2,073.36** to **$1,213.37**. The normalized price per sale was similar, so the decline is primarily volume. This is consistent with the sharp slowdown in premium releases, though the data does not prove that fewer releases caused all of the decline. Free views, by contrast, rose from **156,554** to **200,911**.

4. **Recorded local-payment failures spiked from August, concentrated in Pix, Oxxo and PSE.** Q2 to Q3 failed attempts rose **14 to 142 for Pix**, **16 to 83 for Oxxo**, and **3 to 32 for PSE**. Apple IAP, card and Google Play failure counts were comparatively steady. In Q3, **20** local-method subscription customer/method records and **34** PPV customer/method records had a failed attempt and no successful purchase through that same method and product type. This points to a local-payment checkout problem or a change in failure logging; the data alone does not identify the cause.

5. **The audience also shifted toward lower-revenue markets, and monetization weakened within many markets.** Q3 active users rose in Indonesia (**673 to 1,461**) and the Philippines (**617 to 1,290**), where Q3 revenue per quarter-active user was about **$0.56** and **$0.78**, respectively. After price normalization, the country bridge estimates a **+$1,982** contribution from changing active-user mix, offset by **−$3,771** from within-country revenue-per-active changes, for a net **−$1,789**. Brazil’s within-country result changes materially after the Pix adjustment; the raw revenue increase there should not be read as validated growth.

### Hypotheses rejected

- **“Refund growth caused the flat revenue.”** Rejected as a material explanation: refunds were **−$479.52** in Q2 and **−$489.41** in Q3, a small change relative to quarterly revenue.
- **“The whole MAU increase is fake or unengaged.”** Rejected as a complete explanation: views increased **18%** and watch share stayed around **80%**. However, the affiliate cohort has weak viewing and payer outcomes, and session MAU has a modest post-June gap versus viewers.
- **“Exact duplicate transactions explain the revenue trend.”** Rejected as material: repeated successful charges were small relative to quarterly revenue. Failed attempts and unusual Pix prices are much more consequential issues.

### Recommendations

1. **Reconcile Pix charges before the board and keep two revenue views until resolved.** Ask Finance/Payments to match Q3 Pix transaction IDs to gateway receipts, currency conversion, price configuration and any bundle SKUs. The question at stake is **$1,296.77** of Q3 positive-charge excess under the observed price benchmarks; if it is not valid pricing, the comparable revenue trend is a decline of about **8.6%**, not a near-flat result.
2. **Prioritize Pix, Oxxo and PSE checkout diagnostics and recovery.** Check August release/config changes, provider response codes, retries and customer messaging by method and country; add a daily alert on failure rate. There are **20** Q3 local-method subscription customer/method records with no matching successful purchase; at one **$9.99** charge each, that is a **$199.80** one-month recovery ceiling—not a forecast. Track successful recovery and repeat failure separately.
3. **Pause or renegotiate affiliate acquisition until its quality is verified.** The channel delivered **1,402** Q3 actives for **$360.50** spend, but only **612** viewed content and **2** paid. Validate attribution, incentivized traffic and downstream retention before scaling. As a directional scenario—not a forecast—if those **612** viewers matched the non-affiliate Q3 payer rate and normalized revenue per payer, the opportunity is about **$1.5K** in quarter revenue.
4. **Restore or test a stronger premium release cadence.** The observed release pace fell from **173 to 25 premium episodes**, alongside **401 fewer** PPV sales. Recovering that sales volume at the normalized Q3 PPV revenue per sale implies roughly **$865** additional quarterly PPV revenue, before any subscription or retention benefit. Validate with a staged release/content experiment and measure PPV sales, premium viewing and subscription conversion.
5. **Make acquisition decisions on paid conversion and qualified viewing, not MAU alone.** Compare source-level cost per viewer, payer conversion and revenue at consistent cohort ages; avoid shifting spend based solely on short-term installs. Track monthly MAU alongside viewer rate, payer conversion, PPV sales and price-validated net revenue.

### Confidence and open questions

- **High confidence:** Session-based MAU increased; payer conversion fell; PPV sales/views fell; the Q3 Pix amounts differ sharply from the stated subscription price and the PPV prices observed in other methods.
- **Medium confidence:** Premium release slowdown and low-quality acquisition contributed to weaker monetization; the associations are strong, but the data does not isolate cause.
- **Medium confidence:** Local-payment failures indicate a checkout issue. The increase is concentrated in local methods and begins in August, but the logs do not provide provider error codes or prove an outage.
- **Not checked:** Pix gateway receipts, valid local pricing/bundles or currency conversion; payment-provider response codes and root cause; fraud/incentive flags or device-level traffic quality; causal lift from premium release experiments; longer-term cohort retention and customer lifetime value. Activity and revenue coverage ends **September 30, 2026**, so this analysis does not say whether the Q3 trends continued afterward.

---

## Run stats

- model: gpt-6-luna
- model calls: 15
- run_sql calls: 40 (0 errors)
- tokens: 399,472 in / 35,787 out (20,598 reasoning)
- estimated cost: $0.0578
- wall time: 330 s (model 309 s)
- stopped by: query budget
