# PocketToons analyst: Phase 3 grading, run 2 (trace 20261029_044042)

Graded 29 Oct 2026 against `investigation/grading_rubric.md` (rules unchanged) and `data/story.md` (seed 12).
Evidence refers to the step numbers in the console log (`sql N/40`). Every number in the report was also
re-computed with plain SQL by `investigation/verify_run2.py` (output in `verify_run2_output.txt`).

## Run record

| Field | Value |
|---|---|
| Agent | Version A (`agent/agent.py`) |
| Model | `gpt-6-luna` |
| Question (exact wording) | MAU is up 20% QoQ but revenue is flat. Board meeting Thursday. Figure out what's happening and what we should do about it. |
| Trace files | `investigation/traces/20261029_044042_mau-is-up-20-qoq-but-revenue-is-flat-boa.md` and `.jsonl` |
| run_sql calls used | 31 / 40 (0 errors) |
| Model calls used | 14 / 60 |
| Cost / wall time | $0.0427 / 264 s (271K in, 31K out, of which 22K reasoning) |
| Earlier attempts | **1.** Run 1 (04:29, trace `20261029_042941`, 40/40 queries, stopped by budget) is the first complete run, scored informally in `phase3-investigation-notes.md`. Reason for run 2: _fill in_ (and whether the prompt changed). |

## A. Data quality and traps: 12 / 16

| # | Item | Score | Evidence |
|---|---|---|---|
| A1 | DQ1 bot accounts | 1 | sql 21, 24: 805 session-only user-months in Q3 vs 2 in Q2; sql 15, 29: affiliate 1,486 user-months, 2 payer-months, $19.98. Reports view-based MAU (+13.8%) but never links the session-only months to affiliate signups or removes them; calls bots "inconclusive". |
| A2 | DQ2 pix in BRL | 2 | sql 11, 16–18: finds $49.90 subs, $9.90/$14.90 PPV and −$49.90 refunds on pix from August (49 success, 136 failed, all correct); normalises to −8.2% (true −8.3%). Frames it as a possible price change, not a currency bug, and doesn't spot the ×5 ratio. |
| A3 | DQ3 stale status | 1 | Payers come from transactions, so the trap never bit, but the report never counts subscribers or notices the stale `active` rows. |
| A4 | DQ4 `USA` vs `US` | 2 | sql 3: found both labels, combined for country splits. |
| A5 | Failed charges | 2 | sql 2, 4: revenue = `status='success'` only ($20,795 → $20,302). |
| A6 | Refunds | 2 | Definition states revenue includes negative refunds. |
| A7 | Snapshot table | 2 | sql 10, 25: payer-months built from transactions by month. |
| A8 | Brief vs data | 0 | sql 26 checked only for days **above** 8. SQL: the max is 5 every day Apr–Jun, with 26% of free user-days at exactly 5, then 8 from July (10% at the cap). |

## B. Headline: 3 / 6

| # | Item | Score | Evidence |
|---|---|---|---|
| B1 | GM's numbers | 2 | MAU 4,449 → 5,328 (+19.8%), revenue $20,795 → $20,302 (−2.4%). Exact. |
| B2 | Quarter restated | 1 | Revenue −8.2% is inside −6.5% to −10%. "Real" MAU offered is view-MAU +13.8%, outside +9% to +13% (bots with one view stay in). |
| B3 | Run-rate | 0 | sql 2 pulled monthly revenue, but the report gives quarters only; Sep vs Jun (−26%) never appears. |

## C. Root causes: 2 / 10

| # | Item | Score | Evidence |
|---|---|---|---|
| C1 | RC2 free limit 5 → 8 | 0 | Missed. The conversion fall (20.5% → 14.3%) is blamed on mix and premium supply. Never checked conversion within a fixed cohort (pre-April users: new sub starts 95/94 in May/Jun → 47/30/18 in Jul–Sep). |
| C2 | RC3 LatAm processor | 1 | sql 19, 22, 27: pix/oxxo/pse failure 6.3/13.5/7.3% → 56.4/58.9/62.7%, 257 failed attempts vs ~38 expected. Quarterly only, so the Aug 1 onset is hidden (by month: Jul 7.8% → Aug 78.8%, Sep 69.4%). No LatAm subscriber loss. |
| C3 | RC1 channel shift | 1 | sql 14, 20, 29: Google spend $5,008 → $883, TikTok $1,127 → $2,707, low payer rates for TikTok and affiliate. Missing: total spend −33%, signup counts, CAC vs payback. |
| C4 | Interaction | 0 | Not mentioned. |
| C5 | Ranking | 0 | RC2 not found, so the ranking can't be right. |

## D. Red herring and dead ends: 2 / 4

| # | Item | Score | Evidence |
|---|---|---|---|
| D1 | RH1 PPV hit | 1 | sql 28: premium releases 7 → 1, PPV views −41.6%, PPV sales −$721. Kept as the last finding and hedged, but treated as a contributing cause with its own recommendation instead of ruled immaterial. |
| D2 | No false wins | 1 | "Affiliate and TikTok account for ~89% of the user-month increase." Arithmetic is right, but TikTok (+871) mostly replaced Google and Meta (−952); real growth came from organic and referral (+957). Not called a win, but it credits TikTok with growth. |

