from __future__ import annotations

import subprocess
import os
import sys
import tempfile
import unittest
from pathlib import Path

from lwt.cli import parse_cli_args
from lwt.errors import LwtError, SourceLocation, format_diagnostic


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def run_lwt(
    *arguments: str, input_bytes: bytes = b"", cwd: str | Path | None = None
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "lwt", *arguments],
        cwd=REPOSITORY_ROOT if cwd is None else cwd,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={
            **os.environ,
            "PYTHONPATH": str(REPOSITORY_ROOT)
            + os.pathsep
            + os.environ.get("PYTHONPATH", ""),
        },
        check=False,
    )


def run_source(
    source: str,
    *,
    input_bytes: bytes = b"",
    cwd: str | Path | None = None,
    program_args: tuple[str, ...] = (),
) -> tuple[str, subprocess.CompletedProcess[bytes]]:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "program.lwt"
        path.write_text(source, encoding="utf-8")
        arguments = [str(path)]
        if program_args:
            arguments.extend(("--", *program_args))
        result = run_lwt(*arguments, input_bytes=input_bytes, cwd=cwd)
    return str(path), result


class CliArgumentTests(unittest.TestCase):
    def test_source_without_program_arguments(self) -> None:
        parsed = parse_cli_args(["script.anything"])
        self.assertEqual(parsed.source_path, "script.anything")
        self.assertEqual(parsed.program_args, ())

    def test_separator_preserves_all_later_arguments_including_double_dash(self) -> None:
        parsed = parse_cli_args(["script", "--", "one", "--", "two words", "雪"])
        self.assertEqual(parsed.program_args, ("one", "--", "two words", "雪"))

    def test_missing_source_and_separator_position_are_cli_errors(self) -> None:
        for arguments in ([], ["--"], ["script", "extra"], ["script", "extra", "--"]):
            with self.subTest(arguments=arguments), self.assertRaises(LwtError) as caught:
                parse_cli_args(arguments)
            self.assertEqual(caught.exception.category, "CliError")
            self.assertEqual(caught.exception.exit_code, 4)

    def test_diagnostic_newlines_are_escaped_into_one_line(self) -> None:
        error = LwtError("CliError", "first\r\nsecond", 4)
        self.assertEqual(
            format_diagnostic(error), "lwt: CliError: first\\r\\nsecond"
        )
        located = LwtError(
            "LexError", "bad\nsource", 2, SourceLocation(line=2, column=3)
        )
        self.assertEqual(
            format_diagnostic(located, "a\nb.lwt"),
            "a\\nb.lwt:2:3: LexError: bad\\nsource",
        )


