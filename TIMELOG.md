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
