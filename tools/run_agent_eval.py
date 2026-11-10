"""Objective grader for the Agent blind-eval task set (S45; reused by S47).

The blind agent must run in a *new, context-free* session; this window only
prepares tasks and the grader. The grader performs mechanical checks only and
never judges style:

  1. ``python -m lwt --check`` on the submitted program exits 0
     (skipped only when the task sets ``check_required: false``).
  4. No forbidden construct appears in any submitted ``*.lwt`` file.
  2. The program's exit code and stdout bytes match the task's expected values.
  3. ``--deterministic-runs`` repeated runs are byte-identical.


Submissions live at ``docs/agent-eval/submissions/<task-id>/`` with either
``program.lwt`` (single file) or ``main.lwt`` plus sibling ``.lwt`` modules.
If a submission directory is absent, the task is reported ``NOT_SUBMITTED``
and the summary is ``NOT_RUN`` -- never a fabricated pass.

Usage:
    python tools/run_agent_eval.py                     # grade whatever exists
    python tools/run_agent_eval.py --task <id>          # one task
    python tools/run_agent_eval.py --out reports/s45-acceptance/agent-eval.json
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TASKS_PATH = ROOT / "docs" / "agent-eval" / "tasks.json"
SUBMISSIONS = ROOT / "docs" / "agent-eval" / "submissions"
DEFAULT_OUT = ROOT / "reports" / "s45-acceptance" / "agent-eval.json"


def _run(cmd: list[str], *, stdin: bytes = b"", cwd: Path = ROOT,
         timeout: int = 30) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        cmd, cwd=cwd, input=stdin, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=timeout,
    )


def _display(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _entry(submission_dir: Path) -> Path | None:
    for name in ("program.lwt", "main.lwt"):
        candidate = submission_dir / name
        if candidate.exists():
            return candidate
    # S48: the task prompt names the file (freq.lwt, cleanup.lwt, ...). Accept
    # any single non-library module; prefer mix.lwt when both exist.
    candidates = [
        path for path in sorted(submission_dir.glob("*.lwt"))
        if path.name not in {"lib.lwt"}
    ]
    if len(candidates) == 1:
        return candidates[0]
    for path in candidates:
        if path.name == "mix.lwt":
            return path
    return None


def _forbidden_hits(source: str, forbidden: list[str]) -> list[str]:
    hits: list[str] = []
    for token in forbidden:
        if re.search(re.escape(token), source):
            hits.append(token)
    return hits


def grade_task(task: dict[str, Any], *, timeout: int = 30,
               submission_dir: Path | None = None) -> dict[str, Any]:
    task_id = task["id"]
    submission_dir = submission_dir or (SUBMISSIONS / task_id)
    entry = _entry(submission_dir) if submission_dir.exists() else None
    if entry is None:
        return {
            "id": task_id,
            "title": task["title"],
            "status": "NOT_SUBMITTED",
            "checks": {},
            "detail": f"no submission under {_display(submission_dir)}/{{program,main}}.lwt",
        }

    sources = {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(submission_dir.glob("*.lwt"))
    }
    result: dict[str, Any] = {
        "id": task_id, "title": task["title"], "status": "FAIL",
        "entry": _display(entry), "checks": {},
    }
    checks: dict[str, Any] = {}

    # 1) static check (honor the task's check_required field)
    if task.get("check_required", True):
        check = _run([sys.executable, "-m", "lwt", "--check", str(entry)], timeout=timeout)
        checks["check_exit_zero"] = {
            "pass": check.returncode == 0,
            "exit_code": check.returncode,
            "stderr": check.stderr.decode("utf-8", "replace")[:400],
        }

    # 2) forbidden constructs, across every submitted module
    hits: list[str] = []
    for name, text in sources.items():
        for token in _forbidden_hits(text, task.get("forbidden_constructs", [])):
            hits.append(f"{name}:{token}")
    checks["no_forbidden_constructs"] = {"pass": not hits, "hits": hits}

    # 3) run with args/stdin; compare exit + stdout
    args = list(task.get("args", []))
    run_args = [str(entry)]
    if args:
        run_args.extend(("--", *args))
    stdin_bytes = task.get("stdin", "").encode("utf-8")
    with tempfile.TemporaryDirectory(prefix="lwt-eval-") as folder:
        # Fixture-backed task: write the fixture and pass its path.
        if args and args[0] == "fixture":
            fixture = Path(folder) / "fixture.txt"
            fixture.write_text(task.get("fixture_content", ""), encoding="utf-8", newline="\n")
            run_args = [str(entry), "--", str(fixture)]
        try:
            outputs: list[bytes] = []
            codes: list[int] = []
            for _ in range(max(1, int(task.get("deterministic_runs", 5)))):
                proc = _run([sys.executable, "-m", "lwt", *run_args],
                            stdin=stdin_bytes, timeout=timeout)
                outputs.append(proc.stdout)
                codes.append(proc.returncode)
            expected = task["expected_stdout"].encode("utf-8")
            checks["exit_code_matches"] = {
                "pass": all(code == task["expected_exit_code"] for code in codes),
                "expected": task["expected_exit_code"], "actual": codes,
            }
            checks["stdout_matches"] = {
                "pass": outputs[0] == expected,
                "expected_b64": base64.b64encode(expected).decode("ascii"),
                "actual_b64": base64.b64encode(outputs[0]).decode("ascii"),
                "actual_text": outputs[0].decode("utf-8", "replace")[:400],
            }
            checks["deterministic_bytes"] = {
                "pass": len(set(outputs)) == 1,
                "runs": len(outputs),
            }
        except subprocess.TimeoutExpired:
            checks["timeout"] = {"pass": False, "detail": f">{timeout}s"}

    result["checks"] = checks
    result["status"] = "PASS" if all(c.get("pass") for c in checks.values()) else "FAIL"
    return result


def grade_all(task_filter: str | None = None, timeout: int = 30,
              tasks_path: Path | None = None,
              submissions_dir: Path | None = None,
              samples: int = 1,
              group: str | None = None) -> dict[str, Any]:
    # Resolve module globals at call time so tests can monkey-patch them.
    tasks_path = tasks_path or TASKS_PATH
    submissions_dir = submissions_dir or SUBMISSIONS
    doc = json.loads(tasks_path.read_text(encoding="utf-8"))
    tasks = doc["tasks"]
    if task_filter:
        tasks = [t for t in tasks if t["id"] == task_filter]
        if not tasks:
            raise SystemExit(f"run_agent_eval: unknown task {task_filter!r}")
    results: list[dict[str, Any]] = []
    for task in tasks:
        for index in range(1, max(1, samples) + 1):
            if samples == 1:
                directory = submissions_dir / task["id"]
                if group and (directory / "sample-1").exists():
                    directory = directory / "sample-1"
            else:
                directory = submissions_dir / task["id"] / f"sample-{index}"
            result = grade_task(task, timeout=timeout, submission_dir=directory)
            result["sample"] = index
            result["group"] = group
            results.append(result)
    submitted = [r for r in results if r["status"] != "NOT_SUBMITTED"]
    passed = [r for r in submitted if r["status"] == "PASS"]
    if not submitted:
        overall = "NOT_RUN"
    elif len(passed) == len(results):
        overall = "ALL_PASS"
    else:
        overall = "PARTIAL"
    per_task: dict[str, tuple[int, int]] = {}
    for task in tasks:
        rows = [r for r in results if r["id"] == task["id"]]
        submitted_rows = [r for r in rows if r["status"] != "NOT_SUBMITTED"]
        per_task[task["id"]] = (
            sum(1 for r in submitted_rows if r["status"] == "PASS"),
            len(submitted_rows),
        )
    try:
        from tools.agent_eval_stats import summarize_group
    except ModuleNotFoundError:  # running as a script: sys.path[0] is tools/
        from agent_eval_stats import summarize_group
    stats = summarize_group(group or "default", per_task, k=min(samples, 5)) if submitted else None
    return {
        "schema_version": 2 if samples > 1 else 1,
        "tool": "lwt-agent-eval",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "Blind eval must be run by the user in a new context-free session. "
                "NOT_RUN means no submission was found; it is never reported as a pass.",
        "tasks_total": len(results),
        "submitted": len(submitted),
        "passed": len(passed),
        "overall": overall,
        "results": results,
        # Task book S47 section 4: overall pass@1 = passed tasks / all tasks.
        "pass_at_1": (len(passed) / len(results)) if submitted else None,
        "pass_rate_over_submitted": (len(passed) / len(submitted)) if submitted else None,
        "pass_at_k_formula": "pass@k = 1 - C(n-c,k)/C(n,k); single sample == pass@1",
        "group": group,
        "samples_per_task": samples,
        "stats": stats,
    }


def render(doc: dict[str, Any]) -> str:
    lines = [
        "# S45 Agent 盲测结果（客观判分）",
        "",
        f"> {doc['note']}",
        "",
        f"- 生成时间（UTC）：{doc['generated_at_utc']}",
        f"- 题目总数：{doc['tasks_total']}；已提交：{doc['submitted']}；通过：{doc['passed']}",
        f"- 总判定：**{doc['overall']}**",
        f"- pass@1：{doc['pass_at_1'] if doc['pass_at_1'] is not None else '未执行（无提交）'}",
        "",
        "| 题目 | 状态 | 检查 |",
        "|---|---|---|",
    ]
    for r in doc["results"]:
        if r["status"] == "NOT_SUBMITTED":
            lines.append(f"| {r['id']} | NOT_SUBMITTED | 未提交 |")
            continue
        checks = ", ".join(
            f"{name}={'PASS' if c.get('pass') else 'FAIL'}"
            for name, c in r["checks"].items()
        )
        lines.append(f"| {r['id']} | {r['status']} | {checks} |")
    lines += [
        "",
        "## 判分口径",
        "",
        "- 只做客观检查：`--check` 退出 0、退出码与 stdout 字节匹配、多次运行逐字节一致、未使用禁止构造；不评价代码风格。",
        "- `NOT_SUBMITTED` 表示没有提交目录；`NOT_RUN` 表示盲测未执行，不填 pass@1。",
        "",
    ]
    return "\n".join(lines)


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", default=None, help="grade a single task id")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--tasks", default=str(TASKS_PATH))
    parser.add_argument("--submissions", default=str(SUBMISSIONS))
    parser.add_argument("--group", default=None, choices=["T", "C"])
    parser.add_argument("--samples", type=int, default=1)
    args = parser.parse_args(argv)

    tasks_path = Path(args.tasks)
    if not tasks_path.is_absolute():
        tasks_path = ROOT / tasks_path
    submissions_dir = Path(args.submissions)
    if not submissions_dir.is_absolute():
        submissions_dir = ROOT / submissions_dir
    doc = grade_all(args.task, args.timeout, tasks_path=tasks_path,
                    submissions_dir=submissions_dir, samples=args.samples,
                    group=args.group)
    out = ROOT / args.out
    _atomic(out, json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic(out.with_suffix(".md"), render(doc))
    print(f"run_agent_eval: {doc['overall']} "
          f"(submitted {doc['submitted']}/{doc['tasks_total']}, passed {doc['passed']}); "
          f"wrote {out.relative_to(ROOT)}")
    return 0 if doc["overall"] in ("ALL_PASS", "NOT_RUN", "PARTIAL") else 1


if __name__ == "__main__":
    raise SystemExit(main())
