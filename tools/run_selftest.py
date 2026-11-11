"""One command that runs the LWT-native self-test suite (course chapter 8, task 2).

The self-test itself is written **in LWT** (``tests/selftest/lwt_selftest.lwt``):
its ``expect`` helper is a LWT function, every check prints ``[PASS] <name>`` or
``[FAIL] <name>``, and the last line prints ``<passed>/<total> 全部通过``.

This tool does not assert language behaviour on its own -- it only
invokes the public CLI (``python -m lwt``), checks the *shape* of the output
(zero FAIL, ``passed == total``, summary line present) and records the evidence.

Usage::

    python tools/run_selftest.py
    python tools/run_selftest.py --out reports/s55-selftest/selftest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCRIPT = REPO_ROOT / "tests" / "selftest" / "lwt_selftest.lwt"
DEFAULT_OUT = REPO_ROOT / "reports" / "s55-selftest" / "selftest.json"
# The suite reads exactly one line from stdin for the "basic input" check.
DEFAULT_STDIN = "42\n"
PROTECTED_PREFIXES = ("bench/", "reports/s44-performance/", "tests/cases/")


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _render_markdown(report: dict) -> str:
    lines = [
        "# LWT 原生自测（用 LWT 测试 LWT）",
        "",
        f"- 脚本：`{report['script']}`（SHA-256 `{report['script_sha256'][:16]}…`）",
        f"- 命令：`{report['command']}`",
        f"- 结果：**{report['passed']}/{report['total']}**，失败 {report['failed']}，退出码 {report['exit_code']}",
        f"- 结论：**{'PASS' if report['ok'] else 'FAIL'}**",
        f"- 记录时间（UTC）：{report['recorded_at_utc']}",
        "",
        "## 逐项结果",
        "",
        "| # | 结果 | 项目 |",
        "|---:|---|---|",
    ]
    for item in report["items"]:
        mark = "PASS" if item["result"] == "PASS" else "FAIL"
        lines.append(f"| {item['index']} | {mark} | {item['name']} |")
    lines.append("")
    lines.append("判定只依赖脚本自身输出的 `[PASS]/[FAIL]` 与末尾总数行；")
    lines.append("本工具不重算任何断言，也不比对 Python 侧的期望输出。")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--script", default=str(DEFAULT_SCRIPT))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--stdin", default=DEFAULT_STDIN)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args(argv)

    script = Path(args.script)
    if not script.is_absolute():
        script = (REPO_ROOT / script).resolve()
    if not script.is_file():
        print(f"run_selftest: script not found: {script}", file=sys.stderr)
        return 2
    rel = _relative(script)
    if rel.startswith(PROTECTED_PREFIXES):
        print(f"run_selftest: refusing to treat {rel} as a self-test script", file=sys.stderr)
        return 2

    source = script.read_bytes()
    command = [sys.executable, "-m", "lwt", rel]
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            input=args.stdin.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=args.timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print(f"run_selftest: timed out after {args.timeout}s", file=sys.stderr)
        return 1
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    stdout = completed.stdout.decode("utf-8", "replace")
    stderr = completed.stderr.decode("utf-8", "replace")
    items: list[dict] = []
    summary_line = ""
    for raw in stdout.splitlines():
        line = raw.strip()
        if line.startswith("[PASS] "):
            items.append({"index": len(items) + 1, "result": "PASS", "name": line[7:].strip()})
        elif line.startswith("[FAIL] "):
            items.append({"index": len(items) + 1, "result": "FAIL", "name": line[7:].strip()})
        elif "/" in line and ("全部通过" in line or "有失败" in line):
            summary_line = line

    passed = sum(1 for item in items if item["result"] == "PASS")
    failed = sum(1 for item in items if item["result"] == "FAIL")
    total = len(items)
    summary_ok = bool(summary_line) and summary_line.startswith(f"{passed}/{total} ")
    declared_complete = "全部通过" in summary_line
    ok = (
        completed.returncode == 0
        and failed == 0
        and total > 0
        and passed == total
        and summary_ok
        and declared_complete
    )

    report = {
        "tool": "run_selftest",
        "script": rel,
        "script_sha256": hashlib.sha256(source).hexdigest(),
        "command": "python -m lwt " + rel,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "stdin": args.stdin,
        "exit_code": completed.returncode,
        "elapsed_ms": round(elapsed_ms, 1),
        "passed": passed,
        "failed": failed,
        "total": total,
        "summary_line": summary_line,
        "items": items,
        "stderr": stderr[-2000:],
        "recorded_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ok": ok,
    }

    # Echo the per-item lines so a single command shows every result and the total.
    sys.stdout.write(stdout)
    if not stdout.endswith("\n"):
        sys.stdout.write("\n")
    if stderr.strip():
        sys.stderr.write(stderr)

    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path
    _atomic_write_json(out_path, report)
    out_path.with_suffix(".md").write_text(_render_markdown(report), encoding="utf-8")
    print(f"run_selftest: {passed}/{total} 通过，失败 {failed}，exit={completed.returncode} -> {_relative(out_path)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
