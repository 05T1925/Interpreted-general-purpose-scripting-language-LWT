"""S45 WP0: current-state documentation must agree with the delivery manifest.

The manifest (``docs/delivery-manifest.json``) is the single source of truth for
version, black-box count, unittest count and PPT page count. This test scans the
**current-state** documents for stale values. Historical stage reports
(``docs/s<NN>-*.md``) are exempt via an explicit allowlist because their numbers
are frozen snapshots of earlier phases and must not be rewritten.

Failure here means a reader would see a contradictory number, so it is a hard
gate (task book S45 section 11).
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "docs" / "delivery-manifest.json"

# Current-state documents that a reader may consult for "the current numbers".
CURRENT_STATE_DOCS = [
    "README.md",
    "project.md",
    "阶段执行与审查路线图.md",
    "docs/language-spec.md",
    "docs/developer-guide.md",
    "docs/test-matrix.md",
    "docs/final-acceptance-checklist.md",
    "docs/s44-performance.md",
    "docs/demo-script.md",
    "docs/defense-qa-card.md",
    "docs/concurrency.md",
    "docs/agent-eval/README.md",
    "SUBMISSION.md",
]

# Historical stage reports: frozen snapshots, explicitly exempt.
HISTORICAL_PATTERN = re.compile(r"^docs/s\d+-.*\.md$")

# Lines carrying an explicit historical marker are allowed to quote old values
# (e.g. "S26 当时集合为 287 项", "§4 的 595 基线"). The marker must be visible so
# a reader can tell it is history, not the current count.
HISTORICAL_MARKERS = (
    "历史快照",
    "当时",
    "基线",
    "历史基线",
    "本阶段",
    "S23 ",
    "S24 ",
    "S26 ",
    "S27 ",
    "S32",
    "S33 ",
    "§4 的",
    "旧 12 页",
    "旧 15 页",
    "旧图表",
)

# Lines carrying an explicit dated review record (e.g. "（2026-10-07）") are
# historical records inside current-state documents such as the roadmap.
HISTORICAL_DATE_RE = re.compile(r"[（(]20\d\d-\d\d-\d\d[）)]")

# The roadmap's phase table rows (``| S5 | ... |``) are a frozen stage index, not
# a current-status sentence; they are allowed to say "未推送" of that stage.
HISTORICAL_STAGE_ROW_RE = re.compile(r"^\|\s*S\d+\s*\|")


def _load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _current_state_files() -> list[Path]:
    files: list[Path] = []
    for rel in CURRENT_STATE_DOCS:
        path = REPO_ROOT / rel
        if path.exists():
            files.append(path)
    return files


def _is_historical(rel: str) -> bool:
    return bool(HISTORICAL_PATTERN.match(rel.replace("\\", "/")))


def _has_historical_marker(line: str) -> bool:
    return (
        any(marker in line for marker in HISTORICAL_MARKERS)
        or bool(HISTORICAL_DATE_RE.search(line))
        or bool(HISTORICAL_STAGE_ROW_RE.match(line))
    )


class ManifestShapeTests(unittest.TestCase):
    def test_manifest_has_required_fields(self) -> None:
        doc = _load_manifest()
        for field in (
            "version", "blackbox_cases", "unittest_count", "ppt_pages",
            "ppt_sha256", "protected_paths", "evidence", "last_verified_utc",
        ):
            self.assertIn(field, doc, f"manifest missing {field}")

    def test_manifest_values_are_plausible(self) -> None:
        doc = _load_manifest()
        self.assertRegex(doc["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(doc["blackbox_cases"], 400)
        self.assertGreaterEqual(doc["unittest_count"], 600)
        self.assertGreaterEqual(doc["ppt_pages"], 17)
        self.assertEqual(len(doc["ppt_sha256"]), 64)

    def test_manifest_protected_paths_exist(self) -> None:
        doc = _load_manifest()
        missing = [p for p in doc["protected_paths"] if not (REPO_ROOT / p).exists()]
        self.assertEqual(missing, [], f"manifest lists non-existent protected paths: {missing}")


class VersionConsistencyTests(unittest.TestCase):
    def test_no_stale_lwt_01_in_current_state_docs(self) -> None:
        offenders: list[str] = []
        for path in _current_state_files():
            rel = path.relative_to(REPO_ROOT).as_posix()
            if _is_historical(rel):
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "LWT 0.1" in line:
                    offenders.append(f"{rel}:{number}: {line.strip()[:100]}")
        self.assertEqual(offenders, [], "stale 'LWT 0.1' in current-state docs:\n" + "\n".join(offenders))

    def test_package_version_matches_manifest(self) -> None:
        import lwt

        doc = _load_manifest()
        self.assertEqual(lwt.__version__, doc["version"])


class CountingConsistencyTests(unittest.TestCase):
    def test_no_stale_unittest_595_as_current_count(self) -> None:
        # 595 is the S44 *baseline* count. It may appear only on a line with an
        # explicit historical marker (e.g. "§4 的 595 基线").
        pattern = re.compile(r"(?<![\d.])595(?![\d.])")
        offenders: list[str] = []
        for path in _current_state_files():
            rel = path.relative_to(REPO_ROOT).as_posix()
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if pattern.search(line) and not _has_historical_marker(line):
                    offenders.append(f"{rel}:{number}: {line.strip()[:120]}")
        self.assertEqual(offenders, [], "stale 595 as current unittest count:\n" + "\n".join(offenders))

    def test_no_stale_287_as_current_case_base(self) -> None:
        # 287 died with S26. Only explicit history lines may quote it.
        pattern = re.compile(r"(?<![\d.])287(?![\d.])")
        offenders: list[str] = []
        for path in _current_state_files():
            rel = path.relative_to(REPO_ROOT).as_posix()
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if pattern.search(line) and not _has_historical_marker(line):
                    offenders.append(f"{rel}:{number}: {line.strip()[:120]}")
        self.assertEqual(offenders, [], "stale 287 as current case base:\n" + "\n".join(offenders))

    def test_no_stale_12_page_ppt_claim(self) -> None:
        docs = _load_manifest()["ppt_pages"]
        pattern = re.compile(r"12\s*页")
        offenders: list[str] = []
        for path in _current_state_files():
            rel = path.relative_to(REPO_ROOT).as_posix()
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if pattern.search(line) and not _has_historical_marker(line):
                    offenders.append(f"{rel}:{number}: {line.strip()[:120]}")
        self.assertEqual(offenders, [], f"stale '12 页' claim (current PPT has {docs} pages):\n" + "\n".join(offenders))


class StatusConsistencyTests(unittest.TestCase):
    def test_no_s12_not_started_claim(self) -> None:
        offenders: list[str] = []
        for path in _current_state_files():
            rel = path.relative_to(REPO_ROOT).as_posix()
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "S12 尚未开始" in line and not _has_historical_marker(line):
                    offenders.append(f"{rel}:{number}: {line.strip()[:100]}")
        self.assertEqual(offenders, [], "stale 'S12 尚未开始':\n" + "\n".join(offenders))

    def test_current_state_docs_mention_manifest_version(self) -> None:
        # At least the package and the spec title must carry the adjudicated
        # version; other docs may reference it indirectly.
        doc = _load_manifest()
        spec = (REPO_ROOT / "docs" / "language-spec.md").read_text(encoding="utf-8")
        self.assertIn(doc["version"], spec.splitlines()[0])

    def test_historical_reports_are_exempt(self) -> None:
        # Sanity: the allowlist must actually match real historical files, and
        # they are allowed to contain old values.
        historical = [
            p for p in (REPO_ROOT / "docs").glob("s*-*.md")
            if _is_historical(p.relative_to(REPO_ROOT).as_posix())
        ]
        self.assertGreaterEqual(len(historical), 20, "historical allowlist seems too small")
        joined = "\n".join(p.read_text(encoding="utf-8") for p in historical)
        self.assertIn("287", joined, "expected at least one historical report to quote 287")



    def test_s47_report_quotes_current_manifest_counts(self) -> None:
        # S47 closes the delivery: the submission report must quote the same
        # unittest count and PPT page count as the manifest. Written before the
        # S47 doc was updated, so it fails first and then goes green.
        doc = _load_manifest()
        report = REPO_ROOT / "docs" / "s47-final-submission.md"
        self.assertTrue(report.exists(), "docs/s47-final-submission.md is missing")
        text = report.read_text(encoding="utf-8")
        self.assertIn(str(doc["unittest_count"]), text)
        self.assertIn(f"{doc['ppt_pages']} 页", text)


class SemanticStatusConsistencyTests(unittest.TestCase):
    """S48 WP0-2: status words must agree with the recorded evaluation result.

    Fixing prose is not enough: if the manifest says the blind evaluation ran
    (PARTIAL/PASS), no current-state document may still present NOT_RUN as the
    current conclusion. Lines carrying a historical marker (S45/S46 sections,
    "当时", "历史") stay exempt.
    """

    def _scan(self, pattern: re.Pattern[str]) -> list[str]:
        offenders: list[str] = []
        for path in _current_state_files():
            rel = path.relative_to(REPO_ROOT).as_posix()
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if pattern.search(line) and not _has_historical_marker(line):
                    offenders.append(f"{rel}:{number}: {line.strip()[:140]}")
        return offenders

    def test_blind_eval_status_matches_manifest(self) -> None:
        status = str(_load_manifest().get("agent_eval_status", ""))
        if not ("PARTIAL" in status or status.startswith("PASS")):
            self.skipTest("manifest does not record an executed blind evaluation")
        pattern = re.compile(r"未执行（NOT_RUN）|盲测未执行|Agent 盲测[^。|]{0,16}未执行")
        offenders = self._scan(pattern)
        self.assertEqual(
            offenders, [],
            "manifest records an executed blind eval, but current docs still say NOT_RUN:\n"
            + "\n".join(offenders),
        )

    def test_no_unpushed_claim_as_current_status(self) -> None:
        # A current delivery claim lives in the delivery-facing documents, not in
        # the roadmap (a frozen per-stage ledger whose rows legitimately say
        # "该阶段未推送"). Scanning only delivery docs avoids a blanket file
        # exemption while still catching a stale current statement.
        docs = [
            "README.md", "project.md", "SUBMISSION.md",
            "docs/final-acceptance-checklist.md", "docs/demo-script.md",
            "docs/defense-qa-card.md", "docs/s48-defense-readiness.md",
        ]
        offenders: list[str] = []
        for rel in docs:
            path = REPO_ROOT / rel
            if not path.exists():
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "未推送" in line and not _has_historical_marker(line):
                    offenders.append(f"{rel}:{number}: {line.strip()[:140]}")
        self.assertEqual(offenders, [], "stale '未推送' as current status:\n" + "\n".join(offenders))

    def test_submission_points_to_committed_package_index(self) -> None:
        doc = _load_manifest()
        self.assertEqual(
            doc.get("submission_bundle"),
            "reports/s48-defense/package-index.json",
            "manifest.submission_bundle must point at the committed index, not the gitignored dist/",
        )
        submission = (REPO_ROOT / "SUBMISSION.md").read_text(encoding="utf-8")
        self.assertIn("reports/s48-defense/package-index.json", submission)
        self.assertTrue((REPO_ROOT / "reports/s48-defense/package-index.json").exists())


if __name__ == "__main__":
    unittest.main()
