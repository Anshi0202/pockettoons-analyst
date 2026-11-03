# PocketToons analyst: one-page write-up

Anshi Choudhary · November 2026 · [repo](https://github.com/Anshi0202/pockettoons-analyst)

**The task.** Build an AI analyst that answers the GM's question, *"MAU is up 20% QoQ but revenue is flat. Figure out what's happening and what we should do about it"*, and show honestly how well it works.

## How I built it

- **Data with a known answer.** `data/generate.py` simulates a freemium anime app user by user, day by day (ads → signups → viewing → paywall → payments), and writes April–September 2026 to SQLite. I planted three causes (free limit raised from 5 to 8 episodes a day; ad money moved to cheap, low-paying channels; LatAm payments failing from 1 August), four data traps (bots, Pix amounts in reais, a stale status column, `USA` vs `US`) and one red herring. The answer key is checked by re-running the simulation with each cause switched off, across 12 seeds. Truth: real MAU +11%, revenue −8.3%, September 26% below June.
- **The agent.** A ~330-line Python loop on the OpenAI Responses API (`gpt-6-luna`), no framework. Tools: `get_schema`, `run_sql` (one SELECT, with a required one-line purpose) and `update_hypotheses`. Read-only is enforced in code, not the prompt. Budget: 40 queries; every step is written to a trace.
- **Testing.** A 54-point rubric written before the graded run, and an 18-question eval with SQL answer keys committed before any run. A second prompt (v2) was compared with the first, plus a control world without the free-limit change.

## Results and where it breaks

It is reliable on ordinary work: 8/8 lookups, 3/3 refusals (including a delete request), never invented a number, and the database was unchanged after every run. The graded investigation scored 31/54 with no critical errors. Where it breaks:

- **It misses the largest cause.** It found the 5 → 8 limit in only 1 of 8 open investigations, yet finds it every time when asked directly. It checks a stated rule for breaches ("any day above 8?") instead of measuring what the data shows.
- **It skips data checks on quick questions.** It reported 568 subscribers from a stale status column (530 actually paid) and Brazil revenue in the wrong currency, although it catches the currency bug in long investigations.
- **It doesn't size what it finds.** "Fewer premium releases" became a finding in 2 of 3 runs per version, though it barely explains the gap.
- **It's noisy.** The same agent scored 60–80% on the same question. v2 made it do the skipped checks every time (0/3 → 3/3) and invented nothing in the control world, but it is an improvement, not a fix.

## How a team would use it

As a first-pass analyst, not a decision-maker. Ask it a question and get an answer in under a minute for under a cent, or a drafted investigation in 5–8 minutes for about $0.04–0.10, with every query in the trace. An analyst then reads the trace, checks the biggest claims, and asks the follow-ups ("what was the limit before July?"), which it answers well. Because it can't write to the database, it is safe to point at real data. For "why" questions, run it two or three times with v2 and trust findings that repeat. It finds patterns, not proven causes, so changes like the free limit still need an A/B test.

## What I'd do with more time

1. A quick data-quality pass before every answer: compare status columns with the events behind them, check amount distributions.
2. Make rule checks a by-month table (minimum, typical, maximum) instead of a yes/no breach query.
3. Size each driver before it becomes a finding, and add a reviewer step that challenges the top finding.
4. At least 10 runs per version, and a held-out dataset with a different planted story, ideally written by someone else.
5. Spend more of the time on the board deck. It is the main deliverable, and the first version missed the largest cause and kept the red herring until I revised it on 3 November.
