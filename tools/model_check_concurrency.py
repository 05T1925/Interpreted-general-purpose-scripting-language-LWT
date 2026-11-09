"""S46: bounded systematic schedule exploration for small LWT programs.

This is a *bounded* exploration, not a formal proof: it enumerates alternative
ready-task choices along a prefix of scheduling decisions, up to ``--max-runs``
executions, ``--max-decisions`` per prefix and ``--time-budget`` wall-clock
seconds. A clean result means "no invariant violation in the explored bound";
budget exhaustion is reported as ``BUDGET_EXHAUSTED`` and never as ``PASS``.

Programs live in ``tests/concurrency-model/`` with a ``<stem>.model.json``
sidecar (id, spec refs, expected exit/stdout/stderr or allowed outcomes). The
tool only adds an internal hook (``execute(..., schedule_choices=...)``); it does
not change the public CLI, the trace schema, or any §1-§11 semantics.

Usage::

    python tools/model_check_concurrency.py --corpus tests/concurrency-model \
        --max-runs 500 --max-decisions 30 --time-budget 60 \
        --out reports/s46-concurrency-model

``--mutant duplicate-delivery`` monkey-patches ``Scheduler.wake_receiver`` in
this process only, reproducing the S45 defect (handoff plus enqueue), to prove
the checker catches a bug that random sampling missed. It never touches the
product path.
"""

from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lwt.concurrency import Scheduler, ScheduleReplayMismatch, ScheduleTracer, source_digest
from lwt.errors import LwtError, format_diagnostic
from lwt.modules import ModuleGraph, load_module_graph
from lwt.runtime import execute

SCHEMA = "lwt-s46-model-check/1"
TRACE_SCHEMA = "lwt-schedule-trace/1"
TOOL_NAME = "tools/model_check_concurrency.py"

# Runs the real CLI entry point with the synthetic fault injected in this
# process only. Used exclusively to replay mutant witnesses; the product path
# is untouched.
_MUTANT_REPLAY_HARNESS = r'''
import sys
sys.path.insert(0, {root!r})
from lwt.concurrency import Scheduler
_original = Scheduler.wake_receiver
def _patched(self, channel_id, value):
    channel = self.channels[channel_id]
    had_receiver = bool(channel.waiting)
    _original(self, channel_id, value)
    if had_receiver and value is not None:
        channel.items.append(value)
Scheduler.wake_receiver = _patched
from lwt.cli import main
raise SystemExit(main(sys.argv[1:]))
'''


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _lwt_threads() -> list[str]:
    return [
        thread.name
        for thread in threading.enumerate()
        if thread.name.startswith("lwt-task") or thread.name.startswith("lwt-io")
    ]


# ---------------------------------------------------------------------------
# Program context and one bounded run.
# ---------------------------------------------------------------------------
@dataclass
class ProgramContext:
    program_path: Path
    display_path: str
    graph: ModuleGraph
    texts: dict[str, str]
    digest: str
    model: dict[str, Any]
    model_path: Path


@dataclass
class RunResult:
    exit_code: int
    stdout: bytes
    stderr: bytes
    decisions: list[dict[str, Any]]
    invalid_prefix: bool
    seconds: float

    @property
    def key(self) -> tuple[int, str, str]:
        return (self.exit_code, _sha(self.stdout), _sha(self.stderr))


def load_context(program_path: Path, model_path: Path) -> ProgramContext:
    program_path = program_path.resolve()
    model_path = model_path.resolve()
    display = _display_path(program_path)
    graph = load_module_graph(str(program_path), include_sources=True)
    # Mirror lwt.cli exactly: module keys are display_path or file name, and the
    # entry key is the CLI argument string. A mismatch would make replay fail
    # with "trace binding mismatch: source_sha256".
    texts: dict[str, str] = {}
    for unit in graph.modules:
        key = str(unit.display_path or unit.canonical_path.name).replace("\\", "/")
        texts[key] = unit.source_text or ""
    entry_key = str(graph.entry.display_path or display).replace("\\", "/")
    if entry_key not in texts:
        texts[entry_key] = graph.entry.source_text or ""
    digest = source_digest(texts)
    model = json.loads(model_path.read_text(encoding="utf-8"))
    if not isinstance(model, dict) or "expected" not in model:
        raise ValueError(f"{model_path}: model must contain an 'expected' object")
    return ProgramContext(
        program_path=program_path,
        display_path=display,
        graph=graph,
        texts=texts,
        digest=digest,
        model=model,
        model_path=model_path,
    )


