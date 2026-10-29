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
| `test_prompts.py` | Offline checks of the prompt variants: v1 unchanged, v2 edits generic. |
| `run_eval.py` | Runs `agent/agent.py` once per question, exactly as from the command line, and grades it. |
| `compare.py` | Puts two or more eval runs side by side → `comparison.md`. Uses re-graded results when present. |
| `regrade.py` | Re-grades a finished run from its saved output with the current rules (no agent calls). Used once: three investigation checks misfired on the baseline's real answers; see the change log in `questions.yaml`. |
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

1. **Baseline:** the agent exactly as used in Phase 3. `PT_PROMPT` unset (= v1, the Phase 3 prompt).
2. **v2:** the same agent and question set with `--env PT_PROMPT=v2`. The baseline prompt already
   asked for rule checks, monthly trends and mix-vs-behaviour separation; the agent didn't do them
   (Phase 3 grading). v2 makes those three steps concrete and adds step 9, a self-check before the
   final answer plus ranking drivers by size. The edits are listed in `agent/prompts.py` (`V2_EDITS`);
   `eval/test_prompts.py` checks v1 is unchanged and that the added text has no story-specific terms.
3. **Control:** v2 on a database generated with the free-limit change switched off (`PT_DISABLE=rc2`).
   The limit stays 5 all year there; bots, pix amounts and LatAm payment failures are unchanged.
   Pass = v2 does not report a limit change (`free_limit_5_to_8` 0/3, and T6 says 5, unchanged).
   In that world revenue *rose* (+17% recorded, +6% corrected), so a good answer also corrects the
   GM's "revenue is flat" premise. T6's automatic grade will say "fail" there by design (its patterns
   expect 5 → 8); read that answer by hand.

```
python eval\run_eval.py --label v2 --env PT_PROMPT=v2

set PT_DISABLE=rc2
set PT_DB=data\control_rc2.db
python data\generate.py
set PT_DISABLE=
set PT_DB=
python eval\run_eval.py --label control_v2 --env PT_PROMPT=v2 PT_DB=data\control_rc2.db --only I1_gm_question T6_free_limit
```

Clear `PT_DISABLE` and `PT_DB` right after generating (the two `set ...=` lines), or later commands in
that window would use the control world. Don't commit `data\control_rc2.db` (42 MB).

The v2 rules respond to what the baseline missed, so they could overfit this dataset. The lookups
(unrelated to the story) check for regressions, and the control run checks for false positives.
