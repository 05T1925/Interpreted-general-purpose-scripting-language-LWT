"""Measure LWT interpreter startup cost with a reproducible A/B protocol (S44).

Three commands are timed as fresh subprocesses from the repository root:

  1. ``python -c pass``                     -- bare interpreter baseline
  2. ``python -m lwt --help``               -- LWT package import + CLI parse
  3. ``python -m lwt examples/guide/hello.lwt`` -- full startup + parse + tiny run

Each command runs ``--warmups`` warm-up calls (validated, not timed) followed
by ``--repeats`` timed formal calls. Formal runs are issued in interleaved
round-robin blocks (`pass`, `help`, `hello`, `pass`, `help`, `hello`, ...) to
reduce time drift within a run. Every attempt records its full argv, cwd,
exit code, byte-exact stdout/stderr hashes and perf_counter_ns duration.

This tool NEVER writes to protected evidence (`reports/runtime-profile.*`,
`bench/results.json`, `reports/performance.md`, ...). Output paths must be
under a directory passed with ``--out`` (default ``reports/s44-performance/``).

Usage:
    python tools/measure_startup.py --out reports/s44-performance/before \\
        --label "S44 baseline (before)" --repeats 10 --warmups 2
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
DEFAULT_REPEATS = 10
DEFAULT_WARMUPS = 2
DEFAULT_TIMEOUT = 30

PROTECTED_SUFFIXES = (
    "reports/runtime-profile.json",
    "reports/runtime-profile.md",
    "bench/results.json",
    "reports/performance.md",
)

COMMANDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("python-pass", ("-c", "pass")),
    ("lwt-help", ("-m", "lwt", "--help")),
    ("lwt-hello", ("-m", "lwt", "examples/guide/hello.lwt")),
)


def _now_utc() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _git(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, timeout=10
        )
        return result.stdout.decode("utf-8", "replace").strip()
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


def _probe_environment() -> dict[str, Any]:
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
    # Best-effort CPU model / power scheme. These are Windows-only probes and
    # may emit localized (non-UTF-8) text; decode defensively. Failure is not
    # fatal and is recorded as 'unavailable' so the report stays honest.
    def _probe(cmd: list[str]) -> str:
        try:
            out = subprocess.run(cmd, capture_output=True, timeout=15)
            raw = out.stdout or b""
            text = raw.decode("utf-8", "replace")
            if "\ufffd" in text:  # localized Windows output (e.g. GBK powercfg)
                text = raw.decode("gbk", "replace")
            return " ".join(text.split())[:160] or "unavailable"
        except Exception:  # noqa: BLE001 - probes must never abort a measurement
            return "unavailable"

    env["cpu_model"] = _probe(
        ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"]
    )
    env["power_scheme"] = _probe(["powercfg", "/getactivescheme"])
    return env


def _run_once(name: str, extra_argv: tuple[str, ...], timeout: int) -> dict[str, Any]:
    argv = [sys.executable, *extra_argv]
    started_ns = time.perf_counter_ns()
    result = subprocess.run(
        argv,
        cwd=REPO_ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        timeout=timeout,
    )
    elapsed_ns = time.perf_counter_ns() - started_ns
    return {
        "command": name,
        "argv": argv,
        "cwd": str(REPO_ROOT),
        "exit_code": result.returncode,
        "elapsed_ns": elapsed_ns,
        "stdout_len": len(result.stdout),
        "stderr_len": len(result.stderr),
        "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
    }


def _stats(samples_ns: list[int]) -> dict[str, Any]:
    ordered = sorted(samples_ns)
    return {
        "n": len(ordered),
        "median_ms": round(statistics.median(ordered) / 1e6, 3),
        "min_ms": round(ordered[0] / 1e6, 3),
        "max_ms": round(ordered[-1] / 1e6, 3),
        "range_ms": round((ordered[-1] - ordered[0]) / 1e6, 3),
        "samples_ns": ordered,
    }


def measure(repeats: int, warmups: int, timeout: int) -> dict[str, Any]:
    all_attempts: list[dict[str, Any]] = []
    by_command: dict[str, list[int]] = {name: [] for name, _ in COMMANDS}

    # Warm-ups: validate each command is *stable* (some CLI paths, notably
    # `--help`, legitimately exit non-zero in the current interpreter). We
    # require a stable exit code across warm-ups, not success, and record it.
    warmup_exit: dict[str, int] = {}
    for name, extra in COMMANDS:
        for _ in range(warmups):
            attempt = _run_once(name, extra, timeout)
            if name in warmup_exit and attempt["exit_code"] != warmup_exit[name]:
                raise RuntimeError(
                    f"startup warm-up unstable for {name}: "
                    f"{warmup_exit[name]} vs {attempt['exit_code']}"
                )
            warmup_exit[name] = attempt["exit_code"]

    # Formal: interleaved round-robin blocks to reduce time drift. Every
    # formal run must reproduce its warm-up exit code, otherwise the sample is
    # measuring a different code path and the run is rejected.
    for index in range(repeats):
        for name, extra in COMMANDS:
            attempt = _run_once(name, extra, timeout)
            if attempt["exit_code"] != warmup_exit[name]:
                raise RuntimeError(
                    f"startup formal run {index} for {name} changed exit code: "
                    f"{warmup_exit[name]} -> {attempt['exit_code']}"
                )
            attempt["block"] = index
            all_attempts.append(attempt)
            by_command[name].append(attempt["elapsed_ns"])

    summary = {name: _stats(samples) for name, samples in by_command.items()}
    for name in summary:
        summary[name]["exit_code"] = warmup_exit[name]
    pass_med = summary["python-pass"]["median_ms"]
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": "lwt-startup-bench",
        "generated_at_utc": _now_utc(),
        "environment": _probe_environment(),
        "exit_codes": warmup_exit,
        "note": "python -m lwt --help currently exits 4 (FileError: cannot read source file); "
                "the measurement still captures the full package-import + CLI-parse path. "
                "Exit codes are recorded per command and held stable across warm-ups and formal runs.",
        "protocol": {
            "warmups": warmups,
            "repeats": repeats,
            "order": "interleaved round-robin blocks",
            "timing": "time.perf_counter_ns around subprocess.run",
            "cwd": str(REPO_ROOT),
            "shell": False,
            "stdin": "DEVNULL",
            "timeout_s": timeout,
        },
        "commands": {name: list(extra) for name, extra in COMMANDS},
        "summary": summary,
        "derived": {
            "help_minus_pass_ms": round(summary["lwt-help"]["median_ms"] - pass_med, 3),
            "hello_minus_pass_ms": round(summary["lwt-hello"]["median_ms"] - pass_med, 3),
            "help_over_pass": round(summary["lwt-help"]["median_ms"] / pass_med, 3) if pass_med else None,
            "hello_over_pass": round(summary["lwt-hello"]["median_ms"] / pass_med, 3) if pass_med else None,
        },
        "attempts": all_attempts,
    }


def _render_markdown(doc: dict[str, Any], label: str) -> str:
    env = doc["environment"]
    s = doc["summary"]
    d = doc["derived"]
    lines = [
        f"# LWT 启动成本测量（{label}）",
        "",
        "> 独立证据；新进程端到端墙钟，含 Python 启动 + 包导入 + CLI 解析；"
        "不是纯 AST 执行速度。复算见 `tools/measure_startup.py`，原始逐次样本见同名 JSON。",
        "",
        f"> 说明：{doc['note']}",
        "",
        "## 环境与协议",
        "",
        f"- 采集时间（UTC）：{doc['generated_at_utc']}",
        f"- Git HEAD：`{env['git_head']}`（分支 `{env['branch']}`）",
        f"- Python：`{env['python_version']}`；可执行：`{env['python_executable']}`",
        f"- 平台：`{env['platform']}`；CPU：`{env.get('cpu_model', 'unavailable')}`；逻辑核 {env['cpu_count']}",
        f"- 电源方案：`{env.get('power_scheme', 'unavailable')}`",
        f"- 协议：{doc['protocol']['warmups']} 预热 + {doc['protocol']['repeats']} 正式，"
        f"{doc['protocol']['order']}，perf_counter_ns 紧贴 subprocess.run。",
        "",
        "## 结果（中位数 / min / max / range，ms）",
        "",
        "| 命令 | 中位数 | min | max | range | 退出码 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    labels = {
        "python-pass": "`python -c pass`",
        "lwt-help": "`python -m lwt --help`",
        "lwt-hello": "`python -m lwt examples/guide/hello.lwt`",
    }
    for name, _ in COMMANDS:
        st = s[name]
        lines.append(
            f"| {labels[name]} | {st['median_ms']:.3f} | {st['min_ms']:.3f} | "
            f"{st['max_ms']:.3f} | {st['range_ms']:.3f} | {st['exit_code']} |"
        )
    lines += [
        "",
        "## 派生量",
        "",
        f"- `--help − pass` 中位数差：{d['help_minus_pass_ms']:.3f} ms（LWT 包导入 + CLI 解析的近似上界）",
        f"- `hello − pass` 中位数差：{d['hello_minus_pass_ms']:.3f} ms（上项 + 词法/语法 + 极小程序执行）",
        f"- `--help / pass`：{d['help_over_pass']}；`hello / pass`：{d['hello_over_pass']}",
        "",
        "## 限制",
        "",
        "- 只在本机本次运行有效；未在 Python 3.10 / Linux / 远端 CI 复验。",
        "- 背景负载、电源模式、page cache 与 CPU 调度会影响绝对数值；以同机 A/B 差值与中位数为准。",
        "- 这些数值是端到端墙钟，不能与 `micro_bench.py` 的纯 `execute` 阶段相减或相除。",
        "",
    ]
    return "\n".join(lines)


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default="reports/s44-performance/startup.json",
        help="JSON output path (relative to repo root). The .md is written beside it.",
    )
    parser.add_argument("--label", default="S44 startup", help="provenance label for the markdown title")
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--warmups", type=int, default=DEFAULT_WARMUPS)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _argument_parser().parse_args(argv)
    if args.repeats < 1 or args.warmups < 0 or args.timeout < 1:
        sys.stderr.write("measure_startup: --repeats>=1, --warmups>=0, --timeout>=1 required\n")
        return 4

    out_path = REPO_ROOT / args.out
    md_path = out_path.with_suffix(".md")

    def _display(path: Path) -> str:
        try:
            return path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            return str(path)

    # Refuse to write any protected evidence path.
    out_rel = _display(out_path)
    md_rel = _display(md_path)
    for protected in PROTECTED_SUFFIXES:
        if out_rel == protected or md_rel == protected:
            sys.stderr.write(f"measure_startup: refusing to overwrite protected evidence {protected}\n")
            return 4
    try:
        doc = measure(args.repeats, args.warmups, args.timeout)
    except (RuntimeError, subprocess.SubprocessError) as error:
        sys.stderr.write(f"measure_startup: {error}\n")
        return 3

    _atomic_text(out_path, json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic_text(md_path, _render_markdown(doc, args.label))
    print(f"measure_startup: wrote {out_rel} and {md_rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
