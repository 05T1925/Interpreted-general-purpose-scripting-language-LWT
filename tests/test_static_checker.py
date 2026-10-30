from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lwt.analyzer import analyze_module_graph
from lwt.modules import load_module_graph


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def run_lwt(*arguments: str, input_bytes: bytes = b"") -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "lwt", *arguments],
        cwd=REPOSITORY_ROOT,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={
            **os.environ,
            "PYTHONPATH": str(REPOSITORY_ROOT)
            + os.pathsep
            + os.environ.get("PYTHONPATH", ""),
        },
        timeout=10,
        check=False,
    )


def run_source(source: str, *arguments: str, input_bytes: bytes = b"") -> tuple[Path, subprocess.CompletedProcess[bytes]]:
    directory = tempfile.TemporaryDirectory()
    path = Path(directory.name) / "program.lwt"
    path.write_text(source, encoding="utf-8")
    result = run_lwt("--check", *arguments, str(path), input_bytes=input_bytes)
    directory.cleanup()
    return path, result


def decode_json(result: subprocess.CompletedProcess[bytes]) -> dict[str, object]:
    return json.loads(result.stdout.decode("utf-8"))


class StaticAnalyzerTests(unittest.TestCase):
    def test_valid_complete_ast_and_runtime_effects_are_not_executed(self) -> None:
        source = (
            'fn later() { return global_value; } '
            'when (false) { emit missing_function(); } '
            'attempt { emit input(); } recover(problem) { emit read_text("absent.txt"); } '
            'emit "program output must not appear"; let global_value = 7; '
            'fail("must not execute");'
        )
        _, result = run_source(
            source, "--format=json", input_bytes=b"stdin must remain unused\n"
        )
        self.assertEqual(result.returncode, 2)
        report = decode_json(result)
        diagnostics = report["diagnostics"]
        self.assertEqual([item["code"] for item in diagnostics], ["STC010"])
        self.assertEqual(
            list(diagnostics[0]),
            ["code", "severity", "category", "message", "source", "line", "column"],
        )
        self.assertNotIn(b"program output must not appear", result.stdout)
        self.assertNotIn(b"must not execute", result.stdout)
        self.assertEqual(result.stderr, b"")

    def test_clean_single_file_json_has_fixed_schema_and_one_lf(self) -> None:
        _, result = run_source('fn f(x) { return x; } emit f(2);', "--format=json")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, b"")
        self.assertTrue(result.stdout.endswith(b"\n"))
        self.assertFalse(result.stdout.endswith(b"\n\n"))
        self.assertEqual(
            list(decode_json(result)),
            ["schema_version", "ok", "files_checked", "diagnostics"],
        )
        self.assertEqual(
            decode_json(result),
            {"schema_version": 1, "ok": True, "files_checked": 1, "diagnostics": []},
        )

    def test_existing_multilevel_module_example_checks_without_execution(self) -> None:
        result = run_lwt("--check", "--format=json", "examples/modules/main.lwt")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, b"")
        self.assertEqual(decode_json(result)["files_checked"], 3)

    def test_repeated_and_unknown_function_and_arity_diagnostics_are_ordered(self) -> None:
        source = "fn f(x) {} fn f(y) {} emit f(); emit missing(1);"
        path, result = run_source(source, "--format=json")
        self.assertEqual(result.returncode, 2)
        report = decode_json(result)
        self.assertEqual(
            [item["code"] for item in report["diagnostics"]],
            ["STC001", "STC011", "STC010"],
        )
        self.assertEqual([item["line"] for item in report["diagnostics"]], [1, 1, 1])
        self.assertEqual(report["diagnostics"][0]["source"], str(path))
        self.assertEqual(result.stderr, b"")

    def test_builtin_signature_table_covers_all_ten_builtins(self) -> None:
        valid = (
            'input(); args(); read_text("x"); len("x"); split("x", "y"); '
            'trim("x"); to_int("1"); str(1); push([], 1); fail("x");'
        )
        _, good = run_source(valid, "--format=json")
        self.assertEqual(good.returncode, 0)
        self.assertEqual(decode_json(good)["diagnostics"], [])

        invalid = "input(1); args(1); read_text(); len(); split(1); trim(); to_int(); str(); push([]); fail();"
        _, bad = run_source(invalid, "--format=json")
        self.assertEqual(bad.returncode, 2)
        self.assertEqual(
            [item["code"] for item in decode_json(bad)["diagnostics"]],
            ["STC011"] * 10,
        )

    def test_record_shape_and_function_record_namespace(self) -> None:
        source = (
            "record R { a, b }; fn R() {} "
            "emit R{a: 1, a: 2, extra: 3}; emit Missing{};"
        )
        _, result = run_source(source, "--format=json")
        report = decode_json(result)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(
            [item["code"] for item in report["diagnostics"]],
            ["STC022", "STC021", "STC023", "STC020"],
        )
        _, valid = run_source("record R { a }; fn R() {} emit R{a: R()};", "--format=json")
        self.assertEqual(valid.returncode, 0)

    def test_duplicate_record_and_builtin_conflict(self) -> None:
        source = "record R { a }; record R { b }; fn len() {}"
        _, result = run_source(source, "--format=json")
        self.assertEqual(
            [item["code"] for item in decode_json(result)["diagnostics"]],
            ["STC002", "STC003"],
        )

    def test_variables_follow_function_block_each_attempt_and_assignment_scopes(self) -> None:
        valid = (
            "fn f(arg) { let same = arg; { let same = 2; emit same; } "
            "each (same in [1]) { let same = 3; emit same; } "
            "attempt { fail(\"x\"); } recover(err) { let err = \"shadow\"; emit err; } "
            "return same; } emit f(1);"
        )
        _, good = run_source(valid, "--format=json")
        self.assertEqual(good.returncode, 0, good.stdout)
        self.assertEqual(decode_json(good)["diagnostics"], [])

        invalid = "fn f(arg) { let arg = 1; let x = 0; let x = 1; missing = x; }"
        _, bad = run_source(invalid, "--format=json")
        self.assertEqual(
            [item["code"] for item in decode_json(bad)["diagnostics"]],
            ["STC041", "STC041", "STC040"],
        )

    def test_initializers_hide_only_the_binding_being_created(self) -> None:
        source = "let x = 1; { let x = x + 1; } let self = [self];"
        _, result = run_source(source, "--format=json")
        diagnostics = decode_json(result)["diagnostics"]
        self.assertEqual([item["code"] for item in diagnostics], ["STC040"])
        self.assertIn("'self'", diagnostics[0]["message"])

    def test_block_and_function_local_bindings_do_not_leak_or_capture_callers(self) -> None:
        source = (
            "fn read() { return caller_local; } "
            "fn caller() { let caller_local = 1; return read(); } "
            "{ let block_local = 1; } emit block_local;"
        )
        _, result = run_source(source, "--format=json")
        self.assertEqual(
            [item["message"] for item in decode_json(result)["diagnostics"]],
            ["undefined variable 'caller_local'", "undefined variable 'block_local'"],
        )

    def test_module_namespaces_and_module_call_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.lwt").write_text("fn same() { return 1; }", encoding="utf-8")
            (root / "b.lwt").write_text("fn same() { return 2; }", encoding="utf-8")
            (root / "main.lwt").write_text(
                'import "a.lwt" as a; import "b.lwt" as b; '
                'emit a.same(); emit b.same(); emit a.same(1); '
                'emit missing.call(); emit a.absent();',
                encoding="utf-8",
            )
            result = run_lwt("--check", "--format=json", str(root / "main.lwt"))
        report = decode_json(result)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["files_checked"], 3)
        self.assertEqual(
            [item["code"] for item in report["diagnostics"]],
            ["STC011", "STC030", "STC031"],
        )

    def test_module_function_is_not_allowed_to_capture_entry_local(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "lib.lwt").write_text(
                "fn read() { return entry_local; }", encoding="utf-8"
            )
            (root / "main.lwt").write_text(
                'import "lib.lwt" as lib; let entry_local = 1; emit lib.read();',
                encoding="utf-8",
            )
            result = run_lwt("--check", "--format=json", str(root / "main.lwt"))
        self.assertEqual(result.returncode, 2)
        diagnostic = decode_json(result)["diagnostics"][0]
        self.assertEqual(diagnostic["code"], "STC040")
        self.assertEqual(diagnostic["source"], "lib.lwt")

    def test_direct_analyzer_is_deterministic_for_all_module_units(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "lib.lwt").write_text("fn f() { emit missing_lib; }", encoding="utf-8")
            (root / "main.lwt").write_text(
                'import "lib.lwt" as lib; emit missing_main; emit lib.f();',
                encoding="utf-8",
            )
            graph = load_module_graph(str(root / "main.lwt"))
            first = analyze_module_graph(graph, str(root / "main.lwt"))
            second = analyze_module_graph(graph, str(root / "main.lwt"))
        self.assertEqual(first, second)
        self.assertEqual([item.source for item in first], [str(root / "main.lwt"), "lib.lwt"])


