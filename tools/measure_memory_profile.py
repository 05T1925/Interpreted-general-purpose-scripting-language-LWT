"""S52: supplementary time + space measurements (course chapter 7).

The S11 report has medians; the course also asks for the space dimension and
for P95/P99 rather than a single average. This tool measures, for the three
existing bench workloads and N in {100, 1000, 5000}:

* wall time over 2 warm-up + 9 measured subprocess runs (min/p50/p95/p99/max);
* Python heap peak via ``tracemalloc`` for one in-process CLI invocation;
* peak RSS of the child process on Windows (psapi GetProcessMemoryInfo);
* a bounded pressure sweep N in {1000, 5000, 20000} for growth/leak signals.

It never writes to bench/results.json, reports/performance.md or
reports/s44-performance/. Output is reports/s52-course-align/performance-space.*.

``resource.getrusage`` is Unix-only, so the RSS path uses ctypes on Windows and
reports ``null`` elsewhere instead of pretending to have measured it.
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import ctypes.wintypes as wintypes
import datetime
import io
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))  # tools/ is sys.path[0] when run as a script
DEFAULT_OUT = ROOT / "reports" / "s52-course-align"
WORKLOADS = ("arithmetic", "array_scan", "dict_counts")
SIZES = (100, 1000, 5000)
PRESSURE_SIZES = (1000, 5000, 20000)
WARMUP = 2
SAMPLES = 9


def _utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _percentile(values: list[float], fraction: float) -> float:
    """Nearest-rank percentile; no interpolation, so the number is reproducible."""

    ordered = sorted(values)
    if not ordered:
        return float("nan")
    rank = max(1, math.ceil(fraction * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def _run_once(script: Path, n: int) -> float:
    started = time.perf_counter()
    completed = subprocess.run(
        [sys.executable, "-m", "lwt", str(script), "--", str(n)],
        cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        timeout=300, check=False,
    )
    elapsed = (time.perf_counter() - started) * 1000.0
    if completed.returncode != 0:
        raise RuntimeError(f"{script.name} N={n} exited {completed.returncode}: "
                           f"{completed.stderr[-200:]!r}")
    return elapsed


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _child_peak_rss(script: Path, n: int) -> int | None:
    """Sample WorkingSetSize while the child runs (Windows only)."""

    if os.name != "nt":
        return None
    try:
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        process = subprocess.Popen(
            [sys.executable, "-m", "lwt", str(script), "--", str(n)],
            cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        peak = 0
        query = psapi.GetProcessMemoryInfo
        query.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessMemoryCounters), wintypes.DWORD]
        query.restype = wintypes.BOOL
        access = 0x0400 | 0x0010  # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
        handle = kernel32.OpenProcess(access, False, process.pid)
        try:
            while process.poll() is None:
                counters = _ProcessMemoryCounters()
                counters.cb = ctypes.sizeof(counters)
                if handle and query(handle, ctypes.byref(counters), counters.cb):
                    peak = max(peak, int(counters.WorkingSetSize))
                time.sleep(0.02)
        finally:
            if handle:
                kernel32.CloseHandle(handle)
            process.wait(timeout=30)
        return peak or None
    except Exception:
        return None


def _tracemalloc_peak(script: Path, n: int) -> int | None:
    from lwt import cli

    sink = open(os.devnull, "w", encoding="utf-8")
    tracemalloc.start()
    try:
        # cli.main() reconfigures the standard streams, so a StringIO would fail;
        # a real text stream to devnull supports reconfigure and keeps output quiet.
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            code = cli.main([str(script), "--", str(n)])
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
        sink.close()
    if code != 0:
        return None
    return int(peak)


def _startup_floor() -> float:
    """p50 of a bare interpreter start; CLI wall time includes this floor."""

    samples = []
    for _ in range(SAMPLES):
        started = time.perf_counter()
        subprocess.run([sys.executable, "-c", "pass"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=False)
        samples.append((time.perf_counter() - started) * 1000.0)
    return round(_percentile(samples, 0.50), 2)


def _time_block(script: Path, n: int) -> dict:
    for _ in range(WARMUP):
        _run_once(script, n)
    samples = [_run_once(script, n) for _ in range(SAMPLES)]
    return {
        "samples": SAMPLES,
        "warmup": WARMUP,
        "min_ms": round(min(samples), 2),
        "p50_ms": round(_percentile(samples, 0.50), 2),
        "p95_ms": round(_percentile(samples, 0.95), 2),
        "p99_ms": round(_percentile(samples, 0.99), 2),
        "max_ms": round(max(samples), 2),
        "range_ms": round(max(samples) - min(samples), 2),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--quick", action="store_true",
                        help="smaller sample set for a smoke run (still labelled)")
    args = parser.parse_args(argv)
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    global SAMPLES
    if args.quick:
        SAMPLES = 3

    startup_ms = _startup_floor()

    measurements: dict[str, dict] = {}
    for workload in WORKLOADS:
        script = ROOT / "bench" / f"{workload}.lwt"
        measurements[workload] = {}
        for n in SIZES:
            block = _time_block(script, n)
            # The CLI wall clock includes interpreter start-up; report the net
            # figure as well so a small N is not mistaken for pure workload time.
            block["startup_floor_ms"] = startup_ms
            block["net_p50_ms"] = round(max(0.0, block["p50_ms"] - startup_ms), 2)
            block["net_p95_ms"] = round(max(0.0, block["p95_ms"] - startup_ms), 2)
            measurements[workload][str(n)] = {
                "time": block,
                "peak_bytes": _tracemalloc_peak(script, n),
                "peak_rss_bytes": _child_peak_rss(script, n),
            }

    pressure: dict[str, dict] = {}
    pressure_script = ROOT / "bench" / "array_scan.lwt"
    for n in PRESSURE_SIZES:
        pressure[str(n)] = {
            "p50_ms": _time_block(pressure_script, n)["p50_ms"],
            "peak_bytes": _tracemalloc_peak(pressure_script, n),
            "peak_rss_bytes": _child_peak_rss(pressure_script, n),
        }

    peaks = [row["peak_bytes"] for row in pressure.values() if row["peak_bytes"]]
    monotonic = all(b >= a for a, b in zip(peaks, peaks[1:])) if len(peaks) > 1 else None

    doc = {
        "schema_version": 1,
        "tool": "tools/measure_memory_profile.py",
        "generated_at_utc": _utc(),
        "environment": {
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "executable": sys.executable,
            "startup_floor_ms": startup_ms,
        },
        "objective": (
            "在 N=100/1000/5000 的三个既有负载上给出可复现的 p50/p95/p99 与峰值内存；"
            "不追求比 CPython 快，目标是第 7 章要求的测量方法与空间维度。"
        ),
        "baseline": (
            "S11 正式中位数（reports/performance.md）与 S44 分层加速（reports/s44-performance/）"
            "为基线；本文件只做补充测量，不替代、不修改它们。"
        ),
        "stop_rule": (
            "若 S44 compare_perf 门槛仍满足、且 S52 复测 p95 相对本文件波动 <15%，停止优化；"
            "若某优化使峰值内存单调上升或无时间收益，按第 7 章“无收益即回滚”。"
        ),
        "method": {
            "time": f"subprocess wall clock，{WARMUP} 次预热 + {SAMPLES} 次正式，nearest-rank 分位数",
            "space_in_process": "tracemalloc.get_traced_memory() 峰值（单次 CLI 调用）",
            "space_child": "Windows psapi WorkingSetSize 20 ms 采样；非 Windows 为 null",
        },
        "measurements": measurements,
        "pressure": {
            "workload": "array_scan",
            "sizes": list(PRESSURE_SIZES),
            "rows": pressure,
            "peak_bytes_monotonic": monotonic,
            "boundary": "这是有界规模扫描，不是长时间 soak；不证明 7×24 稳定，也不证明无泄漏。",
        },
        "platforms": {
            "windows": {
                "measured": os.name == "nt",
                "note": "本机主路径" if os.name == "nt" else "非 Windows 主机",
            },
            "ubuntu": {
                "measured": False,
                "maximum_resident_set_kb": None,
                "note": "未在 CI 采集 /usr/bin/time -v 或 resource.getrusage(RUSAGE_CHILDREN)；"
                        "resource 为 Unix-only，本机无法代跑，如实标未验证。",
            },
        },
        "frozen_inputs": {
            "s11_results": "bench/results.json",
            "s11_report": "reports/performance.md",
            "s44_dir": "reports/s44-performance/",
            "note": "这些文件只读；S52 结果不覆盖、不合并进 S11/S44。",
        },
        "quick_mode": bool(args.quick),
        "render_check": False,
    }
    out_json = out_dir / "performance-space.json"
    out_json.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")
    try:
        shown = out_json.relative_to(ROOT)
    except ValueError:  # --out-dir outside the repo (smoke runs)
        shown = out_json
    print(f"measure_memory_profile: {shown}")
    for workload, rows in measurements.items():
        for n, row in rows.items():
            t = row["time"]
            print(f"  {workload:12s} N={n:>5s} p50={t['p50_ms']:8.2f} p95={t['p95_ms']:8.2f} "
                  f"p99={t['p99_ms']:8.2f} peak={row['peak_bytes']} rss={row['peak_rss_bytes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
