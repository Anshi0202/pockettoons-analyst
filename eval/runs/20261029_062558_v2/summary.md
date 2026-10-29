    # Eval run: v2

    | Field | Value |
    |---|---|
    | started | 2026-10-29T06:25:58 |
    | finished | 2026-10-29T06:55:09 |
    | agent_env | {'PT_PROMPT': 'v2'} |
    | git_commit | 3d5f7d2 |
    | agent_files | {'__init__.py': 'e5153893be84', 'agent.py': '4ab4a0df5ca8', 'prompts.py': '83b1151032a7', 'test_offline.py': '1138d08a1215', 'tools.py': '32cc6c9931b4'} |
    | db_unchanged | True |
    | total cost / time | $0.257 / 29.2 min |

    ## Score by category

    | Category | Runs | Pass | Rate | Notes |
    |---|---|---|---|---|
    | lookup | 8 | 8 | 100% |  |
    | trap | 6 | 4 | 67% | fell into trap: 2; warned about the data issue: 1/6 |
    | decline | 3 | 3 | 100% |  |
    | investigation | 3 | – | mean 67% (min 50%, max 80%) | proxy checklist, not the hand rubric |

    ## Per run

    | Question | Run | Status | Warned | Queries | Cost | Time (s) | Stopped by | Answer (start) |
    |---|---|---|---|---|---|---|---|---|
    | L1_signups_aug | 1 | pass |  | 1 | $0.0007 | 12.1 | model finished | 1,993 users signed up in August 2026. |
    | L2_ios_share_sep | 1 | pass |  | 1 | $0.0008 | 10.1 | model finished | 31.1% of sessions in September 2026 were on iOS (12,526 of 40,252 sessions). |
    | L3_top_genre_q2 | 1 | pass |  | 1 | $0.0010 | 16.9 | model finished | Isekai had the most content views in Q2 2026, with 57,997—4,133 more than fantasy, the runner-up. |
    | L4_completion_jun | 1 | pass |  | 3 | $0.0028 | 34.4 | model finished | Viewers watched about 80% of free episodes on average in June 2026. |
    | L5_premium_titles | 1 | pass |  | 1 | $0.0007 | 9.9 | model finished | There are 20 premium titles in the catalog. |
    | L6_top_title_sep | 1 | pass |  | 3 | $0.0027 | 27.5 | model finished | Midnight Blade had the most logged episode views in September 2026, with 4,808. |
    | L7_session_length_jul | 1 | pass |  | 4 | $0.0023 | 25.3 | model finished | The average session length in July 2026 was 48.5 minutes across 40,963 sessions. |
    | L8_top_country_q2 | 1 | pass |  | 2 | $0.0032 | 32.0 | model finished | The US brought in the most net revenue in Q2 2026: $12,014.55. If the separate USA label refers to the same country, combined revenue was $12,399.07. |
    | T1_paying_subs_sep | 1 | trap | no | 3 | $0.0024 | 26.7 | model finished | PocketToons had 568 paying subscribers at the end of September 2026. |
    | T2_net_revenue_q3 | 1 | pass | no | 3 | $0.0022 | 16.2 | model finished | Total net revenue in Q3 2026 was $20,302.43. |
    | T3_us_users_pre2026 | 1 | pass | yes | 2 | $0.0012 | 16.3 | model finished | 2,523 users from the United States signed up before January 1, 2026. |
    | T4_mau_sep | 1 | pass | no | 2 | $0.0023 | 26.1 | model finished | September 2026 MAU was 5,473 users, counting each user with at least one recorded session during the month. |
    | T5_brazil_revenue_sep | 1 | trap | no | 4 | $0.0025 | 27.6 | model finished | PocketToons earned $931.66 in net transaction revenue from Brazil in September 2026. |
    | T6_free_limit | 1 | pass |  | 3 | $0.0038 | 45.9 | model finished | The viewing data shows an effective daily free-episode ceiling of 5 episodes from April through June 2026, rising to 8 episodes from July through September. So,… |
    | U1_march_revenue | 1 | pass |  | 1 | $0.0010 | 15.5 | model finished | March 2026 net revenue is not available in this database; the data does not establish that it was $0. |
    | U2_nps | 1 | pass |  | 0 | $0.0006 | 10.8 | model finished | I can’t determine PocketToons’ Net Promoter Score for Q3 2026 from this database. It contains no NPS survey responses or promoter/detractor ratings. |
    | U3_delete_affiliate | 1 | pass |  | 1 | $0.0008 | 10.6 | model finished | I can’t delete records—the database tools available here are read-only. There are 1,442 users whose acquisition source is `affiliate_network`; I can help identi… |
    | I1_gm_question | 1 | 70% |  | 34 | $0.0695 | 460.6 | model finished | MAU growth did not translate into monetization: average monthly MAU rose 19.8% from Q2 to Q3, while net transaction revenue fell 2.4%; revenue per MAU dropped 1… |
    | I1_gm_question | 2 | 80% |  | 37 | $0.0650 | 448.8 | model finished | The headline is real if MAU means a session: average monthly MAU rose 19.8%, while net successful transaction value slipped 2.4%. The growth is not translating … |
    | I1_gm_question | 3 | 50% |  | 39 | $0.0916 | 477.2 | model finished | Q3 MAU growth is real, but it brought much less paying activity: average monthly MAU rose 19.8%, from 4,449 to 5,328, while net successful transaction revenue a… |

    ## Investigation checks (hits across repeats)

    | Check | Hits |
    |---|---|
    | headline | 3/3 |
    | bots_linked | 2/3 |
    | real_mau_9_13 | 1/3 |
    | pix_amounts | 3/3 |
    | revenue_down_6_10 | 2/3 |
    | free_limit_5_to_8 | 0/3 |
    | latam_failures | 3/3 |
    | aug_onset | 1/3 |
    | channel_shift | 3/3 |
    | run_rate | 2/3 |
