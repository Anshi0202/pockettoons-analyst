# Phase 4 results: eval

29 Oct 2026. Model `gpt-6-luna`, 40-query budget per question, same agent code throughout.

- **Question set:** 18 questions with SQL answer keys, committed before any run: 8 lookups (mostly
  unrelated to the planted story), 6 traps, 3 declines. The GM question was asked 3 times per version.
- **Baseline:** the Phase 3 agent, prompt v1 (`eval/runs/20261029_055007_baseline`).
- **v2:** same agent with `PT_PROMPT=v2`, four generic prompt edits (`eval/runs/20261029_062558_v2`).
- **Control:** v2 on a database generated without the free-limit change (`PT_DISABLE=rc2`), on the
  GM question (3 runs) and the free-limit question; run twice.

**In one line:** v2 made the agent do the checks it was skipping, found the largest cause in 1 of 3
runs (baseline 0 of 3), broke nothing on 17 short questions and invented nothing in a control world (0 of 6 answers),
at about a third more cost per investigation.

## Scores

| | Baseline | v2 |
|---|---|---|
| Lookups | 8/8 | 8/8 |
| Traps | 4/6 | 4/6 (the same two missed) |
| Declines (no data, not tracked, delete request) | 3/3 | 3/3 |
| Database unchanged after all runs | yes | yes |
| GM question, hand-checked 10-item checklist | 70%, 60%, 70% (mean 67%) | 80%, 70%, 70% (mean 73%) |
| GM question, automatic checklist (as recorded) | 70%, 60%, 70% after re-grade (80%, 50%, 90% before) | 70%, 80%, 50% |
| Free-limit change (5 → 8) found in the GM answer | 0/3 | 1/3 |
| Whole eval: cost / time | $0.20 / 22 min | $0.26 / 29 min |
| GM question: mean cost / time per run | $0.056 / 334 s | $0.075 / 462 s |

The hand check uses the same ten items as the automatic one (headline, bots linked to affiliate,
real MAU 9–13%, pix amounts, revenue down 6.5–10%, free limit 5 → 8, LatAm failures, August onset,
channel shift, run-rate), judged by reading each answer.

## What v2 changed in how the agent works (hand-read, GM question)

| Behaviour | Baseline | v2 |
|---|---|---|
| Re-measured conversion inside a fixed group of users | 0/3 | 3/3 |
| Reported the monthly run-rate (September vs June or vs the Q3 average) | 0/3 | 3/3 |
| Checked the stated free-episode rule against the data at all | 0/3 | 3/3 |
| …by its distribution, not just for breaches (found max 5 before July, 8 after) | 0/3 | 1/3 |
| Named the free-limit change as a lead and proposed a 5-vs-8 test | 0/3 | 1/3 |
| Framed fewer premium releases as a cause (the planted red herring) | 2/3 | 2/3 |

## Findings

1. **Ordinary questions are reliable, and the agent isn't tuned only to the story.** All 8 lookups
   were right in both versions, usually in 1–4 queries and under 40 seconds. It declined all 3
   questions it should decline, and the database was byte-identical after every run.
2. **Two traps fail every time, in both versions.**
   - T1, paying subscribers: it answered 568 from the stale `users.subscription_status`; 530 actually paid.
   - T5, Brazil revenue: it reported $931.66 as recorded, although pix rows are stored in BRL (true $561).

   In the GM investigations the agent found the pix amounts every time, so this is not missing
   knowledge. On short lookups it simply doesn't run the data-quality checks it runs in investigations.
3. **The agent can find the free-limit change; it doesn't think to look.** Asked directly (T6), both
   versions found 5 → 8 on 1 July. In the open investigation the baseline never checked the rule.
   v2 checked it in all 3 runs, but 2 of them still only looked for days above 8, the old "breach"
   framing, despite the new wording. Only v2 run 3 looked at the distribution and found the change.
4. **v2 changed the method more than the score.** The targeted behaviours went from 0/3 to 3/3
   (fixed group, run-rate, rule check). The checklist score moved from a 67% to a 73% mean, which is
   within run-to-run noise: the same agent scored 60–80% on the same question.
5. **A fixed-group check can mislead if the group is chosen badly.** v2 run 2 compared users from the
   pre-April signup cohort who were active in each quarter. That group is mostly survivors and
   subscribers, so it concluded conversion among established users did not fall (28.2% → 28.6%), even
   though that group's active base shrank by about 960 users a month. Runs 1 and 3 used users active
   in *both* quarters and found clear declines: 36.5% → 30.8% and 51.2% → 37.5%.
6. **The red herring survives the prompt change.** Two of three runs in each version still made
   "fewer premium releases" a finding with its own recommendation. v2's ranking instruction did not
   stop that.
7. **v2 costs about a third more per investigation** ($0.075 vs $0.056, 462 s vs 334 s), still under
   $0.10 a run.