class CliProcessTests(unittest.TestCase):
    def test_empty_whitespace_and_comment_files_succeed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for content in (b"", b" \t\n\f\v", b"# comment\n# @"):
                path = Path(directory) / "empty script"
                path.write_bytes(content)
                with self.subTest(content=content):
                    result = run_lwt(str(path))
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, b"")
                    self.assertEqual(result.stderr, b"")

    def test_utf8_bom_at_file_start_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bom-only.lwt"
            path.write_bytes(b"\xef\xbb\xbf")
            result = run_lwt(str(path))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, b"")

    def test_relative_source_path_is_resolved_from_process_working_directory(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as directory:
            path = Path(directory) / "script without extension"
            path.write_text("", encoding="utf-8")
            relative_path = path.relative_to(REPOSITORY_ROOT)
            result = run_lwt(str(relative_path))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, b"")

    def test_missing_source_argument_is_cli_error(self) -> None:
        result = run_lwt()
        self.assertEqual(result.returncode, 4)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, b"lwt: CliError: expected a source path\n")

    def test_double_dash_cannot_be_source_path(self) -> None:
        result = run_lwt("--")
        self.assertEqual(result.returncode, 4)
        self.assertEqual(result.stderr, b"lwt: CliError: expected a source path\n")

    def test_extra_argument_without_separator_is_cli_error(self) -> None:
        result = run_lwt("source", "extra")
        self.assertEqual(result.returncode, 4)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, b"lwt: CliError: program arguments must follow --\n")

    def test_nonexistent_file_is_file_error(self) -> None:
        path = str(REPOSITORY_ROOT / "missing source file.lwt")
        result = run_lwt(path)
        self.assertEqual(result.returncode, 4)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, b"lwt: FileError: cannot read source file\n")

    def test_invalid_utf8_is_file_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid-utf8.lwt"
            path.write_bytes(b"\xff")
            result = run_lwt(str(path))
        self.assertEqual(result.returncode, 4)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, b"lwt: FileError: source file is not valid UTF-8\n")

    def test_lexical_error_has_path_position_and_no_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "有 空格.lwt"
            path.write_text("@", encoding="utf-8")
            result = run_lwt(str(path))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{path}:1:1: LexError: unexpected character U+0040\n",
        )
        self.assertNotIn(b"Traceback", result.stderr)

    def test_unknown_escape_and_unterminated_string_diagnostics(self) -> None:
        cases = ((r'emit "bad\q";', 10, "unknown string escape"), ('emit "open', 6, "unterminated string literal"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "errors.lwt"
            for source, column, message in cases:
                path.write_text(source, encoding="utf-8")
                with self.subTest(source=source):
                    result = run_lwt(str(path))
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stdout, b"")
                    self.assertEqual(
                        result.stderr.decode("utf-8"),
                        f"{path}:1:{column}: LexError: {message}\n",
                    )

    def test_supported_nonempty_source_executes_through_cli(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nonempty-no-extension"
            path.write_text("let value = 123; emit value;", encoding="utf-8")
            result = run_lwt(str(path), "--", "first", "--", "雪")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"123\n")
        self.assertEqual(result.stderr, b"")

    def test_scalar_variables_assignments_and_block_scopes(self) -> None:
        source = (
            "let value = 4; emit value; "
            "{ let value = value + 1; emit value; "
            "{ let value = value + 2; emit value; value = value + 3; emit value; } "
            "emit value; value = value + 2; emit value; } "
            "emit value; let total = 1 + 2 * 3; total = total + 1; emit total; "
            "emit total = total + 1; emit total;"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scopes.lwt"
            path.write_text(source, encoding="utf-8")
            result = run_lwt(str(path))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"4\n5\n7\n10\n5\n7\n4\n8\n9\n9\n")
        self.assertEqual(result.stderr, b"")

    def test_scalar_types_and_all_operator_groups_execute(self) -> None:
        source = (
            'emit 2 + 3 * 4; emit (2 + 3) * 4; emit -7 / 3; emit -7 % 3; '
            'emit 8 % -3; emit "a" + "b"; emit "b" > "a"; '
            'emit "雪" > "a"; '
            'emit 2 == 2; emit 2 != 2; emit 1 < 2; emit 1 <= 1; '
            'emit 2 > 1; emit 2 >= 2; emit true == 1; emit true != 1; '
            'emit null == null; emit not false; emit false and true; emit true or false; '
            'emit 1 + 2 < 4 == true or false and false;'
        )
        expected = (
            "14\n20\n-3\n2\n-1\nab\ntrue\ntrue\ntrue\nfalse\n"
            "true\ntrue\ntrue\ntrue\nfalse\ntrue\ntrue\ntrue\n"
            "false\ntrue\ntrue\n"
        ).encode("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "operators.lwt"
            path.write_text(source, encoding="utf-8")
            result = run_lwt(str(path))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, expected)
        self.assertEqual(result.stderr, b"")

    def test_short_circuit_does_not_consume_standard_input(self) -> None:
        source = (
            'emit false and (input() == "consumed"); '
            'emit true or (input() == "consumed"); emit input();'
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "short-circuit.lwt"
            path.write_text(source, encoding="utf-8")
            result = run_lwt(str(path), input_bytes=b"still here\n")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"false\ntrue\nstill here\n")
        self.assertEqual(result.stderr, b"")

    def test_input_line_endings_empty_line_eof_unicode_and_final_line(self) -> None:
        cases = (
            (b"", b"null\n"),
            (b"\n", b"\n"),
            (b"\r\n", b"\n"),
            (b"text\n", b"text\n"),
            (b"final line", b"final line\n"),
            ("雪\n".encode("utf-8"), "雪\n".encode("utf-8")),
            (b"\r", b"\r\n"),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.lwt"
            path.write_text("emit input();", encoding="utf-8")
            for input_bytes, expected_stdout in cases:
                with self.subTest(input_bytes=input_bytes):
                    result = run_lwt(str(path), input_bytes=input_bytes)
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, expected_stdout)
                    self.assertEqual(result.stderr, b"")

    def test_large_integer_literal_and_negative_output_over_6000_digits(self) -> None:
        digits = "9" * 6000
        source = f"emit 0000000000000000; emit {digits}; emit -{digits}; emit -00000;"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large-integer.lwt"
            path.write_text(source, encoding="utf-8")
            result = run_lwt(str(path))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            result.stdout,
            ("0\n" + digits + "\n-" + digits + "\n0\n").encode(),
        )
        self.assertEqual(result.stderr, b"")

    def test_runtime_errors_have_exact_positions_and_preserve_prior_output(self) -> None:
        cases = (
            ("emit missing;", "missing", "undefined variable 'missing'", 3),
            ("emit true + 1;", "+", "'+' requires two integers or two strings", 3),
            ("emit -true;", "-", "unary '-' requires an integer", 3),
            ("emit not 1;", "not", "'not' requires a boolean", 3),
            ("emit 1 / 0;", "/", "division by zero", 3),
            ("emit 1 % 0;", "%", "division by zero", 3),
            ("emit 1 and true;", "and", "'and' requires boolean operands", 3),
            ("emit true and 1;", "and", "'and' requires boolean operands", 3),
            (
                "emit true < false;",
                "<",
                "operator '<' requires two integers or two strings",
                3,
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime-error.lwt"
            for source, marker, message, _ in cases:
                path.write_text(source, encoding="utf-8")
                with self.subTest(source=source):
                    result = run_lwt(str(path))
                    self.assertEqual(result.returncode, 3)
                    self.assertEqual(result.stdout, b"")
                    self.assertEqual(
                        result.stderr.decode("utf-8"),
                        f"{path}:1:{source.index(marker) + 1}: RuntimeError: {message}\n",
                    )
                    self.assertNotIn(b"Traceback", result.stderr)

            source = 'emit "before"; emit 1 / 0;'
            path.write_text(source, encoding="utf-8")
            result = run_lwt(str(path))
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, b"before\n")
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{path}:1:{source.index('/') + 1}: RuntimeError: division by zero\n",
        )

    def test_let_and_assignment_validate_target_before_evaluating_rhs(self) -> None:
        cases = (
            (
                "let x = 1; let x = input();",
                "variable 'x' is already declared in this scope",
                lambda source: source.rfind("let x") + len("let ") + 1,
            ),
            (
                "missing = input();",
                "undefined variable 'missing'",
                lambda source: source.index("=") + 1,
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "target-before-rhs.lwt"
            for source, message, location in cases:
                path.write_text(source, encoding="utf-8")
                with self.subTest(source=source):
                    # Invalid UTF-8 would fail at input() if the RHS ran first.
                    result = run_lwt(str(path), input_bytes=b"\xff")
                    self.assertEqual(result.returncode, 3)
                    self.assertEqual(result.stdout, b"")
                    self.assertEqual(
                        result.stderr.decode("utf-8"),
                        f"{path}:1:{location(source)}: RuntimeError: {message}\n",
                    )
                    self.assertNotIn("standard input is not valid UTF-8", result.stderr.decode("utf-8"))

    def test_block_local_variable_expires_when_block_exits(self) -> None:
        source = "{ let inside = 1; } emit inside;"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scope-error.lwt"
            path.write_text(source, encoding="utf-8")
            result = run_lwt(str(path))
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{path}:1:{source.rfind('inside') + 1}: RuntimeError: undefined variable 'inside'\n",
        )

    def test_input_arity_and_invalid_utf8_are_runtime_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input-error.lwt"
            path.write_text('input("unused");', encoding="utf-8")
            result = run_lwt(str(path))
            self.assertEqual(result.returncode, 3)
            self.assertEqual(result.stdout, b"")
            self.assertEqual(
                result.stderr.decode("utf-8"),
                f"{path}:1:1: RuntimeError: input expects 0 arguments\n",
            )

            path.write_text("emit input();", encoding="utf-8")
            result = run_lwt(str(path), input_bytes=b"\xff\n")
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{path}:1:6: RuntimeError: standard input is not valid UTF-8\n",
        )
        self.assertNotIn(b"Traceback", result.stderr)

    def test_s7_builtins_in_unselected_and_uninvoked_code_are_not_executed(self) -> None:
        source = (
            'emit "visible"; when (false) { emit len(input()); read_text("missing.txt"); } '
            'fn unused() { fail("not called"); }'
        )
        path, result = run_source(source, input_bytes=b"\xff\n")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"visible\n")
        self.assertEqual(result.stderr, b"")

    def test_when_executes_only_the_selected_branch(self) -> None:
        source = (
            'when (true) { emit "then"; } otherwise { emit input(); } '
            'when (false) { emit "wrong"; } otherwise { emit "else"; } '
            'when (false) { emit "also wrong"; } emit input();'
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "when.lwt"
            path.write_text(source, encoding="utf-8")
            result = run_lwt(str(path), input_bytes=b"still here\n")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"then\nelse\nstill here\n")
        self.assertEqual(result.stderr, b"")

    def test_when_condition_requires_boolean_at_keyword_location(self) -> None:
        source = "  when (1) { emit 1; }"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "when-type.lwt"
            path.write_text(source, encoding="utf-8")
            result = run_lwt(str(path))
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{path}:1:3: RuntimeError: when condition must be a boolean\n",
        )
        self.assertNotIn(b"Traceback", result.stderr)

    def test_when_block_has_scope_and_updates_nearest_outer_binding(self) -> None:
        source = (
            "let count = 1; when (true) { let local = count + 1; "
            "count = local; emit local; } emit count; emit local;"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "when-scope.lwt"
            path.write_text(source, encoding="utf-8")
            result = run_lwt(str(path))
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, b"2\n2\n")
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{path}:1:{source.rfind('local') + 1}: RuntimeError: undefined variable 'local'\n",
        )

    def test_while_rechecks_condition_and_creates_a_scope_each_iteration(self) -> None:
        source = (
            "let i = 0; while (i < 4) { let iteration = i; "
            "when (iteration % 2 == 0) { emit iteration; } "
            "otherwise { emit -iteration; } i = i + 1; } emit i;"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "while.lwt"
            path.write_text(source, encoding="utf-8")
            result = run_lwt(str(path))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"0\n-1\n2\n-3\n4\n")
        self.assertEqual(result.stderr, b"")

    def test_while_false_runs_zero_times_and_does_not_leak_bindings(self) -> None:
        source = 'while (false) { emit "wrong"; } emit "done";'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "while-zero.lwt"
            path.write_text(source, encoding="utf-8")
            result = run_lwt(str(path))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"done\n")
        self.assertEqual(result.stderr, b"")

        source = "let i = 0; while (i < 1) { let hidden = 7; i = i + 1; } emit hidden;"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "while-scope.lwt"
            path.write_text(source, encoding="utf-8")
            result = run_lwt(str(path))
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{path}:1:{source.rfind('hidden') + 1}: RuntimeError: undefined variable 'hidden'\n",
        )

    def test_while_condition_requires_boolean_at_keyword_location(self) -> None:
        source = "while (null) {}"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "while-type.lwt"
            path.write_text(source, encoding="utf-8")
            result = run_lwt(str(path))
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{path}:1:1: RuntimeError: while condition must be a boolean\n",
        )
        self.assertNotIn(b"Traceback", result.stderr)

    def test_break_and_continue_remain_syntax_errors_before_execution(self) -> None:
        for keyword in ("break", "continue"):
            source = f'emit "hidden"; {keyword};'
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / f"{keyword}.lwt"
                path.write_text(source, encoding="utf-8")
                with self.subTest(keyword=keyword):
                    result = run_lwt(str(path))
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b"")
            self.assertIn(b"SyntaxError", result.stderr)
            self.assertNotIn(b"Traceback", result.stderr)

    def test_syntax_error_has_source_path_position_and_no_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "syntax error.lwt"
            path.write_text("let value = ;", encoding="utf-8")
            result = run_lwt(str(path))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{path}:1:13: SyntaxError: expected expression\n",
        )
        self.assertNotIn(b"Traceback", result.stderr)

    def test_duplicate_record_declaration_field_points_to_second_name(self) -> None:
        source = "record Person {name, name};"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate-field.lwt"
            path.write_text(source, encoding="utf-8")
            result = run_lwt(str(path))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{path}:1:{source.rfind('name') + 1}: SyntaxError: "
            "duplicate field name in record declaration\n",
        )
        self.assertNotIn(b"Traceback", result.stderr)

    def test_complete_lexing_reports_later_lex_error_before_syntax_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lex-before-parse.lwt"
            path.write_text("let value = ;\n@", encoding="utf-8")
            result = run_lwt(str(path))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{path}:2:1: LexError: unexpected character U+0040\n",
        )
        self.assertNotIn(b"SyntaxError", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)

    def test_comment_bom_and_invalid_characters_inside_comment_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "comments.lwt"
            path.write_text("#\ufeff@\n", encoding="utf-8")
            result = run_lwt(str(path))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, b"")


