# Data files

Three small CSVs. No day-by-day logging required.

## `prs.csv` — lifetime bests

`distance,time,context`. Distances in metres or names (`800`, `1600`, `3200`,
`5k`). Drives the equivalence table and the speed-vs-strength profile.

## `races.csv` — race results

`date,meet,time,course,course_adj,flat_ref,notes`

- `course_adj` — seconds the course cost vs a fast one (flat 0, rolling 30-60,
  hard 90-130).
- `flat_ref` — only for anchor races: the flat-5K time known to correspond to
  that performance. The 2025 opener carries 15:19 because he ran it the
  following week. This is what makes the same-course comparison possible, and
  it is the strongest fitness signal available.

## `weeks.csv` — weekly training shape

`week_start,run_miles,xt_minutes,hard_days,symptoms,notes`

One row per week, Monday-dated. That is the right resolution: the rules that
matter (ceiling, hard days, progression) are all weekly.

`symptoms` is the field his injuries actually show up in — it records how the
week *felt the next morning*, not during:

| Value | Meaning | Response |
|---|---|---|
| `clean` | nothing beyond normal training soreness | proceed |
| `mild` | noticeable, fades with warm-up | hold load |
| `sore` | persistent, affects gait | reduce load, no progression |
| `sharp` | sharp, localized, or new | stop, cross-train, see the trainer |

Two consecutive weeks with no `sore` or `sharp` is what earns a mileage step.

## Logging

Report training in prose and Claude updates the CSVs. The one thing worth
saying every week is how it felt the next morning.
