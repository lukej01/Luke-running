#!/usr/bin/env python3
"""Tests for coachkit. Run: python3 tools/test_coachkit.py"""
from __future__ import annotations

import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coachkit as ck  # noqa: E402


class TestTime(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(ck.parse_time("59"), 59)
        self.assertEqual(ck.parse_time("1:58"), 118)
        self.assertEqual(ck.parse_time("9:29"), 569)
        self.assertEqual(ck.parse_time("15:19"), 919)

    def test_rejects_junk(self):
        for bad in ["", "  ", "1:2:3:4", "abc", "1::2"]:
            with self.assertRaises(ValueError):
                ck.parse_time(bad)

    def test_format(self):
        self.assertEqual(ck.format_time(919), "15:19")
        self.assertEqual(ck.format_time(118), "1:58")


class TestDistance(unittest.TestCase):
    def test_mile_survives_m_stripping(self):
        # Regression: naive "m" stripping turned "mile" into "ile".
        self.assertAlmostEqual(ck.parse_distance("mile"), 1609.344)
        self.assertEqual(ck.parse_distance("1600m"), 1600)
        self.assertEqual(ck.parse_distance("3200"), 3200)

    def test_rejects_unknown(self):
        with self.assertRaises(ValueError):
            ck.parse_distance("furlong")


class TestRiegel(unittest.TestCase):
    def test_longer_is_slower(self):
        self.assertGreater(ck.riegel(569, 3200, 5000), 569)

    def test_3200_anchors_near_his_5k(self):
        """His 9:29 3200 converts to ~15:13 — within seconds of his 15:19 PR.

        This is why the 3200 is the honest anchor: it agrees with reality.
        """
        predicted = ck.riegel(ck.parse_time("9:29"), 3200, 5000)
        actual = ck.parse_time("15:19")
        self.assertLess(abs(predicted - actual), 20)

    def test_800_wildly_overrates_his_5k(self):
        """His 1:58 800 predicts 13:43. He has run 15:19.

        Not a bug — it is the whole diagnosis. He is speed-rich and
        aerobically under-built, so short-distance equivalents must never be
        used to set 5K expectations.
        """
        predicted = ck.riegel(ck.parse_time("1:58"), 800, 5000)
        self.assertLess(predicted, ck.parse_time("14:00"))


class TestRealData(unittest.TestCase):
    def test_prs_load(self):
        prs = ck.load_prs()
        self.assertEqual([p.label for p in prs], ["800", "1600", "3200", "5k"])

    def test_races_load_with_anchor(self):
        races = ck.load_races()
        self.assertEqual(len(races), 2)
        self.assertEqual(races[0].flat_ref, ck.parse_time("15:19"))

    def test_weeks_load(self):
        weeks = ck.load_weeks()
        self.assertTrue(weeks)
        self.assertTrue(all(w.run_miles <= ck.MILEAGE_CEILING for w in weeks))

    def test_current_log_is_clean(self):
        self.assertEqual(ck.evaluate(ck.load_weeks()), [])


def _week(start, miles, hard=2, symptoms="clean"):
    return ck.Week(dt.date.fromisoformat(start), miles, 0, hard, symptoms, "")


class TestRules(unittest.TestCase):
    def test_sixty_is_stop(self):
        flags = ck.evaluate([_week("2026-09-07", 60)])
        self.assertTrue(any("STOP" in f and "injured three times" in f for f in flags))

    def test_over_ceiling_warns(self):
        flags = ck.evaluate([_week("2026-09-07", 52)])
        self.assertTrue(any("ceiling" in f for f in flags))

    def test_three_hard_days_warns(self):
        flags = ck.evaluate([_week("2026-09-07", 45, hard=3)])
        self.assertTrue(any("hard days" in f for f in flags))

    def test_sharp_is_stop(self):
        flags = ck.evaluate([_week("2026-09-07", 45, symptoms="sharp")])
        self.assertTrue(any("STOP" in f and "sharp" in f for f in flags))

    def test_volume_and_intensity_together(self):
        flags = ck.evaluate([_week("2026-09-07", 40, hard=1),
                             _week("2026-09-14", 48, hard=2)])
        self.assertTrue(any("volume and intensity" in f for f in flags))

    def test_step_up_after_symptoms(self):
        flags = ck.evaluate([_week("2026-09-07", 40, symptoms="sore"),
                             _week("2026-09-14", 48)])
        self.assertTrue(any("Progression is earned" in f for f in flags))

    def test_steady_clean_weeks_are_silent(self):
        self.assertEqual(ck.evaluate([_week("2026-09-07", 48),
                                      _week("2026-09-14", 48)]), [])


class TestPlan(unittest.TestCase):
    def test_never_exceeds_ceiling(self):
        for out in range(0, 15):
            self.assertLessEqual(ck.phase_for(out)[0], ck.MILEAGE_CEILING)

    def test_clamps_outside_the_table(self):
        self.assertEqual(ck.phase_for(99), ck.PLAN_BY_WEEKS_OUT[max(ck.PLAN_BY_WEEKS_OUT)])
        self.assertEqual(ck.phase_for(0), ck.PLAN_BY_WEEKS_OUT[0])

    def test_taper_is_small(self):
        """He does not respond to big tapers — the cut is ~15%, not 30%."""
        peak = max(m for m, _, _, _ in ck.PLAN_BY_WEEKS_OUT.values())
        state_week = ck.PLAN_BY_WEEKS_OUT[0][0]
        self.assertLess((peak - state_week) / peak, 0.20)
        self.assertGreater((peak - state_week) / peak, 0.10)

    def test_mileage_never_jumps_more_than_10_percent(self):
        outs = sorted(ck.PLAN_BY_WEEKS_OUT, reverse=True)
        miles = [ck.PLAN_BY_WEEKS_OUT[o][0] for o in outs]
        for before, after in zip(miles, miles[1:]):
            if after > before:
                self.assertLessEqual((after - before) / before, 0.10)


if __name__ == "__main__":
    unittest.main(verbosity=1)
