"""S48 WP1: recompute the small-sample statistics and the multi-sample grader.

The Wilson interval and pass@k are implemented independently here (not imported
from the module under test) so a wrong formula cannot pass by agreeing with
itself. The grader test builds a throwaway task set and submission tree.
"""

from __future__ import annotations

import json
from math import comb, sqrt
from pathlib import Path
import tempfile
import unittest

from tools.agent_eval_stats import (
    difference_interval,
    pass_at_k,
    summarize_group,
    wilson_interval,
)
from tools import run_agent_eval


def _wilson_reference(c: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = c / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z / denom * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, centre - half), min(1.0, centre + half)


class WilsonTests(unittest.TestCase):
    def test_matches_independent_formula(self) -> None:
        for c, n in [(0, 5), (1, 5), (3, 5), (5, 5), (5, 6), (6, 6), (30, 30)]:
            expected = _wilson_reference(c, n)
            actual = wilson_interval(c, n)
            self.assertAlmostEqual(actual[0], expected[0], places=12)
            self.assertAlmostEqual(actual[1], expected[1], places=12)

    def test_interval_bounds_and_degenerate_cases(self) -> None:
        low, high = wilson_interval(0, 5)
        self.assertAlmostEqual(low, 0.0, places=12)
        self.assertGreater(high, 0.0)
        low, high = wilson_interval(5, 5)
        self.assertLess(low, 1.0)
        self.assertAlmostEqual(high, 1.0, places=12)
        with self.assertRaises(ValueError):
            wilson_interval(0, 0)


class PassAtKTests(unittest.TestCase):
    def test_known_values(self) -> None:
        self.assertAlmostEqual(pass_at_k(5, 3, 1), 0.6, places=12)
        self.assertAlmostEqual(pass_at_k(5, 3, 2), 1 - comb(2, 2) / comb(5, 2), places=12)
        self.assertAlmostEqual(pass_at_k(5, 3, 5), 1.0, places=12)
        self.assertAlmostEqual(pass_at_k(5, 5, 1), 1.0, places=12)
        self.assertAlmostEqual(pass_at_k(5, 0, 3), 0.0, places=12)

    def test_rejects_bad_arguments(self) -> None:
        for args in [(0, 0, 1), (5, 6, 1), (5, 3, 0), (5, 3, 6)]:
            with self.assertRaises(ValueError):
                pass_at_k(*args)


class GroupSummaryTests(unittest.TestCase):
    def test_totals_and_per_task(self) -> None:
        summary = summarize_group("T", {"a": (4, 5), "b": (5, 5)}, k=5)
        self.assertEqual(summary["samples"], 10)
        self.assertEqual(summary["passed"], 9)
        self.assertAlmostEqual(summary["pass_at_1"], 0.9, places=12)
        self.assertEqual(summary["per_task"]["a"]["samples"], 5)
        self.assertIn("pass@5", summary["pass_at_k"])
        # n=10, c=9, k=5: n-c=1 < k, so every 5-subset contains a pass.
        self.assertAlmostEqual(summary["pass_at_k"]["pass@5"], 1.0, places=12)

    def test_difference_interval_contains_point_estimate(self) -> None:
        low, high = difference_interval(18, 30, 15, 30)
        self.assertLessEqual(low, 0.1)
        self.assertGreaterEqual(high, 0.1)
        # Symmetric when the inputs swap.
        swapped = difference_interval(15, 30, 18, 30)
        self.assertAlmostEqual(low, -swapped[1], places=12)
        self.assertAlmostEqual(high, -swapped[0], places=12)


class MultiSampleGraderTests(unittest.TestCase):
    def test_samples_are_counted_per_task_and_group(self) -> None:
        with tempfile.TemporaryDirectory(prefix="s48-eval-") as folder:
            root = Path(folder)
            tasks = {
                "tasks": [{
                    "id": "echo",
                    "title": "echo stdin",
                    "prompt": "read stdin and echo",
                    "expected_stdout": "hi\n",
                    "expected_exit_code": 0,
                    "check_required": False,
                    "deterministic_runs": 1,
                    "stdin": "hi\n",
                    "forbidden_constructs": [],
                }]
            }
            tasks_path = root / "tasks.json"
            tasks_path.write_text(json.dumps(tasks, ensure_ascii=False), encoding="utf-8")
            # sample-1 passes, sample-2 prints the wrong text, sample-3 missing.
            good = root / "subs" / "echo" / "sample-1"
            bad = root / "subs" / "echo" / "sample-2"
            good.mkdir(parents=True)
            bad.mkdir(parents=True)
            (good / "program.lwt").write_text(
                "let line = input();\nemit line;\n", encoding="utf-8")
            (bad / "program.lwt").write_text(
                'emit "nope";\n', encoding="utf-8")

            doc = run_agent_eval.grade_all(
                tasks_path=tasks_path,
                submissions_dir=root / "subs",
                samples=3,
                group="T",
                timeout=30,
            )
            self.assertEqual(doc["samples_per_task"], 3)
            self.assertEqual(doc["group"], "T")
            self.assertEqual(len([r for r in doc["results"] if r["id"] == "echo"]), 3)
            statuses = sorted(r["status"] for r in doc["results"])
            self.assertEqual(statuses, ["FAIL", "NOT_SUBMITTED", "PASS"])
            # Only submitted samples enter the denominator.
            self.assertEqual(doc["stats"]["samples"], 2)
            self.assertEqual(doc["stats"]["passed"], 1)
            self.assertAlmostEqual(doc["stats"]["pass_at_1"], 0.5, places=12)

    def test_missing_samples_report_not_run_not_fake_pass(self) -> None:
        with tempfile.TemporaryDirectory(prefix="s48-eval-") as folder:
            root = Path(folder)
            tasks_path = root / "tasks.json"
            tasks_path.write_text(json.dumps({"tasks": [{
                "id": "t", "title": "t", "prompt": "p",
                "expected_stdout": "", "expected_exit_code": 0,
                "check_required": False, "deterministic_runs": 1,
                "stdin": "", "forbidden_constructs": [],
            }]}), encoding="utf-8")
            doc = run_agent_eval.grade_all(
                tasks_path=tasks_path, submissions_dir=root / "none",
                samples=2, group="C", timeout=30)
            self.assertEqual(doc["overall"], "NOT_RUN")
            self.assertIsNone(doc["pass_at_1"])
            self.assertIsNone(doc["stats"])


if __name__ == "__main__":
    unittest.main()