## E. Recommendations: 5 / 10

| # | Item | Score | Evidence |
|---|---|---|---|
| E1 | Fix metrics first | 1 | Report viewer MAU alongside session MAU; audit pix pricing. No bot-free MAU, no restated revenue, no subscribers from transactions. |
| E2 | LatAm payments | 1 | Investigate decline reasons, track success by rail. No rollback/hotfix, retry of failed renewals, or win-back. |
| E3 | Free limit | 0 | Not mentioned. |
| E4 | Acquisition | 1 | Hold affiliate and TikTok expansion, test restoring Search, scale on cohort payback. Doesn't stop affiliate. |
| E5 | Governance | 2 | Viewer MAU and a session → view → payment funnel (qualified MAU); acquisition scale made conditional on payer conversion and payback (revenue guardrail). |

## F. Process: 7 / 8

| # | Item | Score | Evidence |
|---|---|---|---|
| F1 | Grounded numbers | 2 | 21 SQL checks cover every figure in the report; all reproduce exactly, including definition-specific ones (US −$564 only matches revenue in active user-months; −$1,217 only matches pricing odd PPV at $2.99). **Provisional** until the trace confirms each sits in a query result. |
| F2 | Hypothesis board | 1 | Updated only twice (step 5: 4 open, 1 supported; step 32: 5 supported, 1 rejected, 1 inconclusive). Set at the start and filled at the end rather than used to steer. Rejected hypotheses (limit breaches, `USA` label) are minor. |
| F3 | Confidence and limits | 2 | High/medium confidence per finding; open questions on pix intent, decline codes, session-only users. |
| F4 | Budget | 2 | Finished by itself at 31/40. |

## Critical errors

- [ ] Says revenue grew. **No.**
- [ ] Gives the PPV hit as the main cause. **No** (finding 4 of 4, hedged).
- [ ] Presents +20% MAU as real growth without checking for bots. **No** (view MAU and 805 session-only user-months reported).
- [ ] States a number that doesn't appear in any query result. **Pending trace.** All numbers reproduce from SQL; 89%, 17% and 13.8% are arithmetic on queried values.

## Results

| Section | Score | Max |
|---|---|---|
| A. Data quality and traps | 12 | 16 |
| B. Headline | 3 | 6 |
| C. Root causes | 2 | 10 |
| D. Red herring | 2 | 4 |
| E. Recommendations | 5 | 10 |
| F. Process | 7 | 8 |
| **Total** | **31** | **54** |

**Verdict: partial** (27–39, no critical error found so far).

- **Report headline in one line:** MAU +19.8% but revenue −2.4% because fewer active users pay (payer conversion 20.5% → 14.3%), and odd Pix prices hide a real decline of about −8%.
- **Found but not in story.md:**
  - *Premium release cadence* (7 premium titles / 173 episodes in Q2, 1 / 25 in Q3): real in the data, but unplanned; the generator draws release dates at random. Its effect is small: in the generator's own diagnostics, subscriptions started at the premium wall fell 146 → 127 (−13%), while those started at the free cap fell 394 → 161 (−59%).
  - *805 session-only user-months* (2 in Q2): real; this is the bot signal, not a separate finding.
  - *ID+PH+VN +2,220 user-months for +$66 revenue*: real (Q3 revenue from these countries is $2,197; +$66 is the change).
- **Items that felt unfair:**
  - A3: the report never needed subscriber counts, so the DQ3 trap couldn't be exercised. Kept at 1 per the rule.
  - B2: view-MAU is a reasonable "real MAU" definition; it misses the band only because ~30% of bots log one view.
  - F1: scored on SQL reproduction because the trace wasn't available at grading time.
- **What to change before Phase 4 (eval):**
  1. RC2 was missed in both runs, so it is systematic, not bad luck. Two generic method gaps explain it: (a) the agent checks stated rules only for breaches, not against the observed distribution (max per day, value counts); (b) when a rate falls, it doesn't re-measure it inside a fixed population to separate mix from behaviour change.
  2. It reports quarter averages only. Asking for a monthly view of the headline metrics would have surfaced both the Sep run-rate (B3) and the Aug 1 payment onset (C2).
  3. Any prompt change must stay generic (no hints from story.md) and be logged in TIMELOG, otherwise the eval measures the answer key rather than the agent.

## Run 1 vs run 2 (same question)

| | Run 1 (04:29) | Run 2 (04:40) |
|---|---|---|
| Queries / model calls / cost | 40/40, 26, $0.078 | 31/40, 14, $0.043 |
| Stopped by | Query budget | Finished itself |
| DQ2 | $49.90 subs only, −7.5% | All three pix price points + refunds, −8.2% |
| RC1 evidence | 30-day payer rate by channel (Google 20.35%, TikTok 0.70%) | Spend shift + payer-months by source |
| RC2 | Missed | Missed (checked >8 only) |
| RH1 | Finding #4, hedged | Finding #4, hedged |

The same misses in both runs (RC2, RH1 framing, no bot exclusion) point to the method, not sampling noise.
