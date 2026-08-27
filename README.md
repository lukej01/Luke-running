# Luke-running

Cross country training log and coaching assistant for Luke — sophomore distance
runner, Denmark HS, GHSA 6A. Target: top 3 at state and sub-15:00 on
**Saturday, November 7, 2026** at Carrollton.

Open this repo in Claude and it becomes the coach — `CLAUDE.md` loads
automatically with the role, the injury rules, and the athlete history.

## Layout

```
CLAUDE.md                      coach role + hard rules (auto-loaded)
prompts/training-assistant.md  the original prompt, kept verbatim
athlete/profile.md             durable facts: PRs, injury history, standing rules
athlete/season-2026.md         summer 2026 history + current status
data/log.csv                   one row per session — the source of truth
data/README.md                 CSV schema and the next_am scale
data/training-notes.md         narrative that doesn't fit in a cell
data/schedule-2026.md          meets (several still unconfirmed)
tools/coachkit.py              load accounting, rule checks, time conversion
tools/test_coachkit.py         tests
```

## Logging

Report training in prose — "ran 8 easy at 6:40, calf quiet this morning" — and
Claude appends the CSV rows. The one field worth stating every time is **how it
felt the next morning**, because that is where his injuries have always shown
up first.

## The tool

```bash
python3 tools/coachkit.py week --weeks 4        # weekly load + rule flags
python3 tools/coachkit.py check                 # violations only; exit 1 if any
python3 tools/coachkit.py equiv --time 16:59 --from 5k --course-adj 90
python3 tools/coachkit.py xt --minutes 150      # cross-training credit
python3 tools/coachkit.py countdown --to 2026-11-07
python3 tools/test_coachkit.py                  # tests
```

`week` and `check` enforce the standing rules against the actual log: the ~50
mile ceiling, two hard days per week, no volume-and-intensity in the same week,
progression only after symptom-free weeks, and no full workout within 48 hours
of a race.

## The one thing that matters most

He has been injured at 60+ miles per week **three separate times**, and every
flare followed a load or intensity jump — showing up the next morning, not
during the run. He also responds unusually well to cross-training (10 min ≈ 1
mile) and came back from a mono layoff to run 16:59 on a hard course in his
first race back.

Fitness has never been his limiter. Staying healthy is. Any plan that trades
health for volume has the trade backwards.

## Status

Current data is thin: `log.csv` holds three benchmark sessions, two with
estimated dates, and the ~45 mpw month behind them was not logged day by day.
`coachkit week` will flag all of that. Denmark's meet schedule could not be
retrieved — see the checklist in `data/schedule-2026.md`.