def run_prefix(context: ProgramContext, choices: tuple[int, ...] | None) -> RunResult:
    """Execute once with the first N scheduling choices forced."""

    out, err = StringIO(), StringIO()
    decisions: list[dict[str, Any]] = []
    exit_code = 0
    invalid = False
    started = time.perf_counter()
    try:
        execute(
            context.graph.entry.program,
            BytesIO(b""),
            out,
            (),
            module_graph=context.graph,
            source_path=context.display_path,
            schedule_policy="fifo",
            source_texts=context.texts,
            schedule_decisions=decisions,
            schedule_choices=list(choices) if choices is not None else None,
        )
    except LwtError as error:
        exit_code = error.exit_code
        err.write(format_diagnostic(error, context.display_path) + "\n")
        invalid = error.category == "CliError" and "not in ready" in error.message
    except ScheduleReplayMismatch as mismatch:  # defensive: worker-thread path
        exit_code = 4
        err.write(f"{mismatch}\n")
        invalid = True
    return RunResult(
        exit_code=exit_code,
        stdout=out.getvalue().encode("utf-8"),
        stderr=err.getvalue().encode("utf-8"),
        decisions=decisions,
        invalid_prefix=invalid,
        seconds=time.perf_counter() - started,
    )


def matches_expected(model: dict[str, Any], result: RunResult) -> bool:
    expected = model["expected"]
    text_out = result.stdout.decode("utf-8", "replace")
    text_err = result.stderr.decode("utf-8", "replace")
    allowed = expected.get("allowed_outcomes")
    if allowed is not None:
        return any(
            result.exit_code == item.get("exit", 0)
            and text_out == item.get("stdout", "")
            for item in allowed
        )
    if result.exit_code != int(expected.get("exit", 0)):
        return False
    if "stdout" in expected and text_out != expected["stdout"]:
        return False
    if "stderr_contains" in expected and expected["stderr_contains"] not in text_err:
        return False
    return True


# ---------------------------------------------------------------------------
# Exploration.
# ---------------------------------------------------------------------------
def explore(
    context: ProgramContext,
    *,
    max_runs: int,
    max_decisions: int,
    deadline: float,
) -> dict[str, Any]:
    program_max = int(context.model.get("max_decisions", max_decisions))
    depth_limit = min(max_decisions, program_max)
    started = time.perf_counter()
    queue: deque[tuple[int, ...]] = deque([()])
    seen: set[tuple[int, ...]] = {()}
    runs = 0
    invalid_prefixes = 0
    decision_points = 0
    max_depth = 0
    outcomes: dict[tuple[int, str, str], dict[str, Any]] = {}
    violation_records: list[dict[str, Any]] = []
    violation_count = 0
    budget_hit = False
    thread_leaks: list[str] = []

    while queue:
        if runs >= max_runs or time.monotonic() >= deadline:
            budget_hit = True
            break
        prefix = queue.popleft()
        result = run_prefix(context, prefix)
        runs += 1
        leaked = _lwt_threads()
        if leaked:
            thread_leaks.extend(leaked)
        if result.invalid_prefix:
            invalid_prefixes += 1
            continue
        max_depth = max(max_depth, len(result.decisions))
        decision_points += sum(
            1 for decision in result.decisions if len(decision["ready"]) > 1
        )
        entry = outcomes.get(result.key)
        if entry is None:
            entry = {
                "exit_code": result.exit_code,
                "stdout": result.stdout.decode("utf-8", "replace"),
                "stderr": result.stderr.decode("utf-8", "replace"),
                "count": 0,
                "first_prefix": list(prefix),
                "result": result,
            }
            outcomes[result.key] = entry
        entry["count"] += 1

        if not matches_expected(context.model, result):
            violation_count += 1
            if len(violation_records) < 8:
                violation_records.append(
                    {"prefix": list(prefix), "result": result}
                )

        if len(prefix) < depth_limit:
            for index, decision in enumerate(result.decisions):
                if index >= depth_limit:
                    break
                ready = [int(item) for item in decision["ready"]]
                if len(ready) <= 1:
                    continue
                base = tuple(
                    int(item["chosen"]) for item in result.decisions[:index]
                )
                if len(base) >= depth_limit:
                    break
                for alternative in ready:
                    if alternative == decision["chosen"]:
                        continue
                    candidate = base + (alternative,)
                    if len(candidate) <= depth_limit and candidate not in seen:
                        seen.add(candidate)
                        queue.append(candidate)

    status = "BUDGET_EXHAUSTED" if (queue or budget_hit) else "COMPLETE"
    return {
        "status": status,
        "runs": runs,
        "prefixes_discovered": len(seen),
        "queued_when_stopped": len(queue),
        "invalid_prefixes": invalid_prefixes,
        "decision_points": decision_points,
        "max_depth": max_depth,
        "depth_limit": depth_limit,
        "outcomes": outcomes,
        "violations": violation_records,
        "violation_count": violation_count,
        "thread_leaks": thread_leaks,
        "seconds": round(time.perf_counter() - started, 3),
    }