class StaticCheckerCliTests(unittest.TestCase):
    def test_checked_in_invalid_fixture_has_stable_text_and_json_contracts(self) -> None:
        source = "tests/fixtures/static-checker/undefined-function.lwt"
        text_result = run_lwt("--check", source)
        self.assertEqual(text_result.returncode, 2)
        self.assertEqual(text_result.stdout, b"")
        self.assertEqual(
            text_result.stderr,
            (source + ":1:6: StaticError[STC010]: undefined function 'missing'\n").encode(),
        )

        json_result = run_lwt("--check", "--format=json", source)
        self.assertEqual(json_result.returncode, 2)
        self.assertEqual(json_result.stderr, b"")
        self.assertEqual(
            json_result.stdout,
            (
                '{"schema_version":1,"ok":false,"files_checked":1,"diagnostics":'
                '[{"code":"STC010","severity":"error","category":"StaticError",'
                '"message":"undefined function \'missing\'","source":"'
                + source
                + '","line":1,"column":6}]}\n'
            ).encode("utf-8"),
        )

    def test_check_error_json_preserves_codes_categories_locations_and_exit_codes(self) -> None:
        cases = (
            ("@", 2, "LexError", "LEX001", 1, 1),
            ("let x = ;", 2, "SyntaxError", "PAR001", 1, 9),
        )
        for source, code, category, stable_code, line, column in cases:
            with self.subTest(source=source):
                _, result = run_source(source, "--format=json")
                self.assertEqual(result.returncode, code)
                self.assertEqual(result.stderr, b"")
                diagnostic = decode_json(result)["diagnostics"][0]
                self.assertEqual(diagnostic["category"], category)
                self.assertEqual(diagnostic["code"], stable_code)
                self.assertEqual((diagnostic["line"], diagnostic["column"]), (line, column))

    def test_cli_and_file_errors_are_json_and_keep_exit_four(self) -> None:
        missing = run_lwt("--check", "--format=json")
        self.assertEqual(missing.returncode, 4)
        self.assertEqual(missing.stderr, b"")
        self.assertEqual(decode_json(missing)["diagnostics"][0]["code"], "CLI001")

        absent = run_lwt("--check", "--format=json", "not-present.lwt")
        self.assertEqual(absent.returncode, 4)
        self.assertEqual(decode_json(absent)["diagnostics"][0]["category"], "FileError")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad-utf8.lwt"
            path.write_bytes(b"\xff")
            invalid = run_lwt("--check", "--format=json", str(path))
        self.assertEqual(invalid.returncode, 4)
        self.assertEqual(decode_json(invalid)["diagnostics"][0]["code"], "SRC001")

    def test_missing_import_is_module_error_with_import_source_position(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "main.lwt"
            path.write_text('import "absent.lwt" as lib; emit lib.f();', encoding="utf-8")
            result = run_lwt("--check", "--format=json", str(path))
        self.assertEqual(result.returncode, 4)
        diagnostic = decode_json(result)["diagnostics"][0]
        self.assertEqual((diagnostic["code"], diagnostic["category"]), ("MOD001", "ImportError"))
        self.assertEqual((diagnostic["line"], diagnostic["column"]), (1, 1))

    def test_text_diagnostics_are_single_line_on_stderr_and_have_stable_code(self) -> None:
        _, result = run_source("emit absent;")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"StaticError[STC040]: undefined variable 'absent'\n", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)

    def test_invalid_check_format_and_extra_arguments_do_not_parse_as_program_args(self) -> None:
        invalid_format = run_lwt("--check", "--format=text", "example.lwt")
        self.assertEqual(invalid_format.returncode, 4)
        self.assertIn(b"CliError", invalid_format.stderr)

        extra = run_lwt("--check", "--format=json", "example.lwt", "extra")
        self.assertEqual(extra.returncode, 4)
        self.assertEqual(decode_json(extra)["diagnostics"][0]["code"], "CLI001")

    def test_normal_execution_contract_remains_available(self) -> None:
        result = run_lwt("examples/modules/main.lwt")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"demo:2\n")
        self.assertEqual(result.stderr, b"")


if __name__ == "__main__":
    unittest.main()
