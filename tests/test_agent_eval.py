"""S47: the Agent blind-eval grader must honour every tasks.json field.

These tests cover the fields the S47 task book calls out explicitly:
``stdin``, ``args`` (including the fixture convention), ``check_required``,
``deterministic_runs`` and ``forbidden_constructs`` -- plus the pass@1
denominator (passed / all tasks) and the NOT_RUN / NOT_SUBMITTED honesty rules.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools import run_agent_eval as rae

ECHO_PROGRAM = "let line = input();\nemit line;\n"
READ_PROGRAM = "let path = args()[0];\nlet text = read_text(path);\nemit text;\n"
PLAIN_PROGRAM = 'emit "ok";\n'


def _task(task_id: str, **overrides: object) -> dict:
    task = {
        "id": task_id,
        "title": task_id,
        "prompt": "test task",
        "allowed_docs": [],
        "stdin": "",
        "args": [],
        "expected_stdout": "",
        "expected_exit_code": 0,
        "check_required": True,
        "deterministic_runs": 1,
        "forbidden_constructs": [],
    }
    task.update(overrides)
    return task


class GraderFieldTests(unittest.TestCase):
    def _grade(self, task: dict, files: dict[str, str], submissions: Path) -> dict:
        target = submissions / task["id"]
        target.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            (target / name).write_text(text, encoding="utf-8", newline="\n")
        with mock.patch.object(rae, "SUBMISSIONS", submissions):
            return rae.grade_task(task)

    def test_stdin_and_deterministic_runs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt-s47-eval-") as folder:
            submissions = Path(folder)
            task = _task(
                "echo", stdin="hi\n", expected_stdout="hi\n",
                deterministic_runs=3,
            )
            result = self._grade(task, {"program.lwt": ECHO_PROGRAM}, submissions)
            self.assertEqual(result["status"], "PASS", result)
            self.assertEqual(result["checks"]["deterministic_bytes"]["runs"], 3)
            self.assertTrue(result["checks"]["stdout_matches"]["pass"])

    def test_check_required_false_skips_static_check(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt-s47-eval-") as folder:
            submissions = Path(folder)
            task = _task(
                "ok", expected_stdout="ok\n", check_required=False,
            )
            result = self._grade(task, {"program.lwt": PLAIN_PROGRAM}, submissions)
            self.assertEqual(result["status"], "PASS", result)
            self.assertNotIn("check_exit_zero", result["checks"])

    def test_args_fixture_is_written_and_passed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt-s47-eval-") as folder:
            submissions = Path(folder)
            task = _task(
                "fixture", args=["fixture"], fixture_content="abc\n",
                expected_stdout="abc\n\n",
            )
            result = self._grade(task, {"program.lwt": READ_PROGRAM}, submissions)
            self.assertEqual(result["status"], "PASS", result)
            self.assertTrue(result["checks"]["stdout_matches"]["pass"])

    def test_forbidden_construct_in_module_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt-s47-eval-") as folder:
            submissions = Path(folder)
            task = _task(
                "mix", expected_stdout="ok\n",
                forbidden_constructs=["class "],
            )
            result = self._grade(
                task,
                {"program.lwt": PLAIN_PROGRAM, "lib.lwt": "# class smuggled\n"},
                submissions,
            )
            self.assertEqual(result["status"], "FAIL")
            hits = result["checks"]["no_forbidden_constructs"]["hits"]
            self.assertTrue(any(hit.startswith("lib.lwt:") for hit in hits), hits)

    def test_wrong_stdout_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt-s47-eval-") as folder:
            submissions = Path(folder)
            task = _task("wrong", expected_stdout="nope\n")
            result = self._grade(task, {"program.lwt": PLAIN_PROGRAM}, submissions)
            self.assertEqual(result["status"], "FAIL")
            self.assertFalse(result["checks"]["stdout_matches"]["pass"])


class AggregateTests(unittest.TestCase):
    def test_not_submitted_is_not_run(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt-s47-eval-") as folder:
            tasks_path = Path(folder) / "tasks.json"
            tasks_path.write_text(
                json.dumps({"tasks": [_task("a"), _task("b")]}),
                encoding="utf-8", newline="\n",
            )
            with mock.patch.object(rae, "TASKS_PATH", tasks_path), \
                    mock.patch.object(rae, "SUBMISSIONS", Path(folder) / "subs"):
                doc = rae.grade_all()
            self.assertEqual(doc["overall"], "NOT_RUN")
            self.assertIsNone(doc["pass_at_1"])
            self.assertEqual(doc["submitted"], 0)

    def test_pass_at_1_divides_by_all_tasks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt-s47-eval-") as folder:
            root = Path(folder)
            tasks_path = root / "tasks.json"
            tasks_path.write_text(
                json.dumps({
                    "tasks": [
                        _task("a", expected_stdout="ok\n"),
                        _task("b", expected_stdout="ok\n"),
                    ]
                }),
                encoding="utf-8", newline="\n",
            )
            submissions = root / "subs"
            (submissions / "a").mkdir(parents=True)
            (submissions / "a" / "program.lwt").write_text(
                PLAIN_PROGRAM, encoding="utf-8", newline="\n"
            )
            with mock.patch.object(rae, "TASKS_PATH", tasks_path), \
                    mock.patch.object(rae, "SUBMISSIONS", submissions):
                doc = rae.grade_all()
            self.assertEqual(doc["overall"], "PARTIAL")
            self.assertEqual(doc["submitted"], 1)
            self.assertEqual(doc["passed"], 1)
            self.assertAlmostEqual(doc["pass_at_1"], 0.5)
            self.assertAlmostEqual(doc["pass_rate_over_submitted"], 1.0)


if __name__ == "__main__":
    unittest.main()
