from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lwt.cli import parse_cli_args
from lwt.errors import LwtError, SourceLocation, format_diagnostic


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def run_lwt(*arguments: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "lwt", *arguments],
        cwd=REPOSITORY_ROOT,
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

    def test_valid_nonempty_source_reports_temporary_incomplete_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nonempty-no-extension"
            path.write_text("let value = 123;", encoding="utf-8")
            result = run_lwt(str(path), "--", "first", "--", "雪")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{path}:1:1: Incomplete: parser and runtime are not implemented yet\n",
        )
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
