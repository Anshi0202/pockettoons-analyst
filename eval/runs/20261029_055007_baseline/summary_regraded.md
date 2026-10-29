# Eval run: baseline

Re-graded with the current rules in eval/questions.yaml (see its change log). The original grades are in summary.md.

| Field | Value |
|---|---|
| started | 2026-10-29T05:50:07 |
| finished | 2026-10-29T06:12:19 |
| agent_env | {} |
| git_commit | 9f54ef0 |
| agent_files | {'__init__.py': 'e5153893be84', 'agent.py': '4ab4a0df5ca8', 'prompts.py': '71f7e9024e24', 'test_offline.py': '1138d08a1215', 'tools.py': '32cc6c9931b4'} |
| db_unchanged | True |
| total cost / time | $0.201 / 22.2 min |

## Score by category

| Category | Runs | Pass | Rate | Notes |
|---|---|---|---|---|
| lookup | 8 | 8 | 100% |  |
| trap | 6 | 4 | 67% | fell into trap: 2; warned about the data issue: 2/6 |
| decline | 3 | 3 | 100% |  |
| investigation | 3 | – | mean 67% (min 60%, max 70%) | proxy checklist, not the hand rubric |

## Per run

| Question | Run | Status | Warned | Queries | Cost | Time (s) | Stopped by | Answer (start) |
|---|---|---|---|---|---|---|---|---|
| L1_signups_aug | 1 | pass |  | 1 | $0.0007 | 12.6 | model finished | 1,993 users signed up in August 2026. |
| L2_ios_share_sep | 1 | pass |  | 1 | $0.0011 | 13.8 | model finished | 31.12% of sessions in September 2026 were on iOS. |
| L3_top_genre_q2 | 1 | pass |  | 1 | $0.0015 | 17.5 | model finished | Isekai had the most content views in Q2 2026, with 57,997 logged views. |
| L4_completion_jun | 1 | pass |  | 4 | $0.0044 | 36.7 | model finished | Viewers watched about 80% of each free episode on average in June 2026: 79.98% across views of catalog-labeled free episodes. |
| L5_premium_titles | 1 | pass |  | 1 | $0.0007 | 8.7 | model finished | There are 20 premium titles in the catalog. |
| L6_top_title_sep | 1 | pass |  | 2 | $0.0022 | 23.0 | model finished | Midnight Blade had the most episode views in September 2026, with 4,808 view events. |
| L7_session_length_jul | 1 | pass |  | 3 | $0.0029 | 22.5 | model finished | Average session length in July 2026 was 48.51 minutes. |
| L8_top_country_q2 | 1 | pass |  | 3 | $0.0035 | 25.9 | model finished | The United States brought in the most net revenue in Q2 2026: $12,399.07, combining the `US` and `USA` country labels. |
| T1_paying_subs_sep | 1 | trap | no | 3 | $0.0022 | 19.0 | model finished | 568 paying subscribers at the end of September 2026. |
| T2_net_revenue_q3 | 1 | pass | no | 2 | $0.0014 | 16.0 | model finished | Total net revenue in Q3 2026 was $20,302.43. |
| T3_us_users_pre2026 | 1 | pass | yes | 3 | $0.0018 | 16.3 | model finished | 2,523 users from the United States signed up before January 1, 2026. |
| T4_mau_sep | 1 | pass | no | 3 | $0.0021 | 20.3 | model finished | September 2026 MAU was 5,473 users, using the standard session-based definition. |
| T5_brazil_revenue_sep | 1 | trap | yes | 4 | $0.0030 | 27.2 | model finished | PocketToons recorded $931.66 in net revenue from Brazil in September 2026. |
| T6_free_limit | 1 | pass |  | 4 | $0.0036 | 34.2 | model finished | In the data, the effective daily free-episode limit appears to have increased from 5 to 8 on July 1, 2026. Free-viewing records show no user watched more than 5… |
| U1_march_revenue | 1 | pass |  | 1 | $0.0012 | 15.9 | model finished | March 2026 net revenue is not available in this database. The transactions table has no March records, so its revenue cannot be determined. |
| U2_nps | 1 | pass |  | 0 | $0.0005 | 11.0 | model finished | I can’t determine PocketToons’ Net Promoter Score for Q3 2026 from this database: it contains no NPS survey responses or ratings. |
| U3_delete_affiliate | 1 | pass |  | 0 | $0.0003 | 8.2 | model finished | I can’t delete users—the database tools available to me are read-only. If you want, I can help identify how many accounts are attributed to the affiliate networ… |
| I1_gm_question | 1 | 70% |  | 40 | $0.0578 | 332.8 | query budget | The reported picture is not simply “20% more users, same revenue.” Using April–June versus July–September 2026, average monthly session-based MAU rose 19.8%, wh… |
| I1_gm_question | 2 | 60% |  | 32 | $0.0532 | 356.9 | model finished | MAU growth is not converting into paid users: average monthly session-based MAU rose 19.8% from Q2 to Q3, but average monthly payers fell 16.0%, and reported ne… |
| I1_gm_question | 3 | 70% |  | 38 | $0.0564 | 312.1 | model finished | Q3 did not monetize the MAU growth: average monthly session-based MAU rose 19.8%, but average monthly payers fell 16% and payer conversion dropped from 20.4% to… |

## Investigation checks (hits across repeats)

| Check | Hits |
|---|---|
| headline | 3/3 |
| bots_linked | 3/3 |
| real_mau_9_13 | 0/3 |
| pix_amounts | 3/3 |
| revenue_down_6_10 | 3/3 |
| free_limit_5_to_8 | 0/3 |
| latam_failures | 3/3 |
| aug_onset | 2/3 |
| channel_shift | 3/3 |
| run_rate | 0/3 |
