"""S52: the supplementary performance evidence must stay complete and honest.

Course chapter 7 asks for an explicit objective, a baseline, a stop rule, the
space dimension, and P95/P99 rather than a single average. This test pins the
JSON contract and checks that the S11/S44 frozen inputs were not rewritten.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "s52-course-align" / "performance-space.json"
MARKDOWN = ROOT / "reports" / "s52-course-align" / "performance-space.md"


class PerformanceSpaceEvidenceTests(unittest.TestCase):
    def test_json_has_the_required_contract(self) -> None:
        self.assertTrue(REPORT.exists(), f"{REPORT} is missing")
        doc = json.loads(REPORT.read_text(encoding="utf-8"))
        for field in ("objective", "baseline", "stop_rule", "measurements", "pressure", "platforms"):
            self.assertIn(field, doc)
        self.assertFalse(doc.get("render_check"), "no rendering was performed")
        self.assertFalse(doc.get("quick_mode"), "the committed evidence must be a full run")

        for workload, rows in doc["measurements"].items():
            self.assertEqual(sorted(rows), ["100", "1000", "5000"], workload)
            for n, row in rows.items():
                self.assertIn("time", row)
                for field in ("p50_ms", "p95_ms", "p99_ms"):
                    self.assertIn(field, row["time"], f"{workload} N={n} lacks {field}")
                self.assertIsInstance(row.get("peak_bytes"), int)
                self.assertGreater(row["peak_bytes"], 0)

        self.assertIn("peak_bytes_monotonic", doc["pressure"])
        self.assertIn("boundary", doc["pressure"])

    def test_ubuntu_space_sample_is_null_and_marked_unverified(self) -> None:
        doc = json.loads(REPORT.read_text(encoding="utf-8"))
        ubuntu = doc["platforms"]["ubuntu"]
        self.assertIsNone(ubuntu["maximum_resident_set_kb"])
        self.assertFalse(ubuntu["measured"])
        self.assertIn("未验证", ubuntu["note"])

    def test_s11_and_s44_frozen_inputs_are_untouched(self) -> None:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--",
             "bench/results.json", "reports/performance.md", "reports/s44-performance"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.stdout.strip(), "", "S11/S44 frozen inputs were modified")

    def test_markdown_states_it_is_not_the_s11_replacement(self) -> None:
        text = MARKDOWN.read_text(encoding="utf-8")
        self.assertIn("不是 S11 正式结果的替代", text)
        self.assertIn("未验证", text)


if __name__ == "__main__":
    unittest.main()
