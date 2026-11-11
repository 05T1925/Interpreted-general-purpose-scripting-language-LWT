"""Start each GUI app once and record whether a real window appears.

This is a **startup precheck only**. It never clicks, types or judges an
acceptance item: a window that appears proves the process can start and create
its Tk window, not that the GUI behaves correctly. GUI A-E stay NOT_RUN until
the user performs them on an unoccluded desktop (S21 stop rule).

Windows only: window discovery uses ctypes/EnumWindows, no third-party modules.
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import datetime
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "reports" / "s54-closeout" / "gui-preflight.json"

APPS = (
    ("A_language_lab", ["-m", "app.language_lab"]),
    ("B_log_detective", ["-m", "app.log_detective", "--", "app/fixtures/sample.log"]),
    ("C_lwt_snake", ["-m", "app.lwt_snake"]),
    ("D_counterfactual", ["-m", "app.lwt_snake.counterfactual_ui"]),
)


def _tk_interpreter() -> list[str]:
    """Pick an interpreter that can import tkinter; bare ``python`` often cannot."""

    candidates: list[list[str]] = []
    import os

    if os.environ.get("LWT_PYTHON"):
        candidates.append([os.environ["LWT_PYTHON"]])
    candidates += [[sys.executable], ["py", "-3.13"], ["py", "-3"], ["python3"], ["python"]]
    for candidate in candidates:
        try:
            probe = subprocess.run(
                candidate + ["-c", "import tkinter, sys; print(sys.executable)"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if probe.returncode == 0:
            # Use the real interpreter path, not the launcher: ``py -3.13``
            # spawns a child, and the Tk window belongs to that child's PID.
            resolved = probe.stdout.decode("utf-8", "replace").strip().splitlines()
            if resolved and Path(resolved[-1]).exists():
                return [resolved[-1]]
            return candidate
    return [sys.executable]

user32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _windows_for(pid: int) -> list[dict]:
    found: list[dict] = []

    def callback(hwnd, _lparam):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value != pid or not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        found.append({
            "title": buffer.value,
            "width": rect.right - rect.left,
            "height": rect.bottom - rect.top,
        })
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args(argv)

    rows = []
    python = _tk_interpreter()
    print(f"gui_preflight: interpreter={' '.join(python)}")
    for name, app_args in APPS:
        command = python + app_args
        started = time.monotonic()
        process = subprocess.Popen(
            command, cwd=str(ROOT),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        window = None
        status = "timeout"
        while time.monotonic() - started < args.timeout:
            if process.poll() is not None:
                status = f"exited_early({process.returncode})"
                break
            windows = _windows_for(process.pid)
            if windows:
                window = windows[0]
                status = "window_appeared"
                break
            time.sleep(0.25)
        elapsed = round(time.monotonic() - started, 1)
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        rows.append({
            "id": name,
            "command": command[1:],
            "status": status,
            "seconds": elapsed,
            "window": window,
        })
        print(f"[{status}] {name} ({elapsed}s) {window['title'] if window else ''}")

    doc = {
        "schema_version": 1,
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool": "tools/gui_preflight.py",
        "kind": "startup precheck",
        "note": "A window appearing only proves the process starts and creates its Tk "
                "window. No input was sent and nothing was judged. This is NOT the S21 "
                "manual GUI acceptance: A-E remain NOT_RUN until the user performs them.",
        "timeout_seconds": args.timeout,
        "apps": rows,
    }
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    appeared = sum(1 for row in rows if row["status"] == "window_appeared")
    print(f"gui_preflight: windows={appeared}/{len(rows)} -> {out.name}")
    return 0 if appeared == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
