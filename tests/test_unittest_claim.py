"""S50: the unittest claim must name the interpreter it depends on.

The S49 red line was not a language defect. ``docs/defense-claims.json`` ran
``python -m unittest discover``; on the grading machine ``python`` is a bundled
3.13.14 without tkinter, so the GUI module could not be imported, only 711 of
713 tests ran, and two tkinter errors were reported as if they were test
failures. The same command under a Tk-enabled Python is 713 OK.

These tests pin the fix so it cannot silently regress:

* the claim declares ``requires.tkinter`` and a precondition that imports it;
* the probe resolves an interpreter that satisfies it and never passes a bare
  ``python`` through;
* the evidence records ``sys.executable``, the Python version and ``TkVersion``;
* the S49 four-attempt failure history stays in place, with the S50 correction
  saying the cause was the interpreter rather than "environment timing";
* the two-batch runner is not passed off as a single command.
"""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from tools import run_defense_probe

ROOT = Path(__file__).resolve().parents[1]
CLAIMS = ROOT / "docs" / "defense-claims.json"
EVIDENCE = ROOT / "reports" / "s50-closeout" / "unittest-single-command.json"
S49_REPORT = ROOT / "docs" / "s49-defense-rehearsal.md"


def _claim() -> dict:
    doc = json.loads(CLAIMS.read_text(encoding="utf-8"))
    for row in doc["claims"]:
        if row["id"] == "unittest":
            return row
    raise AssertionError("unittest claim is missing")


class UnittestClaimTests(unittest.TestCase):
    def test_claim_declares_tkinter_requirement(self) -> None:
        claim = _claim()
        self.assertTrue((claim.get("requires") or {}).get("tkinter"),
                        "the unittest claim must declare requires.tkinter")
        precondition = claim.get("precondition") or {}
        self.assertEqual(precondition.get("expect_exit_code"), 0)
        command = " ".join(precondition.get("command") or [])
        self.assertIn("import tkinter", command,
                      "the precondition must import tkinter so a Tk-less "
                      "interpreter fails before the suite runs")
        self.assertEqual((claim.get("expect") or {}).get("exit_code"), 0)

    def test_claim_is_a_single_command_not_the_batch_runner(self) -> None:
        claim = _claim()
        command = " ".join(claim["command"])
        self.assertIn("run_unittest_single.py", command)
        self.assertNotIn("run_unittest_batches", command)
        self.assertNotIn("两批", claim["claim"])

    def test_probe_resolves_an_interpreter_with_tkinter(self) -> None:
        try:
            facts = run_defense_probe.resolve_python(require_tkinter=True)
        except RuntimeError as error:
            self.skipTest(f"no Tk-enabled interpreter on this host: {error}")
        self.assertTrue(facts["executable"])
        self.assertTrue(facts["version"])
        self.assertTrue(str(facts["tk_version"]))

    def test_probe_never_passes_a_bare_python_through(self) -> None:
        claim = _claim()
        try:
            command, interpreter = run_defense_probe.build_command(claim)
        except RuntimeError as error:
            self.skipTest(f"no Tk-enabled interpreter on this host: {error}")
        self.assertNotEqual(command[0], "python",
                            "a bare python must be replaced by a resolved interpreter")
        self.assertEqual(command[-1], "tools/run_unittest_single.py")
        self.assertEqual(list(interpreter["argv"]), command[:len(interpreter["argv"])])
        # A claim without the Tk requirement keeps the historical behaviour.
        plain = {"id": "version", "command": ["python", "-m", "lwt", "--version"]}
        plain_command, _ = run_defense_probe.build_command(plain)
        self.assertEqual(plain_command[0], run_defense_probe.sys.executable)

    def test_evidence_records_who_ran_the_suite(self) -> None:
        self.assertTrue(EVIDENCE.exists(), f"{EVIDENCE} is missing")
        doc = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(doc.get("exit_code"), 0)
        self.assertIs(doc.get("ok"), True)
        self.assertIsInstance(doc.get("ran"), int)
        self.assertGreater(doc["ran"], 0)
        for field in ("sys_executable", "python_version", "tk_version"):
            self.assertTrue(doc.get(field), f"evidence must record {field}")
        self.assertEqual(doc["command"][0], doc["sys_executable"])
        log = ROOT / doc["log_path"]
        self.assertTrue(log.is_file(), f"evidence log is missing: {log}")

    def test_s49_failures_are_kept_and_corrected(self) -> None:
        text = S49_REPORT.read_text(encoding="utf-8")
        for marker in ("第 4 次定位", "1201.0 s", "1466.8 s"):
            self.assertIn(marker, text, "S49's four-attempt history must stay")
        self.assertIn("S50 根因修正", text,
                      "S49 report must carry the S50 root-cause correction")
        self.assertIn("tkinter", text)
        self.assertIn("解释器", text)


if __name__ == "__main__":
    unittest.main()
