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


class S49RunbookTests(unittest.TestCase):
    """S49: 21-slide runbook, offline console navigation and rehearsal tooling."""

    def _pages(self) -> dict:
        return json.loads((ROOT / "docs" / "defense-pages.json").read_text(encoding="utf-8"))

    def _claims(self) -> dict:
        return json.loads((ROOT / "docs" / "defense-claims.json").read_text(encoding="utf-8"))

    def test_pages_cover_all_slides_with_valid_claims(self) -> None:
        pages = self._pages()["pages"]
        self.assertEqual([p["page"] for p in pages], list(range(1, 22)),
                         "defense-pages.json must map all 21 slides in order")
        ids = {claim["id"] for claim in self._claims()["claims"]}
        for page in pages:
            self.assertTrue(page["claims"], f"page {page['page']} has no claim")
            self.assertTrue(set(page["claims"]) <= ids,
                            f"page {page['page']} references unknown claim")
            self.assertIn(page["mode"], {"live", "recorded", "talk"})
            self.assertIn("title", page)

    def test_runbook_has_one_row_per_slide(self) -> None:
        text = (ROOT / "docs" / "defense-runbook.md").read_text(encoding="utf-8")
        rows = {}
        for line in text.splitlines():
            cells = [cell.strip() for cell in line.split("|")]
            if len(cells) > 3 and cells[1].isdigit():
                rows[int(cells[1])] = line
        self.assertEqual(sorted(rows), list(range(1, 22)), "runbook must cover 21 slides")
        for page in self._pages()["pages"]:
            line = rows[page["page"]]
            self.assertIn(page["title"][:8], line, f"page {page['page']} title mismatch")
            for cid in page["claims"]:
                self.assertIn(cid, line, f"page {page['page']} misses claim {cid}")

    def test_offline_console_has_anchors_and_no_network(self) -> None:
        from tools import build_defense_index

        html = (ROOT / "docs" / "defense-index.html").read_text(encoding="utf-8")
        self.assertEqual(html.count('id="claim-'), 24)
        self.assertEqual(html.count('id="page-'), 21)
        self.assertNotIn("{cls}", html, "unrendered template placeholder")
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("<script src=", html)
        # The committed file must match the generator, otherwise the console and
        # the claims JSON drift apart.
        self.assertEqual(html, build_defense_index.render(),
                         "docs/defense-index.html is stale; rerun tools/build_defense_index.py")

    def test_rehearsal_dry_run_plans_every_slide(self) -> None:
        from tools import rehearse_defense

        with tempfile.TemporaryDirectory(prefix="s49-rehearse-") as folder:
            out = Path(folder) / "rehearsal.json"
            code = rehearse_defense.main(["--pages", "1-21", "--dry-run", "--out", str(out)])
            self.assertEqual(code, 0)
            doc = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(doc["mode"], "dry-run")
        self.assertGreaterEqual(doc["planned"], 21)
        self.assertEqual(doc["passed"], 0, "dry run must not claim a pass")
        self.assertEqual({row["page"] for row in doc["rows"]}, set(range(1, 22)))
        self.assertTrue(all(row["status"] == "PLANNED" for row in doc["rows"]))
        self.assertIn("NOT the teacher", doc["what"])

    def test_gui_quickref_has_five_scenarios_and_cli_fallback(self) -> None:
        text = (ROOT / "docs" / "gui-acceptance-quickref.md").read_text(encoding="utf-8")
        for letter in "ABCDE":
            self.assertIn(f"## {letter}.", text)
        self.assertIn("CLI 降级", text)
        self.assertIn("NOT_RUN", text)
        self.assertIn("BLOCKED", text)


class PackageLagTests(unittest.TestCase):
    """S49: the lag checker must honour exact and directory-prefix whitelists."""

    def test_classify_exact_and_prefix(self) -> None:
        from tools.check_package_lag import classify

        inside, outside = classify(
            ["reports/a.json", "reports/s49-rehearsal/x.json", "docs/b.md", "lwt/cli.py"],
            ["reports/a.json", "reports/s49-rehearsal/", "docs/b.md"],
        )
        self.assertEqual(inside, ["reports/a.json", "reports/s49-rehearsal/x.json", "docs/b.md"])
        self.assertEqual(outside, ["lwt/cli.py"])

    def test_empty_whitelist_flags_everything(self) -> None:
        from tools.check_package_lag import classify

        inside, outside = classify(["docs/a.md"], [])
        self.assertEqual(inside, [])
        self.assertEqual(outside, ["docs/a.md"])


class FirstScreenTests(unittest.TestCase):
    def test_teacher_first_screen_is_consistent_and_names_the_interpreter(self) -> None:
        """S51: the first screen a teacher reads must agree with the manifest.

        It must also name the interpreter trap explicitly: the bundled
        ``python`` has no tkinter and yields 711 tests + 2 fake failures.
        """

        manifest = json.loads(
            (ROOT / "docs" / "delivery-manifest.json").read_text(encoding="utf-8")
        )
        wanted = [
            str(manifest["blackbox_cases"]),
            str(manifest["unittest_count"]),
            f"{manifest['ppt_pages']} 页",
        ]

        def head(rel: str, lines: int) -> str:
            text = (ROOT / rel).read_text(encoding="utf-8").splitlines()
            return "\n".join(text[:lines])

        readme = head("README.md", 6)
        submission = head("SUBMISSION.md", 8)
        for name, text in (("README.md", readme), ("SUBMISSION.md", submission)):
            for value in wanted:
                self.assertIn(value, text, f"{name} first screen must quote {value}")
        self.assertIn("S50", readme, "the README first screen must name S50")

        checklist = (ROOT / "docs" / "final-acceptance-checklist.md").read_text(encoding="utf-8")
        self.assertIn("## S50", checklist)
        # S50 is a frozen snapshot: it keeps 719. The current phase section must
        # quote the moving manifest count.
        self.assertIn("719", checklist.split("## S50", 1)[1])
        self.assertIn("## S52", checklist)
        self.assertIn(str(manifest["unittest_count"]), checklist.split("## S52", 1)[1])

        for rel in ("SUBMISSION.md", "docs/defense-qa-card.md"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("py -3.13", text, f"{rel} must name the Tk-enabled interpreter")
            self.assertIn("tkinter", text, f"{rel} must explain the tkinter trap")


if __name__ == "__main__":
    unittest.main()
