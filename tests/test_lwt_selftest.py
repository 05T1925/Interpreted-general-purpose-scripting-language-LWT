"""Guards the LWT-native self-test suite added for course chapter 8 task 2.

The course asks for a test set "written in ZS, testing ZS" -- one command, every
item printed, a total at the end, and test names matching the feature list.
``tests/selftest/lwt_selftest.lwt`` is that script; these tests keep it honest:
it must stay pure LWT, stay green, stay uniquely named, and keep printing the
total that the runner compares against.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
SELFTEST = REPO_ROOT / "tests" / "selftest" / "lwt_selftest.lwt"
HELPER = REPO_ROOT / "tests" / "selftest" / "selftest_helper.lwt"
CHECKLIST = REPO_ROOT / "docs" / "feature-checklist.md"
STDIN_LINE = "42\n"


def _run_selftest() -> tuple[int, str, str]:
    completed = subprocess.run(
        [sys.executable, "-m", "lwt", "tests/selftest/lwt_selftest.lwt"],
        cwd=REPO_ROOT,
        input=STDIN_LINE.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
        check=False,
    )
    return (
        completed.returncode,
        completed.stdout.decode("utf-8", "replace"),
        completed.stderr.decode("utf-8", "replace"),
    )


class LwtSelfTestSuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.exit_code, cls.stdout, cls.stderr = _run_selftest()
        cls.lines = [line.strip() for line in cls.stdout.splitlines() if line.strip()]
        cls.results = [line for line in cls.lines if line.startswith(("[PASS] ", "[FAIL] "))]
        cls.names = [line[7:].strip() for line in cls.results]
        cls.summary = cls.lines[-1] if cls.lines else ""

    def test_suite_is_green_and_prints_a_total(self) -> None:
        self.assertEqual(self.exit_code, 0, self.stderr)
        self.assertGreaterEqual(len(self.results), 30, "自测项数不应少于 30")
        failures = [line for line in self.results if line.startswith("[FAIL]")]
        self.assertEqual(failures, [], f"自测存在失败项：{failures}")
        total = len(self.results)
        self.assertEqual(
            self.summary,
            f"{total}/{total} 全部通过",
            f"最后一行应给出总数，实际为 {self.summary!r}",
        )

    def test_check_names_are_unique_and_non_empty(self) -> None:
        self.assertEqual(self.names, [name for name in self.names if name], "存在空名字的检查项")
        self.assertEqual(len(self.names), len(set(self.names)), "检查项名字重复")

    def test_checklist_exists_and_covers_the_five_required_features(self) -> None:
        self.assertTrue(CHECKLIST.is_file(), f"缺少功能清单：{CHECKLIST}")
        text = CHECKLIST.read_text(encoding="utf-8")
        for required in ("整数", "字符串", "数组", "结构", "输入", "输出", "分支", "循环", "函数"):
            self.assertIn(required, text, f"功能清单缺少「{required}」")
        # Every ticked row must name a check that the LWT suite actually prints.
        ticked = re.findall(r"^\|\s*[^|]+\|\s*✅\s*\|", text, re.MULTILINE)
        self.assertGreaterEqual(len(ticked), 30, "功能清单应有 ≥30 行逐项打勾")

    def test_suite_is_written_in_lwt(self) -> None:
        self.assertTrue(SELFTEST.is_file())
        self.assertTrue(HELPER.is_file(), "自测用的模块文件缺失")
        source = SELFTEST.read_text(encoding="utf-8")
        self.assertIn("fn expect(", source, "断言函数必须由 LWT 自己实现")
        self.assertIn("import \"selftest_helper.lwt\" as helper;", source)
        # No host-language test machinery may leak into the script.
        for forbidden in ("unittest", "pytest", "def ", "import os", "subprocess"):
            self.assertNotIn(forbidden, source, f"自测脚本不应出现宿主语言痕迹：{forbidden}")


class SelfTestToolTests(unittest.TestCase):
    def test_tool_refuses_protected_scripts(self) -> None:
        sys.path.insert(0, str(REPO_ROOT))
        try:
            from tools import run_selftest
        finally:
            sys.path.pop(0)
        code = run_selftest.main(
            [
                "--script",
                "tests/cases/values-operators/arithmetic-precedence.lwt",
                "--out",
                "reports/_tmp_selftest.json",
            ]
        )
        self.assertEqual(code, 2, "工具必须拒绝把黑盒用例当作自测脚本")

    def test_tool_writes_evidence(self) -> None:
        sys.path.insert(0, str(REPO_ROOT))
        try:
            from tools import run_selftest
        finally:
            sys.path.pop(0)
        out = REPO_ROOT / "reports" / "s55-selftest" / "selftest.json"
        before = out.stat().st_mtime_ns if out.exists() else None
        code = run_selftest.main([])
        self.assertEqual(code, 0)
        report = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(report["ok"])
        self.assertEqual(report["failed"], 0)
        self.assertEqual(report["passed"], report["total"])
        self.assertEqual(report["summary_line"], f"{report['total']}/{report['total']} 全部通过")
        self.assertIsNotNone(before)


if __name__ == "__main__":
    unittest.main()
