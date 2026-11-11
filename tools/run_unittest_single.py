"""S50: run the whole unittest suite exactly once and record who ran it.

Why this exists
---------------
The defense claim used to be ``python -m unittest discover -s tests -q``. On
this machine ``python`` resolves to a bundled CPython 3.13.14 **without
tkinter**, so the GUI test module cannot even be imported: 711 tests run and
two tkinter-related failures appear, which looks like a language or app defect.
The same command under ``py -3.13`` (3.13.7 + Tk 8.6) runs 713 tests and
passes. The difference is the interpreter, not the suite.

This tool keeps the command a *single* ``unittest discover`` invocation but
makes the interpreter explicit in the evidence: it refuses to run when
``tkinter`` is missing, writes the real exit code, ``Ran N``, elapsed time,
``sys.executable``, the Python version and ``TkVersion`` next to the log, and
prints a one-line summary. ``run_defense_probe.py`` selects a Tk-capable
interpreter for the claim, so a bare ``python`` in PATH can no longer decide
the result.

Nothing about the tests, their assertions or the language changes here.
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "reports" / "s51-closeout"


def _utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json(path: Path, doc: dict) -> None:
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "unittest-system.log"
    evidence_path = out_dir / "unittest-single-command.json"

    try:
        import tkinter  # noqa: F401  (the precondition, made explicit)
        tk_version = tkinter.TkVersion
    except Exception as error:  # pragma: no cover - depends on the interpreter
        doc = {
            "schema_version": 1,
            "tool": "tools/run_unittest_single.py",
            "claim_id": "unittest",
            "generated_at_utc": _utc(),
            "error": "TK_UNAVAILABLE",
            "detail": f"{type(error).__name__}: {error}",
            "exit_code": 3,
            "ran": None,
            "ok": False,
            "sys_executable": sys.executable,
            "python_version": sys.version.split()[0],
            "tk_version": None,
            "note": "GUI tests import tkinter at module level; running without it "
                    "yields 711 tests and two fake failures. Run with py -3.13 or "
                    "set LWT_PYTHON to a Tk-enabled interpreter.",
        }
        _write_json(evidence_path, doc)
        print(f"unittest-single: TK_UNAVAILABLE ({error}); use py -3.13 or set LWT_PYTHON")
        return 3

    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"]
    started = _utc()
    t0 = time.perf_counter()
    timed_out = False
    try:
        with log_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("$ " + " ".join(command) + "\n")
            handle.flush()
            completed = subprocess.run(
                command, cwd=str(ROOT), stdout=handle, stderr=subprocess.STDOUT,
                timeout=args.timeout, check=False,
            )
        exit_code = completed.returncode
    except subprocess.TimeoutExpired:
        exit_code = 124
        timed_out = True
    seconds = round(time.perf_counter() - t0, 3)

    text = log_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^Ran (\d+) tests? in", text, re.M)
    ran = int(match.group(1)) if match else None
    ok = any(line.strip() == "OK" for line in text.splitlines())

    doc = {
        "schema_version": 1,
        "tool": "tools/run_unittest_single.py",
        "claim_id": "unittest",
        "command": command,
        "started_at_utc": started,
        "finished_at_utc": _utc(),
        "exit_code": exit_code,
        "ran": ran,
        "ok": ok,
        "timed_out": timed_out,
        "seconds": seconds,
        "sys_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "tk_version": tk_version,
        "log_path": log_path.relative_to(ROOT).as_posix()
                    if log_path.is_relative_to(ROOT) else str(log_path),
        "note": "single invocation of unittest discover; stdout+stderr redirected "
                "to a file (no pipe) so a surviving grandchild cannot block capture",
    }
    _write_json(evidence_path, doc)
    print(f"unittest-single: ran={ran} ok={ok} exit={exit_code} in {seconds}s "
          f"tk={tk_version} exe={sys.executable}")
    print("OK" if (exit_code == 0 and ok) else "FAILED")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
