#!/usr/bin/env python3
"""Training math for Luke-running.

Works off what actually exists: a set of PRs, a couple of race results, and a
weekly training shape. No day-by-day log required.

    python3 tools/coachkit.py predict          # fitness estimate + race range
    python3 tools/coachkit.py plan             # week-by-week to state
    python3 tools/coachkit.py week             # weekly load + rule flags
    python3 tools/coachkit.py check            # violations only
    python3 tools/coachkit.py equiv --time 9:29 --from 3200
    python3 tools/coachkit.py xt --minutes 150
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"

STATE_MEET = dt.date(2026, 11, 7)

# From athlete/profile.md: three separate injuries at 60+ miles per week.
MILEAGE_CEILING = 50.0
INJURY_THRESHOLD = 60.0
MAX_HARD_DAYS = 2
XT_MINUTES_PER_MILE = 10.0
RIEGEL_EXPONENT = 1.06
METERS_PER_MILE = 1609.344

SYMPTOM_RANK = {"": 0, "clean": 1, "mild": 2, "sore": 3, "sharp": 4}
SYMPTOMATIC = {"sore", "sharp"}

DISTANCES_M = {
    "400": 400.0, "800": 800.0, "1200": 1200.0, "1500": 1500.0,
    "1600": 1600.0, "mile": 1609.344, "3000": 3000.0, "3k": 3000.0,
    "3200": 3200.0, "2mile": 3218.688, "5000": 5000.0, "5k": 5000.0,
    "8k": 8000.0, "10k": 10000.0,
}


def parse_time(text: str) -> float:
    text = text.strip()
    if not text:
        raise ValueError("empty time")
    parts = text.split(":")
    if len(parts) > 3:
        raise ValueError("cannot parse time %r" % text)
    total = 0.0
    for part in parts:
        if not part.strip():
            raise ValueError("cannot parse time %r" % text)
        total = total * 60 + float(part)
    return total


def format_time(seconds: float) -> str:
    whole = int(round(max(0.0, float(seconds))))
    hours, rem = divmod(whole, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return "%d:%02d:%02d" % (hours, minutes, secs)
    return "%d:%02d" % (minutes, secs)


def parse_distance(text: str) -> float:
    key = text.strip().lower().replace(" ", "")
    if key in DISTANCES_M:
        return DISTANCES_M[key]
    if key.endswith("m") and key[:-1] in DISTANCES_M:
        return DISTANCES_M[key[:-1]]
    value = float(text)
    if value <= 0:
        raise ValueError("distance must be positive")
    return value


def distance_name(metres: float) -> str:
    for name, value in DISTANCES_M.items():
        if abs(value - metres) < 0.5 and name not in {"5000", "3000"}:
            return name
    return "%.0fm" % metres


def riegel(seconds: float, from_m: float, to_m: float) -> float:
    return seconds * (to_m / from_m) ** RIEGEL_EXPONENT


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return [r for r in csv.DictReader(handle) if any((v or "").strip() for v in r.values())]


def _num(text, default=0.0):
    try:
        return float((text or "").strip())
    except (ValueError, AttributeError):
        return default


@dataclass
class PR:
    distance: float
    time: float
    label: str
    context: str


def load_prs() -> list[PR]:
    prs = []
    for row in _rows(DATA / "prs.csv"):
        metres = parse_distance(row["distance"])
        prs.append(PR(metres, parse_time(row["time"]), distance_name(metres),
                      (row.get("context") or "").strip()))
    return sorted(prs, key=lambda p: p.distance)


@dataclass
class Race:
    meet: str
    time: float
    course: str
    course_adj: float
    flat_ref: float
    notes: str


def load_races() -> list[Race]:
    return [
        Race((r.get("meet") or "").strip(), parse_time(r["time"]),
             (r.get("course") or "").strip(), _num(r.get("course_adj")),
             _num(r.get("flat_ref")) or (parse_time(r["flat_ref"]) if (r.get("flat_ref") or "").strip() else 0.0),
             (r.get("notes") or "").strip())
        for r in _rows(DATA / "races.csv") if (r.get("time") or "").strip()
    ]


@dataclass
class Week:
    start: dt.date
    run_miles: float
    xt_minutes: float
    hard_days: int
    symptoms: str
    notes: str

    @property
    def xt_credit(self) -> float:
        return self.xt_minutes / XT_MINUTES_PER_MILE

    @property
    def load(self) -> float:
        return self.run_miles + self.xt_credit

    @property
    def symptom_free(self) -> bool:
        return self.symptoms not in SYMPTOMATIC


def load_weeks() -> list[Week]:
    weeks = []
    for row in _rows(DATA / "weeks.csv"):
        weeks.append(Week(
            start=dt.date.fromisoformat(row["week_start"].strip()),
            run_miles=_num(row.get("run_miles")),
            xt_minutes=_num(row.get("xt_minutes")),
            hard_days=int(_num(row.get("hard_days"))),
            symptoms=(row.get("symptoms") or "").strip().lower(),
            notes=(row.get("notes") or "").strip(),
        ))
    return sorted(weeks, key=lambda w: w.start)


# ------------------------------------------------------------------ rules

def evaluate(weeks: list[Week]) -> list[str]:
    flags = []
    for i, week in enumerate(weeks):
        label = "week of %s" % week.start
        prev = weeks[i - 1] if i else None
        if week.symptoms == "sharp":
            flags.append("[STOP] %s: sharp pain. Cross-train only and see the "
                         "athletic trainer." % label)
        if week.run_miles >= INJURY_THRESHOLD:
            flags.append("[STOP] %s: %.0f miles is at the mark where he has been "
                         "injured three times." % (label, week.run_miles))
        elif week.run_miles > MILEAGE_CEILING:
            flags.append("[WARN] %s: %.0f miles is over the %.0f ceiling."
                         % (label, week.run_miles, MILEAGE_CEILING))
        if week.hard_days > MAX_HARD_DAYS:
            flags.append("[WARN] %s: %d hard days, limit is %d (a race counts as one)."
                         % (label, week.hard_days, MAX_HARD_DAYS))
        if prev and prev.run_miles > 0:
            if week.run_miles > prev.run_miles * 1.10 and week.hard_days > prev.hard_days:
                flags.append("[WARN] %s: volume and intensity both rose. Advance one "
                             "at a time." % label)
            if week.run_miles > prev.run_miles * 1.05 and not prev.symptom_free:
                flags.append("[WARN] %s: mileage stepped up after a week with symptoms. "
                             "Progression is earned." % label)
    return flags


# --------------------------------------------------------------- commands

def cmd_predict(args) -> int:
    prs = load_prs()
    races = load_races()

    print("EQUIVALENTS FROM EACH PR")
    print()
    print("%-10s%10s%14s" % ("PR", "time", "-> 5K flat"))
    print("-" * 34)
    equivalents = []
    for pr in prs:
        five_k = riegel(pr.time, pr.distance, 5000.0)
        equivalents.append((pr, five_k))
        print("%-10s%10s%14s" % (pr.label, format_time(pr.time), format_time(five_k)))

    if equivalents:
        fastest = min(equivalents, key=lambda e: e[1])
        actual_5k = next((e for e in equivalents if abs(e[0].distance - 5000) < 1), None)
        print()
        print("PROFILE")
        if actual_5k and fastest[0].distance < 2000:
            gap = actual_5k[1] - fastest[1]
            print("  His %s predicts a %s 5K. He has actually run %s."
                  % (fastest[0].label, format_time(fastest[1]), format_time(actual_5k[1])))
            print("  Gap: %s. He is speed-rich and aerobically under-built." % format_time(gap))
            print("  Sub-15 is an aerobic-strength problem, not a speed problem.")
            print("  Train the weakness: threshold and sustained work, not more 200s.")

    if races:
        latest = races[-1]
        estimates = []

        # Method B: absolute course adjustment. One assumption, applied directly.
        absolute = latest.time - latest.course_adj
        estimates.append(("course-adjusted", absolute))

        # Method A: same-course delta against an anchor race whose flat
        # equivalent is known. Stronger, because the course cancels out.
        anchor = next((r for r in races
                       if r.course == latest.course and r.flat_ref and r is not latest), None)
        if anchor:
            same_course = anchor.flat_ref - (anchor.time - latest.time)
            estimates.append(("same-course delta", same_course))

        print()
        print("CURRENT FITNESS")
        for name, value in estimates:
            print("  %-20s %s" % (name, format_time(value)))
        if anchor:
            print()
            print("  Same-course delta is the stronger read: he ran %s on this course"
                  % format_time(anchor.time))
            print("  and %s the week after, so %s here maps to about %s."
                  % (format_time(anchor.flat_ref), format_time(latest.time),
                     format_time(same_course)))
            print("  And last year that was a week from peak. This year it was race one.")

        low = min(v for _, v in estimates)
        high = max(v for _, v in estimates)
        mid = (low + high) / 2
        print()
        print("  Current 5K: %s - %s (call it %s)"
              % (format_time(low), format_time(high), format_time(mid)))

        days = (STATE_MEET - dt.date.today()).days
        print()
        print("RACE PREDICTION")
        print("  %-26s%s - %s" % ("fast course, now:", format_time(low), format_time(high)))
        print("  %-26s%s - %s" % ("opener-type course, now:",
                                  format_time(low + latest.course_adj),
                                  format_time(high + latest.course_adj)))
        print("  %-26s%s - %s  (likely %s)"
              % ("state, %d days out:" % days, format_time(mid - 20),
                 format_time(high - 10), format_time(mid - 13)))
        print()
        print("  10 weeks of aerobic work is worth 15-25s to him because that is")
        print("  exactly the system he has never been able to build. Someone to")
        print("  chase is worth another 10-15.")
    return 0


# Explicit week-by-week, because the mileage curve is not a formula: it steps
# 45 -> 48 -> 50, holds, then comes down. Volume and intensity never rise in the
# same week, and the state-week cut is ~15%, not a big taper.
PLAN_BY_WEEKS_OUT = {
    9: (48, "Aerobic strength",
        "4 x 1 mile @ 5:10-5:15, 60s rest. Volume steps this week - hold intensity."),
    8: (48, "Aerobic strength",
        "5 x 1 mile @ 5:10, 60s rest. Or 25 min continuous @ 5:20."),
    7: (50, "Aerobic strength",
        "20-25 min continuous tempo @ 5:15-5:20. Volume steps - hold intensity."),
    6: (50, "Strength -> race specific",
        "6 x 1000 @ 3:00 (5K pace), 90s rest."),
    5: (50, "Strength -> race specific",
        "Hill strength: 8-10 x 60s uphill hard, jog down."),
    4: (50, "Strength -> race specific",
        "8 x 1000 @ 3:00, 90s rest."),
    3: (48, "Race specific",
        "5 x 1200 @ 3:36, 2 min rest."),
    2: (48, "Race specific - region",
        "3 x mile @ 4:48-4:52, 3 min rest."),
    1: (45, "Sharpen - sectionals",
        "4 x 800 @ 2:22, full recovery. Crisp, not exhausting."),
    0: (42, "STATE WEEK",
        "Tue: 3 x 800 @ 2:22. ~15% cut, intensity held. No big taper."),
}


def phase_for(weeks_out: int):
    key = min(max(weeks_out, 0), max(PLAN_BY_WEEKS_OUT))
    return PLAN_BY_WEEKS_OUT[key]


def cmd_plan(args) -> int:
    today = dt.date.today()
    weeks = load_weeks()
    earned = sum(1 for w in weeks[-4:] if w.symptom_free) if weeks else 0
    last_miles = weeks[-1].run_miles if weeks else 45.0

    print("PLAN TO STATE - %s (%d days)" % (STATE_MEET, (STATE_MEET - today).days))
    print()
    print("Standing weekly shape while racing every Saturday:")
    print("  Mon  easy 6-8 + XT 30-45min")
    print("  Tue  WORKOUT  <- the only midweek hard day")
    print("  Wed  easy 6-8 + XT 30-45min")
    print("  Thu  easy 5-6 + strides")
    print("  Fri  easy 3-4 + strides")
    print("  Sat  RACE")
    print("  Sun  long easy 10-12, or easy 6 + XT if the race was maximal")
    print()
    print("  Racing Saturday uses one of two hard days, so there is exactly one")
    print("  workout midweek. Tuesday keeps it >48h clear of the race both ways.")
    print("  Off weekends: add a second workout Friday and a real long run.")
    print()

    print("%-13s%6s%7s  %-26s%s" % ("week of", "out", "miles", "phase", "workout"))
    print("-" * 100)
    monday = today - dt.timedelta(days=today.weekday()) + dt.timedelta(days=7)
    while monday <= STATE_MEET:
        weeks_out = max(0, (STATE_MEET - monday).days // 7)
        miles, name, workout = phase_for(weeks_out)
        miles = min(miles, MILEAGE_CEILING)
        print("%-13s%6d%7.0f  %-26s%s" % (monday, weeks_out, miles, name, workout))
        monday += dt.timedelta(days=7)

    print()
    if earned >= 2 and last_miles < MILEAGE_CEILING:
        print("Mileage step from %.0f is EARNED: %d symptom-free weeks behind it."
              % (last_miles, earned))
        print("Step volume this week OR add intensity - never both.")
    else:
        print("Hold mileage. Progression is earned, and it has not been.")
    print("Ceiling is %.0f running miles. Cross-training carries anything above it."
          % MILEAGE_CEILING)
    return 0


def cmd_week(args) -> int:
    weeks = load_weeks()
    if not weeks:
        print("No weeks logged. Add rows to data/weeks.csv.")
        return 0
    print("%-13s%9s%9s%8s%8s%7s  %s"
          % ("week of", "run mi", "XT min", "XT mi", "load", "hard", "felt"))
    print("-" * 68)
    for week in weeks[-args.weeks:] if args.weeks > 0 else weeks:
        print("%-13s%9.0f%9.0f%8.1f%8.1f%7d  %s"
              % (week.start, week.run_miles, week.xt_minutes, week.xt_credit,
                 week.load, week.hard_days, week.symptoms or "-"))
    print()
    print("Load = running miles + XT at %.0f min/mile. Ceiling is %.0f *running* miles."
          % (XT_MINUTES_PER_MILE, MILEAGE_CEILING))
    flags = evaluate(weeks)
    print()
    print("\n".join(flags) if flags else "No rule violations.")
    return 0


def cmd_check(args) -> int:
    flags = evaluate(load_weeks())
    print("\n".join(flags) if flags else "No rule violations.")
    return 1 if flags else 0


def cmd_equiv(args) -> int:
    source = parse_distance(args.source)
    seconds = parse_time(args.time) - args.course_adj
    if seconds <= 0:
        raise SystemExit("course adjustment exceeds the time")
    targets = [parse_distance(args.target)] if args.target else \
        [DISTANCES_M[k] for k in ("800", "1600", "3200", "5k")]
    print("%s at %s%s" % (distance_name(source), format_time(seconds),
                          " (course-adjusted)" if args.course_adj else ""))
    print()
    print("%-10s%12s%12s" % ("distance", "equivalent", "pace/mile"))
    print("-" * 34)
    for target in targets:
        equivalent = riegel(seconds, source, target)
        print("%-10s%12s%12s" % (distance_name(target), format_time(equivalent),
                                 format_time(equivalent / (target / METERS_PER_MILE))))
    print()
    print("Riegel %s. For him these UNDER-rate long from short: his 800 and mile" % RIEGEL_EXPONENT)
    print("are far ahead of his 5K. Use the 3200 as the honest anchor.")
    return 0


def cmd_xt(args) -> int:
    print("%.0f min cross-training = %.1f mile-equivalents at %.0f min/mile"
          % (args.minutes, args.minutes / args.rate, args.rate))
    print("Real fitness for him - he ran 15:19 off almost pure XT.")
    print("Does not count against the running ceiling.")
    return 0


def cmd_countdown(args) -> int:
    target = dt.date.fromisoformat(args.to) if args.to else STATE_MEET
    days = (target - dt.date.today()).days
    print("%s -> %s: %d days, %.1f weeks" % (dt.date.today(), target, days, days / 7))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="coachkit", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    subs = parser.add_subparsers(dest="command", required=True)

    p = subs.add_parser("predict", help="fitness estimate and race prediction")
    p.set_defaults(func=cmd_predict)

    p = subs.add_parser("plan", help="week-by-week plan to state")
    p.set_defaults(func=cmd_plan)

    p = subs.add_parser("week", help="weekly load and rule flags")
    p.add_argument("--weeks", type=int, default=8)
    p.set_defaults(func=cmd_week)

    p = subs.add_parser("check", help="violations only; exit 1 if any")
    p.set_defaults(func=cmd_check)

    p = subs.add_parser("equiv", help="convert a time between distances")
    p.add_argument("--time", required=True)
    p.add_argument("--from", dest="source", required=True)
    p.add_argument("--to", dest="target")
    p.add_argument("--course-adj", type=float, default=0.0, metavar="SEC")
    p.set_defaults(func=cmd_equiv)

    p = subs.add_parser("xt", help="cross-training mileage credit")
    p.add_argument("--minutes", type=float, required=True)
    p.add_argument("--rate", type=float, default=XT_MINUTES_PER_MILE)
    p.set_defaults(func=cmd_xt)

    p = subs.add_parser("countdown", help="days and weeks to a date")
    p.add_argument("--to")
    p.set_defaults(func=cmd_countdown)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