class S5FunctionCliTests(unittest.TestCase):
    def test_functions_are_preregistered_and_top_level_order_is_preserved(self) -> None:
        source = (
            'emit add(2, 3); fn add(left, right) { return left + right; } '
            'emit "after";'
        )
        path, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"5\nafter\n")
        self.assertEqual(result.stderr, b"")

    def test_mutual_recursion_and_recursive_activation_records(self) -> None:
        source = (
            'emit is_even(12); emit is_odd(7); emit factorial(6); '
            'fn is_even(n) { when (n == 0) { return true; } return is_odd(n - 1); } '
            'fn is_odd(n) { when (n == 0) { return false; } return is_even(n - 1); } '
            'fn factorial(n) { let result = 1; when (n > 1) { '
            'result = n * factorial(n - 1); } return result; }'
        )
        path, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"true\ntrue\n720\n")
        self.assertEqual(result.stderr, b"")

    def test_return_propagates_from_nested_block_when_and_while(self) -> None:
        source = (
            'fn find(limit) { let i = 0; while (i < limit) { '
            'when (i == 2) { { return i + 10; } } i = i + 1; } return; } '
            'fn explicit_null() { return null; } fn empty_return() { return; } '
            'fn natural_end() { emit "body"; } '
            'emit find(5); emit find(1); emit explicit_null(); emit empty_return(); '
            'emit natural_end();'
        )
        path, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"12\nnull\nnull\nnull\nbody\nnull\n")
        self.assertEqual(result.stderr, b"")

    def test_function_activation_uses_fresh_locals_and_shares_globals(self) -> None:
        source = (
            'let total = 1; fn add_global(amount) { total = total + amount; '
            'return total; } fn local() { let count = 0; count = count + 1; '
            'return count; } fn show(parameter) { { let parameter = parameter + 1; '
            'emit parameter; } return parameter; } '
            'emit add_global(2); emit total; emit local(); emit local(); emit show(5);'
        )
        path, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"3\n3\n1\n1\n6\n5\n")
        self.assertEqual(result.stderr, b"")

    def test_function_cannot_read_the_callers_local_variable(self) -> None:
        source = (
            'fn outer() { let local = 5; return inner(); } '
            'fn inner() { return local; } emit outer();'
        )
        path, result = run_source(source)
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{path}:1:{source.index('local', source.index('fn inner')) + 1}: "
            "RuntimeError: undefined variable 'local'\n",
        )
        self.assertNotIn(b"Traceback", result.stderr)

    def test_function_does_not_see_a_global_before_its_let_executes(self) -> None:
        source = "fn read_future() { return future; } emit read_future(); let future = 7;"
        path, result = run_source(source)
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{path}:1:{source.index('future', source.index('return future')) + 1}: "
            "RuntimeError: undefined variable 'future'\n",
        )

    def test_unknown_function_is_resolved_before_its_arguments(self) -> None:
        source = 'emit "before"; missing(input());'
        path, result = run_source(source, input_bytes=b"\xff\n")
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, b"before\n")
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{path}:1:{source.index('missing') + 1}: RuntimeError: undefined function 'missing'\n",
        )
        self.assertNotIn(b"valid UTF-8", result.stderr)

    def test_unknown_calls_are_not_pre_resolved_in_unselected_or_unused_code(self) -> None:
        source = (
            'when (false) { missing(input()); } fn unused() { never_declared(); } '
            'emit input();'
        )
        path, result = run_source(source, input_bytes=b"available\n")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"available\n")
        self.assertEqual(result.stderr, b"")

    def test_function_arguments_evaluate_left_to_right_before_arity_check(self) -> None:
        source = (
            'fn mark(value) { emit value; return value; } '
            'fn join(left, right) { return left + right; } '
            'emit join(mark("first"), mark("second")); '
            'fn one(value) { return value; } '
            'fn extra_a() { emit "arg-a"; return 1; } '
            'fn extra_b() { emit "arg-b"; return 2; } '
            'emit one(extra_a(), extra_b());'
        )
        path, result = run_source(source)
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, b"first\nsecond\nfirstsecond\narg-a\narg-b\n")
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{path}:1:{source.rindex('one(') + 1}: RuntimeError: "
            "function 'one' expects 1 arguments, got 2\n",
        )

    def test_function_arity_error_for_too_few_arguments_uses_call_location(self) -> None:
        source = "fn one(value) { return value; } emit one();"
        path, result = run_source(source)
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{path}:1:{source.rindex('one(') + 1}: RuntimeError: "
            "function 'one' expects 1 arguments, got 0\n",
        )

    def test_input_and_emit_work_inside_user_functions(self) -> None:
        source = 'fn ask() { emit "prompt"; return input(); } emit ask();'
        path, result = run_source(source, input_bytes="雪\n".encode("utf-8"))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "prompt\n雪\n".encode("utf-8"))
        self.assertEqual(result.stderr, b"")

    def test_duplicate_function_is_reported_before_top_level_output(self) -> None:
        source = 'emit "must not print"; fn same() {} fn same() {}'
        path, result = run_source(source)
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{path}:1:{source.rfind('fn same') + 4}: RuntimeError: "
            "duplicate function declaration 'same'\n",
        )

    def test_all_builtin_function_names_are_reserved(self) -> None:
        for name in (
            "input",
            "args",
            "read_text",
            "len",
            "split",
            "trim",
            "to_int",
            "str",
            "push",
            "fail",
        ):
            source = f'emit "must not print"; fn {name}() {{}}'
            path, result = run_source(source)
            with self.subTest(name=name):
                self.assertEqual(result.returncode, 3)
                self.assertEqual(result.stdout, b"")
                self.assertEqual(
                    result.stderr.decode("utf-8"),
                    f"{path}:1:{source.index(f'fn {name}') + 4}: RuntimeError: "
                    f"function name '{name}' conflicts with a built-in\n",
                )
                self.assertNotIn(b"Traceback", result.stderr)

    def test_parameter_cannot_be_redeclared_in_function_outer_body(self) -> None:
        source = "fn f(arg) { let arg = input(); } f(1);"
        path, result = run_source(source, input_bytes=b"\xff")
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{path}:1:{source.rfind('let arg') + len('let ') + 1}: RuntimeError: "
            "variable 'arg' is already declared in this scope\n",
        )
        self.assertNotIn(b"valid UTF-8", result.stderr)

    def test_recursion_limit_is_runtime_error_at_recursive_call(self) -> None:
        source = "fn spin() { return spin(); } spin();"
        path, result = run_source(source)
        recursive_call = source.index("spin()", source.index("{") + 1)
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{path}:1:{recursive_call + 1}: RuntimeError: host recursion limit reached\n",
        )
        self.assertNotIn(b"Traceback", result.stderr)

    def test_record_name_shares_no_function_namespace_and_record_executes(self) -> None:
        source = 'record Person {}; fn Person() { return 42; } emit Person(); emit Person{};'
        path, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"42\nPerson{}\n")
        self.assertEqual(result.stderr, b"")

    def test_s7_builtin_in_uninvoked_function_has_no_effect(self) -> None:
        source = 'emit "hidden"; fn unused() { emit len(input()); }'
        path, result = run_source(source, input_bytes=b"\xff")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"hidden\n")
        self.assertEqual(result.stderr, b"")

    def test_builtins_are_reserved_and_resolve_before_argument_evaluation(self) -> None:
        source = 'emit "before"; absent(input());'
        path, result = run_source(source, input_bytes=b"\xff\n")
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, b"before\n")
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{path}:1:{source.index('absent') + 1}: RuntimeError: "
            "undefined function 'absent'\n",
        )
        self.assertNotIn(b"valid UTF-8", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)

    def test_s6_array_index_and_field_access_are_runtime_checked_at_access_tokens(self) -> None:
        cases = (
            ("emit [1][2];", "[2]", "array index is out of range"),
            ("let n = 1; emit n.field;", ".field", "field access requires a record"),
        )
        for source, marker, message in cases:
            path, result = run_source(source)
            with self.subTest(source=source):
                self.assertEqual(result.returncode, 3)
                self.assertEqual(result.stdout, b"")
                self.assertEqual(
                    result.stderr.decode("utf-8"),
                    f"{path}:1:{source.index(marker) + 1}: RuntimeError: {message}\n",
                )