def minimize(
    context: ProgramContext,
    prefix: list[int],
    deadline: float,
) -> tuple[list[int], RunResult]:
    """Greedy deletion, then 'first ready' replacement, then deletion again."""

    def still_bad(candidate: list[int]) -> tuple[bool, RunResult]:
        result = run_prefix(context, tuple(candidate))
        return (
            (not result.invalid_prefix) and (not matches_expected(context.model, result)),
            result,
        )

    current = list(prefix)
    result: RunResult | None = None

    def delete_pass() -> None:
        nonlocal current, result
        changed = True
        while changed and time.monotonic() < deadline:
            changed = False
            for index in range(len(current)):
                candidate = current[:index] + current[index + 1:]
                bad, candidate_result = still_bad(candidate)
                if bad:
                    current = candidate
                    result = candidate_result
                    changed = True
                    break

    delete_pass()
    for index in range(len(current)):
        if time.monotonic() >= deadline:
            break
        probe = run_prefix(context, tuple(current))
        if probe.invalid_prefix or index >= len(probe.decisions):
            break
        ready = sorted(int(item) for item in probe.decisions[index]["ready"])
        if not ready:
            break
        alternative = ready[0]
        if alternative == current[index]:
            continue
        candidate = current[:index] + [alternative] + current[index + 1:]
        bad, candidate_result = still_bad(candidate)
        if bad:
            current = candidate
            result = candidate_result
    delete_pass()
    if result is None:
        _, result = still_bad(current)
    return current, result


# ---------------------------------------------------------------------------
# Trace writing and public-CLI replay.
# ---------------------------------------------------------------------------
def write_trace(context: ProgramContext, result: RunResult, path: Path) -> None:
    document = {
        "schema": TRACE_SCHEMA,
        "schema_version": 1,
        "source": context.display_path,
        "source_sha256": context.digest,
        "program_args": [],
        "policy": "fifo",
        "expected_exit_code": result.exit_code,
        "expected_stdout_sha256": _sha(result.stdout),
        "expected_stderr_sha256": _sha(result.stderr),
        "decisions": result.decisions,
    }
    ScheduleTracer.write(str(path), document)


def replay_trace(context: ProgramContext, trace_path: Path, mutant: str) -> dict[str, Any]:
    """Replay through the public CLI.

    Clean witnesses use ``python -m lwt --schedule-replay=...`` exactly. A
    mutant witness cannot be reproduced by an unmodified process (the fault is
    synthetic), so it is replayed through the same CLI entry point with the
    fault injected in a tool-only harness; the evidence records that mode.
    """

    replay_arg = f"--schedule-replay={trace_path.as_posix()}"
    if mutant == "none":
        command = [sys.executable, "-m", "lwt", replay_arg, context.display_path]
        mode = "public-cli"
    else:
        command = [
            sys.executable,
            "-c",
            _MUTANT_REPLAY_HARNESS.format(root=str(REPO_ROOT)),
            replay_arg,
            context.display_path,
        ]
        mode = f"tool-harness-{mutant}"
    try:
        completed = subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            capture_output=True,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "replay timed out", "command": command, "mode": mode}
    return {
        "ok": True,
        "mode": mode,
        "exit_code": completed.returncode,
        "stdout_sha256": _sha(completed.stdout),
        "stderr_sha256": _sha(completed.stderr),
        "command": command,
    }


