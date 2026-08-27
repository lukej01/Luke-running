#!/usr/bin/env python3
"""Tests for coachkit. Run: python3 tools/test_coachkit.py"""

from __future__ import annotations

import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import coachkit as ck  # noqa: E402


class TestTimeParsing(unittest.TestCase):
    def test_parses_all_shapes(self):
        self.assertEqual(ck.parse_time("59"), 59)
        self.assertEqual(ck.parse_time("2:20"), 140)
        self.assertEqual(ck.parse_time("16:59"), 1019)
        self.assertEqual(ck.parse_time("1:05:30"), 3930)

    def test_rejects_junk(self):
        for bad in ["", "  ", "1:2:3:4", "abc", "1::2"]:
            with self.assertRaises(ValueError):
                ck.parse_time(bad)

    def test_round_trips(self):
        for text in ["59", "2:20", "16:59", "1:05:30"]:
            self.assertEqual(
                ck.format_time(ck.parse_time(text)), text.lstrip("0") if text != "59" else "0:59"
            )


class TestDistanceParsing(unittest.TestCase):
    def test_named(self):
        self.assertEqual(ck.parse_distance("5k"), 5000)
        self.assertEqual(ck.parse_distance("5K"), 5000)
        self.assertAlmostEqual(ck.parse_distance("mile"), 1609.344)
        self.assertEqual(ck.parse_distance("1600"), 1600)

    def test_metre_suffix_does_not_break_mile(self):
        # Regression: naive "m" stripping turned "mile" into "ile".
        self.assertAlmostEqual(ck.parse_distance("mile"), 1609.344)
        self.assertEqual(ck.parse_distance("1600m"), 1600)
        self.assertEqual(ck.parse_distance("800m"), 800)

    def test_raw_metres(self):
        self.assertEqual(ck.parse_distance("4828"), 4828)

    def test_rejects_unknown(self):
        with self.assertRaises(ValueError):
            ck.parse_distance("furlong")
        with self.assertRaises(ValueError):
            ck.parse_distance("-100")


class TestRiegel(unittest.TestCase):
    def test_5k_converts_to_a_plausible_mile(self):
        five_k = ck.parse_time("15:19")
        mile = five_k * (1609.344 / 5000) ** ck.RIEGEL_EXPONENT
        self.assertGreater(mile, 250)
        self.assertLess(mile, 290)

    def test_riegel_underrates_this_athletes_speed(self):
        """Riegel converts his 15:19 to ~4:36. He has actually run 4:20 — sick.

        This is a real calibration fact, not a bug: he is meaningfully faster
        at the mile than his 5K implies. Treat Riegel mile equivalents as a
        floor for him, and do not use them to argue his 5K fitness is worse
        than it looks.
        """
        five_k = ck.parse_time("15:19")
        predicted = five_k * (1609.344 / 5000) ** ck.RIEGEL_EXPONENT
        actual = ck.parse_time("4:20")
        self.assertGreater(predicted, actual)
        self.assertGreater(predicted - actual, 10)

    def test_identity(self):
        time = ck.parse_time("16:59")
        self.assertAlmostEqual(time * (5000 / 5000) ** ck.RIEGEL_EXPONENT, time)


def _write_log(rows: list[str]) -> Path:
    handle = tempfile.NamedTemporaryFile(
        "w", suffix=".csv", delete=False, encoding="utf-8", newline=""
    )
    handle.write("date,type,miles,minutes,pace,hard,next_am,confirmed,notes\n")
    for row in rows:
        handle.write(row + "\n")
    handle.close()
    return Path(handle.name)


class TestWeeklyAggregation(unittest.TestCase):
    def test_xt_credit_and_load(self):
        path = _write_log(
            [
                "2026-08-24,run,10,,6:40,0,clean,yes,easy",
                "2026-08-25,xt,,120,,0,,yes,bike",
            ]
        )
        weeks = ck.build_weeks(ck.load_sessions(path))
        self.assertEqual(len(weeks), 1)
        week = weeks[0]
        self.assertAlmostEqual(week.run_miles, 10.0)
        self.assertAlmostEqual(week.xt_credit_miles, 12.0)
        self.assertAlmostEqual(week.load_miles, 22.0)

    def test_hard_days_count_distinct_dates(self):
        path = _write_log(
            [
                "2026-08-24,workout,8,,,1,clean,yes,am",
                "2026-08-24,run,4,,,1,clean,yes,pm double",
                "2026-08-27,race,3.1,,,1,clean,yes,meet",
            ]
        )
        week = ck.build_weeks(ck.load_sessions(path))[0]
        self.assertEqual(week.hard_days, 2)

    def test_empty_weeks_appear_in_gaps(self):
        path = _write_log(
            [
                "2026-08-03,run,5,,,0,clean,yes,",
                "2026-08-24,run,5,,,0,clean,yes,",
            ]
        )
        weeks = ck.build_weeks(ck.load_sessions(path))
        self.assertEqual(len(weeks), 4)
        self.assertEqual([bool(w.sessions) for w in weeks], [True, False, False, True])

    def test_week_starts_on_monday(self):
        self.assertEqual(ck.week_start(dt.date(2026, 8, 27)), dt.date(2026, 8, 24))
        self.assertEqual(ck.week_start(dt.date(2026, 8, 24)), dt.date(2026, 8, 24))
        self.assertEqual(ck.week_start(dt.date(2026, 8, 23)), dt.date(2026, 8, 17))


