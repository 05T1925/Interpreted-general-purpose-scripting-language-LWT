"""S46: bounded schedule exploration, forced choices, mutant and minimization.

These tests exercise the tool-only hook (``execute(..., schedule_choices=...)``),
the clean corpus (no violations), the S45 duplicate-delivery fault injection
(at least one violation with a short replayable witness), invalid prefixes
(exit 4, no hang, no thread leak) and budget-exhaustion honesty
(``BUDGET_EXHAUSTED`` is not ``PASS``).
"""

from __future__ import annotations

from io import BytesIO, StringIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from lwt.errors import LwtError
from lwt.modules import load_module_graph
from lwt.runtime import execute

from tools import model_check_concurrency as mc

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS = REPO_ROOT / "tests" / "concurrency-model"


def _lwt_threads() -> list[str]:
    return [
        thread.name
        for thread in threading.enumerate()
        if thread.name.startswith("lwt-task") or thread.name.startswith("lwt-io")
    ]


def _run_source(
    source: str, choices: tuple[int, ...] | None
) -> tuple[str, str, int, list[dict]]:
    """Execute an in-memory program with forced choices; return output/exit."""

    with tempfile.TemporaryDirectory(prefix="lwt-s46-") as folder:
        path = Path(folder) / "program.lwt"
        path.write_text(source, encoding="utf-8", newline="\n")
        graph = load_module_graph(str(path), include_sources=True)
        texts = {str(path): graph.entry.source_text or ""}
        out, err = StringIO(), StringIO()
        decisions: list[dict] = []
        exit_code = 0
        try:
            execute(
                graph.entry.program,
                BytesIO(b""),
                out,
                (),
                module_graph=graph,
                source_path=str(path),
                source_texts=texts,
                schedule_decisions=decisions,
                schedule_choices=list(choices) if choices is not None else None,
            )
        except LwtError as error:
            exit_code = error.exit_code
            err.write(f"{error.category}: {error.message}\n")
        return out.getvalue(), err.getvalue(), exit_code, decisions


CHOICE_PROGRAM = (
    'fn worker(name) { emit name + "0"; yield(); emit name + "1"; }\n'
    'let a = spawn worker("A");\n'
    'let b = spawn worker("B");\n'
    "join(a); join(b);\n"
)


class ScheduleChoicesTests(unittest.TestCase):
    """WP1: the forced-choice hook is opt-in and fails safely."""

    def test_none_and_empty_prefix_are_identical(self) -> None:
        baseline = _run_source(CHOICE_PROGRAM, None)
        explicit = _run_source(CHOICE_PROGRAM, ())
        self.assertEqual(baseline[0], explicit[0])
        self.assertEqual(baseline[2], explicit[2])
        self.assertEqual(
            [(d["index"], d["ready"], d["chosen"]) for d in baseline[3]],
            [(d["index"], d["ready"], d["chosen"]) for d in explicit[3]],
        )

    def test_legal_choices_drive_a_different_interleaving(self) -> None:
        baseline = _run_source(CHOICE_PROGRAM, None)
        forced = _run_source(CHOICE_PROGRAM, (2,))
        self.assertEqual(baseline[0], "A0\nB0\nA1\nB1\n")
        self.assertEqual(forced[0], "B0\nA0\nB1\nA1\n")
        self.assertEqual(forced[2], 0)
        self.assertEqual(forced[3][0]["chosen"], 2)
        self.assertEqual(forced[3][0]["ready"], [1, 2])

    def test_invalid_choice_exits_four_without_hang(self) -> None:
        started = time.monotonic()
        out, err, exit_code, _ = _run_source(CHOICE_PROGRAM, (99,))
        elapsed = time.monotonic() - started
        self.assertEqual(exit_code, 4, out)
        self.assertIn("not in ready", err)
        self.assertIn("choice 0", err)
        self.assertLess(elapsed, 15.0, "invalid prefix must not hang")
        self.assertEqual(_lwt_threads(), [])

    def test_choices_have_no_effect_without_spawn(self) -> None:
        out, err, exit_code, decisions = _run_source('emit "plain";\n', (2,))
        self.assertEqual((out, err, exit_code, decisions), ("plain\n", "", 0, []))