class S6CollectionsCliTests(unittest.TestCase):
    def assert_runtime_error_at(
        self,
        source: str,
        marker: str,
        message: str,
        *,
        stdout: bytes = b"",
        input_bytes: bytes = b"",
        occurrence: int = 0,
    ) -> None:
        path, result = run_source(source, input_bytes=input_bytes)
        offset = -1
        search_from = 0
        for _ in range(occurrence + 1):
            offset = source.index(marker, search_from)
            search_from = offset + len(marker)
        prefix = source[:offset]
        line = prefix.count("\n") + 1
        column = len(prefix.rsplit("\n", 1)[-1]) + 1
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, stdout)
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{path}:{line}:{column}: RuntimeError: {message}\n",
        )
        self.assertNotIn(b"Traceback", result.stderr)

    def test_array_literals_are_fresh_nested_and_evaluated_left_to_right(self) -> None:
        source = (
            "fn value(n) { emit n; return n; } "
            "let values = [value(1), [value(2), value(3)]]; "
            "emit values; emit []; emit values[1][0];"
        )
        _, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"1\n2\n3\n[1, [2, 3]]\n[]\n2\n")
        self.assertEqual(result.stderr, b"")

    def test_array_index_zero_last_and_assignment_expression_value(self) -> None:
        source = "let values = [4, 5, 6]; emit values[0]; emit values[2]; emit values[1] = 9; emit values;"
        _, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"4\n6\n9\n[4, 9, 6]\n")
        self.assertEqual(result.stderr, b"")

    def test_invalid_array_indexes_and_receiver_use_access_location(self) -> None:
        cases = (
            ("emit [1][-1];", "[-1]", "array index is out of range"),
            ("emit [1][1];", "[1]", "array index is out of range", 1),
            ("emit [1][true];", "[true]", "array index must be an integer"),
            ("let n = 1; emit n[0];", "[0]", "indexing requires an array"),
        )
        for case in cases:
            source, marker, message, *which = case
            with self.subTest(source=source):
                self.assert_runtime_error_at(
                    source, marker, message, occurrence=which[0] if which else 0
                )

    def test_index_receiver_and_index_expressions_are_each_evaluated_once_in_order(self) -> None:
        source = (
            'let events = ""; let values = [0]; '
            'fn receiver() { events = events + "r"; return values; } '
            'fn index() { events = events + "i"; return 0; } '
            'fn rhs() { events = events + "v"; return 7; } '
            "emit receiver()[index()] = rhs(); emit events; emit values;"
        )
        _, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"7\nriv\n[7]\n")
        self.assertEqual(result.stderr, b"")

    def test_invalid_index_assignment_does_not_evaluate_rhs(self) -> None:
        source = "let values = []; emit values[-1] = input();"
        self.assert_runtime_error_at(
            source,
            "[-1]",
            "array index is out of range",
            input_bytes=b"\xff\n",
        )

    def test_non_array_index_still_evaluates_index_before_type_validation(self) -> None:
        source = 'fn index() { emit "index"; return 0; } let n = 1; emit n[index()];'
        self.assert_runtime_error_at(
            source,
            "[index()]",
            "indexing requires an array",
            stdout=b"index\n",
        )

    def test_arrays_alias_mutably_but_compare_by_identity(self) -> None:
        source = (
            "let first = [1]; let alias = first; let second = [1]; "
            "emit first == alias; emit first == second; emit first != second; "
            "alias[0] = 8; emit first; emit alias; emit [1] == [1];"
        )
        _, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"true\nfalse\ntrue\n[8]\n[8]\nfalse\n")
        self.assertEqual(result.stderr, b"")

    def test_push_mutates_alias_returns_null_and_checks_arguments_at_call(self) -> None:
        source = (
            'let values = [1]; let alias = values; '
            "emit push(values, 2); emit alias; emit values == alias;"
        )
        _, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"null\n[1, 2]\ntrue\n")
        self.assertEqual(result.stderr, b"")

        self.assert_runtime_error_at(
            'push(1, 2);', "push", "push first argument must be an array"
        )
        self.assert_runtime_error_at("push([], 1, 2);", "push", "push expects 2 arguments")

    def test_push_evaluates_arguments_left_to_right_before_arity_check(self) -> None:
        source = 'fn mark(n) { emit n; return n; } push(mark(1), mark(2), mark(3));'
        self.assert_runtime_error_at(
            source,
            "push",
            "push expects 2 arguments",
            stdout=b"1\n2\n3\n",
        )

    def test_array_reference_is_shared_through_function_parameters(self) -> None:
        source = (
            "fn append(items) { push(items, 9); } "
            "let values = [1]; append(values); emit values;"
        )
        _, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"[1, 9]\n")
        self.assertEqual(result.stderr, b"")

    def test_record_types_are_preregistered_and_namespaces_are_independent(self) -> None:
        source = (
            "emit Thing{value: 3}; record Thing { value }; "
            "fn Thing() { return 9; } let Thing = Thing{value: 4}; "
            "emit Thing.value; emit Thing();"
        )
        _, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"Thing{value: 3}\n4\n9\n")
        self.assertEqual(result.stderr, b"")

    def test_duplicate_record_is_reported_before_top_level_output(self) -> None:
        source = 'emit "hidden"; record Data {}; record Data {};'
        self.assert_runtime_error_at(
            source,
            "Data",
            "duplicate record declaration 'Data'",
            occurrence=1,
        )

    def test_record_constructor_evaluates_in_source_order_and_displays_declaration_order(self) -> None:
        source = (
            "record Pair { first, second }; record Empty {}; "
            "fn value(n) { emit n; return n; } "
            'emit Pair{second: value("B"), first: value("A")}; emit Empty{};'
        )
        _, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'B\nA\nPair{first: "A", second: "B"}\nEmpty{}\n')
        self.assertEqual(result.stderr, b"")

    def test_unknown_record_type_is_checked_before_field_expressions(self) -> None:
        source = 'fn side() { emit "field"; return 1; } emit Missing{value: side()};'
        self.assert_runtime_error_at(
            source,
            "Missing",
            "undefined record type 'Missing'",
        )

    def test_record_constructor_validates_duplicate_missing_and_extra_fields_first(self) -> None:
        cases = (
            (
                'record R {a, b}; fn side() { emit "field"; return 1; } '
                "emit R{a: side(), a: side()};",
                "R{",
                "record construction for 'R' repeats field 'a'",
            ),
            (
                'record R {a, b}; fn side() { emit "field"; return 1; } '
                "emit R{a: side()};",
                "R{",
                "record construction for 'R' is missing field 'b'",
            ),
            (
                'record R {a}; fn side() { emit "field"; return 1; } '
                "emit R{a: side(), extra: side()};",
                "R{",
                "record type 'R' has no field 'extra'",
            ),
        )
        for source, marker, message in cases:
            with self.subTest(source=source):
                self.assert_runtime_error_at(source, marker, message)

    def test_record_constructor_stops_at_first_failing_field_expression(self) -> None:
        source = (
            "record R {first, second, third}; "
            'fn first() { emit "first"; return 1; } '
            'fn broken() { emit "broken"; return 1 / 0; } '
            'fn last() { emit "last"; return 3; } '
            "emit R{first: first(), second: broken(), third: last()};"
        )
        self.assert_runtime_error_at(
            source,
            "/",
            "division by zero",
            stdout=b"first\nbroken\n",
        )

    def test_record_field_read_write_alias_and_identity_equality(self) -> None:
        source = (
            "record Node {value, next}; "
            "let node = Node{value: 1, next: null}; let alias = node; "
            "let other = Node{value: 1, next: null}; "
            "emit node == alias; emit node == other; "
            "emit alias.value = 5; emit node.value; emit node;"
        )
        _, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            result.stdout,
            b"true\nfalse\n5\n5\nNode{value: 5, next: null}\n",
        )
        self.assertEqual(result.stderr, b"")

    def test_record_field_errors_and_assignment_validate_before_rhs(self) -> None:
        self.assert_runtime_error_at(
            "let value = 1; emit value.missing;",
            ".missing",
            "field access requires a record",
        )
        self.assert_runtime_error_at(
            'record R {known}; let value = R{known: 1}; emit value.missing;',
            ".missing",
            "record 'R' has no field 'missing'",
        )
        self.assert_runtime_error_at(
            "let value = 1; value.field = input();",
            ".field",
            "field assignment requires a record",
            input_bytes=b"\xff\n",
        )
        self.assert_runtime_error_at(
            'record R {known}; let value = R{known: 1}; value.missing = input();',
            ".missing",
            "record 'R' has no field 'missing'",
            input_bytes=b"\xff\n",
        )

    def test_record_field_assignment_returns_value_and_receiver_runs_once(self) -> None:
        source = (
            "record R {value}; let calls = 0; let rec = R{value: 0}; "
            "fn receiver() { calls = calls + 1; return rec; } "
            "emit receiver().value = 7; emit calls; emit rec;"
        )
        _, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"7\n1\nR{value: 7}\n")
        self.assertEqual(result.stderr, b"")

    def test_each_empty_array_expression_once_and_iteration_scope(self) -> None:
        # S42: `values` became a dict built-in; the local helper is renamed to
        # `values_snapshot` so this S6 test keeps checking the same behavior
        # (the empty-array iterable is evaluated exactly once and the iteration
        # scope is fresh) without colliding with the new built-in name.
        source = (
            "let calls = 0; let item = 99; "
            "fn values_snapshot() { calls = calls + 1; return [3, 4]; } "
            "each (item in []) { emit 0; } "
            "each (item in values_snapshot()) { let local = item; emit local; item = 8; } "
            "emit calls; emit item;"
        )
        _, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"3\n4\n1\n99\n")
        self.assertEqual(result.stderr, b"")

    def test_assigning_each_variable_does_not_replace_source_elements(self) -> None:
        source = "let values = [1, 2]; each (item in values) { item = 9; } emit values;"
        _, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"[1, 2]\n")
        self.assertEqual(result.stderr, b"")

    def test_each_variable_does_not_leak_after_loop(self) -> None:
        source = "each (item in [1]) { emit item; } emit item;"
        self.assert_runtime_error_at(
            source,
            "item;",
            "undefined variable 'item'",
            stdout=b"1\n",
            occurrence=1,
        )

    def test_each_uses_shallow_snapshot_for_appends_and_replacements(self) -> None:
        source = (
            "let values = [1, 2, 3]; let turn = 0; "
            "each (item in values) { emit item; turn = turn + 1; "
            "when (turn == 1) { values[1] = 20; push(values, 4); } } "
            "emit values;"
        )
        _, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"1\n2\n3\n[1, 20, 3, 4]\n")
        self.assertEqual(result.stderr, b"")

    def test_each_snapshot_keeps_references_to_mutable_nested_values(self) -> None:
        source = (
            "let child = [0]; let values = [child, child]; "
            "each (item in values) { when (item[0] == 0) { item[0] = 1; } "
            "otherwise { emit item[0]; } }"
        )
        _, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"1\n")
        self.assertEqual(result.stderr, b"")

    def test_return_propagates_through_each(self) -> None:
        source = (
            "fn find() { each (item in [1, 2, 3]) { "
            "when (item == 2) { return item; } } return 0; } emit find();"
        )
        _, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"2\n")
        self.assertEqual(result.stderr, b"")

    def test_mixed_scalar_and_compound_equality_is_strict_and_cycle_safe(self) -> None:
        source = (
            "let first = []; let second = []; push(first, first); push(second, second); "
            "record R {value}; let record_value = R{value: first}; "
            "emit true == 1; emit 1 == \"1\"; emit null == null; "
            "emit first == second; emit first == first; emit record_value == first;"
        )
        _, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"false\nfalse\ntrue\nfalse\ntrue\nfalse\n")
        self.assertEqual(result.stderr, b"")

    def test_composite_display_handles_cycles_and_shared_children(self) -> None:
        source = (
            "record Node {next}; let node = Node{next: null}; node.next = node; "
            "let cycle = []; push(cycle, cycle); "
            "let child = [1]; let shared = [child, child]; "
            "let left = []; let right = []; push(left, right); push(right, left); "
            "emit cycle; emit node; emit shared; emit left;"
        )
        _, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            result.stdout,
            b"[<cycle>]\nNode{next: <cycle>}\n[[1], [1]]\n[[<cycle>]]\n",
        )
        self.assertEqual(result.stderr, b"")

    def test_nested_string_display_escapes_controls_and_preserves_unicode(self) -> None:
        source = 'emit ["quote: \\" slash: \\\\ line:\\n tab:\\t", input()];'
        _, result = run_source(source, input_bytes=b"\x00\r\x1f\x7f\xe9\x9b\xaa\n")
        self.assertEqual(result.returncode, 0)
        expected = '["quote: \\" slash: \\\\ line:\\n tab:\\t", "\\u0000\\r\\u001F\\u007F雪"]\n'
        self.assertEqual(result.stdout, expected.encode("utf-8"))
        self.assertEqual(result.stderr, b"")

    def test_large_integer_inside_array_uses_safe_decimal_formatting(self) -> None:
        digits = "9" * 6000
        _, result = run_source(f"emit [{digits}, -{digits}];")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, f"[{digits}, -{digits}]\n".encode("ascii"))
        self.assertEqual(result.stderr, b"")

    def test_formatter_host_recursion_failure_is_runtime_error_without_partial_line(self) -> None:
        source = (
            "let value = []; let count = 0; "
            "while (count < 1400) { value = [value]; count = count + 1; } "
            "emit value;"
        )
        self.assert_runtime_error_at(
            source,
            "emit value",
            "host recursion limit reached while displaying value",
        )

    def test_each_requires_array_at_keyword_location(self) -> None:
        source = "each (item in 1) { emit item; }"
        self.assert_runtime_error_at(source, "each", "each requires an array")

    def test_s7_builtins_run_only_when_execution_reaches_the_call(self) -> None:
        cases = (
            ('when (false) { fail("unselected"); } emit "selected";', "selected\n"),
            ('fn unused() { fail("uninvoked"); } emit "selected";', "selected\n"),
        )
        for source, expected_stdout in cases:
            path, result = run_source(source)
            with self.subTest(source=source):
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, expected_stdout.encode("utf-8"))
                self.assertEqual(result.stderr, b"")

    def test_unknown_record_in_unselected_branch_is_not_pre_resolved(self) -> None:
        source = 'when (false) { emit Missing{value: 1}; } emit "ok";'
        _, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"ok\n")
        self.assertEqual(result.stderr, b"")


