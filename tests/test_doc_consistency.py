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

# Lines carrying an explicit dated review record (e.g. "（2026-10-07）" or
# "（S44，2026-11-07）") are historical records inside current-state documents
# such as README's phase blocks and project.md's stage paragraphs.
HISTORICAL_DATE_RE = re.compile(r"20\d\d-\d\d-\d\d")

# The roadmap's phase table rows (``| S5 | ... |``) are a frozen stage index, not
# a current-status sentence; they are allowed to say "未推送" of that stage.
HISTORICAL_STAGE_ROW_RE = re.compile(r"^\|\s*S\d+\s*\|")

# A line that presents *itself* as the current state, e.g.
# ``> **当前状态（S44，2026-11-07）**``. Such a line is a current claim, so a date
# may not turn it into history. The regex is anchored on purpose: project.md
# contains sentences about "当前状态文档" (the test subject), which are not
# claims about the repository.
CURRENT_CLAIM_RE = re.compile(
    r"^\s*>?\s*\*\*当前(?:状态|基数|版本|集合|结论)"
    r"|^\s*>?\s*当前(?:状态|基数|版本|集合|结论)\s*[（(:：]"
)


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
    # Current-state assertions win over the date rule: a stale "current status"
    # line must not be excused just because it carries a date.
    if CURRENT_CLAIM_RE.search(line):
        return False
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
        # S47 is a historical report: it must keep its own frozen numbers (677
        # unittest, 20-page PPT), not the current S48 manifest values.
        report = REPO_ROOT / "docs" / "s47-final-submission.md"
        self.assertTrue(report.exists(), "docs/s47-final-submission.md is missing")
        text = report.read_text(encoding="utf-8")
        self.assertIn("677", text)
        self.assertIn("20 页", text)


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
        if not ("PARTIAL" in status or "EXECUTED" in status or status.startswith("PASS")):
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
            "docs/defense-qa-card.md", "docs/s49-defense-rehearsal.md",
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


    def test_s48_report_quotes_current_manifest_counts(self) -> None:
        # S48 is now a historical phase report: like S47 it must keep its own
        # frozen numbers (695 unittest, 21-page PPT) instead of tracking the
        # S49 manifest values.
        report = REPO_ROOT / "docs" / "s48-defense-readiness.md"
        self.assertTrue(report.exists(), "docs/s48-defense-readiness.md is missing")
        text = report.read_text(encoding="utf-8")
        self.assertIn("695", text)
        self.assertIn("21 页", text)


# ---------------------------------------------------------------------------
# S49 WP1: manifest is the single source of truth for every current number.
#
# The S48 suite could only catch four hand-picked stale values (595/287/12 页).
# S49 generalises it: any current-state document that quotes a unittest count,
# a black-box count or a PPT page count must quote the manifest value, and the
# intermediate values of earlier phases (595/632/664/677/685 and 17–20 页) may
# only survive on a line that is *provably* historical — a dated record or a
# frozen stage section of docs/final-acceptance-checklist.md.
# ---------------------------------------------------------------------------

# Documents a reviewer reads as "the current state". Phase reports are excluded
# on purpose: docs/s47-final-submission.md and docs/s48-defense-readiness.md are
# frozen snapshots whose numbers must not be rewritten.
NUMBER_DOCS = [
    "README.md",
    "SUBMISSION.md",
    "project.md",
    "docs/demo-script.md",
    "docs/defense-qa-card.md",
    "docs/final-acceptance-checklist.md",
    "docs/language-spec.md",
    "docs/developer-guide.md",
    "docs/test-matrix.md",
    "docs/concurrency.md",
    "docs/agent-eval/README.md",
    "docs/defense-runbook.md",
    "docs/gui-acceptance-quickref.md",
]

# Push/CI claims are also checked inside the latest phase report, because that
# is where a reader looks for "is this pushed?".
# The S48 report is a frozen snapshot: its "not pushed yet" line was true when
# written and must not be rewritten. Only the S49 report is a current claim.
STATUS_DOCS = NUMBER_DOCS + ["docs/s49-defense-rehearsal.md"]

