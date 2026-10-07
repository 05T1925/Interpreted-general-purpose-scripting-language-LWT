"""Public-CLI integration tests for the LWT log-report application."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "app/log_report.lwt"
SAMPLE = ROOT / "app" / "fixtures" / "sample.log"
EXPECTED = ROOT / "app" / "fixtures" / "sample.expected.txt"


def report(
    total: int,
    valid: int,
    malformed: int,
    matched: int,
    *,
    levels: tuple[str, ...] = (),
    modules: tuple[str, ...] = (),
    examples: tuple[str, ...] = (),
) -> str:
    """Render hand-specified expectations in the frozen report layout."""
    lines = [
        "LWT log report",
        f"Total lines: {total}",
        f"Valid records: {valid}",
        f"Malformed lines: {malformed}",
        f"Matched records: {matched}",
        "Level counts:",
        *levels,
        "Top modules:",
        *modules,
        "Matching examples (first 3):",
        *examples,
    ]
    return "\n".join(lines) + "\n"


class LogReportCliTests(unittest.TestCase):
    def invoke(self, *application_args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "lwt",
                SOURCE,
                "--",
                *application_args,
            ],
            cwd=ROOT,
            capture_output=True,
            encoding="utf-8",
            errors="strict",
            text=True,
            timeout=15,
            shell=False,
            check=False,
        )

    def invoke_bytes(
        self, content: bytes, *application_args: str
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory(prefix="lwt-log-app-") as directory:
            input_path = Path(directory) / "input.log"
            input_path.write_bytes(content)
            return self.invoke(str(input_path), *application_args)

    def assert_success(self, result: subprocess.CompletedProcess[str], expected: str) -> None:
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout, expected)

    def assert_usage_error(self, *application_args: str) -> None:
        result = self.invoke(*application_args)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(result.stderr.count("\n"), 1, result.stderr)
        self.assertTrue(result.stderr.startswith(f"{SOURCE}:"), result.stderr)
        self.assertIn(": RuntimeError: usage: ", result.stderr)

    def assert_file_error(self, input_path: Path) -> None:
        result = self.invoke(str(input_path))
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(result.stderr.count("\n"), 1, result.stderr)
        self.assertTrue(result.stderr.startswith(f"{SOURCE}:"), result.stderr)
        self.assertIn(": RuntimeError: ", result.stderr)

    def test_sample_default_report_matches_committed_expected_file(self) -> None:
        result = self.invoke(str(SAMPLE.relative_to(ROOT)))
        self.assert_success(result, EXPECTED.read_text(encoding="utf-8"))

    def test_sample_combined_filter_and_top_limit(self) -> None:
        result = self.invoke(
            str(SAMPLE.relative_to(ROOT)),
            "--level",
            "WARN",
            "--keyword",
            "retry",
            "--top",
            "2",
        )
        self.assert_success(
            result,
            report(
                7,
                6,
                1,
                1,
                levels=("WARN|1",),
                modules=("cache|1",),
                examples=("2026-10-07T10:00:03Z|WARN|cache|retry scheduled",),
            ),
        )

    def test_level_filter_is_exact_and_case_sensitive(self) -> None:
        data = (
            b"t1|WARN|cache|retry\n"
            b"t2|warn|cache|retry\n"
            b"t3|WARNING|cache|retry\n"
        )
        upper = self.invoke_bytes(data, "--level", "WARN")
        self.assert_success(
            upper,
            report(
                3,
                3,
                0,
                1,
                levels=("WARN|1",),
                modules=("cache|1",),
                examples=("t1|WARN|cache|retry",),
            ),
        )
        lower = self.invoke_bytes(data, "--level", "warn")
        self.assert_success(
            lower,
            report(
                3,
                3,
                0,
                1,
                levels=("warn|1",),
                modules=("cache|1",),
                examples=("t2|warn|cache|retry",),
            ),
        )

    def test_keyword_checks_only_message_and_supports_unicode(self) -> None:
        data = (
            "needle|INFO|plain|没有关键字\n"
            "t2|INFO|报警模块|消息含报警完成\n"
            "t3|INFO|plain|ALERT now\n"
        ).encode("utf-8")
        result = self.invoke_bytes(data, "--keyword", "报警")
        self.assert_success(
            result,
            report(
                3,
                3,
                0,
                1,
                levels=("INFO|1",),
                modules=("报警模块|1",),
                examples=("t2|INFO|报警模块|消息含报警完成",),
            ),
        )

    def test_keyword_filter_is_case_sensitive(self) -> None:
        result = self.invoke_bytes(
            b"t1|INFO|api|Retry scheduled\nt2|INFO|api|retry scheduled\n",
            "--keyword",
            "retry",
        )
        self.assert_success(
            result,
            report(
                2,
                2,
                0,
                1,
                levels=("INFO|1",),
                modules=("api|1",),
                examples=("t2|INFO|api|retry scheduled",),
            ),
        )

    def test_level_and_keyword_are_combined_with_and(self) -> None:
        result = self.invoke_bytes(
            b"t1|WARN|api|retry\nt2|INFO|api|retry\nt3|WARN|db|done\n",
            "--keyword",
            "retry",
            "--level",
            "WARN",
        )
        self.assert_success(
            result,
            report(
                3,
                3,
                0,
                1,
                levels=("WARN|1",),
                modules=("api|1",),
                examples=("t1|WARN|api|retry",),
            ),
        )

    def test_default_top_is_five_and_ties_sort_by_module_name(self) -> None:
        result = self.invoke(str(SAMPLE.relative_to(ROOT)))
        self.assert_success(result, EXPECTED.read_text(encoding="utf-8"))

    def test_top_one_and_zero(self) -> None:
        one = self.invoke(str(SAMPLE.relative_to(ROOT)), "--top", "1")
        self.assert_success(
            one,
            report(
                7,
                6,
                1,
                6,
                levels=("ERROR|2", "INFO|2", "WARN|2"),
                modules=("cache|2",),
                examples=(
                    "2026-10-07T10:00:00Z|INFO|auth|login accepted",
                    "2026-10-07T10:00:01Z|WARN|cache|eviction started",
                    "2026-10-07T10:00:02Z|ERROR|db|connection lost",
                ),
            ),
        )
        zero = self.invoke(str(SAMPLE.relative_to(ROOT)), "--top", "0")
        self.assert_success(
            zero,
            report(
                7,
                6,
                1,
                6,
                levels=("ERROR|2", "INFO|2", "WARN|2"),
                examples=(
                    "2026-10-07T10:00:00Z|INFO|auth|login accepted",
                    "2026-10-07T10:00:01Z|WARN|cache|eviction started",
                    "2026-10-07T10:00:02Z|ERROR|db|connection lost",
                ),
            ),
        )

    def test_top_accepts_large_decimal_without_host_conversion_limit(self) -> None:
        result = self.invoke(str(SAMPLE.relative_to(ROOT)), "--top", "9" * 6000)
        self.assert_success(result, EXPECTED.read_text(encoding="utf-8"))

    def test_level_order_is_ascending(self) -> None:
        result = self.invoke_bytes(b"t|Z|m|z\nt|A|m|a\nt|M|m|m\n")
        self.assert_success(
            result,
            report(
                3,
                3,
                0,
                3,
                levels=("A|1", "M|1", "Z|1"),
                modules=("m|3",),
                examples=("t|Z|m|z", "t|A|m|a", "t|M|m|m"),
            ),
        )

    def test_zero_matches_keeps_every_section_heading(self) -> None:
        result = self.invoke(str(SAMPLE.relative_to(ROOT)), "--level", "TRACE")
        self.assert_success(result, report(7, 6, 1, 0))

    def test_empty_file_has_zero_logical_lines(self) -> None:
        self.assert_success(self.invoke_bytes(b""), report(0, 0, 0, 0))

    def test_only_newline_is_one_malformed_logical_line(self) -> None:
        self.assert_success(self.invoke_bytes(b"\n"), report(1, 0, 1, 0))

    def test_trailing_lf_does_not_add_a_logical_line(self) -> None:
        self.assert_success(
            self.invoke_bytes(b"t|INFO|m|one\n"),
            report(1, 1, 0, 1, levels=("INFO|1",), modules=("m|1",), examples=("t|INFO|m|one",)),
        )

    def test_missing_trailing_lf_keeps_last_record(self) -> None:
        self.assert_success(
            self.invoke_bytes(b"t|INFO|m|one"),
            report(1, 1, 0, 1, levels=("INFO|1",), modules=("m|1",), examples=("t|INFO|m|one",)),
        )

    def test_consecutive_trailing_lfs_leave_one_blank_bad_row(self) -> None:
        self.assert_success(
            self.invoke_bytes(b"t|INFO|m|one\n\n"),
            report(2, 1, 1, 1, levels=("INFO|1",), modules=("m|1",), examples=("t|INFO|m|one",)),
        )

    def test_internal_blank_row_counts_but_processing_continues(self) -> None:
        self.assert_success(
            self.invoke_bytes(b"t1|INFO|m|one\n\nt2|WARN|n|two\n"),
            report(
                3,
                2,
                1,
                2,
                levels=("INFO|1", "WARN|1"),
                modules=("m|1", "n|1"),
                examples=("t1|INFO|m|one", "t2|WARN|n|two"),
            ),
        )

    def test_malformed_fixture_counts_field_errors_and_continues(self) -> None:
        result = self.invoke("app/fixtures/malformed.log")
        self.assert_success(
            result,
            report(
                5,
                2,
                3,
                2,
                levels=("|1", "INFO|1"),
                modules=("|1", "good|1"),
                examples=("|||", "2026-10-07T10:00:00Z|INFO|good|continue after malformed rows"),
            ),
        )

    def test_pipe_in_message_makes_the_row_malformed(self) -> None:
        self.assert_success(
            self.invoke_bytes(b"t|INFO|m|message|with-pipe\nt|WARN|n|okay\n"),
            report(
                2,
                1,
                1,
                1,
                levels=("WARN|1",),
                modules=("n|1",),
                examples=("t|WARN|n|okay",),
            ),
        )

    def test_empty_fields_are_valid_when_there_are_four(self) -> None:
        self.assert_success(
            self.invoke_bytes(b"|||"),
            report(1, 1, 0, 1, levels=("|1",), modules=("|1",), examples=("|||",)),
        )

    def test_cli_argument_errors_are_single_line_usage_diagnostics(self) -> None:
        invalid_arguments = (
            (),
            ("",),
            ("input.log", "--unknown"),
            ("input.log", "extra"),
            ("input.log", "--level"),
            ("input.log", "--keyword"),
            ("input.log", "--top"),
            ("input.log", "--level", "INFO", "--level", "WARN"),
            ("input.log", "--keyword", "x", "--keyword", "y"),
            ("input.log", "--top", "1", "--top", "2"),
            ("input.log", "--keyword", ""),
            ("input.log", "--top", "1x"),
            ("input.log", "--top", "-1"),
            ("input.log", "--top", "+1"),
            ("input.log", "--top", " 1"),
        )
        for arguments in invalid_arguments:
            with self.subTest(arguments=arguments):
                self.assert_usage_error(*arguments)

    def test_option_value_that_looks_like_option_is_reported_missing(self) -> None:
        self.assert_usage_error("input.log", "--level", "--keyword", "x")

    def test_missing_file_has_runtime_error_without_traceback(self) -> None:
        missing = ROOT / "app" / "fixtures" / "does-not-exist.log"
        self.assert_file_error(missing)

    def test_directory_input_has_runtime_error_without_traceback(self) -> None:
        self.assert_file_error(ROOT / "app" / "fixtures")

    def test_invalid_utf8_input_has_runtime_error_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt-log-app-") as directory:
            invalid = Path(directory) / "invalid.log"
            invalid.write_bytes(b"\xff\xfe")
            self.assert_file_error(invalid)


if __name__ == "__main__":
    unittest.main()
