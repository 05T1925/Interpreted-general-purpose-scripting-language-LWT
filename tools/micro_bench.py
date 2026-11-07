"""S42 Wave D: single-process runtime micro-benchmark and hot-spot profile.

This tool separates source loading/lexing/parsing from *pure tree-walk
execution* by parsing each workload once and then executing the same parsed
``Program`` many times in one process. It is deliberately **not** the S11
formal benchmark: it does not spawn a process per trial, does not include
Python startup/import in the timed region, and never writes to
``bench/results.json`` or ``reports/performance.md``.

Run from the repository root::

    python tools/micro_bench.py --out reports/

Outputs ``runtime-profile.json`` (raw medians and per-run samples) and a
human-readable ``runtime-profile.md`` in ``--out``. Both are new evidence files;
existing S10/S11/S28/S29 raw data are read-only inputs or untouched.
"""

from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lwt.errors import LwtError  # noqa: E402
from lwt.modules import load_module_graph  # noqa: E402
from lwt.observability import ProfileCollector  # noqa: E402
from lwt.runtime import execute  # noqa: E402

SCHEMA_VERSION = 1
DEFAULT_REPEATS = 20
DEFAULT_WARMUPS = 3
SIZES = (100, 1000, 5000)


def _now_utc() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head() -> str:
    import subprocess

    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


def _atomic_text(path: Path, text: str) -> None:
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", dir=path.parent,
        prefix=path.name + ".", suffix=".tmp", delete=False,
    ) as handle:
        temp = Path(handle.name)
        handle.write(text)
    os.replace(temp, path)


def _median_ns(samples: list[int]) -> int:
    return int(statistics.median(samples))


def _stats(samples: list[int]) -> dict[str, int]:
    return {
        "runs": len(samples),
        "median_ns": _median_ns(samples),
        "min_ns": min(samples),
        "max_ns": max(samples),
        "range_ns": max(samples) - min(samples),
    }


# Workloads: (name, source, oracle) where oracle(n) returns exact stdout bytes.
def _arithmetic_expected(n: int) -> bytes:
    return f"{n}|{n * (n + 1) // 2}\n".encode("ascii")


def _array_scan_expected(n: int) -> bytes:
    values = [(i * 17 + 3) % 1009 for i in range(n)]
    return f"{n}|{sum(values)}|{sum(1 for v in values if v % 97 == 0)}\n".encode("ascii")


def _dict_counts_expected(n: int) -> bytes:
    distinct = len({str((i * 17 + 3) % 1009) for i in range(n)})
    return f"{n}|{distinct}\n".encode("ascii")


WORKLOADS = (
    ("arithmetic", "bench/arithmetic.lwt", _arithmetic_expected),
    ("array_scan", "bench/array_scan.lwt", _array_scan_expected),
    ("dict_counts", "bench/dict_counts.lwt", _dict_counts_expected),
)


def _run_once(program: Any, graph: Any, source: str, args: tuple[str, ...]) -> bytes:
    """Execute one already-parsed program with fresh I/O; return raw stdout."""

    sink = io.StringIO()
    execute(
        program,
        io.BytesIO(b""),
        sink,
        args,
        module_graph=graph,
        source_path=source,
    )
    return sink.getvalue().encode("utf-8")


def _measure_workload(
    name: str,
    source: str,
    oracle: Any,
    size: int,
    repeats: int,
    warmups: int,
) -> dict[str, Any]:
    path = REPO_ROOT / source
    expected = oracle(size)
    args = (str(size),)

    parse_samples: list[int] = []
    exec_samples: list[int] = []
    graph = None
    program = None
    last_output = b""

    # Parsing is measured repeatedly so the number is robust, but the *executed*
    # AST is always the final parse of the same source.
    for _ in range(warmups + repeats):
        started = time.perf_counter_ns()
        graph = load_module_graph(source, include_hashes=True)
        parse_samples.append(time.perf_counter_ns() - started)
        program = graph.entry.program

    for _ in range(warmups):
        last_output = _run_once(program, graph, source, args)
    if last_output != expected:
        raise LwtError(
            "RuntimeError",
            f"micro_bench oracle mismatch for {name} N={size}: "
            f"got {last_output!r}, expected {expected!r}",
            3,
        )

    for _ in range(repeats):
        started = time.perf_counter_ns()
        last_output = _run_once(program, graph, source, args)
        exec_samples.append(time.perf_counter_ns() - started)
        if last_output != expected:
            raise LwtError(
                "RuntimeError",
                f"micro_bench oracle mismatch during timed run for {name} N={size}",
                3,
            )

    return {
        "workload": name,
        "source": source,
        "source_sha256": _sha256(path),
        "n": size,
        "expected_stdout_sha256": _sha256_from_bytes(expected),
        "parse": _stats(parse_samples),
        "execute": _stats(exec_samples),
        "parse_to_execute_median_ratio": round(
            _median_ns(parse_samples) / _median_ns(exec_samples), 6
        ),
        "repeats": repeats,
        "warmups": warmups,
    }