# A heading like ``## S45 最终交付加固核对`` starts a frozen stage section. Every
# line up to the next ``## `` heading is a historical snapshot, so the precise
# allowlist is a line range, never a blanket file exemption.
STAGE_SECTION_RE = re.compile(r"^##\s+S\d+\b")

UNIT_COUNT_RE = re.compile(
    r"unittest[^0-9\n]{0,10}(\d{3,4})|(\d{3,4})\s*(?:项)?\s*unittest"
)
BLACKBOX_RE = re.compile(
    r"(?<![\d.])(\d{3})(?![\d.])\s*(?:项)?\s*黑盒"
    r"|黑盒[^0-9\n]{0,8}(?<![\d.])(\d{3})(?![\d.])"
)
PAGES_RE = re.compile(r"(?<![\d.第])(?<!第\s)(\d{1,2})\s*页")
INTERMEDIATE_COUNT_RE = re.compile(r"(?<![\d.])(595|632|664|677|685)(?![\d.])")
INTERMEDIATE_PAGE_RE = re.compile(r"(?<![\d.第])(?<!第\s)(17|18|19|20)\s*页")


def _stage_section_lines(path: Path) -> set[int]:
    """Line numbers inside a ``## S<NN> ...`` stage section of *path*."""

    marked: set[int] = set()
    inside = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if STAGE_SECTION_RE.match(line):
            inside = True
            marked.add(number)
            continue
        if line.startswith("## "):
            inside = False
        if inside:
            marked.add(number)
    return marked


def _iter_matches(pattern: re.Pattern[str], docs: list[str]):
    """Yield ``(rel, line_number, line, value, historical)`` for every match."""

    cache: dict[Path, set[int]] = {}
    for rel in docs:
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        if path not in cache:
            cache[path] = _stage_section_lines(path)
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in pattern.finditer(line):
                value = next((g for g in match.groups() if g), None)
                historical = number in cache[path] or _has_historical_marker(line)
                yield rel, number, line, value, historical


class ManifestSingleSourceTests(unittest.TestCase):
    """400 / unittest / PPT page counts in current docs must equal the manifest."""

    def test_unittest_counts_match_manifest(self) -> None:
        want = str(_load_manifest()["unittest_count"])
        bad = [
            f"{rel}:{number}: {line.strip()[:140]}"
            for rel, number, line, value, historical in _iter_matches(UNIT_COUNT_RE, NUMBER_DOCS)
            if not historical and value != want
        ]
        self.assertEqual(
            bad, [],
            f"current-state documents must quote unittest_count={want} (manifest):\n"
            + "\n".join(bad),
        )

    def test_blackbox_counts_match_manifest(self) -> None:
        want = str(_load_manifest()["blackbox_cases"])
        bad = [
            f"{rel}:{number}: {line.strip()[:140]}"
            for rel, number, line, value, historical in _iter_matches(BLACKBOX_RE, NUMBER_DOCS)
            # A line that records a progression ("354 -> 400") is a historical
            # statement, not a current claim, as long as it also quotes the
            # current value.
            if not historical and value != want and want not in line
        ]
        self.assertEqual(
            bad, [],
            f"current-state documents must quote blackbox_cases={want} (manifest):\n"
            + "\n".join(bad),
        )

    def test_ppt_pages_match_manifest(self) -> None:
        want = str(_load_manifest()["ppt_pages"])
        bad = [
            f"{rel}:{number}: {line.strip()[:140]}"
            for rel, number, line, value, historical in _iter_matches(PAGES_RE, NUMBER_DOCS)
            if not historical and value != want
        ]
        self.assertEqual(
            bad, [],
            f"current-state documents must quote ppt_pages={want} (manifest):\n"
            + "\n".join(bad),
        )

    def test_no_intermediate_unittest_counts_as_current(self) -> None:
        # 595 (S44 baseline), 632 (S44), 664 (S46), 677 (S47), 685 (S48 close)
        # are all superseded. Only dated records and frozen stage sections keep
        # them.
        bad = [
            f"{rel}:{number}: {line.strip()[:140]}"
            for rel, number, line, value, historical in _iter_matches(
                INTERMEDIATE_COUNT_RE, NUMBER_DOCS
            )
            if not historical
        ]
        self.assertEqual(
            bad, [],
            "intermediate unittest counts presented as current:\n" + "\n".join(bad),
        )

    def test_no_intermediate_ppt_pages_as_current(self) -> None:
        bad = [
            f"{rel}:{number}: {line.strip()[:140]}"
            for rel, number, line, value, historical in _iter_matches(
                INTERMEDIATE_PAGE_RE, NUMBER_DOCS
            )
            if not historical
        ]
        self.assertEqual(
            bad, [],
            "intermediate PPT page counts presented as current:\n" + "\n".join(bad),
        )

    def test_frozen_stage_sections_are_actually_exempt(self) -> None:
        # Guard against a blanket exemption: the *current* part of the checklist
        # (before the first stage heading) must not be exempt, while the S45/S46
        # sections must be. If the parser broke, both answers would be equal.
        path = REPO_ROOT / "docs" / "final-acceptance-checklist.md"
        marked = _stage_section_lines(path)
        lines = path.read_text(encoding="utf-8").splitlines()
        s45 = next(i for i, line in enumerate(lines, 1) if line.startswith("## S45"))
        s46 = next(i for i, line in enumerate(lines, 1) if line.startswith("## S46"))
        self.assertIn(s45, marked)
        self.assertIn(s46, marked)
        self.assertNotIn(14, marked, "the current top table must not be exempt")


