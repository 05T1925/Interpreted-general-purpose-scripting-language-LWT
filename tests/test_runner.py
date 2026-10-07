"""Unit tests for the black-box test inventory and byte comparison helpers."""

from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


RUNNER_PATH = Path(__file__).resolve().parents[1] / "tools" / "run_tests.py"
SPEC = importlib.util.spec_from_file_location("lwt_blackbox_runner", RUNNER_PATH)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


class CaseInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "cases"
        self.group = self.root / "group"
        self.group.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_case(
        self,
        filename: str = "one",
        *,
        case_id: str = "one",
        source: str = "emit 1;\n",
        metadata: dict[str, object] | None = None,
        raw_json: str | None = None,
    ) -> None:
        source_path = self.group / f"{filename}.lwt"
        source_path.write_text(source, encoding="utf-8")
        json_path = self.group / f"{filename}.json"
        if raw_json is not None:
            json_path.write_text(raw_json, encoding="utf-8")
            return
        payload: dict[str, object] = {
            "id": case_id,
            "spec_refs": ["3"],
            "args": [],
            "stdin": {"text": ""},
            "expected": {"exit_code": 0, "stdout": "1\n", "stderr": ""},
        }
        if metadata:
            payload.update(metadata)
        json_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def test_discovery_is_sorted_and_ignores_fixture_subtree(self) -> None:
        self.write_case("z-last", case_id="z-last")
        self.write_case("a-first", case_id="a-first")
        fixtures = self.root / "fixtures"
        fixtures.mkdir()
        (fixtures / "sample.txt").write_text("data", encoding="utf-8")

        cases = runner.discover_cases(self.root)

        self.assertEqual([case.case_id for case in cases], ["a-first", "z-last"])

    def test_text_stdin_and_default_timeout(self) -> None:
        self.write_case(metadata={"stdin": {"text": "hello\n"}})

        case = runner.discover_cases(self.root)[0]

        self.assertEqual(case.stdin, b"hello\n")
        self.assertEqual(case.timeout_seconds, runner.DEFAULT_TIMEOUT_SECONDS)

    def test_base64_stdin_and_cli_override(self) -> None:
        self.write_case(
            metadata={
                "stdin": {"base64": base64.b64encode(b"\xff\n").decode("ascii")},
                "cli_args_override": ["--", "--"],
            }
        )

        case = runner.discover_cases(self.root)[0]

        self.assertEqual(case.stdin, b"\xff\n")
        self.assertEqual(case.cli_args_override, ("--", "--"))

    def test_missing_pair_is_configuration_error(self) -> None:
        (self.group / "orphan.lwt").write_text("", encoding="utf-8")

        with self.assertRaisesRegex(runner.ConfigurationError, "missing pair"):
            runner.discover_cases(self.root)

        orphan = self.group / "orphan.lwt"
        orphan.unlink()
        (self.group / "metadata-only.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(runner.ConfigurationError, "missing pair"):
            runner.discover_cases(self.root)

    def test_unexpected_file_is_configuration_error(self) -> None:
        self.write_case()
        (self.group / "notes.txt").write_text("not metadata", encoding="utf-8")

        with self.assertRaisesRegex(runner.ConfigurationError, "unexpected file"):
            runner.discover_cases(self.root)

    def test_duplicate_ids_are_configuration_error(self) -> None:
        self.write_case("first", case_id="same")
        self.write_case("second", case_id="same")

        with self.assertRaisesRegex(runner.ConfigurationError, "duplicate id"):
            runner.discover_cases(self.root)

    def test_unknown_and_missing_fields_are_rejected(self) -> None:
        self.write_case(metadata={"surprise": True})
        with self.assertRaisesRegex(runner.ConfigurationError, "unknown fields"):
            runner.discover_cases(self.root)

        (self.group / "one.json").write_text(
            json.dumps({"id": "one"}), encoding="utf-8"
        )
        with self.assertRaisesRegex(runner.ConfigurationError, "missing required fields"):
            runner.discover_cases(self.root)

    def test_duplicate_json_keys_are_rejected(self) -> None:
        raw = (
            '{"id":"one","id":"two","spec_refs":["3"],"args":[], '
            '"stdin":{"text":""},"expected":{"exit_code":0,"stdout":"","stderr":""}}'
        )
        self.write_case(raw_json=raw)

        with self.assertRaisesRegex(runner.ConfigurationError, "duplicate JSON object key"):
            runner.discover_cases(self.root)

    def test_invalid_json_and_unknown_spec_reference_are_rejected(self) -> None:
        self.write_case(raw_json="{not json}")
        with self.assertRaisesRegex(runner.ConfigurationError, "invalid JSON"):
            runner.discover_cases(self.root)

        self.write_case(metadata={"spec_refs": ["4.99"]})
        with self.assertRaisesRegex(runner.ConfigurationError, "existing language-spec section"):
            runner.discover_cases(self.root)

    def test_invalid_base64_and_non_finite_timeout_are_rejected(self) -> None:
        self.write_case(metadata={"stdin": {"base64": "%%"}})
        with self.assertRaisesRegex(runner.ConfigurationError, "stdin.base64 is invalid"):
            runner.discover_cases(self.root)

        self.write_case(metadata={"timeout_seconds": float("inf")})
        with self.assertRaisesRegex(runner.ConfigurationError, "finite number"):
            runner.discover_cases(self.root)

    def test_override_and_program_args_are_mutually_exclusive(self) -> None:
        self.write_case(metadata={"args": ["x"], "cli_args_override": ["missing.lwt"]})

        with self.assertRaisesRegex(runner.ConfigurationError, "cannot be combined"):
            runner.discover_cases(self.root)


class ComparisonTests(unittest.TestCase):
    def test_only_crlf_is_normalized(self) -> None:
        self.assertEqual(runner.normalize_newlines(b"a\r\nb\rc\n"), b"a\nb\rc\n")

    def test_unified_diff_shows_exact_text_difference(self) -> None:
        diff = runner._unified_diff(b"expected\n", b"actual\n", "stdout")

        self.assertIn("-expected", diff)
        self.assertIn("+actual", diff)

    def test_timeout_failure_keeps_expected_and_partial_output(self) -> None:
        case = runner.TestCase(
            "timeout-case", "group", runner.REPO_ROOT / "tests/cases/group/unused.lwt", ("3",), (), (), b"",
            0, b"expected\n", b"", 0.1, None,
        )
        error = subprocess.TimeoutExpired(["python"], 0.1, output=b"partial")

        with mock.patch.object(runner.subprocess, "run", side_effect=error):
            result = runner.run_case(case)

        self.assertTrue(result.failures)
        self.assertIn("expected", " ".join(result.failures))
        self.assertIn("partial", " ".join(result.failures))

    def test_process_start_failure_is_reported_with_expected_values(self) -> None:
        case = runner.TestCase(
            "start-failure", "group", runner.REPO_ROOT / "tests/cases/group/unused.lwt", ("3",), (), (), b"",
            0, b"expected\n", b"", 1.0, None,
        )

        with mock.patch.object(runner.subprocess, "run", side_effect=OSError("not found")):
            result = runner.run_case(case)

        self.assertTrue(result.failures)
        self.assertIn("expected", " ".join(result.failures))

    def test_configuration_failure_stops_runner_with_nonzero_status(self) -> None:
        from contextlib import redirect_stderr, redirect_stdout
        from io import StringIO

        stdout = StringIO()
        stderr = StringIO()
        with mock.patch.object(
            runner, "discover_cases", side_effect=runner.ConfigurationError("invalid fixture")
        ), redirect_stdout(stdout), redirect_stderr(stderr):
            status = runner.main()

        self.assertEqual(status, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("CONFIGURATION ERROR: invalid fixture", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
