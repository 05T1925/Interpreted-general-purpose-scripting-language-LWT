"""Gate for the S53 semantic-mutation evidence.

The audit itself lives in ``tools/audit_semantic_mutants.py``; this module only
checks that its report is complete, internally consistent and honest about what
a finite set of probes can and cannot prove.
"""

from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "s54-closeout" / "mutation-report.json"
MARKDOWN = ROOT / "reports" / "s54-closeout" / "mutation-report.md"
INVENTORY = ROOT / "reports" / "s54-closeout" / "probe-inventory.md"
CASES = ROOT / "tests" / "cases"


def _case_ids() -> set[str]:
    ids: set[str] = set()
    for path in CASES.glob("*/*.json"):
        ids.add(json.loads(path.read_text(encoding="utf-8"))["id"])
    return ids


class MutationProbeReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.assertTrue(REPORT.exists(), f"missing report: {REPORT}")
        cls.doc = json.loads(REPORT.read_text(encoding="utf-8"))
        cls.probes = cls.doc["probes"]
        cls.case_ids = _case_ids()

    def test_report_contract_is_complete(self) -> None:
        for key in ("schema_version", "generated_at_utc", "tool", "invariants",
                    "repo_clean_before", "repo_clean_after", "totals", "probes"):
            self.assertIn(key, self.doc)
        for key in ("objective", "baseline", "stop_rule"):
            self.assertTrue(self.doc["invariants"].get(key), f"invariants.{key} is empty")
        for probe in self.probes:
            for key in ("name", "area", "targets", "mutation", "status",
                        "killed_by", "passed_targets", "evidence"):
                self.assertIn(key, probe, f"{probe.get('name')} lacks {key}")
            self.assertEqual(probe["status"], probe["status"].lower())
            self.assertIn(probe["status"], ("killed", "survived", "equivalent", "invalid"))

    def test_inventory_reaches_the_s53_target(self) -> None:
        # Course chapter 5.5: a test that can never go red is worthless. S53
        # requires at least 13 probes and at least 12 kills.
        self.assertGreaterEqual(len(self.probes), 13, "probe count below 13")
        killed = [probe for probe in self.probes if probe["status"] == "killed"]
        self.assertGreaterEqual(len(killed), 12, f"only {len(killed)} probes were killed")
        self.assertEqual(self.doc["totals"]["killed"], len(killed))
        self.assertEqual(self.doc["totals"]["total"], len(self.probes))

    def test_every_killed_probe_names_a_real_killing_case(self) -> None:
        for probe in self.probes:
            if probe["status"] != "killed":
                continue
            self.assertTrue(probe["killed_by"], f"{probe['name']} is killed but lists no case")
            for case_id in probe["killed_by"]:
                self.assertIn(case_id, self.case_ids, f"{probe['name']} cites unknown case {case_id}")
            for case_id in probe["killed_by"]:
                self.assertIn(case_id, probe["targets"],
                              f"{probe['name']} was killed by a non-target case {case_id}")

    def test_survived_probes_carry_a_written_reason(self) -> None:
        for probe in self.probes:
            if probe["status"] in ("survived", "equivalent"):
                self.assertTrue(
                    probe.get("equivalent_reason") or probe.get("note"),
                    f"{probe['name']} survived without a written reason",
                )

    def test_s42_and_s43_semantics_are_covered(self) -> None:
        areas = {probe["area"] for probe in self.probes}
        for required in ("dict", "finally", "concurrency"):
            self.assertIn(required, areas, f"no probe covers {required}")
        # At least one concurrency probe must be killed by a 46-case black-box
        # concurrency case, not by a hand-written harness.
        concurrency = [p for p in self.probes if p["area"] == "concurrency"]
        self.assertTrue(concurrency)
        self.assertTrue(any(p["status"] == "killed" for p in concurrency))

    def test_targets_are_real_black_box_cases(self) -> None:
        for probe in self.probes:
            self.assertTrue(probe["targets"], f"{probe['name']} has no target")
            for case_id in probe["targets"]:
                self.assertIn(case_id, self.case_ids, f"{probe['name']} targets unknown case {case_id}")

    def test_isolation_was_verified(self) -> None:
        # Red line: mutations may only live in disposable copies. A dirtied or
        # mutated working tree would show up here.
        self.assertTrue(self.doc["repo_clean_before"], "working tree was dirty before the audit")
        self.assertTrue(self.doc["repo_clean_after"], "working tree was dirty after the audit")
        for probe in self.probes:
            if probe["status"] == "invalid":
                # An invalid probe must say why no patch was applied, so a
                # drifted anchor cannot be mistaken for a kill or a survival.
                self.assertIn("no patch applied", probe["evidence"], probe["name"])
            else:
                self.assertIn("patch_sha256", probe["evidence"], probe["name"])

    def test_report_keeps_the_honest_boundary(self) -> None:
        self.assertTrue(INVENTORY.exists(), f"missing inventory: {INVENTORY}")
        text = MARKDOWN.read_text(encoding="utf-8")
        self.assertIn("不是总体正确率", text)
        self.assertIn("等价", text)


if __name__ == "__main__":
    unittest.main()
