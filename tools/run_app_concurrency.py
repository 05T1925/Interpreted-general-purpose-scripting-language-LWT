"""Verify identical reports from concurrent, independent LWT CLI processes."""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
from threading import Barrier
from time import perf_counter_ns


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "app" / "fixtures" / "concurrency.log"
SOURCE = ROOT / "app" / "log_report.lwt"
JSON_OUTPUT = ROOT / "reports" / "app-concurrency.json"
MARKDOWN_OUTPUT = ROOT / "docs" / "app-concurrency.md"
PROCESS_COUNTS = (1, 2, 4)
TRIALS_PER_COUNT = 5
TIMEOUT_SECONDS = 30
COMMAND = (
    sys.executable,
    "-m",
    "lwt",
    "app/log_report.lwt",
    "--",
    "app/fixtures/concurrency.log",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_value(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        capture_output=True,
        check=True,
        shell=False,
        timeout=10,
    )
    return result.stdout.decode("utf-8").strip()


def raw_stream(data: bytes) -> dict[str, object]:
    return {
        "sha256": sha256(data),
        "byte_length": len(data),
        "base64": base64.b64encode(data).decode("ascii"),
    }


def launch_one() -> dict[str, object]:
    """Start one real child process and always collect/return its streams."""
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            list(COMMAND),
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
        try:
            stdout, stderr = process.communicate(timeout=TIMEOUT_SECONDS)
            timed_out = False
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            timed_out = True
        return {
            "return_code": process.returncode,
            "timed_out": timed_out,
            "stdout": raw_stream(stdout),
            "stderr": raw_stream(stderr),
        }
    except OSError as error:
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate()
        return {
            "return_code": None if process is None else process.returncode,
            "timed_out": False,
            "launch_error": f"{type(error).__name__}: {error}",
            "stdout": raw_stream(b""),
            "stderr": raw_stream(b""),
        }


def launch_concurrently(process_count: int) -> tuple[int, list[dict[str, object]]]:
    """Barrier-release N worker threads which each start one independent process."""
    barrier = Barrier(process_count + 1)

    def worker() -> dict[str, object]:
        barrier.wait(timeout=TIMEOUT_SECONDS)
        return launch_one()

    with ThreadPoolExecutor(max_workers=process_count) as executor:
        futures = [executor.submit(worker) for _ in range(process_count)]
        started_ns = perf_counter_ns()
        barrier.wait(timeout=TIMEOUT_SECONDS)
        outcomes = [future.result(timeout=TIMEOUT_SECONDS + 5) for future in futures]
        elapsed_ns = perf_counter_ns() - started_ns
    return elapsed_ns, outcomes


def is_valid_outcome(outcome: dict[str, object], reference: bytes) -> bool:
    stdout = outcome["stdout"]
    stderr = outcome["stderr"]
    return (
        outcome.get("return_code") == 0
        and outcome.get("timed_out") is False
        and "launch_error" not in outcome
        and isinstance(stdout, dict)
        and isinstance(stderr, dict)
        and stdout.get("base64") == base64.b64encode(reference).decode("ascii")
        and stderr.get("byte_length") == 0
    )


def run_warmup() -> dict[str, object]:
    try:
        completed = subprocess.run(
            list(COMMAND),
            cwd=ROOT,
            capture_output=True,
            check=False,
            shell=False,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        return {
            "return_code": None,
            "timed_out": True,
            "stdout": raw_stream(error.stdout or b""),
            "stderr": raw_stream(error.stderr or b""),
        }
    return {
        "return_code": completed.returncode,
        "timed_out": False,
        "stdout": raw_stream(completed.stdout),
        "stderr": raw_stream(completed.stderr),
    }


def markdown_report(data: dict[str, object]) -> str:
    input_info = data["input"]
    assert isinstance(input_info, dict)
    platform_info = data["environment"]
    assert isinstance(platform_info, dict)
    groups = data["groups"]
    assert isinstance(groups, list)
    lines = [
        "# LWT 日志分析器并发读取验证",
        "",
        f"- 生成时间（UTC）：`{data['generated_at_utc']}`",
        f"- OS：`{platform_info['platform']}`",
        f"- Python：`{platform_info['python']}`",
        f"- 阶段分支提交：`{data['git_sha']}`",
        f"- 应用文件提交：`{data['app_source_commit_sha']}`",
        f"- 应用源 SHA-256：`{data['app_source_sha256']}`",
        f"- 固定输入：`{input_info['path']}` ({input_info['byte_length']} bytes)",
        f"- 输入 SHA-256：`{input_info['sha256']}`",
        f"- 试验后输入 SHA-256：`{input_info['sha256_after_trials']}`（期间未改变：`{input_info['unchanged_during_trials']}`）",
        f"- 命令：`{sys.executable} -m lwt app/log_report.lwt -- app/fixtures/concurrency.log`",
        f"- 单进程 warm-up：return code `{data['warmup']['return_code']}`，stderr bytes `{data['warmup']['stderr']['byte_length']}`，作为逐字比较基准。",
        "",
        "每个计时试次通过 Python 线程池和 barrier 同时启动指定数量的独立 `python -m lwt` 子进程；计时使用 `perf_counter_ns()`，包含进程启动、解释器导入、解析、应用执行、输出和读取所需时间。每个子进程 timeout 为 30 秒。输出按字节与 warm-up stdout 比较，stderr 必须为空、return code 必须为 0。Python 线程仅用于协调外部进程，不是 LWT 线程或运行时并发。",
        "",
        "| 进程数 | 试次数 | 每次批次墙钟时间（ms） | 每个进程输出一致 | return code / stderr |",
        "|---:|---:|---|---|---|",
    ]
    for group in groups:
        assert isinstance(group, dict)
        durations = [f"{trial['elapsed_ns'] / 1_000_000:.3f}" for trial in group["trials"]]
        lines.append(
            f"| {group['process_count']} | {len(group['trials'])} | "
            f"{', '.join(durations)} | {group['all_outputs_match']} | "
            f"{group['all_return_codes_zero']} / {group['all_stderr_empty']} |"
        )
    lines.extend(
        [
            "",
            "全部逐试次原始记录（进程返回码、stdout/stderr 长度、SHA-256 和 Base64 原始字节）保存在 [`reports/app-concurrency.json`](../reports/app-concurrency.json)。",
            "",
            "## 解释与限制",
            "",
            "本次结果只证明固定输入在 1、2、4 个独立进程同时读取时输出一致，且保存了批次墙钟记录；不据此推断进程数增加会更快。样本规模、OS 文件缓存、进程启动与解释器解析成本、背景负载均会影响时间。输入文件在试验期间保持不变；不测试其他进程并发改写文件时的快照一致性。该实验不是 S11 的 LWT/Python 成对性能基准，也不是纯磁盘吞吐测试。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    input_bytes = INPUT.read_bytes()
    app_bytes = SOURCE.read_bytes()
    app_commit = git_value("log", "-1", "--format=%H", "--", "app/log_report.lwt")
    git_sha = git_value("rev-parse", "HEAD")
    warmup = run_warmup()
    reference = base64.b64decode(warmup["stdout"]["base64"])
    errors: list[str] = []
    if warmup["return_code"] != 0 or warmup["timed_out"] or warmup["stderr"]["byte_length"]:
        errors.append("warm-up failed (non-zero return code, timeout, or non-empty stderr)")

    groups: list[dict[str, object]] = []
    for process_count in PROCESS_COUNTS:
        trials: list[dict[str, object]] = []
        for trial_number in range(1, TRIALS_PER_COUNT + 1):
            elapsed_ns, outcomes = launch_concurrently(process_count)
            valid = [is_valid_outcome(outcome, reference) for outcome in outcomes]
            trial = {
                "trial": trial_number,
                "elapsed_ns": elapsed_ns,
                "processes": outcomes,
                "all_outputs_match": all(
                    isinstance(outcome.get("stdout"), dict)
                    and outcome["stdout"].get("base64") == base64.b64encode(reference).decode("ascii")
                    for outcome in outcomes
                ),
                "all_processes_valid": all(valid) and len(outcomes) == process_count,
            }
            trials.append(trial)
            if not trial["all_processes_valid"]:
                errors.append(f"process_count={process_count}, trial={trial_number} did not pass")
        groups.append(
            {
                "process_count": process_count,
                "trials": trials,
                "all_outputs_match": all(trial["all_outputs_match"] for trial in trials),
                "all_return_codes_zero": all(
                    process.get("return_code") == 0
                    for trial in trials
                    for process in trial["processes"]
                ),
                "all_stderr_empty": all(
                    process["stderr"].get("byte_length") == 0
                    for trial in trials
                    for process in trial["processes"]
                ),
            }
        )

    input_sha256_after = sha256(INPUT.read_bytes())
    input_unchanged = input_sha256_after == sha256(input_bytes)
    if not input_unchanged:
        errors.append("fixed concurrency input changed while trials were running")

    data: dict[str, object] = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_branch": git_value("branch", "--show-current"),
        "git_sha": git_sha,
        "app_source_commit_sha": app_commit,
        "app_source_sha256": sha256(app_bytes),
        "command": list(COMMAND),
        "cwd": str(ROOT),
        "timeout_seconds": TIMEOUT_SECONDS,
        "trials_per_process_count": TRIALS_PER_COUNT,
        "warmup": warmup,
        "reference_stdout_sha256": warmup["stdout"]["sha256"],
        "input": {
            "path": "app/fixtures/concurrency.log",
            "byte_length": len(input_bytes),
            "sha256": sha256(input_bytes),
            "sha256_after_trials": input_sha256_after,
            "unchanged_during_trials": input_unchanged,
        },
        "environment": {
            "python": sys.version,
            "python_executable": sys.executable,
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
        },
        "groups": groups,
        "errors": errors,
    }
    JSON_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    MARKDOWN_OUTPUT.write_text(markdown_report(data), encoding="utf-8", newline="\n")

    total_processes = sum(
        len(trial["processes"])
        for group in groups
        for trial in group["trials"]
    )
    print(f"warm-up: return_code={warmup['return_code']} stderr_bytes={warmup['stderr']['byte_length']}")
    for group in groups:
        durations = ", ".join(
            f"{trial['elapsed_ns'] / 1_000_000:.3f} ms" for trial in group["trials"]
        )
        print(
            f"processes={group['process_count']} trials={len(group['trials'])} "
            f"times=[{durations}] outputs={group['all_outputs_match']} "
            f"return_codes={group['all_return_codes_zero']} stderr_empty={group['all_stderr_empty']}"
        )
    print(f"input_sha256={data['input']['sha256']}")
    print(f"app_source_commit_sha={app_commit}")
    print(f"git_sha={git_sha}")
    print(f"concurrent_processes={total_processes}")
    print(f"raw_data={JSON_OUTPUT.relative_to(ROOT)}")
    print(f"report={MARKDOWN_OUTPUT.relative_to(ROOT)}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
