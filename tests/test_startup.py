"""S44 WP1: lazy scheduler import (P0-1) and startup-path regressions.

The decisive invariant: a program with no ``spawn`` must never import
``lwt.concurrency`` (nor its heavy stack: ``concurrent.futures``, ``hashlib``).
A program that uses ``spawn`` must load it and keep producing identical output.
The three non-normal CLI entry points (``--check`` / ``--profile`` / ``--repl``)
and the schedule switches must be unaffected.

All executions go through the public interpreter (``python -m lwt``) or the
public ``execute`` API; no ``eval``/``exec`` of LWT source is used.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def _run_python(code: str, *, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PY, "-c", code], cwd=cwd, capture_output=True, text=True, timeout=40
    )


def _run_lwt(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PY, "-m", "lwt", *args], cwd=REPO_ROOT,
        input=stdin, capture_output=True, text=True, timeout=40,
    )


def _probe_modules(program: str) -> dict[str, object]:
    """Run an LWT program via the public execute API in a fresh interpreter and
    report whether the heavy scheduler stack was imported."""
    code = f"""
import sys, json
from io import BytesIO, StringIO
from lwt.modules import load_module_graph
from lwt.runtime import execute
from pathlib import Path
p = Path({program!r})
g = load_module_graph(str(p))
out = StringIO()
execute(g.entry.program, BytesIO(b""), out, (), module_graph=g, source_path=str(p))
print("MODPROBE=" + json.dumps({{
    "concurrency": "lwt.concurrency" in sys.modules,
    "futures": "concurrent.futures" in sys.modules,
    "hashlib": "hashlib" in sys.modules,
    "output": out.getvalue(),
}}))
"""
    result = _run_python(code)
    if result.returncode != 0:
        raise AssertionError(f"probe failed (exit {result.returncode}): {result.stderr}")
    for line in result.stdout.splitlines():
        if line.startswith("MODPROBE="):
            return json.loads(line[len("MODPROBE="):])
    raise AssertionError(f"no MODPROBE line in stdout: {result.stdout!r}")


class StartupLazyImportTests(unittest.TestCase):
    """P0-1: non-spawn programs must not import the scheduler stack."""

    def test_non_spawn_program_does_not_load_concurrency(self) -> None:
        probe = _probe_modules("examples/guide/hello.lwt")
        self.assertFalse(probe["concurrency"], "lwt.concurrency must not be imported")
        self.assertFalse(probe["futures"], "concurrent.futures must not be imported")
        self.assertFalse(probe["hashlib"], "hashlib must not be imported")
        self.assertIn("hello, LWT", probe["output"])

    def test_importing_cli_does_not_load_concurrency(self) -> None:
        result = _run_python(
            "import sys, lwt.cli; "
            "print('C=', 'lwt.concurrency' in sys.modules, "
            "'F=', 'concurrent.futures' in sys.modules)"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("C= False", result.stdout)
        self.assertIn("F= False", result.stdout)

    def test_spawn_program_loads_concurrency_and_keeps_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt-startup-spawn-") as folder:
            path = Path(folder) / "spawn.lwt"
            path.write_text(
                "fn dbl(x) { return x * 2; }\n"
                "let a = spawn dbl(3);\n"
                "emit str(join(a));\n",
                encoding="utf-8", newline="\n",
            )
            probe = _probe_modules(str(path))
        self.assertTrue(probe["concurrency"], "spawn must load lwt.concurrency")
        self.assertEqual(probe["output"], "6\n")


class ScheduleSwitchTests(unittest.TestCase):
    """WP1 item 3: schedule switches remain functional for non-spawn programs."""

    def test_schedule_log_on_non_spawn_records_zero_decisions(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt-startup-log-") as folder:
            trace = Path(folder) / "trace.json"
            result = _run_lwt(
                f"--schedule=random:7", f"--schedule-log={trace}",
                "examples/guide/hello.lwt",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(trace.exists(), "trace file must be written")
            doc = json.loads(trace.read_text(encoding="utf-8"))
            self.assertEqual(doc["decisions"], [])
            self.assertEqual(doc["policy"], "random:7")
            self.assertIn("lwt-schedule-trace", doc["schema"])

    def test_schedule_replay_on_non_spawn_is_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt-startup-replay-") as folder:
            trace = Path(folder) / "trace.json"
            rec = _run_lwt("--schedule-log=" + str(trace), "examples/guide/hello.lwt")
            self.assertEqual(rec.returncode, 0, rec.stderr)
            rep = _run_lwt("--schedule-replay=" + str(trace), "examples/guide/hello.lwt")
            self.assertEqual(rep.returncode, 0, rep.stderr)
            self.assertEqual(rep.stdout, rec.stdout)


class ToolEntryPointTests(unittest.TestCase):
    """WP1 item 4: --check / --profile / --repl unaffected by lazy imports."""

    def test_check_still_passes(self) -> None:
        result = _run_lwt("--check", "examples/guide/hello.lwt")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Check passed", result.stdout)

    def test_check_json_still_works(self) -> None:
        result = _run_lwt("--check", "--format=json", "examples/guide/hello.lwt")
        self.assertEqual(result.returncode, 0, result.stderr)
        doc = json.loads(result.stdout)
        self.assertTrue(doc["ok"])

    def test_profile_still_writes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt-startup-prof-") as folder:
            target = Path(folder) / "profile.json"
            result = _run_lwt("--profile", str(target), "examples/guide/hello.lwt")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(target.exists(), "profile file must be written")
            doc = json.loads(target.read_text(encoding="utf-8"))
            self.assertIn("schema_version", doc)

    def test_repl_starts_and_exits(self) -> None:
        result = _run_lwt("--repl", stdin="let x = 7;\nx + 1\n.exit\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("REPL", result.stderr)
        self.assertIn(">>>", result.stderr)

    def test_profile_rejects_spawn_before_tasks(self) -> None:
        # Spec 11.8: lazy import must not weaken the tool boundary.
        with tempfile.TemporaryDirectory(prefix="lwt-startup-prof-spawn-") as folder:
            source = Path(folder) / "spawn.lwt"
            source.write_text(
                "fn w(){ return 1; }\nlet t = spawn w();\njoin(t);\n",
                encoding="utf-8", newline="\n",
            )
            target = Path(folder) / "p.json"
            result = _run_lwt("--profile", str(target), str(source))
            self.assertEqual(result.returncode, 4, result.stderr)
            self.assertIn("does not support spawn", result.stderr)
            self.assertFalse(target.exists(), "no partial profile")


if __name__ == "__main__":
    unittest.main()
