"""Auditable paired LWT/Python end-to-end process benchmarks."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import random
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
BENCH_DIR = ROOT / "bench"
RESULTS_PATH = BENCH_DIR / "results.json"
REPORT_PATH = ROOT / "reports" / "performance.md"
BENCHMARKS = ("arithmetic", "array_scan")
LANGUAGES = ("lwt", "python")
DEFAULT_SIZES = (100, 1000, 5000)
DEFAULT_REPEATS = 10
DEFAULT_SEED = 20261007
DEFAULT_TIMEOUT_SECONDS = 60
SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def raw_bytes(data: bytes) -> dict[str, Any]:
    return {
        "base64": base64.b64encode(data).decode("ascii"),
        "byte_length": len(data),
        "sha256": sha256(data),
    }


def expected_values(benchmark: str, n: int) -> tuple[int, ...]:
    """Compute an independent oracle outside the measured child process."""
    if benchmark == "arithmetic":
        return (n, n * (n + 1) // 2)
    if benchmark == "array_scan":
        total = 0
        hits = 0
        i = 0
        while i < n:
            value = (i * 17 + 3) % 1009
            total = total + value
            if value % 97 == 0:
                hits = hits + 1
            i = i + 1
        return (n, total, hits)
    raise ValueError(f"unknown benchmark: {benchmark}")


def expected_stdout(benchmark: str, n: int) -> bytes:
    return ("|".join(str(value) for value in expected_values(benchmark, n)) + "\n").encode("ascii")


def build_schedule(sizes: Iterable[int], repeats: int, seed: int) -> list[dict[str, Any]]:
    """Shuffle paired workload blocks and the language order inside each block."""
    rng = random.Random(seed)
    blocks = [
        {"benchmark": benchmark, "size": size, "repeat_index": repeat_index}
        for benchmark in BENCHMARKS
        for size in sizes
        for repeat_index in range(1, repeats + 1)
    ]
    rng.shuffle(blocks)
    for block_index, block in enumerate(blocks, start=1):
        order = list(LANGUAGES)
        rng.shuffle(order)
        block["pair_id"] = f"pair-{block_index:04d}"
        block["language_order"] = order
    return blocks


def make_argv(language: str, benchmark: str, n: int) -> list[str]:
    if language == "lwt":
        return [
            sys.executable,
            "-m",
            "lwt",
            str(BENCH_DIR / f"{benchmark}.lwt"),
            "--",
            str(n),
        ]
    if language == "python":
        return [sys.executable, str(BENCH_DIR / f"{benchmark}.py"), str(n)]
    raise ValueError(f"unknown language: {language}")


def execute_command(
    argv: list[str], timeout_seconds: int, timed: bool
) -> dict[str, Any]:
    """Run one new child and capture byte evidence; the timer brackets run()."""
    started_ns = time.perf_counter_ns() if timed else None
    try:
        completed = subprocess.run(
            argv,
            cwd=str(ROOT),
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        elapsed_ns = time.perf_counter_ns() - started_ns if timed else None
        return {
            "elapsed_ns": elapsed_ns,
            "return_code": completed.returncode,
            "timed_out": False,
            "launch_error": None,
            "stdout_bytes": completed.stdout,
            "stderr_bytes": completed.stderr,
        }
    except subprocess.TimeoutExpired as error:
        elapsed_ns = time.perf_counter_ns() - started_ns if timed else None
        return {
            "elapsed_ns": elapsed_ns,
            "return_code": None,
            "timed_out": True,
            "launch_error": None,
            "stdout_bytes": error.stdout or b"",
            "stderr_bytes": error.stderr or b"",
        }
    except OSError as error:
        elapsed_ns = time.perf_counter_ns() - started_ns if timed else None
        return {
            "elapsed_ns": elapsed_ns,
            "return_code": None,
            "timed_out": False,
            "launch_error": {"type": type(error).__name__, "message": str(error)},
            "stdout_bytes": b"",
            "stderr_bytes": b"",
        }


def verify_process(result: dict[str, Any], expected: bytes) -> dict[str, Any]:
    reasons: list[str] = []
    if result["timed_out"]:
        reasons.append("timeout")
    if result["launch_error"] is not None:
        reasons.append("launch_error")
    if result["return_code"] != 0:
        reasons.append("nonzero_or_missing_return_code")
    if result["stderr_bytes"] != b"":
        reasons.append("stderr_not_empty")
    if result["stdout_bytes"] != expected:
        reasons.append("stdout_does_not_match_independent_expectation")
    return {
        "exit_success": result["return_code"] == 0 and not result["timed_out"],
        "stderr_empty": result["stderr_bytes"] == b"",
        "expected_output_match": result["stdout_bytes"] == expected,
        "passed": not reasons,
        "failure_reasons": reasons,
    }


def make_attempt_record(
    *,
    attempt_id: str,
    kind: str,
    order: int,
    benchmark: str,
    language: str,
    n: int,
    argv: list[str],
    execution: dict[str, Any],
    expected: bytes,
    timeout_seconds: int,
    pair_id: str | None = None,
    repeat_index: int | None = None,
) -> dict[str, Any]:
    verification = verify_process(execution, expected)
    record: dict[str, Any] = {
        "attempt_id": attempt_id,
        "kind": kind,
        "execution_order": order,
        "timestamp_utc": utc_now(),
        "benchmark": benchmark,
        "language": language,
        "size": n,
        "input": {"n": n},
        "argv": argv,
        "cwd": str(ROOT),
        "timeout_seconds": timeout_seconds,
        "elapsed_ns": execution["elapsed_ns"],
        "return_code": execution["return_code"],
        "timed_out": execution["timed_out"],
        "launch_error": execution["launch_error"],
        "stdout": raw_bytes(execution["stdout_bytes"]),
        "stderr": raw_bytes(execution["stderr_bytes"]),
        "expected_stdout": raw_bytes(expected),
        "verification": verification,
    }
    if pair_id is not None:
        record["pair_id"] = pair_id
    if repeat_index is not None:
        record["repeat_index"] = repeat_index
    return record


def output_bytes(attempt: dict[str, Any], field: str = "stdout") -> bytes:
    return base64.b64decode(attempt[field]["base64"].encode("ascii"))


def make_pair_record(
    pair_id: str,
    benchmark: str,
    n: int,
    repeat_index: int,
    language_attempts: dict[str, dict[str, Any]],
    expected: bytes,
) -> dict[str, Any]:
    lwt_attempt = language_attempts["lwt"]
    python_attempt = language_attempts["python"]
    same_output = output_bytes(lwt_attempt) == output_bytes(python_attempt)
    expected_match = (
        lwt_attempt["verification"]["expected_output_match"]
        and python_attempt["verification"]["expected_output_match"]
        and output_bytes(lwt_attempt, "expected_stdout") == expected
        and output_bytes(python_attempt, "expected_stdout") == expected
    )
    return {
        "pair_id": pair_id,
        "benchmark": benchmark,
        "size": n,
        "repeat_index": repeat_index,
        "lwt_attempt_id": lwt_attempt["attempt_id"],
        "python_attempt_id": python_attempt["attempt_id"],
        "paired_output_match": same_output,
        "independent_expected_match": expected_match,
        "valid": same_output and expected_match and lwt_attempt["verification"]["passed"] and python_attempt["verification"]["passed"],
    }


def summarize_samples(samples_ns: Iterable[int]) -> dict[str, float | int]:
    samples = list(samples_ns)
    if not samples:
        raise ValueError("cannot summarize an empty sample")
    return {
        "count": len(samples),
        "median_ns": statistics.median(samples),
        "min_ns": min(samples),
        "max_ns": max(samples),
        "range_ns": max(samples) - min(samples),
    }


def ratio(lwt_median_ns: float, python_median_ns: float) -> float:
    if python_median_ns == 0:
        raise ValueError("Python median must be nonzero")
    return lwt_median_ns / python_median_ns


def git_snapshot() -> dict[str, Any]:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(ROOT), shell=False,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    ).stdout.decode("ascii").strip()
    status = subprocess.run(
        ["git", "status", "--porcelain=v1"], cwd=str(ROOT), shell=False,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    ).stdout.decode("utf-8", errors="replace")
    return {"commit_sha": revision, "working_tree_clean_at_start": status == "", "status_porcelain_at_start": status}


def file_hashes() -> dict[str, str]:
    names = (
        "bench/arithmetic.lwt", "bench/arithmetic.py",
        "bench/array_scan.lwt", "bench/array_scan.py",
    )
    return {name: sha256((ROOT / name).read_bytes()) for name in names}


def environment_record() -> dict[str, Any]:
    return {
        "os": platform.system(),
        "platform": platform.platform(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "python_version": sys.version,
        "python_executable": sys.executable,
    }


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", dir=path.parent,
        prefix=path.name + ".", suffix=".tmp", delete=False,
    ) as handle:
        temporary = Path(handle.name)
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, path)


def load_results() -> dict[str, Any]:
    if not RESULTS_PATH.exists():
        return {"schema_version": SCHEMA_VERSION, "runs": []}
    data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION or not isinstance(data.get("runs"), list):
        raise ValueError("bench/results.json has an unsupported schema")
    return data


def save_run(run: dict[str, Any]) -> None:
    data = load_results()
    for index, existing in enumerate(data["runs"]):
        if existing.get("run_id") == run["run_id"]:
            data["runs"][index] = run
            break
    else:
        data["runs"].append(run)
    atomic_write_json(RESULTS_PATH, data)


def formal_summaries(run: dict[str, Any]) -> list[dict[str, Any]]:
    if run.get("mode") != "formal" or run.get("status") != "valid":
        return []
    attempts = {item["attempt_id"]: item for item in run["trials"]}
    pairs_by_key: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for pair in run["pairs"]:
        if pair["valid"]:
            key = (pair["benchmark"], pair["size"])
            pairs_by_key.setdefault(key, []).append(pair)
    results = []
    for benchmark in BENCHMARKS:
        for n in run["sizes"]:
            pairs = pairs_by_key.get((benchmark, n), [])
            if len(pairs) != run["formal_repeats"]:
                continue
            language_stats = {}
            for language, id_key in (("lwt", "lwt_attempt_id"), ("python", "python_attempt_id")):
                samples = [attempts[pair[id_key]]["elapsed_ns"] for pair in pairs]
                if any(not isinstance(sample, int) for sample in samples):
                    raise ValueError("valid formal attempt is missing elapsed_ns")
                language_stats[language] = summarize_samples(samples)
            results.append({
                "benchmark": benchmark,
                "size": n,
                "pairs": len(pairs),
                "lwt": language_stats["lwt"],
                "python": language_stats["python"],
                "ratio": ratio(language_stats["lwt"]["median_ns"], language_stats["python"]["median_ns"]),
            })
    return results


def ms(ns: float | int) -> str:
    return f"{ns / 1_000_000:.3f}"


def render_report(results: dict[str, Any]) -> str:
    formal_runs = [run for run in results["runs"] if run.get("mode") == "formal"]
    calibration_runs = [run for run in results["runs"] if run.get("mode") == "calibration"]
    sections = [
        "# LWT/Python 成对性能实验报告",
        "",
        "> 本报告呈现新进程端到端墙钟时间，不是纯 AST 执行速度、CPU 时间或磁盘吞吐率。统计数字由 `bench/results.json` 的有效正式运行逐项复算。",
        "",
        "## 目的与工作负载",
        "",
        "本实验响应课程“使用 LWT 脚本进行性能测试，并与相同功能 Python 脚本比较”的要求。`arithmetic` 逐项累加 1 到 N；`array_scan` 用第一遍循环构造 `(i*17+3)%1009` 数组，再用第二遍循环计算元素总和及 `%97==0` 的数量。两侧使用相同正整数 N、显式循环和一行十进制输出：前者为 `N|sum\\n`，后者为 `N|sum|hits\\n`。Python 被测脚本没有用 `sum`、推导式或生成器替代循环。runner 在计时外另行计算预期值，并要求 LWT、Python 输出字节分别匹配预期且彼此相同。",
        "",
        "按规模 N 传参的命令形式为 `python -m lwt bench/arithmetic.lwt -- N` / `python bench/arithmetic.py N`，以及 `python -m lwt bench/array_scan.lwt -- N` / `python bench/array_scan.py N`。raw JSON 为每个实际子进程保存含当前 `sys.executable` 的完整 argv 和固定仓库根目录 cwd。",
        "",
        "## 协议",
        "",
        "- 命令从仓库根目录启动，使用 `sys.executable`、argv 数组、`shell=False`、stdin=`DEVNULL`、stdout/stderr 字节捕获及有限 timeout。每次 warm-up 和正式试次都是独立的新进程；先逐一校验 warm-up，再进行正式试次。",
        "- 正式样本按固定 seed 随机排列配对块，并在每对内随机 LWT/Python 先后顺序；同一时刻仅运行一个被测子进程。",
        "- `perf_counter_ns()` 紧贴一次 `subprocess.run()` 前后调用。端到端时间包括子进程创建、Python 启动、LWT 包导入与源码词法/语法分析、工作负载、输出生成及等待进程退出；不包括 runner 的输出解码、验证、统计、哈希和 JSON 写入。",
        "- 原始纳秒整数保存于 JSON。表格统一将 ns 除以 1,000,000 换为 ms，固定显示三位小数；range=max−min；比值=LWT median/Python median。比值大于 1 表示该组 LWT 中位时间较长。",
        "- calibration 运行用于确认规模是否可在目标环境完成，不进入正式统计。全部失败/无效尝试仍保存在 JSON；无效 run 不生成有效性能表格。",
        "",
        "计时依据：[Python 3.10 `perf_counter_ns`](https://docs.python.org/3.10/library/time.html#time.perf_counter_ns)、[Python 3.10 `subprocess.run`](https://docs.python.org/3.10/library/subprocess.html)、[`timeit` 重复测量说明](https://docs.python.org/3.10/library/timeit.html)。官方文档指出 `perf_counter` 适于测短时差值并包含等待时间；`timeit` 说明重复样本会受其他进程干扰，因此本报告保留中位数及完整离散范围，不只选择最快值。",
        "",
        "## 校准记录（不计入正式结果）",
        "",
    ]
    if not calibration_runs:
        sections.append("暂无校准记录。")
    for run in calibration_runs:
        failed_warmups = [item for item in run["warmups"] if not item["verification"]["passed"]]
        sections.extend([
            f"### {run['run_id']}（`{run['status']}`）",
            "",
            f"- Git SHA：`{run['git']['commit_sha']}`；开始时工作区干净：`{run['git']['working_tree_clean_at_start']}`；warm-up `{len(run['warmups'])}` 条，校准计时 `{len(run['trials'])}` 条。",
        ])
        if failed_warmups:
            sections.append(
                f"- 该校准因 {len(failed_warmups)} 条 warm-up 未通过而停止；按协议未启动计时校准。失败详情和原始字节见 raw JSON。本次观察到的 Windows Python 文本 stdout 使用 CRLF，而 LWT 契约输出 LF；修复后的 Python workload 改用 ASCII 字节写出。该失败运行保留，不纳入任何性能数字。"
            )
        elif run["status"] == "valid":
            grouped: dict[tuple[str, int], dict[str, dict[str, Any]]] = {}
            for trial in run["trials"]:
                grouped.setdefault((trial["benchmark"], trial["size"]), {})[trial["language"]] = trial
            sections.extend([
                "- 校准持续时间只用于确认三种规模可完成；规模 N=100、1000、5000 在校准后保持不变。选择规模依据是它们代表小/中/大循环工作量，最大规模在此次环境内可完成；未根据 LWT/Python 结果优劣挑选。校准数据不属于正式试次。",
                "",
                "| benchmark | N | LWT calibration (ms) | Python calibration (ms) |",
                "|---|---:|---:|---:|",
            ])
            for (benchmark_name, n), by_language in sorted(grouped.items()):
                if set(by_language) == {"lwt", "python"}:
                    sections.append(
                        f"| {benchmark_name} | {n} | {ms(by_language['lwt']['elapsed_ns'])} | {ms(by_language['python']['elapsed_ns'])} |"
                    )
        sections.append("")
    sections.extend([
        "## 正式结果",
        "",
        "| benchmark | N | 配对数 | LWT median (ms) | LWT min (ms) | LWT max (ms) | LWT range (ms) | Python median (ms) | Python min (ms) | Python max (ms) | Python range (ms) | median ratio LWT/Python |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    found = False
    for run in formal_runs:
        summaries = formal_summaries(run)
        if run.get("status") != "valid":
            sections.extend([f"", f"**无效正式运行** `{run['run_id']}`（Git `{run['git']['commit_sha']}`）：{run.get('failure_count', 0)} 个失败/不匹配尝试。此运行完整保留于原始 JSON，不纳入有效统计。"])
        if not summaries:
            continue
        found = True
        for item in summaries:
            lwt = item["lwt"]
            py = item["python"]
            sections.append(
                f"| {item['benchmark']} | {item['size']} | {item['pairs']} | {ms(lwt['median_ns'])} | {ms(lwt['min_ns'])} | {ms(lwt['max_ns'])} | {ms(lwt['range_ns'])} | {ms(py['median_ns'])} | {ms(py['min_ns'])} | {ms(py['max_ns'])} | {ms(py['range_ns'])} | {item['ratio']:.3f} |"
            )
        by_benchmark = {
            benchmark_name: [item for item in summaries if item["benchmark"] == benchmark_name]
            for benchmark_name in BENCHMARKS
        }
        for benchmark_name, items in by_benchmark.items():
            if len(items) >= 2:
                first = min(items, key=lambda item: item["size"])
                last = max(items, key=lambda item: item["size"])
                sections.append(
                    f"在 run `{run['run_id']}` 的 {benchmark_name} 样本中，N 从 {first['size']} 增至 {last['size']} 时，LWT median 为 {ms(first['lwt']['median_ns'])}→{ms(last['lwt']['median_ns'])} ms，Python median 为 {ms(first['python']['median_ns'])}→{ms(last['python']['median_ns'])} ms，中位数比值为 {first['ratio']:.3f}→{last['ratio']:.3f}。这只描述本机的端到端样本；进程启动和导入/解析成本占比可能遮蔽循环本身的变化，不能据此推断纯运行时倍率。"
                )
    if not found:
        sections.append("| 尚无有效正式运行 | — | — | — | — | — | — | — | — | — | — | — |")
    sections.extend(["", "## 运行身份与原始数据", ""])
    if not formal_runs:
        sections.append("当前 raw JSON 尚无正式运行。运行 `python tools/benchmark.py` 后会追加一个新 run_id 并生成本节的完整身份信息。")
    for run in formal_runs:
        sections.extend([
            f"### {run['run_id']}",
            "",
            f"- 状态：`{run['status']}`；模式：`{run['mode']}`；UTC 开始：`{run['started_at_utc']}`。",
            f"- 采集代码 Git SHA：`{run['git']['commit_sha']}`；开始时工作区干净：`{run['git']['working_tree_clean_at_start']}`。",
            f"- 环境：{run['environment']['platform']}；架构 `{run['environment']['machine']}`；Python `{run['environment']['python_version'].splitlines()[0]}`；可执行文件 `{run['environment']['python_executable']}`。处理器：`{run['environment']['processor'] or '未报告'}`。",
            f"- 固定 seed：`{run['seed']}`；规模：`{', '.join(str(size) for size in run['sizes'])}`；正式重复数：`{run['formal_repeats']}`；timeout：`{run['timeout_seconds']} s`；正式样本 `{len(run['trials'])}` 条、配对 `{len(run['pairs'])}` 组、warm-up `{len(run['warmups'])}` 条。",
            f"- 源文件 SHA-256：`bench/arithmetic.lwt` `{run['source_sha256']['bench/arithmetic.lwt']}`；`bench/arithmetic.py` `{run['source_sha256']['bench/arithmetic.py']}`；`bench/array_scan.lwt` `{run['source_sha256']['bench/array_scan.lwt']}`；`bench/array_scan.py` `{run['source_sha256']['bench/array_scan.py']}`。",
            f"- 原始记录：[bench/results.json](../bench/results.json) 中 run_id `{run['run_id']}` 的完整对象，含每次 argv、执行顺序、elapsed_ns、返回码、timeout、stdout/stderr Base64/长度/hash、预期输出校验及配对状态。",
            "",
        ])
    sections.extend([
        "## 结果解释与限制",
        "",
        "小规模中固定的子进程创建、Python 启动及 LWT 导入/解析成本可能占较大比例；规模增加后循环工作相对增加，但具体趋势仅适用于本报告所列运行。中位数降低偶发调度尖峰的影响，min/max/range 保留了各样本波动；背景进程、CPU 调度、缓存和电源状态仍会影响结果。",
        "",
        "本次测量只代表记录的 Windows 主机、CPU、Python 版本、提交和规模。没有在 Linux、macOS、Python 3.10 或其他硬件上复验；不推及其他机器或平台。计时包含启动、加载和解析，不能解释为纯 LWT 语言运行时倍率；样本规模有限，且未控制操作系统背景负载。S11 未实施解释器性能优化，也没有用 S10 并发读取时间作对照。",
        "",
    ])
    return "\n".join(sections)


def save_report(results: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(render_report(results), encoding="utf-8", newline="\n")


def create_run(mode: str, sizes: tuple[int, ...], repeats: int, seed: int, timeout: int) -> dict[str, Any]:
    git = git_snapshot()
    return {
        "run_id": str(uuid.uuid4()),
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "status": "running",
        "started_at_utc": utc_now(),
        "finished_at_utc": None,
        "git": git,
        "environment": environment_record(),
        "repo_root": str(ROOT),
        "cwd": str(ROOT),
        "source_sha256": file_hashes(),
        "seed": seed,
        "sizes": list(sizes),
        "formal_repeats": repeats if mode == "formal" else 0,
        "calibration_repeats": repeats if mode == "calibration" else 0,
        "warmup_policy": {"runs_per_benchmark_size_language": 1, "timed": False, "validated": True},
        "timeout_seconds": timeout,
        "timing": {
            "clock": "time.perf_counter_ns",
            "boundary": "immediately before subprocess.run through immediately after return/timeout/launch error",
            "metric": "new-process end-to-end wall-clock time",
            "includes": ["process creation", "Python startup", "LWT package import and source lex/parse", "workload", "stdout/stderr production", "waiting for child completion"],
            "excludes_after_timer": ["stdout verification", "hashing", "statistics", "JSON serialization and write"],
            "shell": False,
            "stdin": "subprocess.DEVNULL",
            "stdout_stderr": "captured bytes",
        },
        "planned_subprocess_counts": {
            "warmups": len(BENCHMARKS) * len(sizes) * len(LANGUAGES),
            "measured_trials": len(BENCHMARKS) * len(sizes) * len(LANGUAGES) * repeats,
            "total": len(BENCHMARKS) * len(sizes) * len(LANGUAGES) * (repeats + 1),
        },
        "warmups": [],
        "trials": [],
        "pairs": [],
        "errors": [],
        "failure_count": 0,
    }


def update_run_status(run: dict[str, Any]) -> None:
    failed_attempts = [
        item for item in run["warmups"] + run["trials"]
        if not item["verification"]["passed"]
    ]
    failed_pairs = [item for item in run["pairs"] if not item["valid"]]
    run["failure_count"] = len(failed_attempts) + len(failed_pairs)
    if run["failure_count"]:
        run["status"] = "invalid"
    elif run.get("finished_at_utc") is None:
        run["status"] = "running"
    else:
        run["status"] = "valid"


def run_benchmark(mode: str, sizes: tuple[int, ...], repeats: int, seed: int, timeout: int) -> dict[str, Any]:
    run = create_run(mode, sizes, repeats, seed, timeout)
    data = load_results()
    if any(existing.get("run_id") == run["run_id"] for existing in data["runs"]):
        raise RuntimeError("UUID collision while generating run_id")
    data["runs"].append(run)
    atomic_write_json(RESULTS_PATH, data)
    execution_order = 0

    warmups = [
        (benchmark, n, language)
        for benchmark in BENCHMARKS
        for n in sizes
        for language in LANGUAGES
    ]
    random.Random(seed ^ 0x5A17).shuffle(warmups)
    for benchmark, n, language in warmups:
        execution_order += 1
        argv = make_argv(language, benchmark, n)
        expected = expected_stdout(benchmark, n)
        execution = execute_command(argv, timeout, timed=False)
        record = make_attempt_record(
            attempt_id=f"warmup-{execution_order:04d}", kind="warmup", order=execution_order,
            benchmark=benchmark, language=language, n=n, argv=argv, execution=execution,
            expected=expected, timeout_seconds=timeout,
        )
        run["warmups"].append(record)
        update_run_status(run)
        save_run(run)

    # A failed warm-up makes it unsafe to claim the subsequent formal samples
    # followed the required validated-warm-up protocol. Preserve the evidence,
    # mark this run invalid, and do not start any measured child processes.
    if any(not item["verification"]["passed"] for item in run["warmups"]):
        run["finished_at_utc"] = utc_now()
        update_run_status(run)
        save_run(run)
        if mode == "formal":
            save_report(load_results())
        return run

    schedule = build_schedule(sizes, repeats, seed)
    attempt_by_language: dict[str, dict[str, Any]] = {}
    for block in schedule:
        expected = expected_stdout(block["benchmark"], block["size"])
        attempt_by_language = {}
        for language in block["language_order"]:
            execution_order += 1
            argv = make_argv(language, block["benchmark"], block["size"])
            execution = execute_command(argv, timeout, timed=True)
            record = make_attempt_record(
                attempt_id=f"trial-{len(run['trials']) + 1:04d}", kind="formal" if mode == "formal" else "calibration",
                order=execution_order, benchmark=block["benchmark"], language=language,
                n=block["size"], argv=argv, execution=execution, expected=expected,
                timeout_seconds=timeout, pair_id=block["pair_id"], repeat_index=block["repeat_index"],
            )
            run["trials"].append(record)
            attempt_by_language[language] = record
            update_run_status(run)
            save_run(run)
        pair = make_pair_record(
            block["pair_id"], block["benchmark"], block["size"], block["repeat_index"],
            attempt_by_language, expected,
        )
        run["pairs"].append(pair)
        update_run_status(run)
        save_run(run)

    run["finished_at_utc"] = utc_now()
    update_run_status(run)
    save_run(run)
    all_results = load_results()
    if mode == "formal":
        save_report(all_results)
    return run


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "运行 LWT/Python 成对新进程端到端基准。默认正式模式为 2 个算法 × 3 个规模 × "
            "2 种语言 × 10 次 = 120 个计时子进程，另有 12 个不计时 warm-up；按序运行，可能需要数分钟。"
        )
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--calibration", action="store_true",
        help="运行非正式校准：每个算法/规模/语言 1 次；结果标为 calibration，不进入报告统计。",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help=f"固定交错随机种子（默认 {DEFAULT_SEED}）。")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS, help=f"每个子进程 timeout 秒（默认 {DEFAULT_TIMEOUT_SECONDS}）。")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = argument_parser().parse_args(argv)
    mode = "calibration" if args.calibration else "formal"
    repeats = 1 if args.calibration else DEFAULT_REPEATS
    if args.timeout <= 0:
        print("benchmark: --timeout must be positive", file=sys.stderr)
        return 2
    try:
        run = run_benchmark(mode, DEFAULT_SIZES, repeats, args.seed, args.timeout)
    except Exception as error:
        print(f"benchmark: failed before a run record could be finalized: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    attempt_total = len(run["warmups"]) + len(run["trials"])
    passed = sum(1 for attempt in run["warmups"] + run["trials"] if attempt["verification"]["passed"])
    failed = run["failure_count"]
    print(
        f"run_id={run['run_id']} mode={mode} attempts={attempt_total} "
        f"passed_attempts={passed} failures={failed} status={run['status']}\n"
        f"raw={RESULTS_PATH}\nreport={REPORT_PATH}"
    )
    if failed:
        print("benchmark: invalid run; all attempts were retained in bench/results.json", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
