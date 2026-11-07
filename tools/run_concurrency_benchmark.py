"""S43 WP6: honest I/O-overlap benchmark for the concurrent log report.

Four groups on the same generated fixture set (N files x size MB):
  * lwt_serial    -- N sequential `python -m lwt app/log_report.lwt -- FILE`
  * lwt_concurrent-- one `python -m lwt app/concurrent_log_report.lwt -- FILES`
  * py_serial     -- one Python process reading/stat-ing files sequentially
  * py_threads    -- one Python process reading them via a thread pool

2 warm-ups + 7 timed runs per group; median and min/max are reported. A
startup/import baseline is measured separately so the I/O+execution portion
can be discussed. The report states the Amdahl upper bound: the single-token
LWT model does NOT parallelize CPU work, so only the I/O-wait fraction can
overlap. No protected raw data (bench/results.json, reports/performance.md)
is read or written; all fixtures are generated in a temp dir and removed.

Usage::

    python tools/run_concurrency_benchmark.py --files 8 --size-mb 2 --repeats 7
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "lwt-s43-concurrency-benchmark/1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _sha256(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def _generate_fixtures(folder: Path, files: int, size_mb: int) -> list[str]:
    """Generate plain-text logs of roughly ``size_mb`` MB each at LF boundaries."""

    line = "2026-11-07T00:00:00Z|INFO|cache|retry token\n"
    target = size_mb * 1024 * 1024
    chunk = line * max(1, target // len(line))
    paths: list[str] = []
    for i in range(files):
        path = folder / f"log-{i:02d}.log"
        path.write_bytes(chunk.encode("utf-8"))
        paths.append(path.as_posix())
    return paths


def _timed(command: list[str], env: dict[str, str] | None = None) -> dict[str, float]:
    started = time.perf_counter()
    result = subprocess.run(command, cwd=REPO_ROOT, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, timeout=300, check=False, env=env)
    elapsed = (time.perf_counter() - started) * 1000
    return {"ms": round(elapsed, 3), "exit_code": result.returncode}


def _py_serial(paths: list[str]) -> dict[str, float]:
    started = time.perf_counter()
    counts = 0
    for path in paths:
        with open(path, "rb") as handle:
            counts += sum(1 for line in handle if line.count(b"|") == 3)
    return {"ms": round((time.perf_counter() - started) * 1000, 3), "lines": counts}


def _py_threads(paths: list[str]) -> dict[str, float]:
    def count(path: str) -> int:
        with open(path, "rb") as handle:
            return sum(1 for line in handle if line.count(b"|") == 3)
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=min(8, len(paths))) as pool:
        counts = sum(pool.map(count, paths))
    return {"ms": round((time.perf_counter() - started) * 1000, 3), "lines": counts}


def _summarize(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    return {
        "runs": len(samples),
        "median_ms": round(statistics.median(samples), 3),
        "min_ms": round(ordered[0], 3),
        "max_ms": round(ordered[-1], 3),
        "range_ms": round(ordered[-1] - ordered[0], 3),
    }


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", type=int, default=8)
    parser.add_argument("--size-mb", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--out", default="reports/concurrency-performance.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _argument_parser().parse_args(argv)
    if args.files < 1 or args.size_mb < 1 or args.repeats < 1:
        print("benchmark: --files/--size-mb/--repeats must be >= 1", file=sys.stderr)
        return 4

    groups: dict[str, list[float]] = {
        "lwt_serial": [], "lwt_concurrent": [], "py_serial": [], "py_threads": []
    }
    fixture_sha256: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="lwt-s43-bench-") as folder:
        paths = _generate_fixtures(Path(folder), args.files, args.size_mb)
        for p in paths:
            fixture_sha256[Path(p).name] = _sha256(Path(p).read_bytes())
        commands = {
            "lwt_serial": [[sys.executable, "-m", "lwt", "app/log_report.lwt", "--", p] for p in paths],
            "lwt_concurrent": [[sys.executable, "-m", "lwt", "app/concurrent_log_report.lwt", "--", *paths]],
            "py_serial": [], "py_threads": [],
        }
        warmups = 2
        total = warmups + args.repeats
        for group in ("lwt_serial", "lwt_concurrent"):
            for i in range(total):
                # lwt_serial measures one file per run; sum across files.
                if group == "lwt_serial":
                    batch = sum(_timed(cmd)["ms"] for cmd in commands[group])
                else:
                    batch = _timed(commands[group][0])["ms"]
                if i >= warmups:
                    groups[group].append(batch)
        for i in range(total):
            s = _py_serial(paths)["ms"]
            t = _py_threads(paths)["ms"]
            if i >= warmups:
                groups["py_serial"].append(s)
                groups["py_threads"].append(t)
        # startup/import baseline: `python -c pass` vs `python -m lwt --help`
        startup = [_timed([sys.executable, "-c", "pass"])["ms"] for _ in range(5)]
        import_lwt = [_timed([sys.executable, "-m", "lwt", "--help"])["ms"] for _ in range(5)]

    summary = {name: _summarize(samples) for name, samples in groups.items()}
    serial = summary["lwt_serial"]["median_ms"]
    concurrent = summary["lwt_concurrent"]["median_ms"]
    py_serial = summary["py_serial"]["median_ms"]
    py_threads = summary["py_threads"]["median_ms"]
    document = {
        "schema": SCHEMA,
        "schema_version": 1,
        "generated_at_utc": _now(),
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                                   capture_output=True, text=True, check=False).stdout.strip(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "fixtures": {"files": args.files, "size_mb_each": args.size_mb,
                     "total_mb": args.files * args.size_mb,
                     "sha256_by_file": fixture_sha256},
        "protocol": {"warmups": 2, "repeats": args.repeats,
                     "generation": "temp dir, LF-boundary plain text, removed after run",
                     "page_cache": "warm (same files read repeatedly); see report"},
        "startup_baseline_ms": {"python_c_pass_median": round(statistics.median(startup), 3),
                                "lwt_help_median": round(statistics.median(import_lwt), 3)},
        "groups": summary,
        "lwt_serial_over_concurrent": round(serial / concurrent, 3),
        "py_serial_over_threads": round(py_serial / py_threads, 3),
        "amdahl_note": (
            "The single-token LWT model executes CPU work serially; only the "
            "I/O-wait fraction can overlap. If p is the I/O-wait fraction, the "
            "best possible speedup is 1/(1-p). These numbers are this machine "
            "and this run only; no claim of CPU parallel speedup is made."
        ),
    }
    out_path = REPO_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8", newline="\n")
    print(json.dumps({"out": args.out, "groups": summary,
                      "lwt_serial_over_concurrent": document["lwt_serial_over_concurrent"],
                      "py_serial_over_threads": document["py_serial_over_threads"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
