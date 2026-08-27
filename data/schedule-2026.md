# 2026 schedule

## The shape

**A cross country race essentially every Saturday from now until state**, with
an occasional off weekend. That is all the plan needs — the weekly structure is
identical whichever meet it is.

| Date | Event | Notes |
|---|---|---|
| Sat 2026-11-07 | **GHSA State Championships, Carrollton** | 6A runs Saturday |
| Fri 2026-11-06 | State day 1 | 4A, 5A, Private — not his day |

State date confirmed against GHSA and MileSplit listings. Region and sectionals
dates are not confirmed; they land in the two weeks before state and the plan
already treats those weeks as sharpen and peak.

## Why the exact meet dates barely matter

Racing every Saturday makes the week self-scheduling:

- The race is one of two permitted hard days.
- So there is exactly **one** workout midweek.
- It goes **Tuesday**, which keeps it clear of the 48-hour rule on both sides.

That template holds whether Saturday is a rust-buster or region. What changes
across the season is the *content* of the Tuesday workout and the mileage,
which `coachkit plan` lays out week by week.

## What is worth recording

Not dates — results. After each race, add a row to `data/races.csv`:

```
date,meet,time,course,course_adj,flat_ref,notes
```

`course_adj` is the seconds the course cost versus a fast one. A rough guide:
flat and fast 0, rolling grass 30-60, genuinely hard 90-130. The opener is set
to 110.

Two races on the same course are worth far more than any single time, because
the course cancels out. That is how the current fitness estimate is anchored:
17:30 there last year, 16:59 there this year.
