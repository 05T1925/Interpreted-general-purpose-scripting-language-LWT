"""Run the LWT black-box suite through its public ``python -m lwt`` CLI."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import difflib
import argparse
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_ROOT = REPO_ROOT / "tests" / "cases"
DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_TIMEOUT_SECONDS = 30.0
CASE_ID_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
VALID_SPEC_REFS = frozenset(
    {
        "1", "2", "2.1", "2.2", "3", "4", "4.1", "4.2", "4.3",
        "5", "6", "7", "8", "9", "10",
    }
)


class ConfigurationError(Exception):
    """A test inventory or metadata error that prevents a trustworthy run."""


@dataclass(frozen=True)
class TestCase:
    case_id: str
    category: str
    source: Path
    spec_refs: tuple[str, ...]
    tags: tuple[str, ...]
    args: tuple[str, ...]
    stdin: bytes
    expected_exit_code: int
    expected_stdout: bytes
    expected_stderr: bytes
    timeout_seconds: float
    cli_args_override: tuple[str, ...] | None


@dataclass(frozen=True)
class TestResult:
    case: TestCase
    status: str
    failure_kind: str | None
    failures: tuple[str, ...]
    actual_exit_code: int | None
    actual_stdout: bytes
    actual_stderr: bytes
    elapsed_seconds: float
    raw_stdout: bytes | None = None
    raw_stderr: bytes | None = None


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ConfigurationError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _require_string(value: Any, label: str, *, nonempty: bool = False) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        qualifier = "a non-empty string" if nonempty else "a string"
        raise ConfigurationError(f"{label} must be {qualifier}")
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise ConfigurationError(f"{label} is not valid Unicode text") from error
    return value


def _string_list(value: Any, label: str, *, nonempty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (nonempty and not value):
        qualifier = "a non-empty array" if nonempty else "an array"
        raise ConfigurationError(f"{label} must be {qualifier} of strings")
    items = tuple(_require_string(item, f"{label}[{index}]") for index, item in enumerate(value))
    if nonempty and any(not item for item in items):
        raise ConfigurationError(f"{label} entries must not be empty")
    return items


def _load_stdin(value: Any) -> bytes:
    if not isinstance(value, dict):
        raise ConfigurationError("stdin must be an object with exactly one of 'text' or 'base64'")
    if set(value) == {"text"}:
        return _require_string(value["text"], "stdin.text").encode("utf-8")
    if set(value) == {"base64"}:
        encoded = _require_string(value["base64"], "stdin.base64")
        try:
            return base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ConfigurationError(f"stdin.base64 is invalid: {error}") from error
    raise ConfigurationError("stdin must contain exactly one of 'text' or 'base64'")


def _load_metadata(metadata_path: Path, source_path: Path, category: str) -> TestCase:
    try:
        raw_text = metadata_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ConfigurationError(f"cannot read metadata: {error}") from error
    try:
        metadata = json.loads(raw_text, object_pairs_hook=_reject_duplicate_json_keys)
    except ConfigurationError:
        raise
    except (json.JSONDecodeError, UnicodeError) as error:
        raise ConfigurationError(f"invalid JSON: {error}") from error

    if not isinstance(metadata, dict):
        raise ConfigurationError("top-level JSON value must be an object")
    required = {"id", "spec_refs", "args", "stdin", "expected"}
    optional = {"tags", "timeout_seconds", "cli_args_override"}
    missing = sorted(required - set(metadata))
    unknown = sorted(set(metadata) - required - optional)
    if missing:
        raise ConfigurationError(f"missing required fields: {', '.join(missing)}")
    if unknown:
        raise ConfigurationError(f"unknown fields: {', '.join(unknown)}")

    case_id = _require_string(metadata["id"], "id", nonempty=True)
    if not CASE_ID_RE.fullmatch(case_id):
        raise ConfigurationError("id must match [a-z0-9]+(?:-[a-z0-9]+)*")

    spec_refs = _string_list(metadata["spec_refs"], "spec_refs", nonempty=True)
    if len(set(spec_refs)) != len(spec_refs):
        raise ConfigurationError("spec_refs entries must be unique")
    if any(ref not in VALID_SPEC_REFS for ref in spec_refs):
        raise ConfigurationError("spec_refs entries must name an existing language-spec section, such as '4.2'")

    args = _string_list(metadata["args"], "args")
    tags = _string_list(metadata.get("tags", []), "tags")
    if len(set(tags)) != len(tags):
        raise ConfigurationError("tags entries must be unique")
    stdin = _load_stdin(metadata["stdin"])

    expected = metadata["expected"]
    if not isinstance(expected, dict):
        raise ConfigurationError("expected must be an object")
    expected_keys = {"exit_code", "stdout", "stderr"}
    if set(expected) != expected_keys:
        missing_expected = sorted(expected_keys - set(expected))
        unknown_expected = sorted(set(expected) - expected_keys)
        details = []
        if missing_expected:
            details.append(f"missing: {', '.join(missing_expected)}")
        if unknown_expected:
            details.append(f"unknown: {', '.join(unknown_expected)}")
        raise ConfigurationError("expected fields must be exactly exit_code, stdout, stderr (" + "; ".join(details) + ")")
    expected_exit_code = expected["exit_code"]
    if type(expected_exit_code) is not int or not 0 <= expected_exit_code <= 255:
        raise ConfigurationError("expected.exit_code must be an integer from 0 through 255")
    expected_stdout = _require_string(expected["stdout"], "expected.stdout").encode("utf-8")
    expected_stderr = _require_string(expected["stderr"], "expected.stderr").encode("utf-8")

    timeout = metadata.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise ConfigurationError("timeout_seconds must be a finite number greater than 0 and at most 30")
    timeout = float(timeout)
    if not math.isfinite(timeout) or not 0 < timeout <= MAX_TIMEOUT_SECONDS:
        raise ConfigurationError("timeout_seconds must be a finite number greater than 0 and at most 30")

    override: tuple[str, ...] | None = None
    if "cli_args_override" in metadata:
        override = _string_list(metadata["cli_args_override"], "cli_args_override")
        if args:
            raise ConfigurationError("cli_args_override cannot be combined with non-empty args")

    return TestCase(
        case_id=case_id,
        category=category,
        source=source_path,
        spec_refs=spec_refs,
        tags=tags,
        args=args,
        stdin=stdin,
        expected_exit_code=expected_exit_code,
        expected_stdout=expected_stdout,
        expected_stderr=expected_stderr,
        timeout_seconds=timeout,
        cli_args_override=override,
    )


def discover_cases(case_root: Path = CASE_ROOT) -> list[TestCase]:
    """Validate all case pairs and metadata before returning stable case order."""

    root = case_root.resolve()
    if not root.is_dir():
        raise ConfigurationError(f"case directory does not exist: {root}")

    files: list[Path] = []

    def raise_walk_error(error: OSError) -> None:
        raise ConfigurationError(f"cannot inspect case directory: {error}") from error

    for current, directories, filenames in os.walk(root, onerror=raise_walk_error):
        current_path = Path(current)
        for directory in directories:
            if (current_path / directory).is_symlink():
                raise ConfigurationError(
                    f"symbolic links are not allowed in case directories: "
                    f"{(current_path / directory).relative_to(root).as_posix()}"
                )
        if "fixtures" in directories:
            directories.remove("fixtures")
        directories.sort()
        for filename in sorted(filenames):
            path = current_path / filename
            if path.is_symlink():
                raise ConfigurationError(f"symbolic links are not allowed in case directories: {path.relative_to(root).as_posix()}")
            if path.suffix not in {".lwt", ".json"}:
                raise ConfigurationError(f"unexpected file in case directory: {path.relative_to(root).as_posix()}")
            files.append(path)

    by_stem: dict[Path, dict[str, Path]] = {}
    for path in files:
        key = path.relative_to(root).with_suffix("")
        by_stem.setdefault(key, {})[path.suffix] = path

    problems: list[str] = []
    for key, pair in sorted(by_stem.items(), key=lambda item: item[0].as_posix()):
        if len(key.parts) < 2:
            problems.append(f"{key.as_posix()}: cases must be inside a named category directory")
            continue
        if set(pair) != {".lwt", ".json"}:
            missing = ".json" if ".lwt" in pair else ".lwt"
            problems.append(f"{key.as_posix()}{missing}: missing pair")
    if problems:
        raise ConfigurationError("case pair errors:\n  " + "\n  ".join(problems))

    cases: list[TestCase] = []
    seen_ids: dict[str, str] = {}
    for key in sorted(by_stem, key=lambda item: item.as_posix()):
        pair = by_stem[key]
        relative_source = key.with_suffix(".lwt")
        category = key.parts[0] if len(key.parts) > 1 else "uncategorized"
        metadata_path = pair[".json"]
        try:
            case = _load_metadata(metadata_path, pair[".lwt"], category)
        except ConfigurationError as error:
            problems.append(f"{key.as_posix()}.json: {error}")
            continue
        previous = seen_ids.get(case.case_id)
        if previous is not None:
            problems.append(f"duplicate id {case.case_id!r}: {previous} and {key.as_posix()}.json")
        else:
            seen_ids[case.case_id] = f"{key.as_posix()}.json"
        try:
            pair[".lwt"].read_bytes()
        except OSError as error:
            problems.append(f"{relative_source.as_posix()}: cannot read source: {error}")
            continue
        cases.append(case)

    if problems:
        raise ConfigurationError("test configuration errors:\n  " + "\n  ".join(problems))
    if not cases:
        raise ConfigurationError("no black-box test cases were discovered")
    return cases


def normalize_newlines(data: bytes) -> bytes:
    """Normalize CRLF only; preserve lone CR, spaces, and all other bytes."""

    return data.replace(b"\r\n", b"\n")


def _unified_diff(expected: bytes, actual: bytes, label: str) -> str:
    expected_text = expected.decode("utf-8", errors="backslashreplace").splitlines(keepends=True)
    actual_text = actual.decode("utf-8", errors="backslashreplace").splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(
            expected_text,
            actual_text,
            fromfile=f"expected {label}",
            tofile=f"actual {label}",
        )
    )


def _format_bytes(data: bytes) -> str:
    return repr(data)


def _not_executed_result(case: TestCase, *, status: str = "not_executed") -> TestResult:
    return TestResult(case, status, None, (), None, b"", b"", 0.0)


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
        if process.poll() is None:
            process.kill()
    else:
        try:
            process.send_signal(signal.SIGTERM)
        except OSError:
            process.kill()
        try:
            process.wait(timeout=0.25)
        except subprocess.TimeoutExpired:
            process.kill()


def run_case(
    case: TestCase,
    *,
    cancel_event: threading.Event | None = None,
    on_process_started: Any = None,
) -> TestResult:
    cancellation = cancel_event or threading.Event()
    if cancellation.is_set():
        return _not_executed_result(case, status="cancelled")
    if case.cli_args_override is None:
        source_arg = case.source.relative_to(REPO_ROOT).as_posix()
        command = [sys.executable, "-m", "lwt", source_arg]
        if case.args:
            command.extend(["--", *case.args])
    else:
        command = [sys.executable, "-m", "lwt", *case.cli_args_override]

    started = time.perf_counter()
    options: dict[str, Any] = {}
    if os.name == "nt":
        options["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        process = subprocess.Popen(
            command,
            cwd=REPO_ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            **options,
        )
    except OSError as error:
        elapsed = time.perf_counter() - started
        failures = (
            f"process start failed: {error}",
            "expected: "
            f"exit_code={case.expected_exit_code}, stdout={_format_bytes(case.expected_stdout)}, "
            f"stderr={_format_bytes(case.expected_stderr)}",
            "actual: process did not start; stdout=b'', stderr=b''",
        )
        return TestResult(case, "start_failed", "start_failure", failures, None, b"", b"", elapsed)

    if on_process_started is not None:
        on_process_started(process)

    deadline = started + case.timeout_seconds
    first_communicate = True
    timed_out = False
    cancelled = False
    stdout = b""
    stderr = b""
    while True:
        if cancellation.is_set():
            cancelled = True
            _terminate_process_tree(process)
            stdout, stderr = process.communicate()
            break
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            timed_out = True
            _terminate_process_tree(process)
            stdout, stderr = process.communicate()
            break
        try:
            stdout, stderr = process.communicate(
                input=case.stdin if first_communicate else None,
                timeout=min(0.05, remaining),
            )
            break
        except subprocess.TimeoutExpired:
            first_communicate = False
    elapsed = time.perf_counter() - started

    if cancelled:
        return TestResult(case, "cancelled", None, (), process.returncode, stdout, stderr, elapsed, stdout, stderr)
    if timed_out:
        failures = (
            f"timeout after {case.timeout_seconds:g}s",
            "expected: "
            f"exit_code={case.expected_exit_code}, stdout={_format_bytes(case.expected_stdout)}, "
            f"stderr={_format_bytes(case.expected_stderr)}",
            "actual partial output: "
            f"exit_code=<timeout>, stdout={_format_bytes(stdout)}, stderr={_format_bytes(stderr)}",
        )
        return TestResult(case, "timeout", "timeout", failures, None, stdout, stderr, elapsed, stdout, stderr)

    actual_stdout = normalize_newlines(stdout)
    actual_stderr = normalize_newlines(stderr)
    expected_stdout = normalize_newlines(case.expected_stdout)
    expected_stderr = normalize_newlines(case.expected_stderr)
    failures: list[str] = []

    if process.returncode != case.expected_exit_code:
        failures.append(
            "exit code mismatch: "
            f"expected {case.expected_exit_code}, actual {process.returncode}"
        )
    if actual_stdout != expected_stdout:
        details = _unified_diff(expected_stdout, actual_stdout, "stdout")
        failures.append(
            "stdout mismatch: "
            f"expected {_format_bytes(expected_stdout)}, actual {_format_bytes(actual_stdout)}"
            + ("\n" + details.rstrip("\n") if details else "")
        )
    if actual_stderr != expected_stderr:
        details = _unified_diff(expected_stderr, actual_stderr, "stderr")
        failures.append(
            "stderr mismatch: "
            f"expected {_format_bytes(expected_stderr)}, actual {_format_bytes(actual_stderr)}"
            + ("\n" + details.rstrip("\n") if details else "")
        )

    failure_kind: str | None = None
    if failures:
        failure_kind = "runtime_error" if process.returncode != case.expected_exit_code else "assertion_failure"
    return TestResult(
        case,
        "failed" if failures else "passed",
        failure_kind,
        tuple(failures),
        process.returncode,
        actual_stdout,
        actual_stderr,
        elapsed,
        stdout,
        stderr,
    )


def run_cases(
    cases: list[TestCase],
    cancel_event: threading.Event | None = None,
    *,
    on_process_started: Any = None,
) -> list[TestResult]:
    cancellation = cancel_event or threading.Event()
    results: list[TestResult] = []
    for index, case in enumerate(cases):
        if cancellation.is_set():
            results.extend(_not_executed_result(remaining) for remaining in cases[index:])
            break
        result = run_case(case, cancel_event=cancellation, on_process_started=on_process_started)
        results.append(result)
        if result.status == "cancelled":
            results.extend(_not_executed_result(remaining) for remaining in cases[index + 1 :])
            break
    return results


def case_to_json(case: TestCase) -> dict[str, Any]:
    try:
        case.stdin.decode("utf-8", errors="strict")
        stdin_is_utf8 = True
    except UnicodeDecodeError:
        stdin_is_utf8 = False
    if case.cli_args_override is not None:
        debug_reason = "case uses cli_args_override rather than a standard source entry"
    elif case.expected_exit_code != 0:
        debug_reason = "case expects a non-zero exit code"
    elif not stdin_is_utf8:
        debug_reason = "case stdin is not strict UTF-8"
    else:
        debug_reason = None
    return {
        "id": case.case_id,
        "category": case.category,
        "source": case.source.relative_to(REPO_ROOT).as_posix(),
        "spec_refs": list(case.spec_refs),
        "tags": list(case.tags),
        "args": list(case.args),
        "stdin_base64": base64.b64encode(case.stdin).decode("ascii"),
        "expected": {
            "exit_code": case.expected_exit_code,
            "stdout_base64": base64.b64encode(case.expected_stdout).decode("ascii"),
            "stderr_base64": base64.b64encode(case.expected_stderr).decode("ascii"),
        },
        "timeout_seconds": case.timeout_seconds,
        "cli_args_override": list(case.cli_args_override) if case.cli_args_override is not None else None,
        "debug": {"available": debug_reason is None, "reason": debug_reason},
    }


def result_to_json(result: TestResult) -> dict[str, Any]:
    return {
        **case_to_json(result.case),
        "status": result.status,
        "failure_kind": result.failure_kind,
        "actual": {
            "exit_code": result.actual_exit_code,
            "stdout_base64": base64.b64encode(
                result.raw_stdout if result.raw_stdout is not None else result.actual_stdout
            ).decode("ascii"),
            "stderr_base64": base64.b64encode(
                result.raw_stderr if result.raw_stderr is not None else result.actual_stderr
            ).decode("ascii"),
        },
        "duration_seconds": round(result.elapsed_seconds, 6),
        "differences": list(result.failures),
    }


def inventory_to_json(cases: list[TestCase]) -> dict[str, Any]:
    serialized = [case_to_json(case) for case in cases]
    categories: dict[str, list[str]] = {}
    for case in cases:
        categories.setdefault(case.category, []).append(case.case_id)
    return {
        "schema": "lwt.test-inventory",
        "schema_version": 1,
        "case_count": len(serialized),
        "categories": [
            {"name": name, "case_ids": ids} for name, ids in sorted(categories.items())
        ],
        "cases": serialized,
    }


def results_to_json(results: list[TestResult]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    return {
        "schema": "lwt.test-results",
        "schema_version": 1,
        "status": "cancelled" if any(item.status in {"cancelled", "not_executed"} for item in results) else "completed",
        "summary": {
            "selected": len(results),
            "passed": counts.get("passed", 0),
            "failed": counts.get("failed", 0),
            "timeout": counts.get("timeout", 0),
            "start_failed": counts.get("start_failed", 0),
            "cancelled": counts.get("cancelled", 0),
            "not_executed": counts.get("not_executed", 0),
        },
        "results": [result_to_json(result) for result in results],
    }


def select_cases(
    cases: list[TestCase], case_ids: list[str], categories: list[str]
) -> list[TestCase]:
    if len(case_ids) != len(set(case_ids)):
        raise ConfigurationError("--case IDs must not be repeated")
    if len(categories) != len(set(categories)):
        raise ConfigurationError("--category names must not be repeated")
    known_ids = {case.case_id for case in cases}
    known_categories = {case.category for case in cases}
    unknown_ids = sorted(set(case_ids) - known_ids)
    unknown_categories = sorted(set(categories) - known_categories)
    if unknown_ids:
        raise ConfigurationError(f"unknown case ID(s): {', '.join(unknown_ids)}")
    if unknown_categories:
        raise ConfigurationError(f"unknown category name(s): {', '.join(unknown_categories)}")
    selected = [
        case for case in cases
        if (not case_ids or case.case_id in case_ids)
        and (not categories or case.category in categories)
    ]
    if not selected:
        raise ConfigurationError("selection matched no test cases")
    return selected


def _print_text_results(cases: list[TestCase], started: float, cancel_event: threading.Event | None = None) -> int:
    failed = 0
    category_totals: dict[str, list[int]] = {}
    results = run_cases(cases, cancel_event)
    for result in results:
        category_counts = category_totals.setdefault(result.case.category, [0, 0])
        category_counts[1] += 1
        if result.status != "passed":
            failed += 1
            category_counts[0] += 1
            print(f"[FAIL] {result.case.case_id}")
            for failure in result.failures:
                print(f"  {failure}")
        else:
            print(f"[PASS] {result.case.case_id}")

    elapsed = time.perf_counter() - started
    category_summary = ", ".join(
        f"{name}={counts[1] - counts[0]}/{counts[1]}"
        for name, counts in sorted(category_totals.items())
    ) or "none"
    passed = len(results) - failed
    print(
        f"Black-box tests: passed={passed} failed={failed} total={len(results)}; "
        f"categories (passed/total): {category_summary}; elapsed={elapsed:.3f}s"
    )
    return 130 if any(item.status in {"cancelled", "not_executed"} for item in results) else (1 if failed else 0)


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run LWT public black-box cases.")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--list-json", action="store_true", help="write the validated case inventory as JSON without executing cases")
    modes.add_argument("--format", choices=("text", "json"), default="text", help="select text or versioned JSON results")
    parser.add_argument("--case", action="append", default=[], metavar="ID", help="run one case; may be repeated")
    parser.add_argument("--category", action="append", default=[], metavar="NAME", help="restrict selection to a category; may be repeated")
    return parser


def _configuration_error(message: str) -> int:
    print(f"CONFIGURATION ERROR: {message}", file=sys.stderr)
    return 2


def _write_json_stdout(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    binary_stdout = getattr(sys.stdout, "buffer", None)
    if binary_stdout is not None:
        binary_stdout.write(serialized.encode("utf-8"))
        binary_stdout.flush()
    else:
        # Keep main() directly testable with io.StringIO while real CLI output
        # remains explicitly UTF-8 on Windows and POSIX.
        sys.stdout.write(serialized)


def main(argv: list[str] | None = None) -> int:
    started = time.perf_counter()
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        try:
            cases = discover_cases()
        except ConfigurationError as error:
            return _configuration_error(str(error))
        return _print_text_results(cases, started)

    try:
        options = _argument_parser().parse_args(arguments)
        cases = discover_cases()
        if options.list_json:
            if options.case or options.category:
                raise ConfigurationError("--list-json cannot be combined with --case or --category")
            _write_json_stdout(inventory_to_json(cases))
            return 0
        selected = select_cases(cases, options.case, options.category)
    except ConfigurationError as error:
        return _configuration_error(str(error))
    except SystemExit as error:
        return int(error.code) if isinstance(error.code, int) else 2

    cancellation = threading.Event()
    previous_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, lambda _signum, _frame: cancellation.set())
    try:
        if options.format == "json":
            results = run_cases(selected, cancellation)
            _write_json_stdout(results_to_json(results))
            statuses = {item.status for item in results}
            if statuses & {"cancelled", "not_executed"}:
                return 130
            if statuses & {"failed", "timeout", "start_failed"}:
                return 1
            return 0
        return _print_text_results(selected, started, cancellation)
    finally:
        signal.signal(signal.SIGINT, previous_sigint)


if __name__ == "__main__":
    raise SystemExit(main())
