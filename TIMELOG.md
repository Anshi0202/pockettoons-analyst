# Time log

| Time   | Phase       | What I did                | Decisions / cuts                                                                                 |
| ------ | ----------- | ------------------------- | ------------------------------------------------------------------------------------------------ |
| 01:48– | 01:48–03:05 | Repo setup, env, API test | OpenAI API (the key I have); plain Python loop instead of LangChain: easier to debug and explain |

## Thu 29 Oct 2026

- 03:00 – Phase 0: set up folders and installed packages.
- 03:25 – Phase 1, Step 1: wrote story.md (answer key). 3 linked causes + bot data issue + Android red herring.
- Decision: one main story only, no side stories, to save time.

- 04:05 – Phase 1 done. Built two versions of the data; kept the one with 4 data traps, a validation script and 12-seed testing. Checked: MAU 4,449 → 5,328 (+19.8%), 4,944 without bots.

## Phase 2: Agent (29 Oct, ~03:45–04:30)

- Built agent/: tools.py (get_schema, read-only run_sql: mode=ro, SELECT-only, 30s timeout, 100-row cap), prompts.py (generic analyst method, no story hints), agent.py (OpenAI Responses loop, 40-query budget, step traces with cost).
- Decision: added an update_hypotheses tool beyond the minimal design, so the trace shows which explanations were kept or rejected.
- Decision: kept the brief's "8 free episodes/day" in the prompt as stated; the data shows 5 before July, which tests whether the agent checks rules against data.
- Tests: 46 offline checks pass; 4/4 live smoke tests correct (MAU, net revenue, mobile sessions, top channel), ~$0.007 total.
- Observation: on simple lookups the data-quality checks are shallow (didn't flag low-activity accounts or the new affiliate channel). Revisit in Phase 3/4.

## Phase 3: Investigation (29 Oct, 04:29–04:40)

- Run 1 (baseline, no changes): 40/40 queries, 6 min, $0.08. All numbers verified against SQL.
  Found: headline, LatAm payments, channel shift, USA/US. Partial: bots, BRL bug, red herring.
  Missed: free-limit change (largest cause). Never checked whether existing users' conversion fell, or tested the free-episode rule against the data.

## Phase 4: Eval (29 Oct, 05:26–07:25)

- Built the eval: 18 questions with SQL answer keys (8 lookups, 6 traps, 3 declines, GM question x3),
  auto-marker, runner, compare and regrade scripts. Committed before any run.
- Baseline (agent unchanged): 20 runs, 22 min, $0.20. Database unchanged.
  Lookups 8/8. Declines 3/3. Traps 4/6: fell for stale subscriber status (568 vs 530 paying)
  and Brazil revenue with pix stored in BRL.
  Free-limit question asked directly: found 5 -> 8 on 1 Jul.
  GM question x3: 70% / 60% / 70% (proxy checklist). All found pix amounts, LatAm payment failures,
  channel shift and low-quality affiliate traffic. None found the free-limit change (0/3).
- Marker fix: three checklist rules misfired on real answers (quarter definition read as run-rate;
  revenue -9.1% read as MAU growth; "a 7.9% decline" missed). Fixed, tests added, baseline re-marked
  (80/50/90 -> 70/60/70). Logged in eval/questions.yaml.
- Prompt v2 added behind PT_PROMPT=v2 (default unchanged): steps 3-5 made concrete (measure stated
  rules over time, monthly trend and run-rate, re-measure rate changes in a fixed group) plus a
  step 9 self-check that ranks drivers.
  - v2 run (06:25–06:55): 20 runs, 29 min, $0.26. Lookups 8/8, traps 4/6 (same two), declines 3/3.
    GM question x3 hand-checked 80/70/70% (baseline 70/60/70). Fixed-group check, run-rate and rule
    check 0/3 -> 3/3; free-limit change found 1/3 (baseline 0/3). Red herring still 2/3.
  - Control (12:06–12:25): v2 on a database without the limit change. Free-limit question: "5, no
    change" (correct). GM question x3: no invented limit change (0/3); all 3 said revenue is actually
    up 16.8%, not flat. $0.19.
  - Results in eval/results.md. Recommendation: use v2 for "why" questions; default stays v1 so
    Phase 3 reproduces.

## Final: README and Colab (29 Oct, 12:36–13:30)

- README for graders: overview, quick start, results at a glance, design decisions, honest limits.
- Colab notebook (notebooks/pockettoons_colab.ipynb): runs the whole project in a browser.
  Tested cell by cell; fixed dollar amounts being shown as math formulas in Colab output.
- Repo made public.
