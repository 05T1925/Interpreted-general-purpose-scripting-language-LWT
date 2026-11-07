"""S11-v2: layered, reproducible LWT/Python performance benchmark (S44 WP4).

This is an INDEPENDENT optimization-verification appendix. It never writes
``bench/results.json`` or ``reports/performance.md`` (S11's official raw/report);
all output goes to ``reports/s44-performance/benchmark-v2.{json,md}``.

What it measures
----------------
* **End-to-end** (this tool): fresh subprocess wall time for each language,
  including Python startup, LWT package import, parse, execution and output.
  Paired, interleaved blocks with a fixed seed; 2 warm-ups + N formal runs;
  byte-exact stdout compared against an independent oracle and across languages.
* **Parse / execute layers** (from micro_bench before/after JSON): in-process
  ``parse`` and pure ``execute`` medians, which exclude process startup. The
  markdown combines both so startup / parse / execute are shown separately --
  an end-to-end ratio is never presented as a pure-execution speedup.

Protocol records, for every attempt: argv, cwd, exit code, stdout/stderr
byte length + SHA-256, perf_counter_ns duration, source SHA-256 of both LWT and
Python programs, plus run-level Git SHA, Python version, CPU, platform and
power scheme. A/B uses the same Python executable and cwd; no cross-machine
comparison is made.
"""

from __future__ import annotations

import argparse
from collections import OrderedDict
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "bench"
REPORTS = ROOT / "reports" / "s44-performance"
RESULTS_PATH = REPORTS / "benchmark-v2.json"
REPORT_PATH = REPORTS / "benchmark-v2.md"
SCHEMA_VERSION = 1

