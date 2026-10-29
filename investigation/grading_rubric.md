# PocketToons analyst: Phase 3 grading rubric

> **Note added at submission (29 Oct, 13:50):** this rubric was written before run 2, the graded run,
> but by mistake it was not committed to git until submission. The commit named "grading rubric
> before first run" (04:40) contains the time log and run 1's trace, not this file. The text below is
> unchanged, including its claim that it was committed before the run, which turned out not to be true.

Written 29 Oct 2026, **before** the first full investigation run, and committed before it, so the
grading can't drift toward whatever the agent happens to find. It grades one run of agent Version A
(`agent/agent.py`, `gpt-6-luna`) on the GM question against `data/story.md` (seed 12).

Don't change the scoring rules after the run. If an item turns out to be unfair, keep the score and
say why under "Results".

## How to grade

1. Read the final report cold, as the GM would. Write its headline in one line before scoring.
2. Score each item 0, 1 or 2:
   - **2**: found, numbers within tolerance, and backed by a query in the trace.
   - **1**: mentioned or directionally right, but unquantified, outside tolerance, or not backed by a query.
   - **0**: missed or wrong.
3. Put the trace step or query that supports each score in the Evidence column.
4. Spot-check 10 numbers from the report against the trace (item F1).
5. List anything the agent found that isn't in `story.md`, and check with SQL whether it is real.

The agent can't run counterfactual re-runs, so it isn't expected to give the dollar cost of each
cause. Grade the ranking and the evidence behind it.

## Run record

| Field | Value |
|---|---|
| Agent | Version A (`agent/agent.py`) |
| Model | `gpt-6-luna` |
| Question (exact wording) | |
| Trace files | `investigation/traces/...md` and `.jsonl` |
| run_sql calls used | ___ / 40 |
| Model calls used | ___ / 60 |
| Cost / wall time | |
| Earlier attempts | 0 (if a run had to be repeated, say why) |

## A. Data quality and traps (max 16)

| # | Item | Full marks if the report... | Reference (story.md) | Score | Evidence |
|---|---|---|---|---|---|
| A1 | DQ1 bot accounts | flags `affiliate_network` accounts with near-zero activity and excludes them from MAU | 1,143 bots (heuristic flags 1,142); 304 / 437 / 413 of MAU in Jul / Aug / Sep | | |
| A2 | DQ2 pix stored in BRL | finds pix amounts of 49.90 from August and converts them to USD | 142 subscription rows at 49.90 (185 pix rows), first on 2026-08-03; Q3 overstated by $1,232 | | |
| A3 | DQ3 stale status | counts paying subscribers from `transactions`, not `users.subscription_status` | 568 "active" in users vs 530 paying in September; 47 stale | | |
| A4 | DQ4 `USA` vs `US` | normalises country codes before country splits | 136 users with `USA` | | |
| A5 | Failed charges | sums only `status='success'` | Wrong answer if missed: $22,105 → $28,487 (+29%) | | |
| A6 | Refunds | says revenue is net of refunds | 89 refund rows, −$969 | | |
| A7 | Snapshot table | uses `transactions` for subscriber counts over time | `users` is a 2026-09-30 snapshot with only the latest spell | | |
| A8 | Brief vs data | notices the free limit was 5 before Jul 1, not the 8 stated in the prompt | Limit 5 → 8 on 2026-07-01 | | |

## B. Headline (max 6)

| # | Item | Full marks if the report... | Reference | Score | Evidence |
|---|---|---|---|---|---|
| B1 | GM's numbers reproduced | matches MAU and revenue as reported, within 1 point | MAU 4,449 → 5,328 (+19.8%); revenue $20,795 → $20,302 (−2.4%) | | |
| B2 | Quarter restated | gives real MAU growth between +9% and +13% **and** corrected revenue between −6.5% and −10% | MAU 4,944 (+11.1%); revenue $19,070 (−8.3%) | | |
| B3 | Run-rate shown | shows monthly revenue and that September is well below June | Corrected $7,452 (Jun) → $5,542 (Sep), −26% | | |

