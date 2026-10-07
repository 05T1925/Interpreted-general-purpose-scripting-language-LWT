"""Deterministic tests for the persistent project integrity check."""

from __future__ import annotations

import json
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from tools.check_project_integrity import inspect_project, main


class ProjectIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.docs = self.root / "docs"
        self.docs.mkdir()
        self.cases = self.root / "tests" / "cases" / "sample"
        self.cases.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_case(self, name: str, case_id: str) -> None:
        (self.cases / f"{name}.lwt").write_text('emit "ok";\n', encoding="utf-8")
        metadata = {
            "id": case_id,
            "spec_refs": ["3"],
            "args": [],
            "stdin": {"text": ""},
            "expected": {"exit_code": 0, "stdout": "ok\n", "stderr": ""},
        }
        (self.cases / f"{name}.json").write_text(
            json.dumps(metadata), encoding="utf-8"
        )

    def write_matrix(self, *paths: str) -> None:
        links = "\n".join(f"[case]({path})" for path in paths)
        (self.docs / "test-matrix.md").write_text(links + "\n", encoding="utf-8")

    def test_valid_inventory_and_lwt_and_json_matrix_links(self) -> None:
        self.write_case("one", "one")
        self.write_matrix(
            "../tests/cases/sample/one.lwt",
            "../tests/cases/sample/one.json",
        )

        result = inspect_project(self.root)

        self.assertEqual(result.errors, ())
        self.assertEqual(result.case_count, 1)
        self.assertEqual(result.matrix_link_count, 2)
        self.assertEqual(result.referenced_case_count, 1)

    def test_missing_case_pair_is_reported(self) -> None:
        (self.cases / "orphan.lwt").write_text("emit 1;", encoding="utf-8")
        self.write_matrix("../tests/cases/sample/orphan.lwt")

        result = inspect_project(self.root)

        self.assertEqual(len(result.errors), 1)
        self.assertIn("orphan.json: missing pair", result.errors[0])

    def test_duplicate_metadata_ids_are_reported(self) -> None:
        self.write_case("one", "shared-id")
        self.write_case("two", "shared-id")
        self.write_matrix("../tests/cases/sample/one.lwt")

        result = inspect_project(self.root)

        self.assertEqual(len(result.errors), 1)
        self.assertIn("duplicate id 'shared-id'", result.errors[0])

    def test_invalid_metadata_id_is_reported(self) -> None:
        self.write_case("one", "Upper_Case")
        self.write_matrix("../tests/cases/sample/one.lwt")

        result = inspect_project(self.root)

        self.assertEqual(len(result.errors), 1)
        self.assertIn("id must match [a-z0-9]+(?:-[a-z0-9]+)*", result.errors[0])

    def test_dangling_matrix_reference_is_reported_with_location(self) -> None:
        self.write_case("one", "one")
        self.write_matrix(
            "../tests/cases/sample/one.lwt",
            "../tests/cases/sample/missing.lwt",
        )

        result = inspect_project(self.root)

        self.assertEqual(len(result.errors), 1)
        self.assertIn("docs/test-matrix.md:2", result.errors[0])
        self.assertIn("does not name a discovered case file", result.errors[0])

    def test_matrix_reference_cannot_escape_case_directory(self) -> None:
        self.write_case("one", "one")
        self.write_matrix("../tests/cases/../../outside.lwt")

        result = inspect_project(self.root)

        self.assertEqual(len(result.errors), 1)
        self.assertIn("escapes tests/cases", result.errors[0])

    def test_command_reports_failure_to_stderr_and_returns_nonzero(self) -> None:
        self.write_case("one", "one")
        self.write_matrix("../tests/cases/sample/missing.lwt")
        stdout = StringIO()
        stderr = StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(self.root)

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Project integrity: FAILED", stderr.getvalue())
        self.assertIn("docs/test-matrix.md:1", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
