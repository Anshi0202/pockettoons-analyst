# PocketToons analyst

An AI analyst agent that investigates a business question on its own: *"MAU is up 20% QoQ but revenue
is flat. Board meeting Thursday. Figure out what's happening and what we should do about it."*

The project has four parts, built in order and logged in [`TIMELOG.md`](TIMELOG.md):

1. **Data:** a synthetic SQLite database for a fictional freemium anime streaming app, with planted
   causes, data-quality traps and a red herring. The answer key is kept away from the agent.
2. **Agent:** a plain Python loop on the OpenAI Responses API with read-only SQL tools, a query
   budget and a full trace of every step.
3. **Investigation:** the agent answers the GM's question; the run is graded against a rubric written
   in advance, and a 10-slide board deck is built from its findings.
4. **Eval:** 18 questions with SQL answer keys, run before and after one prompt change, plus a
   control test for false positives.

## Results at a glance

| | Result |
|---|---|
| Ordinary questions (8 lookups) | 8/8 correct, usually in 1–4 queries and under 40 s |
| Data traps (6 questions) | 4/6: misses a stale status column and a currency bug on single lookups |
| Questions it should decline (3) | 3/3: no data, metric not tracked, and a delete request refused; database unchanged |
| GM investigation, prompt v1 (3 runs) | 67% of a 10-item checklist (hand-checked); largest cause found 0/3 |
| GM investigation, prompt v2 (3 runs) | 73%; largest cause found 1/3; nothing invented in a control world (0/6) |
| Phase 3 graded run (fixed rubric) | 31/54, "partial", no critical errors |
| Cost | under $0.01 per lookup; about $0.04–0.09 per investigation |

In short, the agent reliably gets the headline right and finds most of the planted problems: the
currency bug, the LatAm payment failures, the channel shift and the low-quality affiliate traffic.
It usually misses the largest cause, the free-episode limit change. The details and honest limits
are below.

## Try it in Colab (no install)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Anshi0202/pockettoons-analyst/blob/main/notebooks/pockettoons_colab.ipynb)

[`notebooks/pockettoons_colab.ipynb`](notebooks/pockettoons_colab.ipynb) runs the whole project in a
browser:
- get the code and build the database;
- run the offline tests;
- ask the agent questions (prompt v1 or v2) and see every step it took;
- run the GM investigation and a 6-question eval.

The first three steps need no API key. After that it asks for your OpenAI key, which isn't saved
in the notebook.

## Quick start

Python 3.11+. Commands are for Windows Command Prompt; on Mac/Linux use `/` in paths,
`source .venv/bin/activate` to activate and `cp` instead of `copy`.

```
git clone https://github.com/Anshi0202/pockettoons-analyst
cd pockettoons-analyst
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Put your OpenAI key in `.env` (`OPENAI_API_KEY=...`). Then build the database (about 10 seconds,
seed 12), check its headline numbers, and ask the agent a question:

```
python data\generate.py
python data\validate.py
python agent\agent.py "What was MAU in August 2026?"
python agent\agent.py "MAU is up 20% QoQ but revenue is flat. Board meeting Thursday. Figure out what's happening and what we should do about it."
```

The investigation takes about 5–8 minutes. Each run writes a step-by-step trace to
`investigation\traces\`. To use the improved prompt from Phase 4, set `PT_PROMPT=v2` first
(Mac/Linux: put `PT_PROMPT=v2` in front of the command):

```
set PT_PROMPT=v2
python agent\agent.py "MAU is up 20% QoQ but revenue is flat. Board meeting Thursday. Figure out what's happening and what we should do about it."
```

**Without an API key**, these offline tests check, in order: tool safety and the loop against a
mock API; the eval's grading rules; that prompt v1 is unchanged and v2's edits are generic; and
that the eval's answer key matches the database.

```
python agent\test_offline.py
python eval\test_grader.py
python eval\test_prompts.py
python eval\check_answer_key.py
```

**Full eval** (about 22 minutes, about $0.20): `python eval\run_eval.py --label mine`

## Repository layout

```
data/            generate.py (synthetic data), validate.py, story.md (answer key; the agent never sees it)
agent/           agent.py (loop + CLI), tools.py (read-only SQL), prompts.py (v1 and v2), test_offline.py
investigation/   traces/ (every agent run), grading_rubric.md, grading_run2.md, verify_run2.py,
                 run2_console.txt, board_deck.pptx
