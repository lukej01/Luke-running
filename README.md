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
athlete/profile.md             PRs, the speed-vs-strength diagnosis, injury history
athlete/season-2026.md         summer 2026 history + current status
data/prs.csv                   lifetime bests
data/races.csv                 results with course adjustments
data/weeks.csv                 weekly training shape
data/README.md                 CSV schemas
data/schedule-2026.md          race every Saturday to state
tools/coachkit.py              predictions, planning, rule checks
tools/test_coachkit.py         tests
```

## Logging

Report training in prose — "ran 8 easy at 6:40, calf quiet this morning" — and
Claude appends the CSV rows. The one field worth stating every time is **how it
felt the next morning**, because that is where his injuries have always shown
up first.

## The tool

```bash
python3 tools/coachkit.py predict    # equivalents, profile, fitness, race range
python3 tools/coachkit.py plan       # week-by-week to state
python3 tools/coachkit.py week       # weekly load + rule flags
python3 tools/coachkit.py check      # violations only; exit 1 if any
python3 tools/coachkit.py xt --minutes 150
python3 tools/test_coachkit.py       # 23 tests
```

`week` and `check` enforce the standing rules against the actual log: the ~50
mile ceiling, two hard days per week, no volume-and-intensity in the same week,
progression only after symptom-free weeks, and no full workout within 48 hours
of a race.

## The two things that matter most

**Health.** He has been injured at 60+ miles per week three separate times, and
every flare followed a load or intensity jump, showing up the next morning
rather than during the run. Fitness has never been his limiter. Any plan that
trades health for volume has the trade backwards.

**He is speed-rich and aerobically under-built.** His 800 predicts a 13:43 5K;
he has run 15:19. Sub-15 does not require getting faster — it requires the
aerobic strength that mono and three injury cycles have never let him build.
Train threshold, not more 200s.

Those two point the same way: patient aerobic work, cross-training for the
volume he cannot absorb on foot, and a body that arrives in November intact.

## Status

Current fitness estimate ~14:48-15:09 flat 5K, anchored on the same-course
comparison (17:30 on the opener course last year, 16:59 this year). State
projection ~14:38-14:59. Run `predict` for the working.
