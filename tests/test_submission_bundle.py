"""S47: the submission package must be complete, self-consistent and read-only.

Covers:
  * SUBMISSION.md exists with the eight course items and every referenced path
    present in the repository;
  * build_submission produces a bundle that ``git bundle verify`` accepts, a
    zip whose ``manifest.sha256`` matches every entry, and leaves protected
    evidence untouched;
  * verify_fresh_clone has an honest missing-bundle error and a correct
    black-box parser.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from tools import build_submission
from tools import verify_fresh_clone

ROOT = Path(__file__).resolve().parents[1]
SUBMISSION = ROOT / "SUBMISSION.md"

REQUIRED_PATHS = [
    "docs/language-spec.md",
    "lwt",
    "tests/cases",
    "reports/performance.md",
    "docs/developer-guide.md",
    ".agents/skills/lwt-app/SKILL.md",
    "app/log_report.lwt",
    "app/lwt_snake/game.lwt",
    "slides/LWT介绍.pptx",
]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SubmissionDocTests(unittest.TestCase):
    def test_submission_md_lists_all_eight_items(self) -> None:
        self.assertTrue(SUBMISSION.exists(), "SUBMISSION.md must be generated at the repo root")
        text = SUBMISSION.read_text(encoding="utf-8")
        for number in range(1, 9):
            self.assertRegex(text, rf"(?m)^\| {number} \|", f"missing item {number}")
        self.assertIn("三分钟验收路径", text)
        self.assertIn("未验证项", text)

    def test_every_referenced_path_exists(self) -> None:
        for rel in REQUIRED_PATHS:
            self.assertTrue((ROOT / rel).exists(), f"SUBMISSION.md references missing {rel}")


class BuildPackageTests(unittest.TestCase):
    def test_build_produces_verifiable_bundle_and_zip(self) -> None:
        protected = [ROOT / "bench/results.json", ROOT / "reports/performance.md"]
        before = {path: _sha(path) for path in protected if path.exists()}

        with tempfile.TemporaryDirectory(prefix="lwt-s47-pkg-") as folder:
            out = Path(folder) / "pkg"
            code = build_submission.main(["--out", str(out), "--no-latest"])
            self.assertEqual(code, 0)
            record = json.loads((out / "build.json").read_text(encoding="utf-8"))

            bundle = ROOT / record["bundle"]["bundle"]
            self.assertTrue(bundle.exists())
            verify = subprocess.run(
                ["git", "bundle", "verify", str(bundle)],
                cwd=str(ROOT), capture_output=True, text=True, check=False,
            )
            self.assertEqual(verify.returncode, 0, verify.stderr)

            zip_path = ROOT / record["zip"]["zip"]
            self.assertTrue(zip_path.exists())
            import zipfile
            with zipfile.ZipFile(zip_path) as zf:
                self.assertIsNone(zf.testzip())
                names = set(zf.namelist())
                self.assertIn("SUBMISSION.md", names)
                self.assertIn("lwt-history.bundle", names)
                manifest = zf.read("manifest.sha256").decode("utf-8").splitlines()
                listed = {}
                for line in manifest:
                    digest, rel = line.split("  ", 1)
                    listed[rel] = digest
                for rel, digest in listed.items():
                    self.assertEqual(
                        hashlib.sha256(zf.read(rel)).hexdigest(), digest,
                        f"manifest mismatch for {rel}",
                    )
                self.assertEqual(set(listed), names - {"manifest.sha256"})

        after = {path: _sha(path) for path in protected if path.exists()}
        self.assertEqual(before, after, "build must not modify protected evidence")


class FreshCloneHelperTests(unittest.TestCase):
    def test_blackbox_parser(self) -> None:
        parsed = verify_fresh_clone._blackbox_counts(
            "Black-box tests: passed=400 failed=0 total=400; elapsed=1s\n"
        )
        self.assertEqual(parsed, {"parsed": True, "passed": 400, "failed": 0, "total": 400})
        self.assertEqual(verify_fresh_clone._blackbox_counts("nope"), {"parsed": False})

    def test_missing_bundle_returns_two(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt-s47-missing-") as folder:
            out = Path(folder) / "fresh.json"
            code = verify_fresh_clone.main([
                "--bundle", str(Path(folder) / "does-not-exist.bundle"),
                "--out", str(out),
            ])
            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
