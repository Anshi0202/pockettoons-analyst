# PocketToons — the planted story (answer key)

This is the answer key for the synthetic dataset. The agent never sees this file; it is used to
grade the investigation and the eval.

- **Reproduce:** `python data/generate.py` (≈10 s, standard library only, seed 12, byte-identical on Python 3.11 and 3.13), then `python data/validate.py`.
- **Single-run numbers** below come from `validate.py`, i.e. plain SQL on `pockettoons.db`.
- **"Cost of each cause"** numbers come from counterfactual re-runs (`PT_DISABLE=...`), averaged over 12 seeds.

## Definitions

| Term              | Definition                                                                                                                |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Q2 / Q3           | Apr 1–Jun 30 2026 / Jul 1–Sep 30 2026                                                                                     |
| MAU               | Distinct users with ≥1 session in a calendar month. "Quarterly MAU" is the average of the quarter's three months.         |
| Net revenue       | `SUM(amount_usd)` over `status='success'` transactions. Subscriptions + PPV, minus refunds (refunds are stored negative). |
| Corrected revenue | Net revenue with pix rows from Aug 1 divided by 49.90/9.99 (undoes DQ2).                                                  |

---

## 1. The headline: what the GM sees vs what is true

| Metric                                   | Q2      | Q3      | QoQ                |
| ---------------------------------------- | ------- | ------- | ------------------ |
| MAU, as reported                         | 4,449   | 5,328   | **+19.8%**         |
| MAU, excluding bots (DQ1)                | 4,449   | 4,944   | **+11.1%**         |
| Net revenue, as reported                 | $20,795 | $20,302 | **−2.4%** ("flat") |
| Net revenue, corrected for BRL bug (DQ2) | $20,795 | $19,070 | **−8.3%**          |

Monthly corrected revenue shows the trend the quarterly average hides:

|                   | Apr    | May    | Jun    | Jul    | Aug    | Sep    |
| ----------------- | ------ | ------ | ------ | ------ | ------ | ------ |
| Corrected revenue | $6,335 | $7,008 | $7,452 | $7,336 | $6,192 | $5,542 |

**September is 26% below June.** The quarter average understates how fast revenue is falling.

### One-paragraph answer

About half of the "+20% MAU" is bot installs from a new affiliate network. The other half is
real but comes from pre-existing momentum, not the Q3 initiatives. Revenue isn't flat. It is
down 8% for the quarter and 26% on a June→September run-rate, and a currency bug in the new
LatAm payment processor hides part of that decline.

Three Q3 decisions caused the drop:

1. The free-episode limit went from 5 to 8, which removed the main paywall moment (largest cause).
2. A new LatAm payment processor fails ~75% of local-method charges.
3. Paid budget was cut and moved from Google/Meta to cheap TikTok/influencer installs that rarely pay.

Without these changes Q3 revenue would have been roughly **$5.4K higher**, growing about +22%
QoQ in line with users, instead of −8%.

---

## 2. Timeline of planted events

| Date       | Event                                                       | Code          |
| ---------- | ----------------------------------------------------------- | ------------- |
| 2025-10-01 | App launch, followed by a launch-marketing burst of signups | `PRE_WINDOW`  |
| 2026-05-22 | Premium hit "Crimson Requiem" released (PPV spike May–Jun)  | RH1           |
| 2026-07-01 | Paid budget cut ~33% and shifted to TikTok/influencers      | RC1           |
| 2026-07-01 | Free daily limit raised from 5 to 8 episodes                | RC2           |
| 2026-07-10 | `affiliate_network` channel launched, ~80% bots             | DQ1           |
| 2026-08-01 | LatAm local payment methods migrate to a new processor      | RC3, DQ2, DQ3 |

---

## 3. Root causes

### RC2 — Free limit 5 → 8 removed the paywall moment (largest cause)

