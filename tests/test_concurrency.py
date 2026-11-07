"""S43 deterministic concurrency: scheduler, PRNG, I/O barrier, replay, threads.

These tests exercise the public runtime and CLI. Thread no-leak (I7) is
asserted *in-process* via ``threading.enumerate()`` after ``execute()``, not
only across subprocesses. Trace replay asserts the found/absent/tampered
three-state evidence contract (S38/S40/S41 style).
"""

from __future__ import annotations

from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from lwt.concurrency import Scheduler, ScheduleTracer, SplitMix64
from lwt.errors import LwtError
from lwt.modules import load_module_graph
from lwt.runtime import execute

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_source(source: str, *, schedule_policy: str = "fifo",
                schedule_replay: str | None = None,
                schedule_decisions: list[dict] | None = None,
                stdin: bytes = b"") -> tuple[str, str, int | None]:
    """Execute an in-memory LWT program in-process; return (stdout, stderr, exit)."""

    with tempfile.TemporaryDirectory(prefix="lwt-concurrency-") as folder:
        path = Path(folder) / "program.lwt"
        path.write_text(source, encoding="utf-8", newline="\n")
        graph = load_module_graph(str(path), include_sources=True)
        texts = {u.display_path or u.canonical_path.name: u.source_text or ""
                 for u in graph.modules}
        out, err = StringIO(), StringIO()
        exit_code: int | None = None
        try:
            execute(
                graph.entry.program, BytesIO(stdin), out, (),
                module_graph=graph, source_path=str(path),
                schedule_policy=schedule_policy,
                schedule_replay=schedule_replay,
                source_texts=texts,
                schedule_decisions=schedule_decisions,
            )
        except LwtError as error:
            exit_code = error.exit_code
            err.write(f"{error.category}: {error.message}\n")
        return out.getvalue(), err.getvalue(), exit_code


def _lwt_threads() -> list[str]:
    return [
        t.name for t in threading.enumerate()
        if t.name.startswith("lwt-task") or t.name.startswith("lwt-io")
    ]


class PrngVectorTests(unittest.TestCase):
    """Spec 11.4: splitmix64 vectors for seeds 1/7/42, no `random` module."""

    VECTORS = {
        1: [27, 44, 18, 53, 33, 82, 10, 74, 31, 1],
        7: [19, 86, 75, 67, 48, 59, 92, 96, 53, 63],
        42: [42, 6, 54, 6, 58, 88, 38, 91, 22, 15],
    }

    def test_fixed_vectors_match_spec(self) -> None:
        for seed, expected in self.VECTORS.items():
            with self.subTest(seed=seed):
                prng = SplitMix64(seed)
                self.assertEqual([prng.below(97) for _ in range(10)], expected)

    def test_vectors_are_seed_distinct(self) -> None:
        seqs = {
            seed: [SplitMix64(seed).below(97)] for seed in (1, 7, 42)
        }
        # Fresh PRNG per element would be trivial; check full sequences differ.
        full = []
        for seed in (1, 7, 42):
            prng = SplitMix64(seed)
            full.append(tuple(prng.below(97) for _ in range(10)))
        self.assertEqual(len(set(full)), 3)

    def test_no_random_module_import(self) -> None:
        source = Path(REPO_ROOT / "lwt" / "concurrency.py").read_text(encoding="utf-8")
        self.assertNotIn("import random", source)
        self.assertNotIn("from random", source)


class DeterminismTests(unittest.TestCase):
    def test_yield_interleaving_is_byte_identical_ten_runs(self) -> None:
        program = (
            "fn worker(name, n) {\n"
            "  let i = 0;\n"
            "  while (i < n) { emit name + str(i); yield(); i = i + 1; }\n"
            "  return null;\n}\n"
            "let a = spawn worker(\"A\", 3);\n"
            "let b = spawn worker(\"B\", 3);\n"
            "join(a); join(b);\n"
        )
        outputs = set()
        for _ in range(10):
            out, err, code = _run_source(program)
            self.assertEqual(code, None)
            self.assertEqual(err, "")
            outputs.add(out)
        self.assertEqual(len(outputs), 1)
        self.assertEqual(
            outputs.pop(), "A0\nB0\nA1\nB1\nA2\nB2\n"
        )

    def test_fifo_and_random_produce_distinct_interleavings(self) -> None:
        program = (
            "fn worker(name, n) {\n"
            "  let i = 0;\n"
            "  while (i < n) { emit name + str(i); yield(); i = i + 1; }\n"
            "  return null;\n}\n"
            "let a = spawn worker(\"A\", 3);\n"
            "let b = spawn worker(\"B\", 3);\n"
            "join(a); join(b);\n"
        )
        fifo, _, _ = _run_source(program, schedule_policy="fifo")
        random7, _, _ = _run_source(program, schedule_policy="random:7")
        self.assertNotEqual(fifo, random7)

    def test_spawn_does_not_switch_and_join_returns_value(self) -> None:
        program = (
            "fn work(x) { return x * 2; }\n"
            "let t = spawn work(3);\n"
            "emit join(t);\n"
        )
        out, err, code = _run_source(program)
        self.assertEqual((out, err, code), ("6\n", "", None))