## C. Root causes (max 10)

| # | Item | Full marks if the report... | Reference | Score | Evidence |
|---|---|---|---|---|---|
| C1 | RC2 free limit 5 → 8 | links the change to fewer cap hits and fewer new subscriptions, including among older users | Free user-days reaching the cap 26% → 10%; new subs from pre-April users 96 / 94 (May / Jun) → 47 / 30 / 18 (Jul–Sep) | | |
| C2 | RC3 LatAm processor | finds local-method failures from Aug 1 and the loss of LatAm subscribers | Failure rate 7–11% → 79% (Aug), 71% (Sep), other methods unchanged at 5–8%; LatAm paying subs 188 → 115 (−39%) vs US −16%, SEA −21% | | |
| C3 | RC1 channel shift | shows spend moved to low-intent channels and that lower CAC didn't pay back | Spend −33%; Google signups 828 → 147; TikTok 593 → 1,320; non-affiliate signups +2%; 60-day revenue per signup Google $2.34 vs TikTok $0.21 | | |
| C4 | Interaction | notes that acquisition was pushed into LatAm just as LatAm payments broke | RC1 + RC3 | | |
| C5 | Ranking | ranks RC2 as the largest cause, with RC1 and RC3 smaller and similar (1 point if all three are found but ranked differently) | Q3 revenue effect: RC2 −$3.6K, RC1 −$1.25K, RC3 −$1.1K | | |

## D. Red herring and dead ends (max 4)

| # | Item | Full marks if the report... | Reference | Score | Evidence |
|---|---|---|---|---|---|
| D1 | RH1 PPV hit | tests "the hit faded" and calls it real but immaterial to the gap | PPV $2,073 → $1,198; hit PPV views 81 / 74 (May / Jun) → 33 / 22 / 23; net effect ≈ 0 | | |
| D2 | No false wins | doesn't credit TikTok or the free-limit change with the MAU growth | Non-bot signups flat; free limit added ~26 MAU | | |

## E. Recommendations (max 10)

| # | Item | Full marks if the report recommends... | Score | Evidence |
|---|---|---|---|---|
| E1 | Fix metrics first | bot-free MAU, pix in USD, subscribers from transactions | | |
| E2 | LatAm payments | rollback or hotfix, retrying failed renewals, win-back for lost subscribers | | |
| E3 | Free limit | reverting to 5, or an A/B test with a paywall prompt at the cap | | |
| E4 | Acquisition | stopping `affiliate_network`, restoring Google Search, judging channels on LTV/CAC | | |
| E5 | Governance | a "qualified MAU" and a revenue guardrail on growth goals | | |

## F. Process (max 8)

| # | Item | 2 / 1 / 0 | Score | Evidence |
|---|---|---|---|---|
| F1 | Grounded numbers | 10 of 10 spot-checked numbers appear in a query result / 8–9 / 7 or fewer | | |
| F2 | Hypothesis board | hypotheses opened, tested and closed, including rejected ones / partly / not used | | |
| F3 | Confidence and limits | confidence stated per finding and what the data can't show / partly / neither | | |
| F4 | Budget | report delivered inside the budget / budget hit but report still written / no report | | |

## Critical errors

Any one of these makes the verdict "weak", whatever the score, because the board would act on it.

- [ ] Says revenue grew (summed failed charges, or used gross).
- [ ] Gives the PPV hit as the main cause.
- [ ] Presents +20% MAU as real growth without checking for bots.
- [ ] States a number that doesn't appear in any query result.

## Results (fill in after grading)

| Section | Score | Max |
|---|---|---|
| A. Data quality and traps | | 16 |
| B. Headline | | 6 |
| C. Root causes | | 10 |
| D. Red herring | | 4 |
| E. Recommendations | | 10 |
| F. Process | | 8 |
| **Total** | | **54** |

**Verdict:** strong (40 or more, no critical error) / partial (27–39) / weak (under 27, or any critical error)

- Report headline in one line:
- Found but not in story.md (real or wrong?):
- Items that felt unfair, and why:
- What to change before Phase 4 (eval):
