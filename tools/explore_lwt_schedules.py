"""S43 WP5: explore deterministic schedules across seeds and retain witnesses.

Runs one LWT program under many ``random:SEED`` policies, groups outcomes by
(exit_code, stdout sha256), and writes a machine-readable ``explore.json`` plus
one replayable schedule trace per distinct outcome class. This implements the
"divergence -> witness -> replay" method (S38/S40/S41) for concurrency.

Usage::

    python tools/explore_lwt_schedules.py --program PATH --seeds 1..200 --out DIR

The tool uses the public CLI only and never evaluates LWT source with Python
eval/exec. Trace files are written with ``--schedule-log`` by re-running the
program under the seed that first produced each outcome class.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "lwt-s42-explore/1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parse_seeds(spec: str) -> list[int]:
    match = re.fullmatch(r"(\d+)\.\.(\d+)", spec)
    if not match:
        raise ValueError(f"--seeds must be like 1..200, got {spec!r}")
    start, end = int(match.group(1)), int(match.group(2))
    if end < start or end - start > 10000:
        raise ValueError("--seeds range must be ordered and at most 10000 wide")
    return list(range(start, end + 1))


def _run(program: str, seed: int, trace: Path | None, timeout: float) -> dict[str, Any]:
    schedule = f"random:{seed}"
    command = [sys.executable, "-m", "lwt", f"--schedule={schedule}"]
    if trace is not None:
        command.append(f"--schedule-log={trace.as_posix()}")
    command.append(program)
    result = subprocess.run(
        command, cwd=REPO_ROOT, capture_output=True, timeout=timeout, check=False,
    )
    return {
        "seed": seed,
        "policy": schedule,
        "exit_code": result.returncode,
        "stdout_sha256": _sha256(result.stdout),
        "stderr_sha256": _sha256(result.stderr),
        "stdout_len": len(result.stdout),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--program", required=True, help="LWT source path (repo-relative or absolute)")
    parser.add_argument("--seeds", required=True, help="inclusive range like 1..200")
    parser.add_argument("--out", required=True, help="output directory (new/overwritten evidence)")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--policy", default="random:", help="policy prefix (currently random:SEED)")
    args = parser.parse_args(argv)

    try:
        seeds = _parse_seeds(args.seeds)
    except ValueError as error:
        print(f"explore: {error}", file=sys.stderr)
        return 4

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    runs: list[dict[str, Any]] = []
    classes: dict[tuple[int, str], dict[str, Any]] = {}
    for seed in seeds:
        record = _run(args.program, seed, None, args.timeout)
        runs.append(record)
        key = (record["exit_code"], record["stdout_sha256"])
        if key not in classes:
            classes[key] = {
                "exit_code": record["exit_code"],
                "stdout_sha256": record["stdout_sha256"],
                "first_seed": seed,
                "seed_count": 0,
                "example_stdout_len": record["stdout_len"],
            }
        classes[key]["seed_count"] += 1

    # For each outcome class, capture a replayable trace using its first seed.
    witnesses: list[dict[str, Any]] = []
    for index, ((exit_code, digest), info) in enumerate(sorted(classes.items()), 1):
        seed = info["first_seed"]
        trace = out_dir / f"trace-{index}.json"
        reproduced = _run(args.program, seed, trace, args.timeout)
        witnesses.append({
            "class_index": index,
            "exit_code": exit_code,
            "stdout_sha256": digest,
            "seed": seed,
            "seed_count": info["seed_count"],
            "trace": trace.relative_to(REPO_ROOT).as_posix() if trace.is_relative_to(REPO_ROOT) else str(trace),
            "reproduced": reproduced["exit_code"] == exit_code and reproduced["stdout_sha256"] == digest,
            "replay_command": (
                f"python -m lwt --schedule-replay={trace.as_posix()} {args.program}"
            ),
        })

    document = {
        "schema": SCHEMA,
        "schema_version": 1,
        "generated_at_utc": _now(),
        "program": args.program,
        "seeds": {"from": seeds[0], "to": seeds[-1], "count": len(seeds)},
        "class_count": len(classes),
        "outcome_classes": sorted(
            ({"exit_code": k[0], "stdout_sha256": k[1], "seed_count": v["seed_count"]}
             for k, v in classes.items()),
            key=lambda item: (item["exit_code"], item["stdout_sha256"]),
        ),
        "witnesses": witnesses,
        "runs": runs,
    }
    explore_path = out_dir / "explore.json"
    explore_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(f"explore: {len(seeds)} seeds -> {len(classes)} classes -> {out_dir}")
    for witness in witnesses:
        print(f"  class {witness['class_index']}: exit={witness['exit_code']} "
              f"stdout_sha256={witness['stdout_sha256'][:12]} "
              f"seed={witness['seed']} count={witness['seed_count']} "
              f"trace={witness['trace']} reproduced={witness['reproduced']}")
    return 0 if all(w["reproduced"] for w in witnesses) else 1


if __name__ == "__main__":
    raise SystemExit(main())
