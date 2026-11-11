"""S52: the course's "tick every row" coverage gate.

Chapter 8 of the course slides says the black-box suite must cover every
language feature and that "test names map one-to-one to the feature list - tick
each row; a missing row is not complete coverage". The S51 matrix had no §8
table and 20 subsections had no spec_refs at all.

This test is deliberately mechanical:

* parse every ``## N.`` / ``### N.M`` heading from docs/language-spec.md;
* collect spec_refs from tests/cases/**/*.json;
* every leaf/subsection must have a direct reference, or an explicit
  ``covered_by`` row in docs/test-matrix.md, or be in a short, reasoned
  exemption list (pure prose / design decisions only);
* docs/test-matrix.md must contain a §8 table with one row per §8.1-§8.8;
* "use LWT to test LWT" must be stated, and the runner must drive the public
  CLI rather than import the interpreter and synthesise expected output.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "language-spec.md"
MATRIX = ROOT / "docs" / "test-matrix.md"
CASES = ROOT / "tests" / "cases"

HEADING_RE = re.compile(r"^(##|###)\s+(\d+(?:\.\d+)?)\.?\s+\S")

# Prose/design sections that have no executable semantics of their own. Each one
# needs a reasoned row in the matrix; a blanket file-level exemption is not
# allowed and is checked below.
EXEMPT = {
    "1": "范围与特色说明，无可执行语义",
    "8.6": "与既有草案的差异和取舍，属设计决策",
    "11.9": "兼容性与设计取舍，属设计决策",
}


def spec_sections() -> dict[str, str]:
    sections: dict[str, str] = {}
    for line in SPEC.read_text(encoding="utf-8").splitlines():
        match = HEADING_RE.match(line)
        if match:
            sections[match.group(2)] = line.strip()
    return sections


def leaf_sections(sections: dict[str, str]) -> list[str]:
    parents = {sid.split(".")[0] for sid in sections if "." in sid}
    return sorted(
        (sid for sid in sections if "." in sid or sid not in parents),
        key=lambda value: [int(part) for part in value.split(".")],
    )


def case_refs() -> dict[str, list[str]]:
    refs: dict[str, list[str]] = {}
    for path in sorted(CASES.glob("*/*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for ref in data.get("spec_refs", []) or []:
            refs.setdefault(ref, []).append(data["id"])
    return refs


def matrix_rows() -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in MATRIX.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\|\s*§?(\d+(?:\.\d+)?)\s*\|", line)
        if match:
            rows[match.group(1)] = line
    return rows


class CourseCoverageMatrixTests(unittest.TestCase):
    def test_spec_has_the_expected_sections(self) -> None:
        sections = spec_sections()
        for sid in [f"8.{n}" for n in range(1, 9)] + ["9.1", "10.1", "11.1"]:
            self.assertIn(sid, sections, f"language-spec is missing §{sid}")

    def test_section_8_table_lists_every_subsection(self) -> None:
        matrix = MATRIX.read_text(encoding="utf-8")
        self.assertIn("### §8", matrix, "docs/test-matrix.md has no §8 table")
        rows = matrix_rows()
        missing = [f"8.{n}" for n in range(1, 9) if f"8.{n}" not in rows]
        self.assertEqual(missing, [], f"§8 table is missing rows: {missing}")

    def test_every_semantic_section_is_referenced_or_covered_by(self) -> None:
        sections = spec_sections()
        refs = case_refs()
        rows = matrix_rows()
        problems: list[str] = []
        for sid in leaf_sections(sections):
            if sid in refs:
                continue
            row = rows.get(sid, "")
            if sid in EXEMPT:
                if not row or not any(mark in row for mark in ("设计", "说明", "间接")):
                    problems.append(f"§{sid} 豁免缺少理由行 ({EXEMPT[sid]})")
                continue
            if row and ("间接" in row or "covered_by" in row):
                continue
            problems.append(f"§{sid} ({sections[sid][:40]}) 无直接 refs 也无 covered_by")
        self.assertEqual(
            problems, [],
            "coverage gaps:\n" + "\n".join(problems),
        )

    def test_spec_refs_are_registered(self) -> None:
        from tools.run_tests import VALID_SPEC_REFS

        unknown = sorted({ref for ref in case_refs() if ref not in VALID_SPEC_REFS})
        self.assertEqual(unknown, [], f"unregistered spec_refs: {unknown}")

    def test_lwt_tests_lwt_is_stated_and_runner_uses_the_cli(self) -> None:
        matrix = MATRIX.read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("用 LWT 测试 LWT", matrix)
        self.assertIn("用 LWT 测试 LWT", readme)

        lwt = len(list(CASES.glob("*/*.lwt")))
        jsons = len(list(CASES.glob("*/*.json")))
        self.assertGreaterEqual(lwt, jsons, "every case should be authored in LWT")

        runner = (ROOT / "tools" / "run_tests.py").read_text(encoding="utf-8")
        for forbidden in ("from lwt import", "import lwt", "from lwt."):
            self.assertNotIn(
                forbidden, runner,
                "the runner must drive the public CLI, not import the interpreter",
            )


if __name__ == "__main__":
    unittest.main()