# ---------------------------------------------------------------------------
# Fault injection (tool process only).
# ---------------------------------------------------------------------------
class DuplicateDeliveryMutant:
    """Reproduce S45's defect: hand off to a blocked receiver AND enqueue."""

    def __enter__(self) -> "DuplicateDeliveryMutant":
        self.original = Scheduler.wake_receiver

        def patched(scheduler: Scheduler, channel_id: int, value: object) -> None:
            channel = scheduler.channels[channel_id]
            had_receiver = bool(channel.waiting)
            self.original(scheduler, channel_id, value)
            if had_receiver and value is not None:
                channel.items.append(value)

        Scheduler.wake_receiver = patched  # type: ignore[method-assign]
        return self

    def __exit__(self, *exc_info: object) -> None:
        Scheduler.wake_receiver = self.original  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# Reporting.
# ---------------------------------------------------------------------------
def render_markdown(summary: dict[str, Any]) -> str:
    mode = summary["mode"]
    lines = [
        "# S46 bounded schedule exploration",
        "",
        f"- Generated: `{summary['generated_at_utc']}`",
        f"- Tool: `{TOOL_NAME}`",
        f"- Mutant: `{mode['mutant']}`",
        f"- Budget: max_runs={mode['max_runs']} per program, "
        f"max_decisions={mode['max_decisions']}, time_budget={mode['time_budget_s']}s total",
        "",
        "> This is bounded systematic exploration, **not** a formal proof. "
        "`BUDGET_EXHAUSTED` is not `PASS`.",
        "",
        "| program | status | runs | outcomes | violations | min prefix | replay |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for program in summary["programs"]:
        witness = program.get("witness") or {}
        prefix = witness.get("minimized_prefix")
        if witness:
            replay_text = "ok" if witness.get("replay", {}).get("matches") else "FAIL"
        else:
            outcome_witnesses = [
                item["witness"] for item in program["outcomes"] if "witness" in item
            ]
            replay_text = (
                "ok" if outcome_witnesses
                and all(item["replay"].get("matches") for item in outcome_witnesses)
                else ("n/a" if not outcome_witnesses else "FAIL")
            )
        lines.append(
            f"| {program['id']} | {program['status']} | {program['runs']} | "
            f"{len(program['outcomes'])} | {program['violation_count']} | "
            f"{prefix if prefix is not None else '-'} | {replay_text} |"
        )
    lines += [
        "",
        f"- Programs: {summary['totals']['programs']}",
        f"- Runs: {summary['totals']['runs']}",
        f"- Violations: {summary['totals']['violations']}",
        f"- Budget exhausted: {summary['totals']['budget_exhausted']}",
        f"- Invalid prefixes (skipped): {summary['totals']['invalid_prefixes']}",
        f"- Thread leaks: {summary['totals']['thread_leaks']}",
        f"- Replay failures: {summary['totals']['replay_failures']}",
        "",
        "## Outcome classes",
        "",
    ]
    for program in summary["programs"]:
        lines.append(f"### {program['id']}")
        for item in program["outcomes"]:
            stdout = item["stdout"].replace("\n", "\\n")
            lines.append(
                f"- exit={item['exit_code']} stdout=`{stdout}` count={item['count']} "
                f"first_prefix={item['first_prefix']}"
            )
        for violation in program["violations"]:
            lines.append(
                f"- VIOLATION exit={violation['exit_code']} "
                f"minimized_prefix={violation['minimized_prefix']}"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def build_summary(
    results: list[dict[str, Any]],
    *,
    mutant: str,
    max_runs: int,
    max_decisions: int,
    time_budget: float,
    elapsed: float,
) -> dict[str, Any]:
    totals = {
        "programs": len(results),
        "runs": sum(item["runs"] for item in results),
        "violations": sum(item["violation_count"] for item in results),
        "budget_exhausted": sum(1 for item in results if item["status"] == "BUDGET_EXHAUSTED"),
        "invalid_prefixes": sum(item["invalid_prefixes"] for item in results),
        "thread_leaks": sum(len(item["thread_leaks"]) for item in results),
        "replay_failures": sum(item["replay_failures"] for item in results),
    }
    return {
        "schema": SCHEMA,
        "schema_version": 1,
        "generated_at_utc": _now(),
        "tool": TOOL_NAME,
        "mode": {
            "mutant": mutant,
            "max_runs": max_runs,
            "max_decisions": max_decisions,
            "time_budget_s": time_budget,
            "elapsed_s": round(elapsed, 3),
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": sys.platform,
        },
        "programs": results,
        "totals": totals,
        "all_pass": totals["violations"] == 0 and totals["budget_exhausted"] == 0
        and totals["thread_leaks"] == 0 and totals["replay_failures"] == 0,
    }


# ---------------------------------------------------------------------------
# Driver.
# ---------------------------------------------------------------------------
def check_program(
    context: ProgramContext,
    *,
    mutant: str,
    max_runs: int,
    max_decisions: int,
    deadline: float,
    out_dir: Path,
    witness_limit: int,
) -> dict[str, Any]:
    exploration = explore(
        context,
        max_runs=max_runs,
        max_decisions=max_decisions,
        deadline=deadline,
    )
    program_dir = out_dir / "witnesses" / context.model["id"]
    outcomes: list[dict[str, Any]] = []
    for index, entry in enumerate(exploration["outcomes"].values()):
        item = {
            "exit_code": entry["exit_code"],
            "stdout": entry["stdout"],
            "stderr": entry["stderr"],
            "count": entry["count"],
            "first_prefix": entry["first_prefix"],
        }
        if index < witness_limit:
            trace_path = program_dir / f"outcome-{index + 1}-trace.json"
            write_trace(context, entry["result"], trace_path)
            replay = replay_trace(context, trace_path, mutant)
            replay["expected_exit_code"] = entry["exit_code"]
            replay["expected_stdout_sha256"] = _sha(entry["result"].stdout)
            replay["matches"] = (
                replay.get("exit_code") == entry["exit_code"]
                and replay.get("stdout_sha256") == _sha(entry["result"].stdout)
            )
            item["witness"] = {
                "trace": _display_path(trace_path),
                "replay": replay,
            }
        outcomes.append(item)

    replay_failures = 0
    for item in outcomes:
        replay = (item.get("witness") or {}).get("replay") or {}
        if "matches" in replay and not replay["matches"]:
            replay_failures += 1
    violations: list[dict[str, Any]] = []
    witness: dict[str, Any] | None = None
    for index, record in enumerate(exploration["violations"]):
        minimized, minimized_result = minimize(context, record["prefix"], deadline)
        trace_path = program_dir / f"violation-{index + 1}-trace.json"
        write_trace(context, minimized_result, trace_path)
        replay = replay_trace(context, trace_path, mutant)
        replay["matches"] = (
            replay.get("exit_code") == minimized_result.exit_code
            and replay.get("stdout_sha256") == _sha(minimized_result.stdout)
        )
        violation = {
            "exit_code": minimized_result.exit_code,
            "stdout": minimized_result.stdout.decode("utf-8", "replace"),
            "stderr": minimized_result.stderr.decode("utf-8", "replace"),
            "original_prefix": record["prefix"],
            "minimized_prefix": minimized,
            "trace": _display_path(trace_path),
            "replay": replay,
        }
        violations.append(violation)
        if not replay.get("matches"):
            replay_failures += 1
        if witness is None:
            witness = {
                "minimized_prefix": minimized,
                "original_prefix": record["prefix"],
                "trace": violation["trace"],
                "replay": replay,
            }

    return {
        "id": context.model["id"],
        "program": context.display_path,
        "model": _display_path(context.model_path),
        "spec_refs": context.model.get("spec_refs", []),
        "tags": context.model.get("tags", []),
        "status": exploration["status"],
        "runs": exploration["runs"],
        "prefixes_discovered": exploration["prefixes_discovered"],
        "queued_when_stopped": exploration["queued_when_stopped"],
        "invalid_prefixes": exploration["invalid_prefixes"],
        "decision_points": exploration["decision_points"],
        "max_depth": exploration["max_depth"],
        "depth_limit": exploration["depth_limit"],
        "outcomes": outcomes,
        "violations": violations,
        "violation_count": exploration["violation_count"],
        "replay_failures": replay_failures,
        "thread_leaks": exploration["thread_leaks"],
        "seconds": exploration["seconds"],
        "witness": witness,
    }


def discover_programs(corpus: Path) -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    for program in sorted(corpus.glob("*.lwt")):
        model = program.with_name(program.stem + ".model.json")
        if not model.exists():
            raise ValueError(f"{program}: missing model sidecar {model.name}")
        pairs.append((program, model))
    if not pairs:
        raise ValueError(f"{corpus}: no *.lwt programs found")
    return pairs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--corpus", help="directory of *.lwt + *.model.json")
    source.add_argument("--program", help="single program (model must be <stem>.model.json)")
    parser.add_argument("--max-runs", type=int, default=500, help="runs per program")
    parser.add_argument("--max-decisions", type=int, default=30, help="forced prefix depth cap")
    parser.add_argument("--time-budget", type=float, default=60.0, help="total wall-clock budget (s)")
    parser.add_argument("--mutant", choices=("none", "duplicate-delivery"), default="none")
    parser.add_argument("--require-clean", action="store_true",
                        help="fail if any violation, budget exhaustion or thread leak")
    parser.add_argument("--expect-violation", action="store_true",
                        help="tool succeeds iff at least one violation is found (mutant self-test)")
    parser.add_argument("--witness-limit", type=int, default=4,
                        help="max outcome traces written per program")
    parser.add_argument("--out", required=True, help="output directory")
    args = parser.parse_args(argv)

    if args.max_runs < 1 or args.max_decisions < 1 or args.time_budget <= 0:
        print("model-check: budgets must be positive", file=sys.stderr)
        return 2

    if args.corpus:
        corpus = Path(args.corpus)
        if not corpus.is_absolute():
            corpus = REPO_ROOT / corpus
        try:
            pairs = discover_programs(corpus)
        except ValueError as error:
            print(f"model-check: {error}", file=sys.stderr)
            return 2
    else:
        program = Path(args.program)
        if not program.is_absolute():
            program = REPO_ROOT / program
        model = program.with_name(program.stem + ".model.json")
        if not model.exists():
            print(f"model-check: missing model sidecar {model.name}", file=sys.stderr)
            return 2
        pairs = [(program, model)]

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    deadline = started + args.time_budget
    results: list[dict[str, Any]] = []
    tool_error: str | None = None

    mutant_context = DuplicateDeliveryMutant() if args.mutant == "duplicate-delivery" else None
    try:
        if mutant_context is not None:
            mutant_context.__enter__()
        for program_path, model_path in pairs:
            context = load_context(program_path, model_path)
            results.append(
                check_program(
                    context,
                    mutant=args.mutant,
                    max_runs=args.max_runs,
                    max_decisions=args.max_decisions,
                    deadline=deadline,
                    out_dir=out_dir,
                    witness_limit=args.witness_limit,
                )
            )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        tool_error = str(error)
    finally:
        if mutant_context is not None:
            mutant_context.__exit__(None, None, None)

    elapsed = time.monotonic() - started
    summary = build_summary(
        results,
        mutant=args.mutant,
        max_runs=args.max_runs,
        max_decisions=args.max_decisions,
        time_budget=args.time_budget,
        elapsed=elapsed,
    )
    if tool_error is not None:
        summary["tool_error"] = tool_error

    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (out_dir / "summary.md").write_text(render_markdown(summary), encoding="utf-8", newline="\n")

    totals = summary["totals"]
    print(
        f"model-check: mutant={args.mutant} programs={totals['programs']} runs={totals['runs']} "
        f"violations={totals['violations']} budget_exhausted={totals['budget_exhausted']} "
        f"invalid_prefixes={totals['invalid_prefixes']} thread_leaks={totals['thread_leaks']} "
        f"replay_failures={totals['replay_failures']} "
        f"elapsed={elapsed:.2f}s"
    )
    for program in results:
        witness = program.get("witness") or {}
        print(
            f"  {program['id']}: {program['status']} runs={program['runs']} "
            f"outcomes={len(program['outcomes'])} violations={program['violation_count']} "
            f"min_prefix={witness.get('minimized_prefix')}"
        )

    if tool_error is not None:
        print(f"model-check: tool error: {tool_error}", file=sys.stderr)
        return 1
    if args.expect_violation:
        any_violation = totals["violations"] >= 1
        replays_ok = totals["replay_failures"] == 0 and all(
            violation["replay"].get("matches")
            for program in results
            for violation in program["violations"]
        )
        return 0 if (any_violation and replays_ok) else 1
    if args.require_clean:
        clean = (
            totals["violations"] == 0
            and totals["budget_exhausted"] == 0
            and totals["thread_leaks"] == 0
            and totals["replay_failures"] == 0
        )
        return 0 if clean else 1
    return 0 if totals["thread_leaks"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
