"""Subprocess contract tests for launching the Tk language lab."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_module_entry(setup: str) -> subprocess.CompletedProcess[str]:
    source = (
        setup
        + "\nimport runpy\n"
        + "runpy.run_module('app.language_lab', run_name='__main__')\n"
    )
    return subprocess.run(
        [sys.executable, "-X", "utf8", "-c", source],
        cwd=PROJECT_ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        shell=False,
        check=False,
    )


class LanguageLabEntryTests(unittest.TestCase):
    def test_missing_tkinter_module_entry_exits_nonzero_without_traceback(self) -> None:
        result = run_module_entry("import sys\nsys.modules['tkinter'] = None")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("LWT 语义实验室不可用", result.stderr)
        self.assertIn("无法导入 Tkinter", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_tcl_creation_failure_module_entry_exits_nonzero_without_traceback(self) -> None:
        result = run_module_entry(
            "import tkinter\n"
            "def fail_tk():\n"
            "    raise tkinter.TclError('injected Tcl init failure')\n"
            "tkinter.Tk = fail_tk"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("LWT 语义实验室不可用", result.stderr)
        self.assertIn("injected Tcl init failure", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_module_entry_returns_zero_with_a_headless_success_shim(self) -> None:
        result = run_module_entry(
            "import sys, types\n"
            "tk = types.ModuleType('tkinter')\n"
            "class TclError(Exception): pass\n"
            "class Root:\n"
            "    def mainloop(self): pass\n"
            "tk.TclError = TclError\n"
            "tk.Tk = Root\n"
            "ui = types.ModuleType('app.language_lab_ui')\n"
            "class StubLab:\n"
            "    def __init__(self, root): pass\n"
            "ui.LanguageLabApp = StubLab\n"
            "sys.modules['tkinter'] = tk\n"
            "sys.modules['app.language_lab_ui'] = ui"
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_unexpected_ui_runtime_error_is_not_swallowed(self) -> None:
        result = run_module_entry(
            "import sys, types\n"
            "tk = types.ModuleType('tkinter')\n"
            "class TclError(Exception): pass\n"
            "class Root:\n"
            "    def mainloop(self): pass\n"
            "tk.TclError = TclError\n"
            "tk.Tk = Root\n"
            "ui = types.ModuleType('app.language_lab_ui')\n"
            "class BrokenLab:\n"
            "    def __init__(self, root): raise RuntimeError('injected UI defect')\n"
            "ui.LanguageLabApp = BrokenLab\n"
            "sys.modules['tkinter'] = tk\n"
            "sys.modules['app.language_lab_ui'] = ui"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("injected UI defect", result.stderr)
        self.assertIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
