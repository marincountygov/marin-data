#!/usr/bin/env python3
"""Tests for the ACS calculations in build_statistics.py, with made-up source values."""
import importlib.util
import math
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_statistics", HERE / "build_statistics.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

GEO = "1400000US06041000100"


def tables(**cells):
    """One table T whose columns are the given cells: name -> (estimate, margin) as published text."""
    names = list(cells)
    columns = []
    row = []
    for n, (e, m) in cells.items():
        t, i = n.split("_")
        columns += [f"{t}_E{i}", f"{t}_M{i}"]
        row += [e, m]
    return {"T": {"table": "T", "columns": columns, "rows": {GEO: row}}}


def variable(**calc):
    return {"calculation": calc}


class ReadCell(unittest.TestCase):
    def test_estimate_and_margin(self):
        self.assertEqual(b.read_cell(tables(T_001=("100", "10")), GEO, "T_001"), (100, 10, 10))

    def test_decimal_estimate_is_kept(self):
        self.assertEqual(b.read_cell(tables(T_001=("43.2", "1.1")), GEO, "T_001"), (43.2, 1.1, 1.1))

    def test_controlled_estimate_has_no_published_margin_and_counts_as_zero(self):
        self.assertEqual(b.read_cell(tables(T_001=("5000", "-555555555")), GEO, "T_001"), (5000, None, 0))

    def test_margin_not_computable_keeps_the_estimate(self):
        self.assertEqual(b.read_cell(tables(T_001=("5000", "-222222222")), GEO, "T_001"), (5000, None, None))

    def test_open_ended_median_is_not_a_value(self):
        with self.assertRaises(b.Missing) as caught:
            b.read_cell(tables(T_001=("250001", "-333333333")), GEO, "T_001")
        self.assertIn("open-ended", caught.exception.reason)

    def test_no_sample_is_not_zero(self):
        with self.assertRaises(b.Missing):
            b.read_cell(tables(T_001=("-666666666", "-222222222")), GEO, "T_001")

    def test_blank_is_not_zero(self):
        with self.assertRaises(b.Missing):
            b.read_cell(tables(T_001=("", "")), GEO, "T_001")

    def test_zero_is_a_real_value(self):
        self.assertEqual(b.read_cell(tables(T_001=("0", "12")), GEO, "T_001")[0], 0)


class Sums(unittest.TestCase):
    def test_margin_is_root_of_summed_squares(self):
        t = tables(T_001=("100", "3"), T_002=("50", "4"))
        value, moe, used = b.value_of(variable(type="sum", cells=["T_001", "T_002"]), {}, t, GEO)
        self.assertEqual((value, moe), (150, 5))
        self.assertEqual(used, ["T_001", "T_002"])

    def test_difference_adds_the_margins_in_quadrature(self):
        t = tables(T_001=("100", "3"), T_002=("20", "4"))
        value, moe, _ = b.value_of(variable(type="sum", cells=["T_001"], subtract=["T_002"]), {}, t, GEO)
        self.assertEqual((value, moe), (80, 5))

    def test_controlled_part_counts_as_zero(self):
        t = tables(T_001=("100", "3"), T_002=("50", "-555555555"))
        _, moe, _ = b.value_of(variable(type="sum", cells=["T_001", "T_002"]), {}, t, GEO)
        self.assertEqual(moe, 3)

    def test_unknown_margin_in_a_part_gives_no_margin(self):
        t = tables(T_001=("100", "3"), T_002=("50", "-222222222"))
        value, moe, _ = b.value_of(variable(type="sum", cells=["T_001", "T_002"]), {}, t, GEO)
        self.assertEqual((value, moe), (150, None))

    def test_missing_part_leaves_the_sum_out(self):
        t = tables(T_001=("100", "3"), T_002=("-666666666", "-222222222"))
        with self.assertRaises(b.Missing):
            b.value_of(variable(type="sum", cells=["T_001", "T_002"]), {}, t, GEO)


