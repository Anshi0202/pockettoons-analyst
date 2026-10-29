# Phase 4: eval

Measures how well the PocketToons analyst agent answers questions with known answers, how often it
falls for the planted data traps, and how much its open-ended investigation varies between runs.
Then tests one generic prompt change (v2) against the baseline.

## Files

| File | What it is |
|---|---|
| `questions.yaml` | 18 questions, each with its expected answer and the SQL that produces it. Written before any eval run. |
| `check_answer_key.py` | Re-runs that SQL against `data/pockettoons.db` and confirms the key. |
| `grade.py` | The grading rules (no API calls). |
| `test_grader.py` | Offline checks of the grader, including on Phase 3 run 2's real report. |
| `run_eval.py` | Runs `agent/agent.py` once per question, exactly as from the command line, and grades it. |
| `compare.py` | Puts two or more eval runs side by side → `comparison.md`. |
| `runs/<timestamp>_<label>/` | One folder per eval run: `summary.md`, `results.jsonl`, `meta.json`, `raw/` console output, `traces/`. |

## The question set

| Category | Items | What it tests |
|---|---|---|
| lookup | 8 | Plain questions, mostly unrelated to the planted story (genre, platform, completion, sessions…). Does the agent generalise beyond what it was built around? |
| trap | 6 | A planted data issue gives a wrong answer if missed: stale subscription status, failed charges in revenue, `USA` vs `US`, bot accounts in MAU, pix amounts in BRL, the free-limit rule in the brief vs the data. |
| decline | 3 | The data can't answer (March revenue, NPS), or the action isn't allowed (delete users). |
| investigation | 1 × 3 runs | The GM's question, repeated to measure run-to-run variance. |

## How it is graded

- **number:** pass if any number in the answer is within tolerance of an accepted value; **trap** if
  it gives the trap value instead. **Warned** = the answer mentions the data issue (or contrasts the
  trap value with the right one).
- **text / decline:** regex patterns (case-insensitive).
- **investigation:** a 10-item regex checklist (headline, bots linked to affiliate, real MAU 9–13%,
  pix amounts, revenue down 6.5–10%, free limit 5 → 8, LatAm failures, August onset, channel shift,
  run-rate). Run 2 from Phase 3 scores 5/10 on it, in line with its hand grading.
  **This is a proxy for comparing runs, not a replacement for the hand rubric**
  (`investigation/grading_rubric.md`). Pick one investigation run per version and grade it by hand too.
- The runner also checks that the database file is byte-identical before and after (the agent is read-only).

Known limits of automatic grading: a number can pass by coincidence (a correct value appearing for
another reason), and regexes can miss correct phrasing. `summary.md` shows the start of every answer,
and `raw/` has the full output, so spot-check anything surprising.

## Run it (Windows cmd, venv active, project folder)

```
python eval\test_grader.py
python eval\check_answer_key.py
python eval\run_eval.py --label baseline --dry-run
python eval\run_eval.py --label baseline
```

Expect about 20 agent runs, roughly 25 minutes and $0.20–0.30. To compare two runs:

```
python eval\compare.py eval\runs\<baseline folder> eval\runs\<v2 folder>
```

## Experiment plan

1. **Baseline:** the agent exactly as used in Phase 3 (no prompt changes).
2. **v2:** the same agent with a few generic method rules added to the prompt, behind an env var
   (`--env PT_PROMPT=v2`). They are logged in TIMELOG.
3. **Control:** v2 on a database generated without the free-limit change (`PT_DISABLE=rc2`), to check
   the new rules don't make the agent "find" a change that isn't there.

The v2 rules are written in response to what the baseline missed, so they could overfit this dataset.
The lookups (unrelated to the story) and the control run are there to catch that.
