"""Headless game logic and public-CLI integration tests for Log Detective."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

from app.log_detective_core import (
    DEFAULT_LOG,
    PROJECT_ROOT,
    QUESTIONS,
    AnalysisResult,
    AnalyzerError,
    GameSession,
    analyze_question,
    build_lwt_command,
    full_report,
    parse_matched_records,
    run_lwt_report,
)


class ReportParserTests(unittest.TestCase):
    def test_valid_report_field(self) -> None:
        self.assertEqual(parse_matched_records("LWT log report\nMatched records: 12\n"), 12)

    def test_missing_duplicate_negative_and_nonnumeric_fields(self) -> None:
        for report in (
            "LWT log report\n",
            "Matched records: 1\nMatched records: 2\n",
            "Matched records: -1\n",
            "Matched records: many\n",
            "Matched records:  1\n",
        ):
            with self.subTest(report=report), self.assertRaises(AnalyzerError):
                parse_matched_records(report)

    def test_decimal_conversion_limit_is_reported_cleanly_when_enabled(self) -> None:
        get_limit = getattr(sys, "get_int_max_str_digits", None)
        if get_limit is None or get_limit() == 0:
            self.skipTest("this Python does not impose a decimal integer conversion limit")
        report = f"Matched records: {'9' * (get_limit() + 1)}\n"
        with self.assertRaisesRegex(AnalyzerError, "整数转换限制"):
            parse_matched_records(report)


class GameSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.game = GameSession()

    def test_correct_wrong_next_end_and_restart(self) -> None:
        self.game.start()
        self.assertEqual(self.game.round_number, 1)
        self.assertTrue(self.game.submit(2, 2))
        self.assertEqual(self.game.score, 1)
        self.assertTrue(self.game.advance())
        self.assertEqual(self.game.round_number, 2)
        self.assertFalse(self.game.submit(99, 3))
        self.assertEqual(self.game.score, 1)
        for _ in range(self.game.question_count - 2):
            self.game.advance()
            self.game.submit(0, 0)
        self.assertFalse(self.game.advance())
        self.assertTrue(self.game.finished)
        self.game.start()
        self.assertEqual((self.game.round_number, self.game.score), (1, 0))
        self.assertFalse(self.game.answered)
        self.assertFalse(self.game.finished)

    def test_cannot_advance_before_answer_or_submit_twice(self) -> None:
        self.game.start()
        with self.assertRaises(RuntimeError):
            self.game.advance()
        self.game.submit(0, 0)
        with self.assertRaises(RuntimeError):
            self.game.submit(0, 0)


class CliBoundaryTests(unittest.TestCase):
    def test_argv_uses_public_cli_and_keeps_unicode_space_path_one_argument(self) -> None:
        path = Path("临时 日志/input one.log")
        command = build_lwt_command(path, ("--keyword", "请求 有效"))
        self.assertEqual(command[1:3], ["-m", "lwt"])
        self.assertEqual(command[4], "--")
        self.assertEqual(command[5], str(path.resolve()))
        self.assertEqual(command[6:], ["--keyword", "请求 有效"])

    def test_subprocess_configuration_is_safe_and_utf8(self) -> None:
        fake = Mock(return_value=subprocess.CompletedProcess([], 0, "Matched records: 4\n", ""))
        result = run_lwt_report(DEFAULT_LOG, ("--level", "WARN"), runner=fake)
        self.assertIn("Matched records: 4", result)
        argv = fake.call_args.args[0]
        options = fake.call_args.kwargs
        self.assertIsInstance(argv, list)
        self.assertEqual(argv[:3], [argv[0], "-m", "lwt"])
        self.assertEqual(argv[-2:], ["--level", "WARN"])
        self.assertEqual(options["cwd"], PROJECT_ROOT)
        self.assertFalse(options["shell"])
        self.assertEqual(options["encoding"], "utf-8")
        self.assertTrue(options["capture_output"])
        self.assertGreater(options["timeout"], 0)

    def test_nonzero_timeout_and_malformed_report_are_user_facing(self) -> None:
        nonzero = Mock(return_value=subprocess.CompletedProcess([], 3, "", "input.log:1: RuntimeError: bad log"))
        with self.assertRaisesRegex(AnalyzerError, "bad log"):
            run_lwt_report(DEFAULT_LOG, runner=nonzero)

        timed_out = Mock(side_effect=subprocess.TimeoutExpired("lwt", 0.01))
        with self.assertRaisesRegex(AnalyzerError, "超过"):
            run_lwt_report(DEFAULT_LOG, timeout=0.01, runner=timed_out)

        bad_argv = Mock(side_effect=ValueError("embedded null byte"))
        with self.assertRaisesRegex(AnalyzerError, "调用参数无效"):
            run_lwt_report(DEFAULT_LOG, runner=bad_argv)

        malformed = Mock(return_value=subprocess.CompletedProcess([], 0, "report without count\n", ""))
        with self.assertRaisesRegex(AnalyzerError, "缺少 Matched records"):
            analyze_question(DEFAULT_LOG, QUESTIONS[0], runner=malformed)


class PublicCliIntegrationTests(unittest.TestCase):
    def test_default_sample_report_comes_from_real_lwt_cli(self) -> None:
        report = full_report(DEFAULT_LOG)
        self.assertTrue(report.startswith("LWT log report\n"))
        self.assertIn("Matched records: 6\n", report)
        self.assertIn("Malformed lines: 1\n", report)

    def test_question_and_and_filter_answers_come_from_real_lwt_cli(self) -> None:
        retry = analyze_question(DEFAULT_LOG, QUESTIONS[2])
        combined = analyze_question(DEFAULT_LOG, QUESTIONS[4])
        self.assertEqual(retry.matched_records, 1)
        self.assertEqual(combined.matched_records, 1)
        self.assertIn("Level counts:\nWARN|1\n", combined.report)
        self.assertIn("WARN|cache|retry scheduled", combined.report)

    def test_selected_unicode_and_space_path_uses_public_cli(self) -> None:
        with tempfile.TemporaryDirectory(prefix="LWT 日志 空格 ") as directory:
            path = Path(directory) / "用户 请求 日志.log"
            path.write_text(
                "2026-10-07T12:00:00Z|INFO|应用|用户请求已接收\n",
                encoding="utf-8",
            )
            result = analyze_question(path, QUESTIONS[0])
        self.assertEqual(result.matched_records, 1)
        self.assertIn("Matched records: 1\n", result.report)
        self.assertIn("INFO|应用|用户请求已接收", result.report)


if __name__ == "__main__":
    unittest.main()
