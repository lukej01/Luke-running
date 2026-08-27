# 2026 schedule

## Confirmed

| Date | Event | Venue | Notes |
|---|---|---|---|
| Fri 2026-11-06 | GHSA XC State Championships — day 1 | Carrollton HS course | 4A, 5A, Private (2A–4A) |
| **Sat 2026-11-07** | **GHSA XC State Championships — day 2** | **Carrollton HS course** | **6A, 2A, 1A, 7A, 3A — Luke races this day** |

Source: GHSA state cross country championship listings and the MileSplit GA meet
page for the 2026 championships. The two-day split (6A on Saturday) matches the
target date already in the plan.

## Countdown

Anchor date 2026-08-27:

| Milestone | Date | Weeks out |
|---|---|---|
| State (6A) | Sat 2026-11-07 | 10.3 |
| Region | *unconfirmed* | — |
| Sectionals | *unconfirmed* | — |

Recompute with:

```bash
python3 tools/coachkit.py countdown --to 2026-11-07
```

## Unconfirmed — needs Luke's input

**I could not retrieve the Denmark High School meet schedule.** Both
`ga.milesplit.com` and `ghsa.net` are blocked by this environment's network
egress proxy, so the team schedule page and the GHSA calendar could not be read.
Rather than guess at meet names and dates, they are left blank here.

**Luke — please fill in:**

- [ ] Denmark's remaining regular-season meets (name, date, course)
- [ ] Which course the season-opening 16:59 was run on
- [ ] Region meet date and site
- [ ] Sectionals date and site (if 6A runs sectionals this year)
- [ ] Which meets are goal races vs. rust-busters vs. skips

Add them to the table below and the phasing in `athlete/season-2026.md` can be
pinned to real dates.

| Date | Meet | Course | Priority | Course difficulty |
|---|---|---|---|---|
| | | | | |

**Course difficulty** is worth recording every time. Use it to adjust race times
back to a flat-5K equivalent — a 17:00 on a hard course is not a 17:00 5K.

The reference point available: last year he ran ~17:30 on the opener course and
15:19 the following week. Do **not** read that 2:11 gap as pure course
difficulty — it also contains a fast course on the other end, another week of
fitness, and peak-race conditions. The honest split is unknown. What the pairing
does establish is that a ~17:30 on this course was consistent with 15:19
ability, which is why this year's 16:59 is the strong signal it is.
