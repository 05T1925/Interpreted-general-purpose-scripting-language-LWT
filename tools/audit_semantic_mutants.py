"""Run a small, explicit semantic-mutant audit in disposable project copies.

Each probe first runs its selected existing black-box case on a correct copy,
then applies one unique runtime source patch in a separate temporary copy and
runs the same case through the copied project runner and public LWT CLI.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_RELATIVE = Path("lwt") / "runtime.py"
RUNNER_RELATIVE = Path("tools") / "run_tests.py"
TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class Probe:
    name: str
    target_ids: tuple[str, ...]
    patch_note: str
    old: str
    new: str


PROBES = (
    Probe(
        "division-truncates-toward-zero",
        ("negative-floor-division-modulo",),
        "Replace floor division with truncation toward zero.",
        "if operator is TokenKind.SLASH:\n            return left // right",
        "if operator is TokenKind.SLASH:\n"
        "            return (abs(left) // abs(right)) * (1 if (left < 0) == (right < 0) else -1)",
    ),
    Probe(
        "modulo-loses-divisor-sign",
        ("negative-floor-division-modulo",),
        "Return a nonnegative magnitude remainder for every divisor sign.",
        "return left % right",
        "return abs(left) % abs(right)",
    ),
    Probe(
        "and-evaluates-skipped-right-side",
        ("short-circuit-and",),
        "Remove the false-left early return for and.",
        "if not left:\n                return False",
        "if False and not left:\n                return False",
    ),
    Probe(
        "or-evaluates-skipped-right-side",
        ("short-circuit-or",),
        "Remove the true-left early return for or.",
        "if left:\n                return True",
        "if False and left:\n                return True",
    ),
    Probe(
        "composite-values-use-structural-equality",
        ("arrays-identity-equality", "record-instance-identity"),
        "Use list value equality and record type/field equality instead of object identity.",
        "elif type(left) is list or isinstance(left, (_RecordValue, _ErrorValue)):\n"
        "            # Never invoke Python's recursive container/record equality.\n"
        "            equal = left is right",
        "elif type(left) is list:\n"
        "            # Probe mutation: lists use structural equality.\n"
        "            equal = left == right\n"
        "        elif isinstance(left, _RecordValue):\n"
        "            # Probe mutation: records use structural equality.\n"
        "            equal = left.type_name == right.type_name and left.fields == right.fields\n"
        "        elif isinstance(left, _ErrorValue):\n"
        "            equal = left is right",
    ),
    Probe(
        "each-iterates-live-array",
        ("each-snapshot-replacement",),
        "Iterate the mutable source array directly instead of an entry snapshot.",
        "snapshot = list(iterable)",
        "snapshot = iterable",
    ),
    Probe(
        "call-arguments-evaluate-right-to-left",
        ("argument-evaluation-order",),
        "Evaluate user-call arguments in reversed source order.",
        "# Both user and built-in calls evaluate all arguments left-to-right\n"
        "        # before checking arity, once the callee has been found.\n"
        "        arguments = [\n"
        "            _evaluate(argument, environment, runtime)\n"
        "            for argument in expression.arguments\n"
        "        ]",
        "# Both user and built-in calls evaluate all arguments left-to-right\n"
        "        # before checking arity, once the callee has been found.\n"
        "        arguments = [\n"
        "            _evaluate(argument, environment, runtime)\n"
        "            for argument in reversed(expression.arguments)\n"
        "        ]",
    ),
    Probe(
        "call-arguments-reversed-distinct-effects",
        ("argument-evaluation-order-distinct-effects",),
        "Evaluate arguments with distinct logged effects in reversed source order.",
        "# Both user and built-in calls evaluate all arguments left-to-right\n"
        "        # before checking arity, once the callee has been found.\n"
        "        arguments = [\n"
        "            _evaluate(argument, environment, runtime)\n"
        "            for argument in expression.arguments\n"
        "        ]",
        "# Both user and built-in calls evaluate all arguments left-to-right\n"
        "        # before checking arity, once the callee has been found.\n"
        "        arguments = [\n"
        "            _evaluate(argument, environment, runtime)\n"
        "            for argument in reversed(expression.arguments)\n"
        "        ]",
    ),
    Probe(
        "and-accepts-host-truthiness",
        ("boolean-left-is-strict",),
        "Skip the strict boolean type check for the left and operand.",
        "if expression.operator is TokenKind.AND:\n"
        "            if type(left) is not bool:\n"
        "                _runtime_error(\"'and' requires boolean operands\", expression.operator_location)",
        "if expression.operator is TokenKind.AND:",
    ),
    Probe(
        "len-counts-utf8-bytes",
        ("len-unicode-codepoints",),
        "Count UTF-8 bytes rather than Unicode code points for strings.",
        "if type(value) is str or type(value) is list:\n"
        "            return len(value)",
        "if type(value) is str:\n"
        "            return len(value.encode(\"utf-8\"))\n"
        "        if type(value) is list:\n"
        "            return len(value)",
    ),
)


def _load_runner(root: Path) -> ModuleType:
    runner_path = root / RUNNER_RELATIVE
    module_name = f"_s23_runner_{hashlib.sha1(str(root).encode('utf-8')).hexdigest()[:12]}"
    spec = importlib.util.spec_from_file_location(module_name, runner_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load temporary project runner: {runner_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    return module


def _copy_minimal_project(destination: Path, case_sources: dict[str, Path]) -> None:
    destination.mkdir(parents=True)
    shutil.copytree(
        REPO_ROOT / "lwt",
        destination / "lwt",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    runner_target = destination / RUNNER_RELATIVE
    runner_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / RUNNER_RELATIVE, runner_target)
    for case_id, source in case_sources.items():
        relative_source = source.relative_to(REPO_ROOT / "tests" / "cases")
        source_target = destination / "tests" / "cases" / relative_source
        source_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, source_target)
        metadata_target = source_target.with_suffix(".json")
        shutil.copy2(source.with_suffix(".json"), metadata_target)


def _verify_runtime_import(root: Path) -> tuple[bool, str]:
    command = [
        sys.executable,
        "-c",
        "import lwt.runtime; print(lwt.runtime.__file__)",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=TIMEOUT_SECONDS,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, f"import-path verification failed: {error}"
    if completed.returncode != 0:
        return False, f"import-path verification exited {completed.returncode}: {completed.stderr!r}"
    try:
        imported_path = Path(completed.stdout.decode("utf-8").strip()).resolve()
        expected_root = (root / "lwt").resolve()
        imported_path.relative_to(expected_root)
    except (UnicodeError, ValueError, OSError):
        return False, f"runtime import escaped temporary copy: {completed.stdout!r}"
    return True, str(imported_path)


def _run_cases(root: Path, case_ids: tuple[str, ...]) -> tuple[bool, list[object], str]:
    runner = _load_runner(root)
    cases = runner.discover_cases(root / "tests" / "cases")
    selected = [case for case in cases if case.case_id in set(case_ids)]
    found = {case.case_id for case in selected}
    if found != set(case_ids):
        return False, [], f"target case inventory mismatch: expected={case_ids!r}, found={sorted(found)!r}"
    results = [runner.run_case(case) for case in selected]
    return True, results, ""


def _patch_runtime(root: Path, probe: Probe) -> tuple[bool, str]:
    runtime_path = root / RUNTIME_RELATIVE
    original = runtime_path.read_text(encoding="utf-8")
    matches = original.count(probe.old)
    if matches != 1:
        return False, f"patch target must occur once; found {matches}"
    mutated = original.replace(probe.old, probe.new, 1)
    if mutated == original or probe.new not in mutated:
        return False, "patch did not change runtime source"
    runtime_path.write_text(mutated, encoding="utf-8", newline="")
    return True, hashlib.sha256(mutated.encode("utf-8")).hexdigest()


def _result_summary(results: list[object]) -> str:
    return "; ".join(
        f"{result.case.case_id}: exit={result.actual_exit_code!r} "
        f"stdout={result.actual_stdout!r} stderr={result.actual_stderr!r}"
        for result in results
    )


def audit_probe(probe: Probe) -> tuple[str, str]:
    original_runner = _load_runner(REPO_ROOT)
    inventory = original_runner.discover_cases()
    case_sources = {
        case.case_id: case.source
        for case in inventory
        if case.case_id in set(probe.target_ids)
    }
    if set(case_sources) != set(probe.target_ids):
        return "invalid", "one or more target case IDs are absent from the original inventory"

    with tempfile.TemporaryDirectory(prefix="lwt-s23-mutant-audit-") as temporary:
        temporary_root = Path(temporary)
        baseline_root = temporary_root / "baseline-project"
        mutant_root = temporary_root / "mutant-project"
        _copy_minimal_project(baseline_root, case_sources)
        _copy_minimal_project(mutant_root, case_sources)

        baseline_import_ok, baseline_import = _verify_runtime_import(baseline_root)
        mutant_import_ok, mutant_import = _verify_runtime_import(mutant_root)
        if not baseline_import_ok or not mutant_import_ok:
            return "invalid", f"temporary import verification failed: baseline={baseline_import}; mutant={mutant_import}"

        baseline_inventory_ok, baseline_results, baseline_error = _run_cases(
            baseline_root, probe.target_ids
        )
        if not baseline_inventory_ok:
            return "invalid", baseline_error
        baseline_failures = [result for result in baseline_results if result.failures]
        if baseline_failures:
            return "invalid", "correct-copy target failed: " + _result_summary(baseline_failures)

        patch_ok, patch_evidence = _patch_runtime(mutant_root, probe)
        if not patch_ok:
            return "invalid", patch_evidence

        mutant_inventory_ok, mutant_results, mutant_error = _run_cases(
            mutant_root, probe.target_ids
        )
        if not mutant_inventory_ok:
            return "invalid", mutant_error
        if not any(result.failures for result in mutant_results):
            return "survived", (
                f"patch_sha256={patch_evidence}; runtime_import={mutant_import}; "
                f"mutant_results={_result_summary(mutant_results)}"
            )

        failed_results = [result for result in mutant_results if result.failures]
        if any(
            b"Traceback (most recent call last)" in result.actual_stderr
            or b"ModuleNotFoundError" in result.actual_stderr
            for result in failed_results
        ):
            return "invalid", (
                f"mutant produced an unrelated host/import failure; patch_sha256={patch_evidence}; "
                f"results={_result_summary(failed_results)}"
            )
        return "killed", (
            f"correct baseline passed; patch_sha256={patch_evidence}; runtime_import={mutant_import}; "
            f"mutant_results={_result_summary(failed_results)}"
        )


def main() -> int:
    totals = {status: 0 for status in ("killed", "survived", "equivalent", "invalid")}
    for probe in PROBES:
        status, evidence = audit_probe(probe)
        totals[status] += 1
        print(f"[{status.upper()}] {probe.name}")
        print(f"  targets={','.join(probe.target_ids)}")
        print(f"  mutation={probe.patch_note}")
        print(f"  evidence={evidence}")
    print(
        "probe-summary: "
        + " ".join(f"{status}={totals[status]}" for status in totals)
        + f" total={len(PROBES)}"
    )
    return 0 if totals["invalid"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