class PushStatusTests(unittest.TestCase):
    """A current document must not claim 'not pushed' once origin matches HEAD."""

    @staticmethod
    def _git(*args: str) -> str | None:
        import subprocess

        result = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    def test_no_stale_current_status_with_date(self) -> None:
        # S51: the old rule treated any line with a date as history, so
        # "当前状态（S44，2026-11-07）...632 项...未推送" stayed green. A line that
        # calls itself the current state is a current claim; its numbers and
        # status must match the manifest whatever date it carries.
        doc = _load_manifest()
        expected = {
            UNIT_COUNT_RE: str(doc["unittest_count"]),
            BLACKBOX_RE: str(doc["blackbox_cases"]),
            INTERMEDIATE_COUNT_RE: str(doc["unittest_count"]),
            PAGES_RE: str(doc["ppt_pages"]),
            INTERMEDIATE_PAGE_RE: str(doc["ppt_pages"]),
        }
        bad: list[str] = []
        for rel in NUMBER_DOCS:
            path = REPO_ROOT / rel
            if not path.exists():
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if not CURRENT_CLAIM_RE.search(line):
                    continue
                if not HISTORICAL_DATE_RE.search(line):
                    continue
                for pattern, want in expected.items():
                    for match in pattern.finditer(line):
                        value = next((group for group in match.groups() if group), None)
                        if value is not None and value != want:
                            bad.append(f"{rel}:{number}: {value} != {want} | {line.strip()[:140]}")
        self.assertEqual(
            bad, [],
            "a dated line that calls itself the current state must use manifest numbers://n"
            + "\n".join(bad),
        )

    def test_push_status_matches_origin(self) -> None:
        head = self._git("rev-parse", "HEAD")
        origin = self._git("rev-parse", "origin/main")
        if not head or not origin:
            self.skipTest("origin/main is not resolvable in this clone")

        # "Pushed" means the delivered content is on origin. Evidence-only
        # commits after a push (docs/reports/evidence) do not make the delivery
        # unpushed, otherwise every recorded proof would flip the status back.
        ahead_paths: list[str] = []
        if head != origin:
            diff = self._git("diff", "--name-only", f"{origin}..{head}") or ""
            ahead_paths = [line for line in diff.splitlines() if line.strip()]
        evidence_only = all(
            path.startswith(("docs/", "reports/", "evidence/")) or path.endswith(".md")
            for path in ahead_paths
        )
        pushed = head == origin or (bool(ahead_paths) and evidence_only)

        stale: list[str] = []
        todo: list[str] = []
        for rel in STATUS_DOCS:
            path = REPO_ROOT / rel
            if not path.exists():
                continue
            marked = _stage_section_lines(path)
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if number in marked or _has_historical_marker(line):
                    continue
                if any(word in line for word in ("未推送", "未合入 main", "未合并", "待主窗口复核")):
                    stale.append(f"{rel}:{number}: {line.strip()[:140]}")
                if "待推送" in line:
                    todo.append(f"{rel}:{number}: {line.strip()[:140]}")
        if pushed:
            self.assertEqual(stale, [], "origin/main has this content but docs still say not pushed:\n" + "\n".join(stale))
        else:
            self.assertTrue(todo, "origin/main is behind HEAD (non-evidence changes) but no current doc says 待推送")


