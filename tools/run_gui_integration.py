"""Run Tk widget integration tests and print an explicit result summary."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

try:
    import tkinter as tk
except ModuleNotFoundError as error:
    tk = None
    TK_IMPORT_ERROR = str(error)
else:
    TK_IMPORT_ERROR = None


def _probe_display() -> str:
    if tk is None:
        return f"unavailable (Tkinter unavailable: {TK_IMPORT_ERROR})"
    try:
        root = tk.Tk()
        version = str(root.tk.call("info", "patchlevel"))
        root.withdraw()
        root.update_idletasks()
        root.destroy()
        return f"available (Tk {version})"
    except (tk.TclError, RuntimeError) as error:
        return f"unavailable ({error})"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-no-skips",
        action="store_true",
        help="fail if Tk integration cases skip, for a display-backed CI job",
    )
    options = parser.parse_args()

    print(f"Tk display probe: {_probe_display()}")
    suite = unittest.defaultTestLoader.discover(
        str(REPOSITORY_ROOT / "tests"), pattern="test_gui_integration.py"
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    failures = len(result.failures) + len(result.errors)
    skipped = len(result.skipped)
    passed = result.testsRun - failures - skipped
    print(
        "GUI integration summary: "
        f"discovered={suite.countTestCases()} run={result.testsRun} "
        f"pass={passed} fail={failures} skip={skipped}"
    )
    for test, reason in result.skipped:
        print(f"GUI integration skip: {test}: {reason}")

    if not result.wasSuccessful():
        return 1
    if options.require_no_skips and skipped:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