class ErrorAndDeadlockTests(unittest.TestCase):
    def test_join_reraises_original_location_and_recover_catches(self) -> None:
        program = (
            "fn risky() { let x = 1 / 0; return x; }\n"
            "let t = spawn risky();\n"
            "attempt { join(t); } recover (p) {\n"
            "  emit p.category; emit p.message; emit str(p.line);\n}\n"
        )
        out, err, code = _run_source(program)
        self.assertEqual(code, None)
        self.assertEqual(err, "")
        self.assertEqual(out, "RuntimeError\ndivision by zero\n1\n")

    def test_unjoined_failed_task_raises_at_drain(self) -> None:
        program = "fn bad() { fail(\"task failed\"); }\nlet t = spawn bad();\nemit \"top\";\n"
        out, err, code = _run_source(program)
        self.assertEqual(code, 3)
        self.assertIn("task failed", err)
        self.assertEqual(out, "top\n")

    def test_input_inside_task_is_rejected(self) -> None:
        program = "fn f() { let x = input(); return x; }\nlet t = spawn f();\njoin(t);\n"
        _out, err, code = _run_source(program)
        self.assertEqual(code, 3)
        self.assertIn("input is not available in a task", err)

    def test_deadlock_is_detected_not_hung(self) -> None:
        program = (
            "fn waiter(ch) { let v = receive(ch); return v; }\n"
            "let c1 = channel();\nlet c2 = channel();\n"
            "let a = spawn waiter(c1);\nlet b = spawn waiter(c2);\n"
            "join(a); join(b);\n"
        )
        out, err, code = _run_source(program)
        self.assertEqual(code, 3)
        self.assertIn("deadlock detected", err)

    def test_channel_fifo_close_and_send_on_closed(self) -> None:
        program = (
            "fn producer(ch) { send(ch, 1); send(ch, 2); send(ch, 3); close(ch); return null; }\n"
            "fn consumer(ch) { let v = receive(ch); while (v != null) { emit str(v); v = receive(ch); } return null; }\n"
            "let ch = channel();\nlet p = spawn producer(ch);\nlet c = spawn consumer(ch);\n"
            "join(p); join(c);\n"
        )
        out, err, code = _run_source(program)
        self.assertEqual((out, err, code), ("1\n2\n3\n", "", None))

        bad = "fn s(ch) { close(ch); send(ch, 1); return null; }\nlet ch = channel();\nlet t = spawn s(ch);\njoin(t);\n"
        _o, err, code = _run_source(bad)
        self.assertEqual(code, 3)
        self.assertIn("send on a closed channel", err)


class IoBatchBarrierTests(unittest.TestCase):
    def test_io_pending_batch_does_not_mask_as_deadlock(self) -> None:
        # Task A blocks on join, B is io_pending, C is runnable. The scheduler
        # must not declare deadlock while B's I/O batch is outstanding.
        log = REPO_ROOT / "app" / "fixtures" / "sample.log"
        program = (
            "fn blocked_join(ch) { let v = receive(ch); return v; }\n"
            "fn io_task() { let t = read_text(\"" + str(log).replace("\\", "/") + "\"); emit \"io-done\"; return len(t); }\n"
            "fn runnable() { emit \"runnable\"; return 1; }\n"
            "let ch = channel();\n"
            "let a = spawn blocked_join(ch);\nlet b = spawn io_task();\nlet c = spawn runnable();\n"
            "send(ch, 42);\nemit str(join(a));\njoin(b); join(c);\n"
        )
        out, err, code = _run_source(program)
        self.assertEqual(code, None, f"unexpected error: {err}")
        self.assertEqual(err, "")
        self.assertEqual(set(out.splitlines()), {"runnable", "42", "io-done"})


class ThreadNoLeakTests(unittest.TestCase):
    """I7: after execute() on every path, no LWT task/IO threads remain."""

    def _assert_no_leak(self, program: str) -> None:
        before = set(_lwt_threads())
        _run_source(program)
        # ThreadPoolExecutor threads are joined by scheduler.close() in execute
        # (finally), so enumerate() must be back to the baseline.
        after = set(_lwt_threads())
        self.assertEqual(after - before, set())

    def test_normal_path_no_leak(self) -> None:
        self._assert_no_leak(
            "fn w(){return 1;} let a=spawn w(); emit str(join(a));"
        )

    def test_runtime_error_path_no_leak(self) -> None:
        self._assert_no_leak(
            "fn w(){fail(\"bad\");} let a=spawn w(); "
            "attempt{join(a);}recover(p){emit p.message;}"
        )

    def test_deadlock_path_no_leak(self) -> None:
        self._assert_no_leak(
            "fn w(ch){let v=receive(ch);return v;} let c=channel(); "
            "let a=spawn w(c); join(a);"
        )