eval/            questions.yaml, run_eval.py, grade.py, regrade.py, compare.py, tests, runs/, results.md
notebooks/       pockettoons_colab.ipynb (the whole project in Google Colab)
TIMELOG.md       what was done when, and why
```

## 1. Data

`data/generate.py` (standard library only, deterministic) simulates the app from launch in October
2025 and writes April–September 2026 to six tables:

| Table | Rows |
|---|---|
| `users` | 20,708 |
| `sessions` | 232,354 |
| `content_views` | 564,780 |
| `transactions` (includes failed attempts) | 5,965 |
| `marketing_spend` | 815 |
| `content_catalog` | 81 |

Behaviour is simulated causally (acquisition → engagement → paywall → payments), so the story
emerges from the mechanics rather than being written into totals. Planted in Q3:

- **Three causes:**
  - **RC2, the largest:** the free limit rose from 5 to 8 episodes a day, so far fewer users hit
    the paywall.
  - **RC1:** paid budget moved to cheap, low-intent channels.
  - **RC3:** a LatAm payment processor started failing local payment methods.
- **Four data-quality traps:**
  - bot accounts from a new affiliate network;
  - Pix amounts stored in BRL;
  - a stale subscription-status column;
  - `USA` vs `US` country codes.
- **One red herring:** a premium hit fading.

Truth: MAU is really +11% (not +20%), and revenue is −8% for the quarter and −26% from June to
September (not flat). Each cause's dollar effect comes from counterfactual re-runs
(`PT_DISABLE=rc1,...`) across 12 seeds. Full answer key and known simplifications:
[`data/story.md`](data/story.md).

## 2. Agent

- **Loop** (`agent/agent.py`): no framework. The model either calls tools or writes its final report.
  Hard limits: 40 SQL queries and 60 model calls; when either runs out, tools are switched off and
  the model must report what it has.
- **Tools:**
  - `get_schema` returns tables, column notes, row counts and date ranges.
  - `run_sql` runs one SELECT and requires a one-sentence `purpose`, so the trace explains itself.
  - `update_hypotheses` is the model's working board of open, supported and rejected explanations.
- **Safety in code, not the prompt** (`agent/tools.py`): read-only SQLite connection (`mode=ro`),
  `PRAGMA query_only`, a single SELECT/WITH only, 30 s query timeout, 100-row cap. Errors come back as
  text so the model can fix its SQL.
- **Prompt** (`agent/prompts.py`): a generic analyst method (define the metric, check data quality,
  decompose, segment, test hypotheses, quantify, recommend, state confidence). Nothing from the answer
  key. The business context is copied from the brief, including its "8 free episodes per day", which
  the data contradicts before July. That tests whether the agent checks stated facts.
- **Model:** `gpt-6-luna` ($0.10 / $0.50 per 1M tokens). Not `gpt-5-nano`, which shuts down in
  December 2026. Change it in one line or with `PT_MODEL`.
- **Traces:** every step (purpose, SQL, result, hypotheses, tokens, cost) goes to `.md` and `.jsonl`
  as it happens, so even a crash leaves a usable record.

## 3. Investigation (Phase 3)

The rubric ([`investigation/grading_rubric.md`](investigation/grading_rubric.md)) was written before
the graded run (run 2). By mistake it was only committed to git at the end, so the git history
can't prove its timing; its scoring rules are unchanged.

- **Two runs.** Same agent, same question:
  - run 1: 40 queries, $0.08;
  - run 2: 31 queries, $0.04.
- **Run 2 graded:** 31/54, "partial", no critical errors
  ([`investigation/grading_run2.md`](investigation/grading_run2.md)).
- **Verified:** every figure in its report reproduces with plain SQL
  ([`investigation/verify_run2.py`](investigation/verify_run2.py)).
- **Found:** the headline, the odd Pix prices (corrected revenue −8.2% vs true −8.3%), LatAm payment
  failures, the Google → TikTok shift, and the `USA`/`US` codes.
- **Missed:**
  - the free-limit change: it checked only for days *above* 8, never what the limit was before July;
  - a bot-free MAU figure;
  - the September run-rate.
- **Red herring:** it made "fewer premium releases" a (hedged) finding.

The **board deck** (`investigation/board_deck.pptx`, 10 slides) uses only what the agent found, plus
one slide on what it couldn't establish. Adding causes by hand would have used the answer key, since
the same person wrote the data and the agent.

## 4. Eval (Phase 4)

Full write-up: [`eval/results.md`](eval/results.md). How to run it: [`eval/README.md`](eval/README.md).

- **18 questions** with SQL answer keys, committed before any run:
  - 8 lookups, mostly unrelated to the planted story;
  - 6 traps;
  - 3 declines;
  - the GM question, run 3 times per version.
- **v2 prompt** (`PT_PROMPT=v2`, off by default): the v1 prompt already asked for rule checks,
  monthly trends and separating mix from behaviour, but the agent skipped them. v2 makes those steps
  concrete and adds a self-check before answering. A test confirms the added text contains no
  story-specific terms.
- **Results:**
  - The targeted behaviours went from 0/3 to 3/3 runs: re-measuring conversion in a fixed group,
    the monthly run-rate, and checking the stated rule.
  - The largest cause was found 1/3 (was 0/3).
  - No change on the 17 short questions.
  - About $0.02 more per investigation.
- **Control:** v2 on a database generated *without* the limit change, run twice. No answer
  reported a limit change (0/6), and all 6 corrected the false "revenue is flat" premise; revenue
  had actually risen 17%.

## Design decisions

- **Plain loop, no agent framework:** about 330 lines that a reviewer can read end to end.
- **Read-only enforced in code:** the prompt can't be talked out of it. A delete request in the eval
  was refused, and the database was byte-identical before and after.
- **Answer key isolated:** the prompt is generic, and `story.md` is never in the agent's context.
- **Grading fixed in advance:** the eval questions were committed before any eval run (05:49; the
  first run started 05:50). The Phase 3 rubric was written before the graded run but committed late,
  as noted above. The one later change to the eval's grading rules is logged, and every run was
  re-graded with it.
- **v2 behind a switch:** the default stays v1, so the Phase 3 runs and the deck reproduce exactly.

## Honest limits

- **One author.** The same person wrote the data, the agent, the questions and the grader. The
  mitigations are lookups unrelated to the story, a control world, a test that the prompt is generic,
  and eval questions committed before the runs. A held-out dataset with a different story would be the real test.
- **Few runs.** Three runs per version, and the same agent scores 60–80% on the same question.
  Differences of a point or two are noise; only the 0/3 → 3/3 behaviour changes are clear.
- **The agent usually misses the largest cause.** Asked directly, it finds the 5 → 8 change every
  time. In an open investigation it found it once in eight runs (two in Phase 3, six in the eval).
- **Automatic grading of long answers is unreliable**: it misses numbers written as words and
  phrasings like "7.5% below". For the investigation, the hand check is the result.
- **Simplified data:** one price, 30-day renewals, no time zones; see `data/story.md` §8.
- **Costs are upper bounds:** prompt-cache discounts are ignored.