class EvidenceReachabilityTests(unittest.TestCase):
    """Every path a reviewer may copy from SUBMISSION.md / claims must exist."""

    @staticmethod
    def _submission_paths(text: str) -> list[str]:
        paths: list[str] = []
        for line in text.splitlines():
            if not line.startswith("| "):
                continue
            for token in re.findall(r"`([^`]+)`", line):
                for part in token.split("、"):
                    part = part.split("（")[0].strip()
                    part = part.replace("dist/ 内的 ", "")
                    if "=" in part or not part:
                        continue  # metrics such as referenced_cases=400/400
                    looks_like_path = "." in part.rsplit("/", 1)[-1] or part.endswith("/")
                    if "/" in part and looks_like_path and not part.startswith(("python", "git", "http")):
                        paths.append(part)
        return paths

    def test_submission_table_paths_exist(self) -> None:
        text = (REPO_ROOT / "SUBMISSION.md").read_text(encoding="utf-8")
        missing = [
            path
            for path in self._submission_paths(text)
            if not path.startswith("dist/") and not (REPO_ROOT / path).exists()
        ]
        self.assertEqual(missing, [], f"SUBMISSION.md points at missing paths: {missing}")

    def test_defense_claim_evidence_paths_exist(self) -> None:
        doc = json.loads((REPO_ROOT / "docs" / "defense-claims.json").read_text(encoding="utf-8"))
        missing = [c["evidence_path"] for c in doc["claims"] if not (REPO_ROOT / c["evidence_path"]).exists()]
        self.assertEqual(missing, [], f"defense claims point at missing evidence: {missing}")

    def test_public_cli_is_runnable(self) -> None:
        # The task book asks for at least "--help works" from the documented
        # entry point, not just that the file exists.
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "lwt", "--help"], cwd=REPO_ROOT, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr[-400:])
        self.assertIn("--check", result.stdout)


class S49ReportTests(unittest.TestCase):
    def test_phase_reports_quote_their_own_or_current_counts(self) -> None:
        # S49 is a dated snapshot: its 713 tests were true then and must not be
        # rewritten when a later phase adds tests. The *current* report carries
        # the moving manifest value instead, so the two cannot drift together.
        s49 = REPO_ROOT / "docs" / "s49-defense-rehearsal.md"
        self.assertTrue(s49.exists(), "docs/s49-defense-rehearsal.md is missing")
        frozen = s49.read_text(encoding="utf-8")
        self.assertIn("713", frozen)
        self.assertIn("21 页", frozen)

        s50 = REPO_ROOT / "docs" / "s50-closeout.md"
        self.assertTrue(s50.exists(), "docs/s50-closeout.md is missing")
        self.assertIn("719", s50.read_text(encoding="utf-8"))  # frozen at S50

        doc = _load_manifest()
        current = REPO_ROOT / "docs" / "s51-first-screen.md"
        self.assertTrue(current.exists(), "docs/s51-first-screen.md is missing")
        text = current.read_text(encoding="utf-8")
        self.assertIn(str(doc["unittest_count"]), text)
        self.assertIn(f"{doc['ppt_pages']} 页", text)


if __name__ == "__main__":
    unittest.main()