class CleanCorpusTests(unittest.TestCase):
    def test_clean_corpus_completes_with_zero_violations(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt-s46-clean-") as out:
            code = mc.main([
                "--corpus", str(CORPUS),
                "--max-runs", "200", "--max-decisions", "30",
                "--time-budget", "60", "--require-clean", "--out", out,
            ])
            self.assertEqual(code, 0)
            summary = json.loads((Path(out) / "summary.json").read_text(encoding="utf-8"))
            self.assertTrue(summary["all_pass"])
            self.assertEqual(summary["totals"]["violations"], 0)
            self.assertEqual(summary["totals"]["budget_exhausted"], 0)
            self.assertEqual(summary["totals"]["thread_leaks"], 0)
            ids = {item["id"] for item in summary["programs"]}
            self.assertIn("channel-exactly-once", ids)
            self.assertIn("deadlock-two-receivers", ids)
            # lost-update must be reported as divergence, not as a violation.
            lost = next(item for item in summary["programs"] if item["id"] == "lost-update")
            self.assertEqual(lost["violation_count"], 0)
            self.assertEqual(len(lost["outcomes"]), 2)
            self.assertEqual({item["stdout"] for item in lost["outcomes"]}, {"1\n", "2\n"})

    def test_clean_witness_replays_byte_identically(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt-s46-replay-") as out:
            self.assertEqual(mc.main([
                "--program", str(CORPUS / "lost-update.lwt"),
                "--max-runs", "50", "--time-budget", "30", "--out", out,
            ]), 0)
            summary = json.loads((Path(out) / "summary.json").read_text(encoding="utf-8"))
            witnesses = [
                item["witness"] for item in summary["programs"][0]["outcomes"]
                if "witness" in item
            ]
            self.assertGreaterEqual(len(witnesses), 2)
            for witness in witnesses:
                replay = witness["replay"]
                self.assertEqual(replay["mode"], "public-cli")
                self.assertTrue(replay["matches"], replay)
                self.assertEqual(replay["exit_code"], 0)

    def test_budget_exhaustion_is_not_pass(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt-s46-budget-") as out:
            code = mc.main([
                "--corpus", str(CORPUS),
                "--max-runs", "1", "--time-budget", "30",
                "--require-clean", "--out", out,
            ])
            summary = json.loads((Path(out) / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(code, 1)
            self.assertGreater(summary["totals"]["budget_exhausted"], 0)
            self.assertFalse(summary["all_pass"])


class MutantAndMinimizationTests(unittest.TestCase):
    def test_mutant_catches_the_s45_duplicate_delivery(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt-s46-mutant-") as out:
            code = mc.main([
                "--corpus", str(CORPUS),
                "--max-runs", "200", "--time-budget", "60",
                "--mutant", "duplicate-delivery", "--expect-violation",
                "--out", out,
            ])
            self.assertEqual(code, 0)
            summary = json.loads((Path(out) / "summary.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(summary["totals"]["violations"], 1)
            by_id = {item["id"]: item for item in summary["programs"]}
            finding = by_id["channel-exactly-once"]
            self.assertGreaterEqual(finding["violation_count"], 1)
            violation = finding["violations"][0]
            self.assertLessEqual(len(violation["minimized_prefix"]), 3)
            self.assertEqual(violation["stdout"], "7\n7\n")
            self.assertTrue(violation["replay"]["matches"], violation["replay"])
            self.assertIn("duplicate-delivery", violation["replay"]["mode"])

    def test_minimization_keeps_only_the_needed_choice(self) -> None:
        source = (
            'fn worker(name) { emit name; }\n'
            'let a = spawn worker("A");\n'
            'let b = spawn worker("B");\n'
            "join(a); join(b);\n"
        )
        model = {
            "id": "order-fixed",
            "spec_refs": ["test"],
            "max_decisions": 10,
            "expected": {"exit": 0, "stdout": "A\nB\n"},
        }
        with tempfile.TemporaryDirectory(prefix="lwt-s46-min-") as folder:
            program = Path(folder) / "order-fixed.lwt"
            program.write_text(source, encoding="utf-8", newline="\n")
            program.with_name("order-fixed.model.json").write_text(
                json.dumps(model), encoding="utf-8", newline="\n"
            )
            out = Path(folder) / "out"
            code = mc.main([
                "--program", str(program), "--max-runs", "50",
                "--time-budget", "30", "--expect-violation", "--out", str(out),
            ])
            self.assertEqual(code, 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            violation = summary["programs"][0]["violations"][0]
            self.assertEqual(len(violation["minimized_prefix"]), 1)
            self.assertEqual(violation["minimized_prefix"], [2])
            self.assertTrue(violation["replay"]["matches"])

    def test_invalid_prefix_is_marked_and_skipped(self) -> None:
        context = mc.load_context(
            CORPUS / "channel-exactly-once.lwt",
            CORPUS / "channel-exactly-once.model.json",
        )
        result = mc.run_prefix(context, (99,))
        self.assertTrue(result.invalid_prefix)
        self.assertEqual(result.exit_code, 4)
        self.assertIn(b"not in ready", result.stderr)
        self.assertEqual(_lwt_threads(), [])


class NoLeakTests(unittest.TestCase):
    def test_no_lwt_threads_remain_after_corpus_runs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt-s46-leak-") as out:
            mc.main([
                "--corpus", str(CORPUS), "--max-runs", "50",
                "--time-budget", "30", "--out", out,
            ])
        self.assertEqual(_lwt_threads(), [])


if __name__ == "__main__":
    unittest.main()
