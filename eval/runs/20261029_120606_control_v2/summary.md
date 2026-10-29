# Eval run: control_v2

| Field | Value |
|---|---|
| started | 2026-10-29T12:06:06 |
| finished | 2026-10-29T12:24:31 |
| agent_env | {'PT_PROMPT': 'v2', 'PT_DB': 'data\\control_rc2.db'} |
| git_commit | 3d5f7d2 |
| agent_files | {'__init__.py': 'e5153893be84', 'agent.py': '4ab4a0df5ca8', 'prompts.py': '83b1151032a7', 'test_offline.py': '1138d08a1215', 'tools.py': '32cc6c9931b4'} |
| db_unchanged | True |
| total cost / time | $0.187 / 18.4 min |

## Score by category

| Category | Runs | Pass | Rate | Notes |
|---|---|---|---|---|
| trap | 1 | 0 | 0% | fell into trap: 0; warned about the data issue: 0/1 |
| investigation | 3 | – | mean 57% (min 50%, max 70%) | proxy checklist, not the hand rubric |

## Per run

| Question | Run | Status | Warned | Queries | Cost | Time (s) | Stopped by | Answer (start) |
|---|---|---|---|---|---|---|---|---|
| T6_free_limit | 1 | fail |  | 5 | $0.0053 | 55.2 | model finished | The data indicate an effective limit of five free episodes per user per day, with no change in the observed period. This conflicts with the product brief’s stat… |
| I1_gm_question | 1 | 50% |  | 37 | $0.0642 | 383.2 | model finished | The data does not show flat revenue: average monthly MAU rose 17.5% from Q2 to Q3, and average monthly net transaction revenue rose 16.8%. What is flat is reven… |
| I1_gm_question | 2 | 50% |  | 29 | $0.0469 | 302.2 | model finished | The data does not show flat revenue QoQ: from Q2 to Q3 2026, session-based MAU rose 17.4% and successful net transaction revenue rose 16.8%. But the latest mont… |
| I1_gm_question | 3 | 70% |  | 40 | $0.0703 | 364.8 | query budget | Using average monthly session-based MAU, Q3 2026 (July–September) was up 17.5% from Q2 (April–June), not quite 20%. Recorded net transaction revenue was up 16.8… |

## Investigation checks (hits across repeats)

| Check | Hits |
|---|---|
| headline | 0/3 |
| bots_linked | 1/3 |
| real_mau_9_13 | 2/3 |
| pix_amounts | 3/3 |
| revenue_down_6_10 | 1/3 |
| free_limit_5_to_8 | 0/3 |
| latam_failures | 3/3 |
| aug_onset | 1/3 |
| channel_shift | 3/3 |
| run_rate | 3/3 |