class Shares(unittest.TestCase):
    DEN = {"den": {"calculation": {"type": "direct", "cell": "T_001"}}}

    def share(self, num, den):
        t = tables(T_001=den, T_002=num)
        v = variable(type="share", numerator={"cells": ["T_002"]}, denominator="den")
        return b.value_of(v, self.DEN, t, GEO)

    def test_proportion_formula(self):
        # p = 0.2; margin = sqrt(20^2 - 0.2^2 * 50^2) / 1000 = sqrt(400 - 100) / 1000 -> in percent
        value, moe, _ = self.share(("200", "20"), ("1000", "50"))
        self.assertEqual(value, 20)
        self.assertAlmostEqual(moe, 100 * math.sqrt(300) / 1000, places=6)

    def test_ratio_formula_when_the_root_would_be_negative(self):
        value, moe, _ = self.share(("500", "10"), ("1000", "200"))
        self.assertAlmostEqual(moe, 100 * math.sqrt(10 ** 2 + 0.5 ** 2 * 200 ** 2) / 1000, places=6)

    def test_zero_numerator_is_zero_percent(self):
        value, moe, _ = self.share(("0", "12"), ("1000", "50"))
        self.assertEqual(value, 0)
        self.assertAlmostEqual(moe, 1.2, places=6)

    def test_zero_denominator_has_no_share(self):
        with self.assertRaises(b.Missing):
            self.share(("0", "0"), ("0", "0"))

    def test_controlled_denominator_is_exact_for_the_margin(self):
        value, moe, _ = self.share(("200", "20"), ("1000", "-555555555"))
        self.assertAlmostEqual(moe, 2.0, places=6)

    def test_unknown_margin_gives_value_without_margin(self):
        value, moe, _ = self.share(("200", "-222222222"), ("1000", "50"))
        self.assertEqual((value, moe), (20, None))


class OpenEnded(unittest.TestCase):
    """A median published as 'or more' becomes a one-sided bound, never the stand-in number."""

    AREA = {"kind": "place", "id": "https://example.org/id/area/a", "label": "A", "code": "a", "geoId": GEO, "geoid": "g"}

    def run_build(self, est, moe):
        t = {"B19013": {"table": "B19013", "columns": ["B19013_E001", "B19013_M001"], "rows": {GEO: [est, moe]}}}
        saved = b.MAPPING["variables"]
        b.MAPPING["variables"] = [v for v in saved if v["id"] == "median-household-income"]
        try:
            return b.build_observations([self.AREA], t)
        finally:
            b.MAPPING["variables"] = saved

    def test_stand_in_with_open_ended_margin_is_a_lower_bound(self):
        observations, omitted, counts = self.run_build("250001", "-333333333")
        (o,) = observations["places"]
        self.assertEqual(o["minValue"], 250000)
        self.assertNotIn("value", o)
        self.assertNotIn("marginOfError", o)
        self.assertEqual((omitted, counts["bound-only"]), ([], 1))

    def test_the_same_number_with_a_real_margin_is_a_real_estimate(self):
        observations, omitted, _ = self.run_build("250001", "4000")
        (o,) = observations["places"]
        self.assertEqual(o["value"], 250001)
        self.assertNotIn("minValue", o)

    def test_open_ended_margin_with_another_number_is_left_out_and_listed(self):
        observations, omitted, _ = self.run_build("180000", "-333333333")
        self.assertEqual(observations["places"], [])
        self.assertEqual(len(omitted), 1)
        self.assertIn("open-ended", omitted[0]["reason"])


class Values(unittest.TestCase):
    def test_whole_numbers_stay_whole_and_decimals_keep_six_places(self):
        self.assertEqual(b.tidy(5.0), 5)
        self.assertEqual(b.tidy(1 / 3), 0.333333)
        self.assertIsInstance(b.tidy(7), int)


if __name__ == "__main__":
    unittest.main()
