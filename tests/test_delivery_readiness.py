"""S48 WP2/WP3 structural tests: claims, package index, GUI registration.

These are cheap invariants: every defense claim is runnable and points at an
existing evidence path; the package index declares a bundle tip and a
whitelist; the GUI registrar never turns a file's presence into PASS.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools import register_gui_evidence

ROOT = Path(__file__).resolve().parents[1]


class DefenseClaimsTests(unittest.TestCase):
    def test_at_least_twenty_unique_claims(self) -> None:
        doc = json.loads((ROOT / "docs" / "defense-claims.json").read_text(encoding="utf-8"))
        claims = doc["claims"]
        self.assertGreaterEqual(len(claims), 20)
        ids = [claim["id"] for claim in claims]
        self.assertEqual(len(ids), len(set(ids)), "duplicate claim id")
        for claim in claims:
            self.assertTrue(claim["command"], claim["id"])
            self.assertIn("expect", claim)
            self.assertIn("exit_code", claim["expect"])

    def test_evidence_paths_exist(self) -> None:
        doc = json.loads((ROOT / "docs" / "defense-claims.json").read_text(encoding="utf-8"))
        missing = [
            claim["evidence_path"] for claim in doc["claims"]
            if not (ROOT / claim["evidence_path"]).exists()
        ]
        self.assertEqual(missing, [], f"claims point at missing evidence: {missing}")

    def test_defense_html_is_offline_single_file(self) -> None:
        html = (ROOT / "docs" / "defense-index.html").read_text(encoding="utf-8")
        self.assertIn("LWT 现场可质询证据台", html)
        self.assertIn("run_defense_probe.py", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("<script src=", html)


class PackageIndexTests(unittest.TestCase):
    def test_index_declares_bundle_and_whitelist(self) -> None:
        doc = json.loads(
            (ROOT / "reports" / "s48-defense" / "package-index.json").read_text(encoding="utf-8")
        )
        for field in ("bundle_ref_sha", "final_tip_sha", "diff_paths",
                      "diff_whitelist", "generated_at_utc", "rebuild_command"):
            self.assertIn(field, doc)
        self.assertEqual(len(doc["bundle_ref_sha"]), 40)
        self.assertIn("reports/s48-defense/package-index.json", doc["diff_whitelist"])


class GuiRegistrationTests(unittest.TestCase):
    def test_empty_evidence_is_not_run_and_never_pass(self) -> None:
        with tempfile.TemporaryDirectory(prefix="s48-gui-") as folder:
            original = register_gui_evidence.EVIDENCE
            register_gui_evidence.EVIDENCE = Path(folder)
            try:
                doc = register_gui_evidence.scan()
            finally:
                register_gui_evidence.EVIDENCE = original
            self.assertEqual(doc["registered"], 0)
            self.assertEqual(doc["overall"], "REGISTERED 0/5")
            self.assertIsNone(doc["pass"])
            for item in doc["items"].values():
                self.assertEqual(item["status"], "NOT_RUN")
                self.assertIsNone(item["pass"])

    def test_a_file_registers_but_does_not_pass(self) -> None:
        with tempfile.TemporaryDirectory(prefix="s48-gui-") as folder:
            evidence = Path(folder)
            (evidence / "A-2-predict-20261110T120501.png").write_bytes(b"png")
            original = register_gui_evidence.EVIDENCE
            register_gui_evidence.EVIDENCE = evidence
            try:
                doc = register_gui_evidence.scan()
            finally:
                register_gui_evidence.EVIDENCE = original
            self.assertEqual(doc["items"]["A"]["status"], "REGISTERED")
            self.assertIsNone(doc["items"]["A"]["pass"])
            self.assertEqual(doc["items"]["B"]["status"], "NOT_RUN")
            self.assertIsNone(doc["pass"])


if __name__ == "__main__":
    unittest.main()
