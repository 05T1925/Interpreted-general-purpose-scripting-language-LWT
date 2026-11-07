"""S43 determinism evidence: repeat every concurrency black-box case N times.

Runs each ``tests/cases/concurrency/*.lwt`` case through the public CLI under
the default ``fifo`` policy, N times, and asserts byte-identical stdout, stderr,
and exit code across all repetitions. A single divergent byte fails the run.

This is a new, independent evidence file (``reports/s42-determinism.json``);
it never modifies protected raw data or the black-box protocol.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_ROOT = REPO_ROOT / "tests" / "cases" / "concurrency"
DEFAULT_REPEATS = 10
DEFAULT_TIMEOUT = 20.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run_case(source_rel: str, args: list[str], override: list[str] | None,
              timeout: float) -> dict[str, Any]:
    if override is not None:
        command = [sys.executable, "-m", "lwt", *override]
    else:
        command = [sys.executable, "-m", "lwt", source_rel]
        if args:
            command.extend(["--", *args])
    started = time.perf_counter()
    result = subprocess.run(
        command, cwd=REPO_ROOT, capture_output=True, timeout=timeout, check=False,
    )
    elapsed = (time.perf_counter() - started) * 1000
    return {
        "exit_code": result.returncode,
        "stdout_sha256": _sha256(result.stdout),
        "stderr_sha256": _sha256(result.stderr),
        "stdout_bytes": len(result.stdout),
        "elapsed_ms": round(elapsed, 3),
    }


def _load_case(source: Path) -> tuple[list[str], list[str] | None]:
    metadata = json.loads(source.with_suffix(".json").read_text(encoding="utf-8"))
    args = list(metadata.get("args", []))
    override = metadata.get("cli_args_override")
    return args, list(override) if override is not None else None


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=DEFAULT_REPEATS,
                        help="repetitions per case (default 10)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                        help="per-run timeout in seconds (default 20)")
    parser.add_argument("--out", default="reports/s42-determinism.json",
                        help="output JSON path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _argument_parser().parse_args(argv)
    if args.repeat < 2:
        print("determinism: --repeat must be >= 2", file=sys.stderr)
        return 4
    if not CASE_ROOT.is_dir():
        print(f"determinism: no case directory {CASE_ROOT}", file=sys.stderr)
        return 4

    case_sources = sorted(CASE_ROOT.glob("*.lwt"))
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    for source in case_sources:
        source_rel = source.relative_to(REPO_ROOT).as_posix()
        program_args, override = _load_case(source)
        runs: list[dict[str, Any]] = []
        for _ in range(args.repeat):
            try:
                runs.append(_run_case(source_rel, program_args, override, args.timeout))
            except subprocess.TimeoutExpired:
                failures.append(f"{source_rel}: timed out")
                break
        if len(runs) != args.repeat:
            continue
        signatures = {(r["exit_code"], r["stdout_sha256"], r["stderr_sha256"]) for r in runs}
        stable = len(signatures) == 1
        if not stable:
            failures.append(f"{source_rel}: {len(signatures)} distinct signatures")
        results.append({
            "case": source.stem,
            "source": source_rel,
            "repeats": args.repeat,
            "stable": stable,
            "signature": sorted(signatures)[0] if stable else sorted(signatures),
            "median_elapsed_ms": sorted(r["elapsed_ms"] for r in runs)[len(runs) // 2],
        })

    document = {
        "schema": "lwt-s42-determinism/1",
        "schema_version": 1,
        "generated_at_utc": _now(),
        "git_head": _git_head(),
        "python_version": sys.version,
        "policy": "fifo",
        "repeats": args.repeat,
        "case_count": len(results),
        "all_stable": not failures,
        "failures": failures,
        "cases": results,
    }
    out_path = REPO_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(f"determinism: {len(results)} cases x {args.repeat} runs -> {args.out}; "
          f"stable={not failures}; failures={len(failures)}")
    for failure in failures:
        print("  FAIL", failure)
    return 0 if not failures else 1


def _git_head() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


if __name__ == "__main__":
    raise SystemExit(main())