class S7BuiltinCliTests(unittest.TestCase):
    def assert_runtime_error_at(
        self,
        source: str,
        marker: str,
        message: str,
        *,
        stdout: bytes = b"",
        input_bytes: bytes = b"",
        cwd: str | Path | None = None,
        program_args: tuple[str, ...] = (),
    ) -> None:
        path, result = run_source(
            source,
            input_bytes=input_bytes,
            cwd=cwd,
            program_args=program_args,
        )
        offset = source.index(marker)
        prefix = source[:offset]
        line = prefix.count("\n") + 1
        column = len(prefix.rsplit("\n", 1)[-1]) + 1
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, stdout)
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{path}:{line}:{column}: RuntimeError: {message}\n",
        )
        self.assertNotIn(b"Traceback", result.stderr)

    def test_args_empty_vector_preserves_program_argument_boundaries_and_is_fresh(self) -> None:
        _, empty = run_source("emit args();")
        self.assertEqual((empty.returncode, empty.stdout, empty.stderr), (0, b"[]\n", b""))

        source = 'let first = args(); push(first, "changed"); emit args(); emit first;'
        _, result = run_source(
            source,
            program_args=("plain", "", "two words", "雪", "--"),
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            result.stdout,
            b'["plain", "", "two words", "\xe9\x9b\xaa", "--"]\n'
            b'["plain", "", "two words", "\xe9\x9b\xaa", "--", "changed"]\n',
        )
        self.assertEqual(result.stderr, b"")

    def test_text_tools_example_runs_through_public_cli_with_program_arguments(self) -> None:
        result = run_lwt(
            "examples/text_tools.lwt",
            "--",
            "examples/fixtures/text_tools.txt",
            "preview",
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'2\n[12, "apple", 5]\n[7, "pear", 4]\n')
        self.assertEqual(result.stderr, b"")

    def test_read_text_utf8_bom_newline_and_empty_file_cases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases = (
                (b"", b"\n"),
                ("雪\nline".encode("utf-8"), "雪\nline\n".encode("utf-8")),
                (b"last line", b"last line\n"),
                (b"\xef\xbb\xbfbody", b"body\n"),
                (b"\xef\xbb\xbf\xef\xbb\xbfbody", b"\xef\xbb\xbfbody\n"),
                (b"a\r\nb\rc\nd\r", b"a\nb\nc\nd\n\n"),
            )
            path = root / "data.txt"
            source = 'emit read_text("data.txt");'
            for contents, expected in cases:
                path.write_bytes(contents)
                _, result = run_source(source, cwd=root)
                with self.subTest(contents=contents):
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, expected)
                    self.assertEqual(result.stderr, b"")

    def test_read_text_uses_process_cwd_not_source_directory(self) -> None:
        with tempfile.TemporaryDirectory() as working_directory, tempfile.TemporaryDirectory() as source_directory:
            Path(working_directory, "relative.txt").write_text("cwd", encoding="utf-8")
            Path(source_directory, "relative.txt").write_text("source", encoding="utf-8")
            source_path = Path(source_directory, "program.lwt")
            source_path.write_text('emit read_text("relative.txt");', encoding="utf-8")
            result = run_lwt(str(source_path), cwd=working_directory)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"cwd\n")
        self.assertEqual(result.stderr, b"")

    def test_read_text_data_failures_are_runtime_errors_but_source_failures_remain_file_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "directory").mkdir()
            (root / "invalid.txt").write_bytes(b"\xff")
            cases = (
                ('read_text("missing.txt");', "could not read text file"),
                ('read_text("directory");', "could not read text file"),
                ('read_text(input());', "could not read text file"),
                ('read_text("invalid.txt");', "text file is not valid UTF-8"),
            )
            for expression, message in cases:
                source = f"{expression}"
                self.assert_runtime_error_at(
                    source,
                    "read_text",
                    message,
                    input_bytes=b"bad\x00path\n",
                    cwd=root,
                )

        with tempfile.TemporaryDirectory() as directory:
            missing_source = Path(directory, "missing.lwt")
            result = run_lwt(str(missing_source))
        self.assertEqual(result.returncode, 4)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, b"lwt: FileError: cannot read source file\n")
        self.assertNotIn(b"Traceback", result.stderr)

    def test_len_counts_unicode_codepoints_and_array_elements(self) -> None:
        source = 'emit len(""); emit len("A😀é"); emit len([]); emit len([null, 1, "x"]);'
        _, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"0\n4\n0\n3\n")
        self.assertEqual(result.stderr, b"")

    def test_len_rejects_non_string_non_array_values_at_call(self) -> None:
        for value in ("1", "true", "null", 'R{}'):
            source = f"record R {{}}; emit len({value});"
            self.assert_runtime_error_at(source, "len", "len expects a string or array")

    def test_split_preserves_empty_fields_and_uses_literal_nonoverlapping_matches(self) -> None:
        source = (
            'emit split("", ","); emit split("abc", "x"); '
            'emit split(",a,,b,", ","); emit split("aaa", "aa"); '
            'emit split("a--b----c", "--"); '
            'let fields = split("x,y", ","); '
            'each (field in fields) { emit len(field); } emit fields[1];'
        )
        _, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            result.stdout,
            b'[""]\n["abc"]\n["", "a", "", "b", ""]\n["", "a"]\n'
            b'["a", "b", "", "c"]\n1\n1\ny\n',
        )
        self.assertEqual(result.stderr, b"")

    def test_split_rejects_empty_separator_and_wrong_types_at_call(self) -> None:
        self.assert_runtime_error_at(
            'split("x", "");', "split", "split separator must not be empty"
        )
        self.assert_runtime_error_at(
            'split("x", 1);', "split", "split expects two strings"
        )

    def test_trim_removes_exact_ascii_whitespace_and_preserves_other_unicode_space(self) -> None:
        source = 'emit trim(input() + "\\n"); emit trim(input()); emit trim(input());'
        _, result = run_source(
            source,
            input_bytes=(
                b" \t\r\v\fco re \t\r\v\f\n"
                b"\xc2\xa0wide\xe3\x80\x80\n"
                b" \t\r\v\f\n"
            ),
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"co re\n\xc2\xa0wide\xe3\x80\x80\n\n")
        self.assertEqual(result.stderr, b"")

    def test_trim_rejects_non_string_values(self) -> None:
        self.assert_runtime_error_at("trim(1);", "trim", "trim expects a string")

    def test_to_int_accepts_strict_ascii_decimal_and_arbitrary_precision(self) -> None:
        digits = "9" * 6000
        source = (
            'emit to_int("42"); emit to_int("-42"); emit to_int("00042"); '
            'emit to_int("-000"); '
            f'emit len(str(to_int("{digits}"))); emit str(to_int("-{digits}"));'
        )
        _, result = run_source(source)
        expected = f"42\n-42\n42\n0\n6000\n-{digits}\n".encode("ascii")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, expected)
        self.assertEqual(result.stderr, b"")

    def test_to_int_rejects_noncanonical_or_non_ascii_decimal_text(self) -> None:
        cases = (
            'to_int("");',
            'to_int("-");',
            'to_int("+1");',
            'to_int(" 1");',
            'to_int("1 ");',
            'to_int("1 2");',
            'to_int("1.0");',
            'to_int("1_0");',
            'to_int("١");',
        )
        for source in cases:
            with self.subTest(source=source):
                self.assert_runtime_error_at(
                    source, "to_int", "to_int expects text matching -?[0-9]+"
                )
        self.assert_runtime_error_at("to_int(true);", "to_int", "to_int expects a string")

    def test_str_matches_emit_for_scalars_composites_escaping_and_cycles(self) -> None:
        source = (
            r'let escaped = ["quote: \" slash: \\ line:\n tab:\t"]; '
            'emit str("plain"); emit str(42); emit str(true); emit str(null); '
            'emit str(escaped); emit escaped; '
            'let child = [1]; emit str([child, child]); '
            'let cycle = []; push(cycle, cycle); emit str(cycle); '
            'let left = []; let right = []; push(left, right); push(right, left); '
            'emit str(left); '
            'record Node { next }; let node = Node{next: null}; '
            'node.next = node; emit str(node);'
        )
        _, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        lines = result.stdout.splitlines()
        self.assertEqual(lines[:4], [b"plain", b"42", b"true", b"null"])
        self.assertEqual(lines[4], lines[5])
        self.assertEqual(
            lines[6:],
            [b"[[1], [1]]", b"[<cycle>]", b"[[<cycle>]]", b"Node{next: <cycle>}"],
        )
        self.assertEqual(result.stderr, b"")

    def test_str_handles_large_integer_and_returns_ordinary_composable_string(self) -> None:
        digits = "8" * 6000
        source = (
            f'let rendered = str(to_int("{digits}")); '
            'emit len(rendered); emit rendered == rendered; emit "value=" + str(12);'
        )
        _, result = run_source(source)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, f"6000\ntrue\nvalue=12\n".encode("ascii"))
        self.assertEqual(result.stderr, b"")

    def test_str_control_escaping_matches_emit_for_all_ascii_control_bytes(self) -> None:
        source = 'let controls = [input()]; emit str(controls); emit controls;'
        _, result = run_source(source, input_bytes=b"\x00\r\x1f\x7f\xe9\x9b\xaa\n")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            result.stdout,
            b'["\\u0000\\r\\u001F\\u007F\xe9\x9b\xaa"]\n'
            b'["\\u0000\\r\\u001F\\u007F\xe9\x9b\xaa"]\n',
        )
        self.assertEqual(result.stderr, b"")

    def test_fail_preserves_prior_output_escapes_diagnostic_and_has_no_traceback(self) -> None:
        source = 'emit "before"; fail(input() + "\\nlast");'
        self.assert_runtime_error_at(
            source,
            "fail",
            "first\\rinside\\nlast",
            stdout=b"before\n",
            input_bytes=b"first\rinside\n",
        )
        self.assert_runtime_error_at(
            "fail(1);", "fail", "fail expects a string message"
        )
        self.assert_runtime_error_at("fail(\"\");", "fail", "")

    def test_all_builtin_arity_and_type_failures_point_to_call_name(self) -> None:
        cases = (
            ('args(1);', "args", "args expects 0 arguments"),
            ('read_text();', "read_text", "read_text expects 1 argument"),
            ('read_text(1);', "read_text", "read_text expects a string path"),
            ('len();', "len", "len expects 1 argument"),
            ('split("x");', "split", "split expects 2 arguments"),
            ('split(1, "x");', "split", "split expects two strings"),
            ('trim(1);', "trim", "trim expects a string"),
            ('to_int(1);', "to_int", "to_int expects a string"),
            ('str();', "str", "str expects 1 argument"),
            ('fail();', "fail", "fail expects 1 argument"),
            ('fail(1);', "fail", "fail expects a string message"),
        )
        for source, marker, message in cases:
            with self.subTest(source=source):
                self.assert_runtime_error_at(source, marker, message)

    def test_all_call_arguments_run_left_to_right_before_builtin_arity_or_type_checks(self) -> None:
        source = (
            'fn mark(value) { emit value; return value; } '
            'len(mark(1), mark(2));'
        )
        self.assert_runtime_error_at(
            source,
            "len",
            "len expects 1 argument",
            stdout=b"1\n2\n",
        )
        source = 'fn mark(value) { emit value; return value; } len(mark(1));'
        self.assert_runtime_error_at(
            source,
            "len",
            "len expects a string or array",
            stdout=b"1\n",
        )

    def test_argument_failure_stops_later_arguments_and_builtin_operation(self) -> None:
        source = (
            'fn broken() { emit "first"; return 1 / 0; } '
            'fn later() { emit "later"; return "text"; } '
            'len(broken(), later());'
        )
        self.assert_runtime_error_at(
            source,
            "/",
            "division by zero",
            stdout=b"first\n",
        )


if __name__ == "__main__":
    unittest.main()
