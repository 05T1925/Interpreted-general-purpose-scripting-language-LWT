"""Headless and public-CLI tests for the fixed LWT language lab."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

import app.language_lab_core as lab


PREDICTION_CONTRACTS = {
    "control-flow": ("0 → -1 → 2 → -3", "0\n-1\n2\n-3\n", 0),
    "functions": ("120", "120\n", 0),
    "collections": (
        "访问 draft、review；不访问 replacement 或 late",
        "draft\nreview\n[\"draft\", \"review\"]\n"
        "[Task{name: \"draft\", done: true}, Task{name: \"replacement\", done: false}, "
        "Task{name: \"late\", done: false}]\n",
        0,
    ),
    "text-cli": ("2 个", '2\n[12, "apple", 5]\n[7, "pear", 4]\n', 0),
    "stdin": ("不会保留 LF", "Enter one line:\nLWT 输入演示\n", 0),
    "runtime-error": ("exit 3，RuntimeError，2:8", "", 3),
}


class LanguageLabManifestTests(unittest.TestCase):
    def test_allowlist_has_unique_topics_and_complete_read_only_sources(self) -> None:
        self.assertEqual(len(lab.EXAMPLES), 6)
        self.assertEqual(len({example.id for example in lab.EXAMPLES}), 6)
        expected_topics = {
            "control-flow",
            "functions",
            "collections",
            "text-cli",
            "stdin",
            "runtime-error",
        }
        self.assertEqual({example.id for example in lab.EXAMPLES}, expected_topics)
        for example in lab.EXAMPLES:
            with self.subTest(example=example.id):
                loaded_example, source = lab.load_source(example.id)
                self.assertEqual(loaded_example, example)
                self.assertTrue(source)
                self.assertEqual(source, (lab.PROJECT_ROOT / example.source_path).read_text(encoding="utf-8"))

    def test_prediction_questions_match_the_fixed_cli_contracts(self) -> None:
        self.assertEqual({example.id for example in lab.EXAMPLES}, set(PREDICTION_CONTRACTS))
        for example in lab.EXAMPLES:
            with self.subTest(example=example.id):
                question = example.prediction
                self.assertTrue(question.prompt.strip())
                self.assertGreaterEqual(len(question.options), 2)
                self.assertEqual(len(question.options), len(set(question.options)))
                self.assertIn(question.correct_option, question.options)
                self.assertTrue(question.explanation.strip())
                self.assertEqual(
                    (question.correct_option, example.expected_stdout, example.expected_exit_code),
                    PREDICTION_CONTRACTS[example.id],
                )

    def test_arbitrary_paths_are_not_an_execution_interface(self) -> None:
        with self.assertRaisesRegex(lab.LanguageLabError, "未找到"):
            lab.load_source("C:/Users/anyone/program.lwt")

    def test_missing_allowlisted_source_has_a_readable_error(self) -> None:
        original = lab.get_example("control-flow")
        missing = replace(original, source_path="examples/language_lab/missing.lwt")
        with patch.dict(lab._EXAMPLES_BY_ID, {"control-flow": missing}):
            with self.assertRaisesRegex(lab.LanguageLabError, "无法读取示例源码"):
                lab.run_example("control-flow")


class LanguageLabCliIntegrationTests(unittest.TestCase):
    def test_every_example_runs_through_the_public_cli_and_matches_its_contract(self) -> None:
        for example in lab.EXAMPLES:
            with self.subTest(example=example.id):
                result = lab.run_example(example.id)
                self.assertEqual(result.returncode, example.expected_exit_code)
                self.assertEqual(result.stdout, example.expected_stdout)
                self.assertTrue(result.expectation_met)
                self.assertIn("-m", result.command)
                self.assertIn("lwt", result.command)
                self.assertEqual(result.working_directory, lab.PROJECT_ROOT)
                self.assertEqual(result.source_text, (lab.PROJECT_ROOT / example.source_path).read_text(encoding="utf-8"))
                if example.expected_error_category is None:
                    self.assertEqual(result.stderr, "")
                else:
                    self.assertIn(":2:8: RuntimeError:", result.stderr)
                    self.assertIn("division by zero", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)

    def test_outcome_summary_distinguishes_success_from_expected_diagnostic(self) -> None:
        successful = lab.run_example("functions")
        diagnostic = lab.run_example("runtime-error")
        self.assertEqual(
            lab.describe_outcome(successful), "成功，符合 stdout 与退出码预期"
        )
        self.assertEqual(
            lab.describe_outcome(diagnostic), "按预期报告 RuntimeError"
        )
        self.assertIn(":2:8: RuntimeError:", diagnostic.stderr)

    def test_cli_arguments_and_stdin_are_forwarded_as_declared(self) -> None:
        text_result = lab.run_example("text-cli")
        self.assertEqual(
            text_result.command[-3:],
            ("--", "examples/fixtures/text_tools.txt", "preview"),
        )
        self.assertEqual(text_result.stdin_text, "")
        stdin_result = lab.run_example("stdin")
        self.assertEqual(stdin_result.stdin_text, "LWT 输入演示\n")
        self.assertEqual(stdin_result.stdout, "Enter one line:\nLWT 输入演示\n")

    def test_subprocess_uses_argv_shell_false_utf8_cwd_and_finite_timeout(self) -> None:
        captured: dict[str, object] = {}

        def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            captured["command"] = command
            captured.update(kwargs)
            return subprocess.CompletedProcess(command, 0, "Enter one line:\nLWT 输入演示\n", "")

        result = lab.run_example("stdin", runner=runner)
        self.assertTrue(result.expectation_met)
        self.assertEqual(captured["input"], "LWT 输入演示\n")
        self.assertEqual(captured["cwd"], lab.PROJECT_ROOT)
        self.assertFalse(captured["shell"])
        self.assertEqual(captured["encoding"], "utf-8")
        self.assertEqual(captured["timeout"], lab.DEFAULT_TIMEOUT_SECONDS)

    def test_mismatched_cli_result_is_shown_as_unexpected(self) -> None:
        def runner(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(command, 0, "not the expected stdout", "")

        result = lab.run_example("control-flow", runner=runner)
        self.assertFalse(result.expectation_met)
        self.assertEqual(result.stdout, "not the expected stdout")


class LanguageLabFailureAndStateTests(unittest.TestCase):
    def test_timeout_and_process_start_failure_are_readable(self) -> None:
        with self.assertRaisesRegex(lab.LanguageLabError, "超过"):
            lab.run_example(
                "control-flow",
                runner=Mock(
                    side_effect=subprocess.TimeoutExpired(["python", "-m", "lwt"], 0.1)
                ),
            )
        with self.assertRaisesRegex(lab.LanguageLabError, "无法启动 LWT CLI"):
            lab.run_example(
                "control-flow",
                runner=Mock(side_effect=OSError("executable missing")),
            )

    def test_prediction_must_be_selected_and_submitted_before_running(self) -> None:
        session = lab.LabSession()
        session.select("control-flow")
        with self.assertRaisesRegex(lab.LanguageLabError, "提交预测"):
            session.begin()
        with self.assertRaisesRegex(lab.LanguageLabError, "选择一个预测"):
            session.submit_prediction()
        with self.assertRaisesRegex(lab.LanguageLabError, "预测选项"):
            session.choose_prediction("not an option")
        session.choose_prediction("0 → -1 → 2 → -3")
        self.assertTrue(session.submit_prediction())
        self.assertTrue(session.prediction_submitted)

    def test_prediction_feedback_is_separate_from_cli_contract_and_reset_clears_both(self) -> None:
        session = lab.LabSession()
        session.select("control-flow")
        session.choose_prediction("0 → 1 → 2 → 3")
        self.assertFalse(session.submit_prediction())
        revision = session.begin()
        result = lab.run_example("control-flow")
        self.assertTrue(session.complete(revision, result))
        self.assertFalse(session.prediction_correct)
        self.assertTrue(session.result.expectation_met)

        session.reset_lesson()
        self.assertIsNone(session.prediction_choice)
        self.assertIsNone(session.prediction_correct)
        self.assertFalse(session.prediction_submitted)
        self.assertIsNone(session.result)
        with self.assertRaisesRegex(lab.LanguageLabError, "提交预测"):
            session.begin()

    def test_failed_attempt_can_be_reset_and_retried_without_stale_result(self) -> None:
        session = lab.LabSession()
        session.select("functions")
        session.choose_prediction("120")
        session.submit_prediction()
        revision = session.begin()
        self.assertTrue(session.complete(revision, None, "simulated timeout"))
        self.assertEqual(session.error, "simulated timeout")
        session.reset_lesson()
        self.assertIsNone(session.error)
        self.assertIsNone(session.result)
        self.assertIsNone(session.prediction_choice)
        session.choose_prediction("120")
        session.submit_prediction()
        retry_revision = session.begin()
        result = lab.run_example("functions")
        self.assertTrue(session.complete(retry_revision, result))
        self.assertTrue(session.result.expectation_met)

    def test_switching_example_discards_old_result_and_allows_retry(self) -> None:
        session = lab.LabSession()
        session.select("control-flow")
        session.choose_prediction("0 → -1 → 2 → -3")
        session.submit_prediction()
        revision = session.begin()
        with self.assertRaisesRegex(lab.LanguageLabError, "正在运行"):
            session.begin()
        session.select("functions")
        self.assertFalse(session.complete(revision, None, "late result"))
        self.assertEqual(session.selected_id, "functions")
        self.assertIsNone(session.pending)
        self.assertIsNone(session.prediction_choice)
        session.choose_prediction("120")
        session.submit_prediction()
        next_revision = session.begin()
        result = lab.run_example("functions")
        self.assertTrue(session.complete(next_revision, result))
        self.assertEqual(session.result, result)

    def test_close_invalidates_pending_result_and_prevents_reuse(self) -> None:
        session = lab.LabSession()
        session.select("control-flow")
        session.choose_prediction("0 → -1 → 2 → -3")
        session.submit_prediction()
        revision = session.begin()
        session.close()
        self.assertFalse(session.complete(revision, lab.run_example("control-flow")))
        self.assertIsNone(session.pending)
        with self.assertRaisesRegex(lab.LanguageLabError, "关闭"):
            session.begin()


if __name__ == "__main__":
    unittest.main()