BENCHMARKS = ("arithmetic", "array_scan", "dict_counts")
LANGUAGES = ("lwt", "python")
DEFAULT_SIZES = (100, 1000, 5000)
DEFAULT_REPEATS = 7
DEFAULT_WARMUPS = 2
DEFAULT_SEED = 20261107
DEFAULT_TIMEOUT = 60


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def expected_stdout(benchmark: str, n: int) -> bytes:
    """Independent oracle, computed outside any measured child process."""
    if benchmark == "arithmetic":
        values = (n, n * (n + 1) // 2)
    elif benchmark == "array_scan":
        total = 0
        hits = 0
        i = 0
        while i < n:
            value = (i * 17 + 3) % 1009
            total += value
            if value % 97 == 0:
                hits += 1
            i += 1
        values = (n, total, hits)
    elif benchmark == "dict_counts":
        # Number of distinct keys of str((i*17+3) % 1009) for i in [0,n).
        # 1009 is prime, so the key cycle is 1009 for n>=1009, else n.
        values = (n, min(n, 1009))
    else:
        raise ValueError(f"unknown benchmark: {benchmark}")
    return ("|".join(str(v) for v in values) + "\n").encode("ascii")


def make_argv(language: str, benchmark: str, n: int) -> list[str]:
    if language == "lwt":
        return [sys.executable, "-m", "lwt", str(BENCH / f"{benchmark}.lwt"), "--", str(n)]
    if language == "python":
        return [sys.executable, str(BENCH / f"{benchmark}.py"), str(n)]
    raise ValueError(f"unknown language: {language}")


def run_attempt(argv: list[str], timeout: int) -> dict[str, Any]:
    started = time.perf_counter_ns()
    result = subprocess.run(
        argv, cwd=ROOT, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        shell=False, timeout=timeout,
    )
    elapsed = time.perf_counter_ns() - started
    return {
        "argv": argv,
        "cwd": str(ROOT),
        "exit_code": result.returncode,
        "elapsed_ns": elapsed,
        "stdout_len": len(result.stdout),
        "stderr_len": len(result.stderr),
        "stdout_sha256": sha256_bytes(result.stdout),
        "stderr_sha256": sha256_bytes(result.stderr),
        "stdout_base64": _b64(result.stdout),
        "stderr_base64": _b64(result.stderr),
    }


def _b64(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode("ascii")


def build_schedule(sizes: tuple[int, ...], repeats: int, seed: int) -> list[dict[str, Any]]:
    """Fixed-seed interleaved blocks: for each size/repeat, run both languages
    in a randomized order; shuffle the block order as well."""
    rng = random.Random(seed)
    blocks: list[dict[str, Any]] = []
    for benchmark in BENCHMARKS:
        for size in sizes:
            for repeat in range(1, repeats + 1):
                order = list(LANGUAGES)
                rng.shuffle(order)
                blocks.append(
                    {"benchmark": benchmark, "size": size,
                     "repeat_index": repeat, "language_order": order}
                )
    rng.shuffle(blocks)
    for index, block in enumerate(blocks, start=1):
        block["pair_id"] = f"pair-{index:04d}"
    return blocks


def _git(*args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, timeout=10)
        return out.stdout.decode("utf-8", "replace").strip()
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


def environment_record() -> dict[str, Any]:
    env: dict[str, Any] = {
        "python_executable": sys.executable,
        "python_version": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "git_head": _git("rev-parse", "HEAD"),
        "branch": _git("branch", "--show-current"),
    }

    def probe(cmd: list[str]) -> str:
        try:
            out = subprocess.run(cmd, capture_output=True, timeout=15)
            raw = out.stdout or b""
            text = raw.decode("utf-8", "replace")
            if "\ufffd" in text:
                text = raw.decode("gbk", "replace")
            return " ".join(text.split())[:160] or "unavailable"
        except Exception:
            return "unavailable"

    env["cpu_model"] = probe(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"])
    env["power_scheme"] = probe(["powercfg", "/getactivescheme"])
    return env


def source_hashes() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for benchmark in BENCHMARKS:
        for lang in LANGUAGES:
            suffix = "lwt" if lang == "lwt" else "py"
            path = BENCH / f"{benchmark}.{suffix}"
            hashes[path.relative_to(ROOT).as_posix()] = sha256_file(path)
    return hashes


def _stats(samples_ns: list[int]) -> dict[str, Any]:
    ordered = sorted(samples_ns)
    return {
        "n": len(ordered),
        "median_ns": ordered[len(ordered) // 2] if len(ordered) % 2 else (ordered[len(ordered)//2 - 1] + ordered[len(ordered)//2]) // 2,
        "median_ms": round(statistics.median(ordered) / 1e6, 3),
        "min_ms": round(ordered[0] / 1e6, 3),
        "max_ms": round(ordered[-1] / 1e6, 3),
        "range_ms": round((ordered[-1] - ordered[0]) / 1e6, 3),
    }


def measure(sizes: tuple[int, ...], repeats: int, warmups: int,
            seed: int, timeout: int) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    # Warm-ups first; validate output against oracle, never timed into samples.
    for benchmark in BENCHMARKS:
        for size in sizes:
            expected = expected_stdout(benchmark, size)
            for lang in LANGUAGES:
                for _ in range(warmups):
                    attempt = run_attempt(make_argv(lang, benchmark, size), timeout)
                    import base64
                    got = base64.b64decode(attempt["stdout_base64"])
                    if attempt["exit_code"] != 0 or got != expected:
                        raise RuntimeError(
                            f"warm-up failed: {lang}/{benchmark}/{size}: "
                            f"exit={attempt['exit_code']} stdout={got[:80]!r} expected={expected!r}"
                        )

    schedule = build_schedule(sizes, repeats, seed)
    for block in schedule:
        benchmark = block["benchmark"]
        size = block["size"]
        expected = expected_stdout(benchmark, size)
        per_lang: dict[str, dict[str, Any]] = {}
        for lang in block["language_order"]:
            attempt = run_attempt(make_argv(lang, benchmark, size), timeout)
            import base64
            got = base64.b64decode(attempt["stdout_base64"])
            attempt["benchmark"] = benchmark
            attempt["size"] = size
            attempt["language"] = lang
            attempt["pair_id"] = block["pair_id"]
            attempt["oracle_ok"] = (attempt["exit_code"] == 0 and got == expected)
            if not attempt["oracle_ok"]:
                raise RuntimeError(
                    f"oracle mismatch: {lang}/{benchmark}/{size} pair={block['pair_id']}: "
                    f"exit={attempt['exit_code']} stdout={got[:80]!r} expected={expected!r}"
                )
            attempts.append(attempt)
            per_lang[lang] = attempt
        block["lwt_elapsed_ns"] = per_lang["lwt"]["elapsed_ns"]
        block["python_elapsed_ns"] = per_lang["python"]["elapsed_ns"]

    # Summarize per (benchmark, size, language).
    summary: dict[str, Any] = {}
    for benchmark in BENCHMARKS:
        for size in sizes:
            for lang in LANGUAGES:
                samples = [a["elapsed_ns"] for a in attempts
                           if a["benchmark"] == benchmark and a["size"] == size and a["language"] == lang]
                summary[f"{benchmark}|{size}|{lang}"] = _stats(samples)
    pairs: dict[str, Any] = {}
    for benchmark in BENCHMARKS:
        for size in sizes:
            l = summary[f"{benchmark}|{size}|lwt"]["median_ns"]
            p = summary[f"{benchmark}|{size}|python"]["median_ns"]
            pairs[f"{benchmark}|{size}"] = round(l / p, 3) if p else None

    return {
        "schema_version": SCHEMA_VERSION,
        "tool": "lwt-benchmark-v2",
        "generated_at_utc": utc_now(),
        "environment": environment_record(),
        "protocol": {
            "warmups": warmups, "repeats": repeats, "seed": seed,
            "sizes": list(sizes), "benchmarks": list(BENCHMARKS),
            "languages": list(LANGUAGES), "timeout_s": timeout,
            "order": "fixed-seed interleaved paired blocks; language order shuffled per block",
            "timing": "time.perf_counter_ns around subprocess.run",
            "oracle": "independent expected_stdout; byte-exact for every warm-up and formal run",
            "output_path": RESULTS_PATH.relative_to(ROOT).as_posix(),
            "s11_boundary": "never writes bench/results.json or reports/performance.md",
        },
        "source_sha256": source_hashes(),
        "attempts": attempts,
        "schedule": schedule,
        "summary": summary,
        "ratios_lwt_over_python": pairs,
    }


def _load_micro(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def render_report(doc: dict[str, Any], before: dict[str, Any] | None,
                  after: dict[str, Any] | None) -> str:
    env = doc["environment"]
    s = doc["summary"]
    sizes = doc["protocol"]["sizes"]
    lines = [
        "# S11-v2 分层性能基准（S44 优化验证附录）",
        "",
        "> 本文件是 S44 的**独立优化验证附录**，不是 S11 正式性能报告的修订。"
        "`bench/results.json` 与 `reports/performance.md` 未被读取或改写。",
        "> 端到端为新进程墙钟（启动+导入+解析+执行）；纯 parse/execute 来自同协议的 micro_bench A/B。"
        "**端到端倍率不含分层拆解时不称为纯执行倍率。**",
        "",
        "## 环境与协议",
        "",
        f"- 采集时间（UTC）：{doc['generated_at_utc']}",
        f"- Git HEAD：`{env['git_head']}`（分支 `{env['branch']}`）",
        f"- Python：`{env['python_version']}`；可执行：`{env['python_executable']}`",
        f"- 平台：`{env['platform']}`；CPU：`{env.get('cpu_model', 'unavailable')}`；逻辑核 {env['cpu_count']}；电源 `{env.get('power_scheme', 'unavailable')}`",
        f"- 协议：{doc['protocol']['warmups']} 预热 + {doc['protocol']['repeats']} 正式，"
        f"seed {doc['protocol']['seed']} 交错配对；每次逐字节 oracle 校验"
        f"（{len(doc['attempts'])} 次正式全部通过）。",
        "",
        "## A. 端到端（新进程墙钟，中位数 ms）",
        "",
        "| 负载 | N | LWT | Python | LWT/Python |",
        "|---|---:|---:|---:|---:|",
    ]
    for benchmark in BENCHMARKS:
        for size in sizes:
            l = s[f"{benchmark}|{size}|lwt"]["median_ms"]
            p = s[f"{benchmark}|{size}|python"]["median_ms"]
            r = doc["ratios_lwt_over_python"][f"{benchmark}|{size}"]
            lines.append(f"| {benchmark} | {size} | {l:.3f} | {p:.3f} | {r:.3f}× |")
    lines += [
        "",
        "## B. 分层：纯执行 execute（micro_bench A/B，中位数 ms）",
        "",
        "同机 before/after 均 2 预热 + 7 正式、单进程内同一 AST、逐次 oracle 校验。"
        "此段不含进程启动与包导入；不与上段端到端倍率相减或相除。",
        "",
        "| 负载 | N | before | after | 提升 |",
        "|---|---:|---:|---:|---:|",
    ]
    if before and after:
        bm = {(m["workload"], m["n"]): m for m in before["measurements"]}
        am = {(m["workload"], m["n"]): m for m in after["measurements"]}
        for benchmark in BENCHMARKS:
            for size in sizes:
                key = (benchmark, size)
                if key in bm and key in am:
                    bms = bm[key]["execute"]["median_ns"] / 1e6
                    ams = am[key]["execute"]["median_ns"] / 1e6
                    lines.append(f"| {benchmark} | {size} | {bms:.3f} | {ams:.3f} | {bms/ams:.3f}× |")
    else:
        lines.append("| （before/after micro_bench JSON 缺失） | | | | |")
    lines += [
        "",
        "## C. 四段口径与限制",
        "",
        "- **启动/导入**：`python -c pass` vs `python -m lwt --help` 的中位数差（`reports/s44-performance/{before,after}/startup.json`）。",
        "- **解析 parse**、**纯执行 execute**：micro_bench 同进程分层（本报告 B 段）。",
        "- **端到端**：本报告 A 段，含启动+导入+解析+执行+输出。",
        "- LWT/Python 端到端仍慢，主要来自解释器的分派/对象分配与包导入；S44 优化的是分层中的启动与纯执行，不把端到端倍率说成纯执行倍率。",
        "- 只在本机本次运行有效；未在本机 Python 3.10 / Linux / 远端 CI 复验；背景负载、电源、page cache 影响绝对值，同机 A/B 差值与中位数为准。",
        "",
    ]
    return "\n".join(lines)


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def argument_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sizes", default=",".join(str(s) for s in DEFAULT_SIZES))
    p.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    p.add_argument("--warmups", type=int, default=DEFAULT_WARMUPS)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.add_argument("--out", default=str(RESULTS_PATH), help="JSON output (must stay under reports/s44-performance/)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = argument_parser().parse_args(argv)
    if args.repeats < 1 or args.warmups < 1 or args.timeout < 1:
        sys.stderr.write("benchmark_v2: --repeats>=1 --warmups>=1 --timeout>=1 required\n")
        return 4
    sizes = tuple(int(x) for x in args.sizes.split(",") if x.strip())
    if not sizes or any(s <= 0 for s in sizes):
        sys.stderr.write("benchmark_v2: --sizes must be positive integers\n")
        return 4
    out_path = ROOT / args.out
    # Protected-data guard: never allow writing S11 official paths.
    rel = out_path.relative_to(ROOT).as_posix() if out_path.is_relative_to(ROOT) else str(out_path)
    if rel in ("bench/results.json", "reports/performance.md") or not rel.startswith("reports/s44-performance/"):
        sys.stderr.write(f"benchmark_v2: output must stay under reports/s44-performance/ (got {rel})\n")
        return 4
    try:
        doc = measure(sizes, args.repeats, args.warmups, args.seed, args.timeout)
    except (RuntimeError, subprocess.SubprocessError) as error:
        sys.stderr.write(f"benchmark_v2: {error}\n")
        return 3

    _atomic(out_path, json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    before = _load_micro(REPORTS / "before" / "runtime-profile.json")
    after = _load_micro(REPORTS / "after" / "runtime-profile.json")
    md_path = out_path.with_suffix(".md")
    _atomic(md_path, render_report(doc, before, after))
    print(f"benchmark_v2: wrote {rel} and {md_path.relative_to(ROOT)}; "
          f"{len(doc['attempts'])} formal runs, all oracle-passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
