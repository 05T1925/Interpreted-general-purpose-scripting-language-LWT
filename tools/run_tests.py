"""Run the LWT black-box suite through its public ``python -m lwt`` CLI."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import difflib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_ROOT = REPO_ROOT / "tests" / "cases"
DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_TIMEOUT_SECONDS = 30.0
CASE_ID_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
VALID_SPEC_REFS = frozenset(
    {"1", "2", "2.1", "2.2", "3", "4", "4.1", "4.2", "4.3", "5", "6", "7", "8"}
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
    failures: tuple[str, ...]
    actual_exit_code: int | None
    actual_stdout: bytes
    actual_stderr: bytes
    elapsed_seconds: float


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
        rel_dir = current_path.relative_to(root)
        for directory in directories:
            if (current_path / directory).is_symlink():
                raise ConfigurationError(
                    f"symbolic links are not allowed in case directories: "
                    f"{(current_path / directory).relative_to(root).as_posix()}"
                )
        if not rel_dir.parts and "fixtures" in directories:
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


def run_case(case: TestCase) -> TestResult:
    if case.cli_args_override is None:
        source_arg = case.source.relative_to(REPO_ROOT).as_posix()
        command = [sys.executable, "-m", "lwt", source_arg]
        if case.args:
            command.extend(["--", *case.args])
    else:
        command = [sys.executable, "-m", "lwt", *case.cli_args_override]

    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            input=case.stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=case.timeout_seconds,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired as error:
        elapsed = time.perf_counter() - started
        stdout = error.stdout or b""
        stderr = error.stderr or b""
        if isinstance(stdout, str):
            stdout = stdout.encode("utf-8", errors="backslashreplace")
        if isinstance(stderr, str):
            stderr = stderr.encode("utf-8", errors="backslashreplace")
        failures = (
            f"timeout after {case.timeout_seconds:g}s",
            "expected: "
            f"exit_code={case.expected_exit_code}, stdout={_format_bytes(case.expected_stdout)}, "
            f"stderr={_format_bytes(case.expected_stderr)}",
            "actual partial output: "
            f"exit_code=<timeout>, stdout={_format_bytes(stdout)}, stderr={_format_bytes(stderr)}",
        )
        return TestResult(case, failures, None, stdout, stderr, elapsed)
    except OSError as error:
        elapsed = time.perf_counter() - started
        failures = (
            f"process start failed: {error}",
            "expected: "
            f"exit_code={case.expected_exit_code}, stdout={_format_bytes(case.expected_stdout)}, "
            f"stderr={_format_bytes(case.expected_stderr)}",
            "actual: process did not start; stdout=b'', stderr=b''",
        )
        return TestResult(case, failures, None, b"", b"", elapsed)

    elapsed = time.perf_counter() - started
    actual_stdout = normalize_newlines(completed.stdout)
    actual_stderr = normalize_newlines(completed.stderr)
    expected_stdout = normalize_newlines(case.expected_stdout)
    expected_stderr = normalize_newlines(case.expected_stderr)
    failures: list[str] = []

    if completed.returncode != case.expected_exit_code:
        failures.append(
            "exit code mismatch: "
            f"expected {case.expected_exit_code}, actual {completed.returncode}"
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

    return TestResult(case, tuple(failures), completed.returncode, actual_stdout, actual_stderr, elapsed)


def main() -> int:
    started = time.perf_counter()
    try:
        cases = discover_cases()
    except ConfigurationError as error:
        print(f"CONFIGURATION ERROR: {error}", file=sys.stderr)
        return 2

    failed = 0
    category_totals: dict[str, list[int]] = {}
    for case in cases:
        category_counts = category_totals.setdefault(case.category, [0, 0])
        result = run_case(case)
        category_counts[1] += 1
        if result.failures:
            failed += 1
            category_counts[0] += 1
            print(f"[FAIL] {case.case_id}")
            for failure in result.failures:
                print(f"  {failure}")
        else:
            print(f"[PASS] {case.case_id}")

    elapsed = time.perf_counter() - started
    category_summary = ", ".join(
        f"{name}={counts[1] - counts[0]}/{counts[1]}"
        for name, counts in sorted(category_totals.items())
    ) or "none"
    passed = len(cases) - failed
    print(
        f"Black-box tests: passed={passed} failed={failed} total={len(cases)}; "
        f"categories (passed/total): {category_summary}; elapsed={elapsed:.3f}s"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