**Mechanism in the generator.** A free user who wants more episodes than the limit "hits the cap".
At that point they may subscribe (`P_SUB_AT_CAP`), buy a premium episode (`P_PPV_AT_CAP`), stop
for the day, or occasionally give up on the app. The cap drove ~68% of new subscriptions in Q2.

**How it shows up in SQL:**

| Signal                                                                    | Q2                 | Q3                           |
| ------------------------------------------------------------------------- | ------------------ | ---------------------------- |
| Free-viewing user-days that reach the daily limit                         | 26%                | 10%                          |
| New subscription starts from users who signed up before April (per month) | 96 (May), 94 (Jun) | 47 (Jul), 30 (Aug), 18 (Sep) |
| Free episodes per active free user-day                                    | 2.83               | 3.21                         |

- **The decline hits every cohort.** Subscription starts fall even among long-standing users, which proves this isn't just a mix effect from new signups.
- **Engagement rose, retention didn't.** Free episodes per day are up ~14%, but month-over-month retention of free viewers is 71–72% in Q2 and 69% in Q3. Among users who signed up before April, retention drifts up steadily with no step at Jul 1.
- **Cost:** Q3 revenue **−$3.6K** (±0.2K); September run-rate **−$1.4K/month**. Effect on Q3 MAU: about +26 users, i.e. negligible.

### RC3 — LatAm payment migration broke local payment methods

**Mechanism in the generator.** From Aug 1, pix (BR), oxxo (MX) and pse (CO) fail 60% of first
attempts. If an attempt fails, retries fail 90% of the time. So renewals turn into involuntary
churn, and new sign-ups fail.

**How it shows up in SQL:**

| Signal                                                            | Before Aug 1 | After Aug 1          |
| ----------------------------------------------------------------- | ------------ | -------------------- |
| Failure rate of all attempts (incl. retries), local LatAm methods | 7–11%        | 79% (Aug), 71% (Sep) |
| Failure rate, all other methods                                   | 5–8%         | 5–8% (unchanged)     |
| LatAm paying subscribers at month end (from transactions)         | 188 (Jun 30) | 115 (Sep 30), −39%   |

For comparison, US paying subscribers fell 16% (399 → 334) and SEA fell 21% (102 → 81).

- **LatAm revenue:** −21% corrected ($5,708 → $4,515), but **+0.7% as reported**, because DQ2 inflates exactly these rows.
- **Cost:** Q3 revenue **−$1.1K** (±0.2K); September run-rate **−$0.6K/month**.
- **Interrelation:** RC1 deliberately pushed acquisition into LatAm just as RC3 broke LatAm payments.

### RC1 — Paid acquisition shifted to cheap, low-intent installs

**Mechanism in the generator.** Each user has a hidden intent (engagement) drawn per channel, and
a country-level willingness to pay. Google/Meta users are US-heavy and high-intent.
TikTok/influencer users are SEA/LatAm-heavy and low-intent.

|                             | Q2      | Q3                                                   | Change           |
| --------------------------- | ------- | ---------------------------------------------------- | ---------------- |
| Paid spend                  | $10,173 | $6,842                                               | −33%             |
| Google signups              | 828     | 147                                                  | −82%             |
| Meta signups                | 714     | 359                                                  | −50%             |
| TikTok signups              | 593     | 1,320                                                | +123%            |
| Influencer signups          | 136     | 394                                                  | +190%            |
| Affiliate signups           | 0       | 1,442                                                | new              |
| All signups                 | 4,289   | 5,821                                                | +36%             |
| Signups excluding affiliate | 4,289   | 4,379                                                | +2% (flat)       |
| Blended paid CAC            | $4.48   | $1.87 (bots counted as users), $2.72 (bots excluded) | looks like a win |

**Channel economics** (60-day corrected revenue per signup vs CAC, Apr–May cohorts):

