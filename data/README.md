# Data files

## `log.csv` — one row per session

The single source of truth for training. `tools/coachkit.py` reads this file.

### Columns

| Column | Meaning |
|---|---|
| `date` | ISO date, `YYYY-MM-DD`. Multiple rows per date are fine (doubles, run + lift). |
| `type` | `run`, `workout`, `race`, `xt`, `lift`, `off` |
| `miles` | Running miles. Blank for `xt`, `lift`, `off`. |
| `minutes` | Duration. **Required for `xt`** (drives the mileage credit). Optional elsewhere. |
| `pace` | Average pace, `M:SS` per mile. Blank if not meaningful. |
| `hard` | `1` if it counts against the two-hard-days-per-week limit, else `0`. Races and workouts are normally `1`. |
| `next_am` | How it felt the **next morning**: `clean`, `mild`, `sore`, `sharp`. Blank = not yet reported. |
| `confirmed` | `yes` if the date and details came from Luke directly; `no` if inferred or estimated and still needs checking. |
| `notes` | Free text. Splits, effort, weather, how it felt. Quote if it contains commas. |

### `next_am` values

This is the most important field in the file — his injury pattern shows up the
morning after, not during.

| Value | Meaning | Response |
|---|---|---|
| `clean` | Nothing. Normal training soreness at most. | Proceed. |
| `mild` | Noticeable but not sharp, fades with warm-up. | Hold load, watch it. |
| `sore` | Persistent, affects gait or lingers past warm-up. | Reduce load. No progression. |
| `sharp` | Sharp, localized, or new. | Stop. Cross-train. See the athletic trainer. |

Two consecutive weeks with no `sore` or `sharp` is what "symptom-free" means for
the progression rule.

### Example rows

```csv
2026-08-24,workout,9.0,,,1,clean,yes,"1.5mi @ 5:05 / 1mi @ 4:59 / 800 2:20 / 400 59 / 200 26, minimal rest"
2026-08-25,run,7.0,,6:45,0,clean,yes,easy
2026-08-25,xt,,45,,0,,yes,bike, spin
2026-08-26,off,,,,0,clean,yes,
```

## `training-notes.md`

Narrative that does not fit in a CSV cell — how a block felt, context for a bad
week, conversations with the trainer. Keep the numbers in `log.csv`.

## `schedule-2026.md`

Meet schedule. Several dates are still unconfirmed — see the checklist in that
file.

## Logging workflow

Luke does not need to write CSV. Report training in prose and Claude appends the
rows (see `CLAUDE.md`). The one thing worth reporting explicitly every time is
**how it felt the next morning**.
