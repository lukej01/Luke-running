#!/usr/bin/env python3
"""Training-log arithmetic for Luke-running.

Reads data/log.csv and applies the standing rules in athlete/profile.md:
the ~50 mile ceiling, two hard days per week, no volume-and-intensity in the
same week, progression only after symptom-free weeks, and no full workout
within 48 hours of a race.

Also converts race times between distances and cross-training minutes into
mileage credit.

    python3 tools/coachkit.py week --weeks 4
    python3 tools/coachkit.py check
    python3 tools/coachkit.py equiv --time 16:59 --from 5k --to mile
    python3 tools/coachkit.py xt --minutes 150
    python3 tools/coachkit.py countdown --to 2026-11-07
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG = REPO_ROOT / "data" / "log.csv"

# Standing limits. See athlete/profile.md — these come from three separate
# injuries at 60+ miles per week.
MILEAGE_CEILING = 50.0
INJURY_THRESHOLD = 60.0
MAX_HARD_DAYS = 2
XT_MINUTES_PER_MILE = 10.0
RIEGEL_EXPONENT = 1.06

# A week only counts as progression-earning if nothing worse than "mild"
# appeared the morning after any session.
SYMPTOM_RANK = {"": 0, "clean": 1, "mild": 2, "sore": 3, "sharp": 4}
SYMPTOMATIC = {"sore", "sharp"}

RUNNING_TYPES = {"run", "workout", "race"}
VALID_TYPES = RUNNING_TYPES | {"xt", "lift", "off"}

DISTANCES_M = {
    "400": 400.0,
    "800": 800.0,
    "1200": 1200.0,
    "1500": 1500.0,
    "1600": 1600.0,
    "mile": 1609.344,
    "3000": 3000.0,
    "3k": 3000.0,
    "3200": 3200.0,
    "2mile": 3218.688,
    "5000": 5000.0,
    "5k": 5000.0,
    "8k": 8000.0,
    "10k": 10000.0,
}

METERS_PER_MILE = 1609.344


# ---------------------------------------------------------------- parsing


def parse_time(text: str) -> float:
    """'59' -> 59, '2:20' -> 140, '16:59' -> 1019, '1:05:30' -> 3930."""
    text = text.strip()
    if not text:
        raise ValueError("empty time")
    parts = text.split(":")
    if len(parts) > 3:
        raise ValueError(f"cannot parse time {text!r}")
    total = 0.0
    for part in parts:
        if not part.strip():
            raise ValueError(f"cannot parse time {text!r}")
        total = total * 60 + float(part)
    return total


def format_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    whole = int(round(seconds))
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def parse_distance(text: str) -> float:
    """Return metres. Accepts named distances or a raw metre count."""
    key = text.strip().lower().replace(" ", "")
    if key in DISTANCES_M:
        return DISTANCES_M[key]
    # Tolerate a trailing metre suffix ("1600m", "800m") without mangling
    # names that legitimately contain an "m", such as "mile".
    if key.endswith("m") and key[:-1] in DISTANCES_M:
        return DISTANCES_M[key[:-1]]
    try:
        value = float(text)
    except ValueError:
        raise ValueError(
            f"unknown distance {text!r} — use metres or one of: "
            + ", ".join(sorted(DISTANCES_M))
        ) from None
    if value <= 0:
        raise ValueError("distance must be positive")
    return value


def _float_or_none(text: str) -> float | None:
    text = (text or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


@dataclass
class Session:
    date: dt.date
    type: str
    miles: float | None
    minutes: float | None
    pace: str
    hard: bool
    next_am: str
    confirmed: bool
    notes: str
    line_no: int

    @property
    def is_running(self) -> bool:
        return self.type in RUNNING_TYPES


def load_sessions(path: Path) -> list[Session]:
    if not path.exists():
        raise SystemExit(f"no log file at {path}")
    sessions: list[Session] = []
    problems: list[str] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for line_no, row in enumerate(csv.DictReader(handle), start=2):
            raw_date = (row.get("date") or "").strip()
            if not raw_date:
                continue
            try:
                date = dt.date.fromisoformat(raw_date)
            except ValueError:
                problems.append(f"line {line_no}: bad date {raw_date!r}")
                continue
            session_type = (row.get("type") or "").strip().lower()
            if session_type not in VALID_TYPES:
                problems.append(
                    f"line {line_no}: unknown type {session_type!r} "
                    f"(expected one of {', '.join(sorted(VALID_TYPES))})"
                )
                continue
            next_am = (row.get("next_am") or "").strip().lower()
            if next_am not in SYMPTOM_RANK:
                problems.append(f"line {line_no}: unknown next_am {next_am!r}")
                next_am = ""
            sessions.append(
                Session(
                    date=date,
                    type=session_type,
                    miles=_float_or_none(row.get("miles", "")),
                    minutes=_float_or_none(row.get("minutes", "")),
                    pace=(row.get("pace") or "").strip(),
                    hard=(row.get("hard") or "").strip() in {"1", "yes", "true"},
                    next_am=next_am,
                    confirmed=(row.get("confirmed") or "").strip().lower()
                    in {"yes", "y", "true", "1"},
                    notes=(row.get("notes") or "").strip(),
                    line_no=line_no,
                )
            )
    if problems:
        print("Log problems:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print("", file=sys.stderr)
    sessions.sort(key=lambda s: (s.date, s.line_no))
    return sessions


# ------------------------------------------------------------- aggregation


def week_start(date: dt.date) -> dt.date:
    return date - dt.timedelta(days=date.weekday())


@dataclass
class Week:
    start: dt.date
    sessions: list[Session] = field(default_factory=list)

    @property
    def run_miles(self) -> float:
        return sum(s.miles or 0.0 for s in self.sessions if s.is_running)

    @property
    def xt_minutes(self) -> float:
        return sum(s.minutes or 0.0 for s in self.sessions if s.type == "xt")

    @property
    def xt_credit_miles(self) -> float:
        return self.xt_minutes / XT_MINUTES_PER_MILE

    @property
    def load_miles(self) -> float:
        return self.run_miles + self.xt_credit_miles

    @property
    def hard_days(self) -> int:
        return len({s.date for s in self.sessions if s.hard})

    @property
    def worst_symptom(self) -> str:
        worst = ""
        for session in self.sessions:
            if SYMPTOM_RANK[session.next_am] > SYMPTOM_RANK[worst]:
                worst = session.next_am
        return worst

    @property
    def symptom_free(self) -> bool:
        return not any(s.next_am in SYMPTOMATIC for s in self.sessions)

    @property
    def missing_mileage(self) -> list[Session]:
        return [s for s in self.sessions if s.is_running and s.miles is None]

    @property
    def unreported_hard(self) -> list[Session]:
        return [s for s in self.sessions if s.hard and not s.next_am]


def build_weeks(sessions: list[Session]) -> list[Week]:
    """Group into Monday-start weeks, including empty weeks in any gap."""
    if not sessions:
        return []
    buckets: dict[dt.date, Week] = {}
    for session in sessions:
        start = week_start(session.date)
        buckets.setdefault(start, Week(start)).sessions.append(session)
    first = min(buckets)
    last = max(buckets)
    weeks = []
    cursor = first
    while cursor <= last:
        weeks.append(buckets.get(cursor, Week(cursor)))
        cursor += dt.timedelta(days=7)
    return weeks


# ------------------------------------------------------------------ rules


@dataclass
class Flag:
    severity: str  # "STOP", "WARN", "INFO"
    message: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.message}"


def evaluate(weeks: list[Week], sessions: list[Session]) -> list[Flag]:
    flags: list[Flag] = []

    # Sharp pain outranks everything else in this file.
    for session in sessions:
        if session.next_am == "sharp":
            flags.append(
                Flag(
                    "STOP",
                    f"{session.date} ({session.type}) reported SHARP pain the next "
                    "morning. Cross-train only and see the athletic trainer — "
                    "this is not something to train through.",
                )
            )

    for index, week in enumerate(weeks):
        label = f"week of {week.start}"
        previous = weeks[index - 1] if index else None

        if week.run_miles >= INJURY_THRESHOLD:
            flags.append(
                Flag(
                    "STOP",
                    f"{label}: {week.run_miles:.1f} running miles is at or above "
                    f"the {INJURY_THRESHOLD:.0f}-mile mark where he has been "
                    "injured three times. Cut back now.",
                )
            )
        elif week.run_miles > MILEAGE_CEILING:
            flags.append(
                Flag(
                    "WARN",
                    f"{label}: {week.run_miles:.1f} running miles is over the "
                    f"{MILEAGE_CEILING:.0f}-mile ceiling.",
                )
            )

        if week.hard_days > MAX_HARD_DAYS:
            flags.append(
                Flag(
                    "WARN",
                    f"{label}: {week.hard_days} hard days, limit is "
                    f"{MAX_HARD_DAYS} (a race counts as one).",
                )
            )

        if previous and previous.run_miles > 0 and previous.sessions:
            volume_up = week.run_miles > previous.run_miles * 1.10
            intensity_up = week.hard_days > previous.hard_days
            if volume_up and intensity_up:
                flags.append(
                    Flag(
                        "WARN",
                        f"{label}: volume and intensity both rose "
                        f"({previous.run_miles:.1f} → {week.run_miles:.1f} mi, "
                        f"{previous.hard_days} → {week.hard_days} hard days). "
                        "Advance one at a time.",
                    )
                )

        # Progression is earned: two clean weeks before mileage goes up.
        if previous and previous.run_miles > 0:
            stepping_up = week.run_miles > previous.run_miles * 1.05
            lookback = [w for w in weeks[max(0, index - 2) : index] if w.sessions]
            if stepping_up and lookback and not all(w.symptom_free for w in lookback):
                flags.append(
                    Flag(
                        "WARN",
                        f"{label}: mileage stepped up after a week with symptoms. "
                        "Progression is earned — hold until two consecutive "
                        "symptom-free weeks.",
                    )
                )

        if week.missing_mileage:
            dates = ", ".join(str(s.date) for s in week.missing_mileage)
            flags.append(
                Flag(
                    "INFO",
                    f"{label}: running sessions with no mileage recorded "
                    f"({dates}) — weekly totals are undercounted.",
                )
            )

        if week.unreported_hard:
            dates = ", ".join(str(s.date) for s in week.unreported_hard)
            flags.append(
                Flag(
                    "INFO",
                    f"{label}: hard sessions with no next-morning report "
                    f"({dates}). Ask before prescribing more load.",
                )
            )

    # No full workout within 48 hours before a race.
    races = [s for s in sessions if s.type == "race"]
    workouts = [s for s in sessions if s.type == "workout"]
    for race in races:
        for workout in workouts:
            gap = (race.date - workout.date).days
            if 0 <= gap <= 2:
                flags.append(
                    Flag(
                        "WARN",
                        f"workout on {workout.date} was {gap} day(s) before the "
                        f"race on {race.date} — the rule is no full workout "
                        "within 48 hours.",
                    )
                )

    unconfirmed = [s for s in sessions if not s.confirmed]
    if unconfirmed:
        dates = ", ".join(sorted({str(s.date) for s in unconfirmed}))
        flags.append(
            Flag(
                "INFO",
                f"{len(unconfirmed)} unconfirmed entr(y/ies) ({dates}). "
                "Dates or details were inferred — confirm before relying on them.",
            )
        )

    return flags


# --------------------------------------------------------------- commands


def cmd_week(args: argparse.Namespace) -> int:
    sessions = load_sessions(Path(args.log))
    weeks = build_weeks(sessions)
    if not weeks:
        print("No sessions logged yet.")
        return 0
    shown = weeks[-args.weeks :] if args.weeks > 0 else weeks

    header = (
        f"{'Week of':<12}{'Run mi':>8}{'XT min':>8}{'XT mi':>8}"
        f"{'Load':>8}{'Hard':>6}  {'Next AM':<8}"
    )
    print(header)
    print("-" * len(header))
    for week in shown:
        if not week.sessions:
            print(f"{str(week.start):<12}{'— no sessions logged —':>38}")
            continue
        print(
            f"{str(week.start):<12}"
            f"{week.run_miles:>8.1f}"
            f"{week.xt_minutes:>8.0f}"
            f"{week.xt_credit_miles:>8.1f}"
            f"{week.load_miles:>8.1f}"
            f"{week.hard_days:>6d}  "
            f"{(week.worst_symptom or '—'):<8}"
        )
    print()
    print(
        f"Load = running miles + cross-training credit at "
        f"{XT_MINUTES_PER_MILE:.0f} min/mile. Ceiling is "
        f"{MILEAGE_CEILING:.0f} *running* miles."
    )

    flags = evaluate(weeks, sessions)
    print()
    _print_flags(flags)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    sessions = load_sessions(Path(args.log))
    weeks = build_weeks(sessions)
    flags = evaluate(weeks, sessions)
    _print_flags(flags)
    return 1 if any(f.severity in {"STOP", "WARN"} for f in flags) else 0


def _print_flags(flags: list[Flag]) -> None:
    if not flags:
        print("No rule violations found.")
        return
    for severity in ("STOP", "WARN", "INFO"):
        matching = [f for f in flags if f.severity == severity]
        for flag in matching:
            print(flag)


def cmd_equiv(args: argparse.Namespace) -> int:
    source_time = parse_time(args.time)
    source_distance = parse_distance(args.source)
    adjusted = source_time - args.course_adj
    if adjusted <= 0:
        raise SystemExit("course adjustment is larger than the time itself")

    targets = (
        [parse_distance(args.target)]
        if args.target
        else [DISTANCES_M[k] for k in ("800", "1600", "mile", "3200", "5k")]
    )

    if args.course_adj:
        print(
            f"{args.time} on a course worth {args.course_adj:+.0f}s "
            f"→ flat equivalent {format_time(adjusted)} for "
            f"{source_distance:.0f}m"
        )
    else:
        print(f"{format_time(adjusted)} for {source_distance:.0f}m")
    print()
    print(f"{'Distance':<12}{'Equivalent':>12}{'Pace/mile':>12}")
    print("-" * 36)
    for distance in targets:
        equivalent = adjusted * (distance / source_distance) ** RIEGEL_EXPONENT
        pace = equivalent / (distance / METERS_PER_MILE)
        name = _distance_name(distance)
        print(f"{name:<12}{format_time(equivalent):>12}{format_time(pace):>12}")
    print()
    print(f"Riegel exponent {RIEGEL_EXPONENT}. Equivalents, not predictions —")
    print("weight recent races heaviest and adjust for course difficulty.")
    print()
    print("Calibration: Riegel turns his 15:19 into a ~4:36 mile, but he has")
    print("actually run 4:20 (while sick). He is faster at the mile than his")
    print("5K implies — treat mile equivalents as a floor, not a verdict.")
    return 0


def _distance_name(metres: float) -> str:
    for name, value in DISTANCES_M.items():
        if abs(value - metres) < 0.5 and name not in {"5000", "3000"}:
            return name
    return f"{metres:.0f}m"


def cmd_xt(args: argparse.Namespace) -> int:
    credit = args.minutes / args.rate
    print(
        f"{args.minutes:.0f} min cross-training ≈ {credit:.1f} mile-equivalents "
        f"at {args.rate:.0f} min/mile"
    )
    print()
    print("He responds unusually well to cross-training — he ran 15:19 off")
    print("almost pure cross-training. This credit is real fitness, but it does")
    print("not count against the running-mileage ceiling.")
    return 0


def cmd_pace(args: argparse.Namespace) -> int:
    distance = parse_distance(args.distance)
    total = parse_time(args.time)
    miles = distance / METERS_PER_MILE
    print(f"{args.time} for {_distance_name(distance)} ({miles:.2f} mi)")
    print(f"  pace/mile: {format_time(total / miles)}")
    print(f"  pace/400m: {format_time(total / (distance / 400.0))}")
    return 0


def cmd_countdown(args: argparse.Namespace) -> int:
    target = dt.date.fromisoformat(args.to)
    start = dt.date.fromisoformat(args.from_date) if args.from_date else dt.date.today()
    days = (target - start).days
    print(f"{start} → {target}")
    print(f"  {days} days")
    print(f"  {days / 7:.1f} weeks")
    if days < 0:
        print("  (already past)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="coachkit", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--log", default=str(DEFAULT_LOG), help="path to log.csv")
    subparsers = parser.add_subparsers(dest="command", required=True)

    week_parser = subparsers.add_parser("week", help="weekly load summary and rule flags")
    week_parser.add_argument("--weeks", type=int, default=6, help="how many recent weeks (0 = all)")
    week_parser.set_defaults(func=cmd_week)

    check_parser = subparsers.add_parser("check", help="rule violations only; exits 1 if any")
    check_parser.set_defaults(func=cmd_check)

    equiv_parser = subparsers.add_parser("equiv", help="convert a time between distances")
    equiv_parser.add_argument("--time", required=True, help="e.g. 16:59")
    equiv_parser.add_argument("--from", dest="source", required=True, help="e.g. 5k")
    equiv_parser.add_argument("--to", dest="target", help="omit for a full table")
    equiv_parser.add_argument(
        "--course-adj",
        type=float,
        default=0.0,
        metavar="SEC",
        help="seconds the course cost; subtracted before converting",
    )
    equiv_parser.set_defaults(func=cmd_equiv)

    xt_parser = subparsers.add_parser("xt", help="cross-training mileage credit")
    xt_parser.add_argument("--minutes", type=float, required=True)
    xt_parser.add_argument("--rate", type=float, default=XT_MINUTES_PER_MILE)
    xt_parser.set_defaults(func=cmd_xt)

    pace_parser = subparsers.add_parser("pace", help="pace breakdown for a time and distance")
    pace_parser.add_argument("--time", required=True)
    pace_parser.add_argument("--distance", required=True)
    pace_parser.set_defaults(func=cmd_pace)

    countdown_parser = subparsers.add_parser("countdown", help="weeks until a date")
    countdown_parser.add_argument("--to", required=True, help="YYYY-MM-DD")
    countdown_parser.add_argument("--from", dest="from_date", help="YYYY-MM-DD (default today)")
    countdown_parser.set_defaults(func=cmd_countdown)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
