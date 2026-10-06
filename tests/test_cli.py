from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lwt.cli import parse_cli_args
from lwt.errors import LwtError, SourceLocation, format_diagnostic


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def run_lwt(
    *arguments: str, input_bytes: bytes = b""
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "lwt", *arguments],
        cwd=REPOSITORY_ROOT,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


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

    def test_unimplemented_valid_syntax_is_rejected_before_any_output(self) -> None:
        cases = (
            ('emit "hidden"; when (false) { emit "also hidden"; }', "when"),
            ('emit "hidden"; len("value");', "len"),
            ('emit "hidden"; emit [1, 2];', "["),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "incomplete.lwt"
            for source, marker in cases:
                path.write_text(source, encoding="utf-8")
                with self.subTest(source=source):
                    result = run_lwt(str(path))
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, b"")
                    self.assertEqual(
                        result.stderr.decode("utf-8"),
                        f"{path}:1:{source.index(marker) + 1}: Incomplete: "
                        "runtime support for this syntax is not implemented yet\n",
                    )
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


if __name__ == "__main__":
    unittest.main()