def _sha256_from_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _profile_workload(name: str, source: str, size: int) -> dict[str, Any]:
    """Collect one S28-compatible profile for a workload at a fixed size."""

    graph = load_module_graph(source, include_hashes=True)
    collector = ProfileCollector(graph, source)
    sink = io.StringIO()
    try:
        execute(
            graph.entry.program,
            io.BytesIO(b""),
            sink,
            (str(size),),
            module_graph=graph,
            source_path=source,
            observer=collector,
        )
    except LwtError:
        pass  # The profile document still records the error status.
    document = collector.as_dict()
    events = document.get("events", [])
    from collections import Counter

    kinds = Counter(event.get("event") for event in events)
    total = len(events) or 1
    distribution = [
        {"event": str(kind), "count": int(count), "percentage": round(count * 100.0 / total, 2)}
        for kind, count in sorted(kinds.items(), key=lambda item: (-item[1], str(item[0])))
    ]
    statements = document.get("coverage", {}).get("summary", {}).get("statements", {})
    decisions = document.get("coverage", {}).get("summary", {}).get("decisions", {})
    functions = document.get("coverage", {}).get("summary", {}).get("functions", {})
    return {
        "workload": name,
        "size": size,
        "status": document.get("status"),
        "exit_code": document.get("exit_code"),
        "event_count": len(events),
        "event_distribution": distribution,
        "statement_coverage": statements,
        "decision_coverage": decisions,
        "function_coverage": functions,
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# LWT 运行时微基准与热点画像（S42 Wave D）")
    lines.append("")
    lines.append("> 本文件是 S42 新增的**独立画像证据**，不是 S11 正式性能报告的修订。"
                 "计时口径、原始 run 身份与六组表格仍以 [S11 报告](../reports/performance.md) 为准；"
                 "本工具不写入 `bench/results.json`，也不改写任何 S10/S11/S28/S29 固定证据。")
    lines.append("")
    meta = report["environment"]
    lines.append("## 环境与口径")
    lines.append("")
    lines.append(f"- 采集时间（UTC）：{meta['generated_at_utc']}")
    lines.append(f"- Git HEAD：`{meta['git_head']}`")
    lines.append(f"- Python：`{meta['python_version']}`；平台：`{meta['platform']}`")
    lines.append(f"- 工具：`tools/micro_bench.py`（schema v{report['schema_version']}）")
    lines.append(f"- 每负载每规模：预热 {meta['warmups']} 次、计时 {meta['repeats']} 次；"
                 "同一进程、同一已解析 AST，输出逐次与独立 oracle 比对。")
    lines.append("- `parse` = 读源文件 + 词法 + 语法 + 模块链接；"
                 "`execute` = 纯 AST 树遍历执行（**不含**进程创建、Python 启动和包导入）。"
                 "因此本表中的 `execute` 不能直接与 S11 端到端墙钟倍率相减或相除。")
    lines.append("")
    lines.append("## 阶段耗时（中位数，ms）")
    lines.append("")
    lines.append("| 负载 | N | parse | execute | parse/execute | 输出校验 |")
    lines.append("|---|---:|---:|---:|---:|---|")
    for row in report["measurements"]:
        lines.append(
            f"| {row['workload']} | {row['n']} | "
            f"{row['parse']['median_ns'] / 1e6:.3f} | "
            f"{row['execute']['median_ns'] / 1e6:.3f} | "
            f"{row['parse_to_execute_median_ratio']:.3f} | pass |"
        )
    lines.append("")
    lines.append("## 热点事件分布（S28 ProfileCollector，单次采集）")
    lines.append("")
    lines.append("| 负载 | N | 事件总数 | 事件类型占比 |")
    lines.append("|---|---:|---:|---|")
    for row in report["profiles"]:
        dist = ", ".join(
            f"{item['event']}={item['count']} ({item['percentage']:.1f}%)"
            for item in row["event_distribution"]
        )
        lines.append(f"| {row['workload']} | {row['size']} | {row['event_count']} | {dist} |")
    lines.append("")
    lines.append("## S43 决策规则（本轮只测量，不优化）")
    lines.append("")
    lines.append("S42 **不实现字节码 VM**。是否进入 S43 VM 评估，按以下门槛判断：")
    lines.append("")
    lines.append("1. 若 `execute` 阶段在总耗时中占主导，且 S28 事件分布显示 **>60% 事件落在高频语句/decision 分派**，"
                 "才有必要评估寄存器式 VM 以减少分派开销；否则优先树遍历热点优化"
                 "（热循环局部变量化、整数 opcode + 跳转表替代 Enum/`isinstance`、"
                 "`@dataclass(slots=True)`、超级指令/指令融合）。")
    lines.append("2. 任何 VM 方案必须以**双后端交叉验证**为首要价值（用独立后端暴露树遍历漏掉的正确性缺陷），"
                 "性能只是副产品；不得只以倍率作为立项理由。")
    lines.append("3. VM 结论必须绑定具体 CPython 版本：PEP 659 特化解释器会改变相对倍率，"
                 "不得把某一版本的微基准外推到其它版本或真实负载。")
    lines.append("4. 本表数据仅代表本机本进程内重复执行；不含启动与导入，"
                 "不得与 S11 端到端 2.7–5.0× 混为一谈，也不得在 PPT/答辩中作为 S11 性能提升。")
    lines.append("")
    lines.append("## 已知限制")
    lines.append("")
    lines.append("- 微基准在**单进程**内重复执行，规避了进程启动噪声，因此看不到 S11 所量的启动/导入成本；"
                 "它用于定位**解释器内部**耗时结构，不用于评价端到端用户体验。")
    lines.append("- S28 profile 观测本身带来额外开销，事件分布只用于结构占比，不用于计时。")
    lines.append("- 未在本轮运行 Python 3.10 / Linux / 远端 CI；相关兼容结论仍为未验证。")
    lines.append("")
    return "\n".join(lines)


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="reports/", help="output directory (default: reports/)")
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--warmups", type=int, default=DEFAULT_WARMUPS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _argument_parser().parse_args(argv)
    if args.repeats < 1 or args.warmups < 0:
        sys.stderr.write("micro_bench: --repeats must be >=1 and --warmups >=0\n")
        return 4

    measurements: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []
    try:
        for name, source, oracle in WORKLOADS:
            for size in SIZES:
                measurements.append(
                    _measure_workload(name, source, oracle, size, args.repeats, args.warmups)
                )
        for name, source, _oracle in WORKLOADS:
            profiles.append(_profile_workload(name, source, 1000))
    except LwtError as error:
        sys.stderr.write(f"micro_bench: {error.category}: {error.message}\n")
        return error.exit_code

    report = {
        "schema_version": SCHEMA_VERSION,
        "tool": "lwt-micro-bench",
        "environment": {
            "generated_at_utc": _now_utc(),
            "git_head": _git_head(),
            "python_version": sys.version,
            "platform": platform.platform(),
            "repeats": args.repeats,
            "warmups": args.warmups,
        },
        "method": {
            "timing": "perf_counter_ns around load_module_graph (parse) and execute (pure execution)",
            "process_model": "single process; parsed once, executed repeatedly",
            "excludes": ["process creation", "Python startup", "package import"],
            "oracle": "byte-exact stdout compared before and after every timed run",
            "s11_relationship": "independent evidence; never written into bench/results.json",
        },
        "measurements": measurements,
        "profiles": profiles,
    }

    out_dir = REPO_ROOT / args.out
    json_path = out_dir / "runtime-profile.json"
    md_path = out_dir / "runtime-profile.md"
    _atomic_text(json_path, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic_text(md_path, _render_markdown(report))
    print(f"micro_bench: wrote {json_path.relative_to(REPO_ROOT)} and {md_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