class TraceReplayTests(unittest.TestCase):
    """Found / absent / tampered three-state evidence (spec 11.4)."""

    PROGRAM = (
        "fn worker(name, n) {\n"
        "  let i = 0;\n"
        "  while (i < n) { emit name + str(i); yield(); i = i + 1; }\n"
        "  return null;\n}\n"
        "let a = spawn worker(\"A\", 2);\nlet b = spawn worker(\"B\", 2);\n"
        "join(a); join(b);\n"
    )

    def _cli(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [sys.executable, "-m", "lwt", *args],
            cwd=REPO_ROOT, capture_output=True, timeout=20, check=False,
        )

    def _record(self, folder: str, name: str) -> tuple[Path, bytes]:
        source = Path(folder) / "program.lwt"
        source.write_text(self.PROGRAM, encoding="utf-8", newline="\n")
        trace = Path(folder) / f"{name}.json"
        record = self._cli(f"--schedule-log={trace}", str(source))
        self.assertEqual(record.returncode, 0, record.stderr.decode())
        return trace, record.stdout

    def test_found_record_then_replay_is_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt-trace-") as folder:
            trace, recorded = self._record(folder, "found")
            doc = json.loads(trace.read_text(encoding="utf-8"))
            self.assertEqual(doc["schema"], "lwt-schedule-trace/1")
            for field in ("source_sha256", "program_args", "policy",
                          "expected_exit_code", "expected_stdout_sha256",
                          "expected_stderr_sha256", "decisions"):
                self.assertIn(field, doc)
            replay = self._cli(f"--schedule-replay={trace}",
                               str(Path(folder) / "program.lwt"))
            self.assertEqual(replay.returncode, 0, replay.stderr.decode())
            self.assertEqual(replay.stdout, recorded)

    def test_absent_ordered_aggregate_has_one_result_class(self) -> None:
        # A program with no yield has a single interleaving across seeds.
        program = (
            "fn w(x){ return x; }\nlet a = spawn w(1);\nlet b = spawn w(2);\n"
            "emit str(join(a) + join(b));\n"
        )
        with tempfile.TemporaryDirectory(prefix="lwt-absent-") as folder:
            source = Path(folder) / "program.lwt"
            source.write_text(program, encoding="utf-8", newline="\n")
            results = set()
            for seed in range(1, 21):
                r = self._cli(f"--schedule=random:{seed}", str(source))
                self.assertEqual(r.returncode, 0)
                results.add((r.returncode, __import__("hashlib").sha256(r.stdout).hexdigest()))
            self.assertEqual(len(results), 1)

    def test_tampered_chosen_source_and_output_are_all_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt-tamper-") as folder:
            trace, _recorded = self._record(folder, "base")
            base = json.loads(trace.read_text(encoding="utf-8"))
            source = str(Path(folder) / "program.lwt")
            tampered = {}
            chosen = json.loads(json.dumps(base))
            chosen["decisions"][0]["chosen"] = (
                2 if chosen["decisions"][0]["chosen"] != 2 else 1
            )
            tampered["chosen"] = chosen
            digest = json.loads(json.dumps(base))
            digest["source_sha256"] = "0" * 64
            tampered["source_sha256"] = digest
            output = json.loads(json.dumps(base))
            output["expected_stdout_sha256"] = "0" * 64
            tampered["expected_stdout_sha256"] = output
            for name, doc in tampered.items():
                with self.subTest(field=name):
                    path = Path(folder) / f"tampered_{name}.json"
                    path.write_text(json.dumps(doc), encoding="utf-8")
                    r = self._cli(f"--schedule-replay={path}", source)
                    self.assertEqual(r.returncode, 4, r.stderr.decode())
                    self.assertIn(b"CliError", r.stderr)

    def test_mutually_exclusive_schedule_switches(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt-args-") as folder:
            source = Path(folder) / "program.lwt"
            source.write_text(self.PROGRAM, encoding="utf-8")
            r = self._cli(
                f"--schedule-log={folder}/a.json",
                f"--schedule-replay={folder}/a.json", str(source),
            )
            self.assertEqual(r.returncode, 4)
            self.assertIn(b"mutually exclusive", r.stderr)


if __name__ == "__main__":
    unittest.main()
