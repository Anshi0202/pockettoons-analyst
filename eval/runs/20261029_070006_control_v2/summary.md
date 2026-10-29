# Eval run: control_v2

| Field | Value |
|---|---|
| started | 2026-10-29T07:00:06 |
| finished | 2026-10-29T08:03:15 |
| agent_env | {'PT_PROMPT': 'v2', 'PT_DB': 'data\\control_rc2.db'} |
| git_commit | 3d5f7d2 |
| agent_files | {'__init__.py': 'e5153893be84', 'agent.py': '4ab4a0df5ca8', 'prompts.py': '83b1151032a7', 'test_offline.py': '1138d08a1215', 'tools.py': '32cc6c9931b4'} |
| db_unchanged | True |
| total cost / time | $0.308 / 63.1 min |

## Score by category

| Category | Runs | Pass | Rate | Notes |
|---|---|---|---|---|
| trap | 1 | 0 | 0% | fell into trap: 0; warned about the data issue: 0/1 |
| investigation | 3 | – | mean 57% (min 50%, max 70%) | proxy checklist, not the hand rubric |

## Per run

| Question | Run | Status | Warned | Queries | Cost | Time (s) | Stopped by | Answer (start) |
|---|---|---|---|---|---|---|---|---|
| T6_free_limit | 1 | fail |  | 5 | $0.0047 | 48.8 | model finished | The viewing data shows an observed ceiling of 5 free episodes per user per day, not 8. It was unchanged in every month covered, April–September 2026; the data d… |
| I1_gm_question | 1 | 50% |  | 40 | $0.0941 | 429.6 | query budget | The database does not show flat Q3 transaction revenue: average monthly MAU rose 17.5% from Q2 to Q3, while successful transaction revenue net of refunds rose 1… |
| I1_gm_question | 2 | 70% |  | 37 | $0.0745 | 407.8 | model finished | The data does not show a clean “MAU up 20%, revenue flat” on a standard quarter-over-quarter basis: average monthly MAU rose 17.5% from Q2 to Q3, while net tran… |
| I1_gm_question | 3 | 50% |  | 37 | $0.1349 | 2901.8 | model finished | The data does not show flat transaction revenue: for Q2 (April–June 2026) versus Q3 (July–September), average monthly session-based MAU rose 17.5% and net succe… |

## Investigation checks (hits across repeats)

| Check | Hits |
|---|---|
| headline | 0/3 |
| bots_linked | 2/3 |
| real_mau_9_13 | 1/3 |
| pix_amounts | 2/3 |
| revenue_down_6_10 | 2/3 |
| free_limit_5_to_8 | 2/3 |
| latam_failures | 3/3 |
| aug_onset | 3/3 |
| channel_shift | 1/3 |
| run_rate | 1/3 |
