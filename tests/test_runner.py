"""Unit tests for the black-box test inventory and byte comparison helpers."""

from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path
import threading
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
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

    def test_nested_module_fixture_subtrees_are_not_discovered_as_cases(self) -> None:
        self.write_case("library-user", case_id="library-user")
        nested_fixtures = self.group / "fixtures"
        nested_fixtures.mkdir()
        (nested_fixtures / "library.lwt").write_text(
            "fn value() { return 1; }", encoding="utf-8"
        )

        cases = runner.discover_cases(self.root)

        self.assertEqual([case.case_id for case in cases], ["library-user"])

    def test_module_spec_section_is_a_valid_case_reference(self) -> None:
        self.write_case(metadata={"spec_refs": ["9"]})

        cases = runner.discover_cases(self.root)

        self.assertEqual(cases[0].spec_refs, ("9",))

    def test_runtime_recovery_spec_section_is_a_valid_case_reference(self) -> None:
        self.write_case(metadata={"spec_refs": ["10"]})

        cases = runner.discover_cases(self.root)

        self.assertEqual(cases[0].spec_refs, ("10",))

    def test_concurrency_spec_sections_11_and_11_x_are_valid_references(self) -> None:
        # S43 gate: section 11 and all nine subsections must be registered in
        # VALID_SPEC_REFS *before* any 11.x black-box case is introduced.
        refs = ("11", "11.1", "11.2", "11.3", "11.4",
                "11.5", "11.6", "11.7", "11.8", "11.9")
        for ref in refs:
            with self.subTest(ref=ref):
                self.write_case(
                    filename=f"ref-{ref.replace('.', '-')}",
                    case_id=f"ref-{ref.replace('.', '-')}",
                    metadata={"spec_refs": [ref]},
                )
        cases = runner.discover_cases(self.root)
        self.assertEqual(sorted(case.spec_refs[0] for case in cases), sorted(refs))

    def test_unknown_spec_section_12_is_rejected(self) -> None:
        # Unknown references must still fail as a configuration error; widening
        # the set for 11.x must not turn validation into a no-op.
        self.write_case(metadata={"spec_refs": ["12"]})
        with self.assertRaisesRegex(
            runner.ConfigurationError, "existing language-spec section"
        ):
            runner.discover_cases(self.root)

    def test_empty_case_tree_is_a_configuration_error(self) -> None:
        with self.assertRaisesRegex(
            runner.ConfigurationError, "no black-box test cases were discovered"
        ):
            runner.discover_cases(self.root)

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
        with tempfile.TemporaryDirectory(dir=runner.REPO_ROOT, prefix="runner timeout ") as directory:
            source = Path(directory) / "超时 source.lwt"
            source.write_text("while (true) { }\n", encoding="utf-8")
            case = runner.TestCase(
                "timeout-case", "group", source, ("3",), (), (), b"",
                0, b"expected\n", b"", 0.2, None,
            )
            started: list[subprocess.Popen[bytes]] = []
            result = runner.run_case(case, on_process_started=started.append)

        self.assertEqual(result.status, "timeout")
        self.assertEqual(result.failure_kind, "timeout")
        self.assertIn("expected", " ".join(result.failures))
        self.assertTrue(started)
        self.assertIsNotNone(started[0].poll())

    def test_process_start_failure_is_reported_with_expected_values(self) -> None:
        case = runner.TestCase(
            "start-failure", "group", runner.REPO_ROOT / "tests/cases/group/unused.lwt", ("3",), (), (), b"",
            0, b"expected\n", b"", 1.0, None,
        )

        with mock.patch.object(runner.subprocess, "Popen", side_effect=OSError("not found")):
            result = runner.run_case(case)

        self.assertEqual(result.status, "start_failed")
        self.assertEqual(result.failure_kind, "start_failure")
        self.assertIn("expected", " ".join(result.failures))

    def test_configuration_failure_stops_runner_with_nonzero_status(self) -> None:
        stdout = StringIO()
        stderr = StringIO()
        with mock.patch.object(
            runner, "discover_cases", side_effect=runner.ConfigurationError("invalid fixture")
        ), redirect_stdout(stdout), redirect_stderr(stderr):
            status = runner.main([])

        self.assertEqual(status, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("CONFIGURATION ERROR: invalid fixture", stderr.getvalue())


class SelectionAndJsonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = runner.discover_cases()
        self.by_id = {case.case_id: case for case in self.cases}

    def test_case_category_intersection_and_stable_inventory_order(self) -> None:
        candidates = [
            self.by_id["array-zero-index-and-nesting"],
            self.by_id["array-upper-bound"],
            self.by_id["split-arity"],
        ]
        selected = runner.select_cases(candidates, ["array-upper-bound", "array-zero-index-and-nesting"], ["arrays-records-each"])
        self.assertEqual(
            [case.case_id for case in selected],
            ["array-zero-index-and-nesting", "array-upper-bound"],
        )

    def test_duplicate_and_unknown_selection_is_a_configuration_error(self) -> None:
        with self.assertRaisesRegex(runner.ConfigurationError, "must not be repeated"):
            runner.select_cases(self.cases, ["args-empty", "args-empty"], [])
        with self.assertRaisesRegex(runner.ConfigurationError, "unknown case ID"):
            runner.select_cases(self.cases, ["missing-case"], [])
        with self.assertRaisesRegex(runner.ConfigurationError, "unknown category"):
            runner.select_cases(self.cases, [], ["missing-category"])
        with self.assertRaisesRegex(runner.ConfigurationError, "matched no test cases"):
            runner.select_cases(self.cases, ["args-empty"], ["lexer-parser"])

    def test_inventory_json_is_complete_and_labels_debug_restrictions(self) -> None:
        payload = runner.inventory_to_json(self.cases)
        self.assertEqual(payload["schema"], "lwt.test-inventory")
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["case_count"], len(self.cases))
        ids = {item["id"] for item in payload["cases"]}
        self.assertEqual(ids, set(self.by_id))
        normal = next(item for item in payload["cases"] if item["id"] == "args-empty")
        self.assertEqual(normal["source"], "tests/cases/builtins-text-io/args-empty.lwt")
        self.assertTrue(normal["debug"]["available"])
        self.assertEqual(base64.b64decode(normal["stdin_base64"]), self.by_id["args-empty"].stdin)
        override = next(item for item in payload["cases"] if item["id"] == "cli-no-arguments")
        self.assertFalse(override["debug"]["available"])
        self.assertIn("cli_args_override", override["debug"]["reason"])
        expected_error = next(item for item in payload["cases"] if item["id"] == "division-by-zero")
        self.assertFalse(expected_error["debug"]["available"])

    def test_result_json_round_trips_arbitrary_output_bytes(self) -> None:
        case = self.by_id["args-empty"]
        result = runner.TestResult(case, "failed", "assertion_failure", ("stdout mismatch",), 0, b"\xff\x00\x80", b"\xfe", 0.125)
        serialized = runner.result_to_json(result)
        self.assertEqual(base64.b64decode(serialized["actual"]["stdout_base64"]), b"\xff\x00\x80")
        self.assertEqual(base64.b64decode(serialized["actual"]["stderr_base64"]), b"\xfe")
        self.assertEqual(serialized["expected"]["exit_code"], case.expected_exit_code)
        self.assertEqual(serialized["actual"]["exit_code"], 0)

    def test_json_preserves_raw_crlf_even_though_comparison_is_normalized(self) -> None:
        case = self.by_id["args-empty"]
        result = runner.TestResult(
            case, "passed", None, (), 0, b"expected\n", b"", 0.125,
            raw_stdout=b"expected\r\n", raw_stderr=b"",
        )

        serialized = runner.result_to_json(result)

        self.assertEqual(serialized["actual"]["stdout_base64"], base64.b64encode(b"expected\r\n").decode("ascii"))
        self.assertEqual(runner.normalize_newlines(b"expected\r\n"), b"expected\n")

    def test_list_json_does_not_execute_programs_or_pollute_stdout(self) -> None:
        stdout = StringIO()
        stderr = StringIO()
        with mock.patch.object(runner, "discover_cases", return_value=self.cases), \
            mock.patch.object(runner, "run_case", side_effect=AssertionError("list mode executed a case")), \
            redirect_stdout(stdout), redirect_stderr(stderr):
            status = runner.main(["--list-json"])
        payload = json.loads(stdout.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(payload["case_count"], len(self.cases))

    def test_inventory_validation_happens_before_selection(self) -> None:
        stdout = StringIO()
        stderr = StringIO()
        with mock.patch.object(runner, "discover_cases", side_effect=runner.ConfigurationError("unselected metadata is invalid")) as discover, \
            mock.patch.object(runner, "run_case", side_effect=AssertionError("invalid inventory ran a case")), \
            redirect_stdout(stdout), redirect_stderr(stderr):
            status = runner.main(["--case", "args-empty", "--format", "json"])
        self.assertEqual(discover.call_count, 1)
        self.assertEqual(status, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("unselected metadata is invalid", stderr.getvalue())

    def test_json_configuration_errors_are_stderr_only_and_nonzero(self) -> None:
        stdout = StringIO()
        stderr = StringIO()
        with mock.patch.object(runner, "discover_cases", return_value=self.cases), redirect_stdout(stdout), redirect_stderr(stderr):
            status = runner.main(["--case", "args-empty", "--case", "args-empty", "--format", "json"])
        self.assertEqual(status, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("--case IDs must not be repeated", stderr.getvalue())

    def test_real_cli_single_case_json_and_unicode_path(self) -> None:
        source = self.by_id["module-unicode-space-module-path"].source
        result = subprocess.run(
            [sys.executable, "tools/run_tests.py", "--case", "module-unicode-space-module-path", "--format", "json"],
            cwd=runner.REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            timeout=15,
            check=False,
        )
        payload = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        self.assertEqual(payload["summary"]["passed"], 1)
        self.assertTrue(payload["results"][0]["source"].endswith("unicode-space-module-path.lwt"))
        self.assertTrue(source.exists())

        with tempfile.TemporaryDirectory(dir=runner.REPO_ROOT, prefix="runner 路径 λ with spaces ") as directory:
            unicode_source = Path(directory) / "case 文件 with spaces.lwt"
            unicode_source.write_text('emit "路径通过";\n', encoding="utf-8")
            unicode_case = runner.TestCase(
                "unicode-path", "temporary", unicode_source, ("3",), (), (), b"",
                0, "路径通过\n".encode("utf-8"), b"", 5.0, None,
            )
            unicode_result = runner.run_case(unicode_case)
        self.assertEqual(unicode_result.status, "passed")

    def test_real_cli_category_selection_emits_one_valid_json_batch(self) -> None:
        result = subprocess.run(
            [sys.executable, "tools/run_tests.py", "--category", "arrays-records-each", "--format", "json"],
            cwd=runner.REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            timeout=30,
            check=False,
        )

        payload = json.loads(result.stdout.decode("utf-8", errors="strict"))
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        self.assertEqual(result.stderr, b"")
        self.assertEqual(payload["summary"]["selected"], 32)
        self.assertEqual(payload["summary"]["passed"], 32)
        self.assertEqual(payload["summary"]["failed"], 0)
        self.assertTrue(all(item["category"] == "arrays-records-each" for item in payload["results"]))

    def test_default_entry_keeps_legacy_text_summary_shape(self) -> None:
        case = self.by_id["args-empty"]
        stdout = StringIO()
        with mock.patch.object(runner, "discover_cases", return_value=[case]), \
            mock.patch.object(runner, "run_cases", return_value=[runner.TestResult(case, "passed", None, (), 0, b"", b"", 0.01)]), \
            redirect_stdout(stdout):
            status = runner.main([])
        self.assertEqual(status, 0)
        self.assertEqual(stdout.getvalue().splitlines()[0], "[PASS] args-empty")
        self.assertRegex(stdout.getvalue().splitlines()[1], r"^Black-box tests: passed=1 failed=0 total=1; categories \(passed/total\): builtins-text-io=1/1; elapsed=\d+\.\d{3}s$")

    def test_cancellation_stops_active_process_and_does_not_start_next_case(self) -> None:
        with tempfile.TemporaryDirectory(dir=runner.REPO_ROOT, prefix="runner cancel ") as directory:
            root = Path(directory)
            source = root / "while case λ.lwt"
            source.write_text("while (true) { }\n", encoding="utf-8")
            first = runner.TestCase("cancel-loop", "temporary", source, ("5",), (), (), b"", 0, b"", b"", 10, None)
            second = runner.TestCase("must-not-start", "temporary", source, ("5",), (), (), b"", 0, b"", b"", 10, None)
            cancellation = threading.Event()
            started: list[subprocess.Popen[bytes]] = []

            def cancel_after_spawn(process: subprocess.Popen[bytes]) -> None:
                started.append(process)
                cancellation.set()

            results = runner.run_cases([first, second], cancellation, on_process_started=cancel_after_spawn)

        self.assertEqual([item.status for item in results], ["cancelled", "not_executed"])
        self.assertEqual(len(started), 1)
        self.assertIsNotNone(started[0].poll())


if __name__ == "__main__":
    unittest.main()