| Channel                 | 60-day revenue per signup | CAC   | Recovered in 60 days |
| ----------------------- | ------------------------- | ----- | -------------------- |
| Google                  | $2.34                     | $6.01 | 39%                  |
| Meta                    | $0.90                     | $5.09 | 18%                  |
| TikTok                  | $0.21                     | $1.85 | 11%                  |
| Influencer              | $0.37                     | $3.41 | 11%                  |
| Affiliate (July cohort) | $0.03                     | $0.25 | ~0%                  |

30-day free→paid conversion by signup quarter: US 6.1% → 3.9%, LatAm 3.3% → 1.2%,
SEA 2.3% → 0.6%. These figures mix RC1 (who signs up) with RC2 (the cap).

- **Cost:** Q3 revenue **−$1.2K** (±0.3K); September run-rate **−$0.6K/month**, and growing, because lost high-intent cohorts would have kept converting.
- **It did not buy MAU.** Q3 MAU was about −130 users with the shift vs without it, because the cheap users churn faster.
- **Board framing:** spend fell $3.3K/quarter, but the run-rate revenue loss (~$1.9K/quarter by September) keeps growing, so the "efficiency" is mostly an illusion.

### Counterfactual attribution (12 seeds; effect = world with the cause − world without it)

| Cause                    | Q3 revenue                          | Sep run-rate | Q3 MAU (reported) |
| ------------------------ | ----------------------------------- | ------------ | ----------------- |
| RC2 free limit 5→8       | −$3,560 ± 180                       | −$1,420/mo   | +26               |
| RC1 channel shift        | −$1,250 ± 270                       | −$650/mo     | −128              |
| RC3 LatAm processor      | −$1,100 ± 170                       | −$560/mo     | +3                |
| RH1 PPV hit              | +$820 ± 220 (Q2 also +$430)         | +$250/mo     | +6                |
| DQ1 affiliate bots       | −$220 ± 250 (noise; bots never pay) | ~0           | **+539**          |
| RC1+RC2+RC3+RH1 together | −$5,360 ± 320                       | −$2,590/mo   | −105              |

In a world without RC1, RC2, RC3 and RH1, Q3/Q2 true revenue would be **+21.6%** and real MAU
**+13.0%**. Causes interact, so the individual rows don't sum exactly to the combined row.
(± is the standard error across seeds.)

---

## 4. Data quality issues (planted)

| ID  | Issue                                                       | How to detect                                                                                                                                                                | Impact if missed                                                                    |
| --- | ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| DQ1 | Bot accounts from `affiliate_network` (1,143 bots)          | Affiliate users with total session time under 2 minutes, only seen within 3 days of signup. This heuristic flags 1,142. Bots were 304 / 437 / 413 of MAU in Jul / Aug / Sep. | MAU growth overstated: +19.8% vs +11.1% real                                        |
| DQ2 | pix amounts stored in BRL from Aug 1 (49.90 / 9.90 / 14.90) | `amount_usd` for subscriptions should only ever be 9.99. 142 subscription rows (185 pix rows in total) are 49.90, first seen 2026-08-03.                                     | Q3 revenue overstated by $1,232; LatAm looks flat instead of −21%                   |
| DQ3 | `users.subscription_status` stale for failed LatAm renewals | 47 users are `active` with no successful subscription payment in the last 35 days                                                                                            | "Active subscribers" from the users table = 568 vs 530 actually paying in September |
| DQ4 | 136 users have `country='USA'` (legacy web form, pre-2026)  | Profile distinct values of `country`                                                                                                                                         | US-only queries miss ~2% of US users (active US subs: 323 vs 330)                   |

### Natural traps (not planted bugs, but realistic gotchas)

- **Failed charges are logged as rows.** Summing `amount_usd` without `status='success'` gives Q2 $22,105 → Q3 $28,487 (+29%), which is very wrong and is inflated by RC3's failed retries.
- **Refunds are negative rows** (89 rows, −$969). Gross vs net must be stated explicitly.
- **April is left-censored.** Renewals of subscriptions that started before the data window look like new starts.
- **The `users` table is a snapshot** as of 2026-09-30. It holds only the latest subscription spell, so it cannot answer "how many subscribers did we have in May"; use transactions.
- **PPV transactions have no `content_id`.** Attributing PPV to titles requires joining through `content_views` (`view_type='ppv'`).
- **`marketing_spend.impressions` is NULL for `affiliate_network`** (CPI networks report clicks/installs only).
- **No spend rows for organic/referral.** "CAC" for those channels is undefined, not zero.
- **Data starts 2026-04-01, but users signed up from 2025-10-01.** Older users have no activity history before April.