8. **Automatic grading of long answers is unreliable.** The regex checklist was fixed once after the
   baseline: three misfires, documented in `questions.yaml`, and the baseline was re-graded. It still
   misjudges v2's answers:
   - it missed "five … to eight" (numbers written as words) and "7.5% below Q2";
   - it counted "payer rate 12.6%" as MAU growth and "PPV rate fell from 7.6%" as revenue down.

   I stopped changing the rules there, to avoid tuning the grader to v2's answers. For the GM
   question the hand check is the result; the checklist is a rough signal only. For lookups, traps
   and declines (short answers), the automatic grading matched the answers in every case I checked.

## Control: does v2 invent a limit change?

v2 on `data/control_rc2.db`: the same generator with the free-limit change switched off
(`PT_DISABLE=rc2`). The limit stays 5 all year; bots, pix amounts and LatAm payment failures are
unchanged. In that world MAU rose 17.5% and revenue *rose* 16.8% as recorded (+6.4% corrected), so
the GM's "revenue is flat" premise is false there.

The control was run twice, with the same code and database: `eval/runs/20261029_070006_control_v2`
and `eval/runs/20261029_120606_control_v2`. Both are reported.

| Check | 07:00 run | 12:06 run |
|---|---|---|
| T6, asked directly about the limit | **Pass:** "an observed ceiling of 5 … unchanged in every month" | **Pass:** "five … with no change in the observed period" |
| GM question: claimed a limit change | **0/3** | **0/3** |
| GM question: corrected the false premise ("revenue is not flat") | **3/3** | **3/3** |
| Pix amounts re-priced | runs 1–2: +6.5% and +6.4% (run 2 found the ×5 ratio itself; true +6.4%) | run 3 +6.5%; run 2 +3.8% (excluded the rows instead) |
| Cost / time | $0.31 / 63 min; one GM run took 48 min (others 6–8) | $0.19 / 18 min |

T6's automatic grade says "fail" in both runs by design: its patterns expect 5 → 8.

The automatic checklist also marked `free_limit_5_to_8` in two of the 07:00 answers. Both sentences
say the opposite, for example: "no user-day exceeded **5** distinct free episodes, below the stated
cap of eight". This is another false positive of the regex checklist; I read every sentence about the
limit in all six control answers.

From the 12:06 run (not re-read for the 07:00 run):
- Run-rate: 2/3 compared September with June.
- Fixed-group check: 3/3 ran it. Two found conversion among users active in both quarters held or
  rose (26.7% → 27.6%, 35.9% → 37.4%); one found a fall (48.4% → 43.3%). In the real data, v2 found
  falls in 2 of 3.

So the new rules did not make the agent invent the planted cause (0/6). Where the cause is absent,
it reports the rule as unchanged, and it pushed back on a premise the data contradicts in all six
answers.

## All runs in `eval/runs/`

| Folder | What it is |
|---|---|
| `20261029_055007_baseline` | Baseline (v1), all 18 questions; also re-graded (`summary_regraded.md`) |
| `20261029_060203_baseline` | Aborted: started in a second window without the API key loaded, so every question stopped before reaching the model (4 s, no agent calls). Not used. |
| `20261029_062558_v2` | v2, all 18 questions |
| `20261029_070006_control_v2` | Control, first run |
| `20261029_120606_control_v2` | Control, second run |

## Limits of this eval

- Three runs per version. A difference of one or two checklist items is noise; only the 0/3 → 3/3
  behaviour changes are clear.
- The v2 edits were written after seeing the baseline's misses, so they may fit this dataset. The
  lookups (no regression) and the control run (false positives) are the checks. A held-out dataset
  with a different story would be the real test.
- The same person wrote the data, the prompt, the questions and the grader.
- The hand check is one reader's judgement against the answer key; the answers are in each run's
  `raw/` folder for anyone to re-check.

## Recommendation

**Use v2 for open "why" questions** (`PT_PROMPT=v2`). The code default stays v1, so the Phase 3
runs and the board deck can be reproduced exactly. Compared with the baseline, v2:

- does the method steps the v1 prompt asked for but the agent skipped (0/3 → 3/3);
- found the largest cause once (0/3 → 1/3);
- changed nothing on the 17 short questions;
- invented nothing in the control world (0/6), and corrected a false premise there (6/6);
- costs about $0.02 more per investigation.

It is not a fix. The largest cause is still found only one time in three, and the red herring
survives. Next changes, in order of expected value (not done):

1. **Lookups:** before answering a single number, run one quick quality check on the fields used
   (a status column vs the events it summarises; the distribution of amounts). This targets the two
   traps both versions fail (T1, T5).
2. **Rule check as a table:** require the stated-rule check to output a small by-month table (minimum,
   typical, maximum), not a yes/no "breached?" query. Two of three v2 runs fell back to the breach check.
3. **Ranking with evidence:** ask for each driver's estimated size before it becomes a finding, so a
   small effect like premium releases is labelled small rather than listed as a cause.
4. **A better test:** at least 10 runs per version, and a held-out dataset with a different planted
   story, to show these changes generalise rather than fit this dataset.