class TestRules(unittest.TestCase):
    def _flags(self, rows: list[str]) -> list[ck.Flag]:
        sessions = ck.load_sessions(_write_log(rows))
        return ck.evaluate(ck.build_weeks(sessions), sessions)

    def test_sharp_pain_is_a_stop(self):
        flags = self._flags(["2026-08-24,run,6,,,0,sharp,yes,calf"])
        self.assertTrue(any(f.severity == "STOP" and "SHARP" in f.message for f in flags))

    def test_sixty_miles_is_a_stop(self):
        flags = self._flags(
            [f"2026-08-2{d},run,10,,,0,clean,yes," for d in range(4, 8)]
            + ["2026-08-28,run,12,,,0,clean,yes,", "2026-08-29,run,12,,,0,clean,yes,"]
        )
        self.assertTrue(any(f.severity == "STOP" and "injured three times" in f.message for f in flags))

    def test_over_ceiling_warns_below_threshold(self):
        flags = self._flags(
            [
                "2026-08-24,run,26,,,0,clean,yes,",
                "2026-08-25,run,26,,,0,clean,yes,",
            ]
        )
        self.assertTrue(any(f.severity == "WARN" and "ceiling" in f.message for f in flags))
        self.assertFalse(any(f.severity == "STOP" for f in flags))

    def test_three_hard_days_warns(self):
        flags = self._flags(
            [
                "2026-08-24,workout,8,,,1,clean,yes,",
                "2026-08-26,workout,8,,,1,clean,yes,",
                "2026-08-29,race,3.1,,,1,clean,yes,",
            ]
        )
        self.assertTrue(any("hard days" in f.message for f in flags))

    def test_volume_and_intensity_together_warns(self):
        flags = self._flags(
            [
                "2026-08-17,run,30,,,0,clean,yes,",
                "2026-08-18,workout,10,,,1,clean,yes,",
                "2026-08-24,run,40,,,0,clean,yes,",
                "2026-08-25,workout,10,,,1,clean,yes,",
                "2026-08-27,workout,10,,,1,clean,yes,",
            ]
        )
        self.assertTrue(
            any("volume and intensity both rose" in f.message for f in flags)
        )

    def test_workout_within_48h_of_race_warns(self):
        flags = self._flags(
            [
                "2026-08-27,workout,8,,,1,clean,yes,",
                "2026-08-29,race,3.1,,,1,clean,yes,",
            ]
        )
        self.assertTrue(any("within 48 hours" in f.message for f in flags))

    def test_workout_four_days_before_race_is_fine(self):
        flags = self._flags(
            [
                "2026-08-25,workout,8,,,1,clean,yes,",
                "2026-08-29,race,3.1,,,1,clean,yes,",
            ]
        )
        self.assertFalse(any("within 48 hours" in f.message for f in flags))

    def test_stepping_up_after_symptoms_warns(self):
        flags = self._flags(
            [
                "2026-08-17,run,30,,,0,sore,yes,adductor",
                "2026-08-24,run,40,,,0,clean,yes,",
            ]
        )
        self.assertTrue(any("Progression is earned" in f.message for f in flags))

    def test_clean_hold_produces_no_warnings(self):
        flags = self._flags(
            [
                "2026-08-17,run,30,,,0,clean,yes,",
                "2026-08-18,workout,10,,,1,clean,yes,",
                "2026-08-24,run,30,,,0,clean,yes,",
                "2026-08-25,workout,10,,,1,clean,yes,",
            ]
        )
        self.assertEqual([f for f in flags if f.severity in {"STOP", "WARN"}], [])

    def test_missing_next_am_on_hard_session_is_flagged(self):
        flags = self._flags(["2026-08-24,workout,8,,,1,,yes,"])
        self.assertTrue(any("no next-morning report" in f.message for f in flags))

    def test_unconfirmed_entries_flagged(self):
        flags = self._flags(["2026-08-24,run,6,,,0,clean,no,guessed date"])
        self.assertTrue(any("unconfirmed" in f.message for f in flags))


class TestRealLog(unittest.TestCase):
    def test_repo_log_parses(self):
        sessions = ck.load_sessions(ck.DEFAULT_LOG)
        self.assertGreater(len(sessions), 0)
        for session in sessions:
            self.assertIn(session.type, ck.VALID_TYPES)
            self.assertIn(session.next_am, ck.SYMPTOM_RANK)


if __name__ == "__main__":
    unittest.main(verbosity=2)