---

## 5. Red herring

**RH1 — "Revenue is flat because the June PPV hit faded."**

PPV revenue did fall, from $2,073 in Q2 to $1,198 in Q3 (corrected). The hit title's PPV views
were 81 in May and 74 in June, then 33 / 22 / 23 from July to September. So the hypothesis is
partly true for the PPV line.

But the title also triggered subscriptions that carried into Q3. Its net effect on the Q2→Q3
gap is about zero or slightly positive (+$0.4K ± 0.2K). An agent that stops here has found a
real but immaterial explanation.

**Other dead ends worth testing:**

- "The free-limit change grew MAU." It barely did (+26 users).
- "TikTok drove the growth." Non-bot signups were flat; the channel shift reduced real MAU.

---

## 6. What a strong investigation should conclude

1. **Fix the metrics before the board meeting.**
   - Report MAU excluding bot accounts.
   - Normalise pix amounts to USD.
   - Rebuild "active subscribers" from transactions.
   - Normalise `USA` to `US`.

   Headline restated: real MAU +11%, revenue −8% for the quarter and −26% June→September run-rate.

2. **LatAm payments (fastest money).** Roll back or hotfix the processor, re-attempt failed renewals, and run a win-back for involuntarily churned users. LatAm had 188 paying subscribers in June and 115 in September; recovering the ~70 lost is worth about $700/month, with more from new sign-ups that currently fail.
3. **Free limit.** Revert to 5, or A/B test 5 vs 6 vs 8 with a paywall prompt at the cap. At 8 the limit costs about $1.4K/month at current run-rate for a negligible retention benefit.
4. **Paid acquisition.**
   - Stop `affiliate_network` immediately: ~80% bots, about $0.03 of revenue per signup.
   - Restore Google Search budget: by far the best 60-day payback.
   - Hold TikTok and influencers to geos and creatives that convert.
   - Judge channels on LTV/CAC, not CAC or installs.
5. **Governance.** The growth push was judged on MAU and CAC, and both looked great. Add a "qualified MAU" and a revenue guardrail metric (e.g., paywall-hit rate or new paid starts) to any growth OKR.

---

## 7. Robustness (12 seeds, same parameters)

| Metric (Q3 vs Q2)      | Mean   | SD across seeds | Seed 12 (shipped) |
| ---------------------- | ------ | --------------- | ----------------- |
| MAU, reported          | +20.0% | 1.7             | +19.8%            |
| MAU, excluding bots    | +10.9% | 1.6             | +11.1%            |
| Net revenue, reported  | +2.0%  | 5.2             | −2.4%             |
| Net revenue, corrected | −5.3%  | 4.5             | −8.3%             |

- True revenue declined in 11 of 12 seeds.
- The MAU story is stable across seeds.
- Revenue has more sampling noise, because there are only ~500 paying subscribers. Seed 12 was chosen as a representative draw, not an extreme one.

## 8. Known simplifications (honest limits of the simulation)

- **New-user activity isn't front-loaded.** Day-1 return is 13–20% by channel, lower than typical apps. Weekly and monthly retention are more realistic (week-2 return 28–59% by channel).
- **Pricing is simplified:** one global price ($9.99), no annual plans or trials, renewals every 30 days.
- **Release schedule:** all episodes of a title are available on its release date; there is no weekly simulcast.
- **Granularity is one day,** with no timezones and no session timestamps.
- **The `users` table keeps only the latest subscription spell.** Full history lives in `transactions`.
