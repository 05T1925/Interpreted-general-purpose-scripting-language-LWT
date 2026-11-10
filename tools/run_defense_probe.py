"""S48 WP3: run the defense claims and report real results.

Usage:
    python tools/run_defense_probe.py --list
    python tools/run_defense_probe.py --claim version
    python tools/run_defense_probe.py --random 3
    python tools/run_defense_probe.py --all            # includes heavy rows
    python tools/run_defense_probe.py --all --skip-heavy

Every row is executed as a real subprocess; PASS requires the expected exit code
and the expected stdout substring. A timeout or mismatch is FAIL, never "mostly
passed". Heavy rows (full black-box, full unittest, 46x10 determinism) are
marked so a live defense can choose a fast subset.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import random
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
CLAIMS = ROOT / "docs" / "defense-claims.json"
OUT_DIR = ROOT / "reports" / "s48-defense"

# S50: a claim that needs Tk must not inherit a bare "python". On this machine
# "python" is a bundled 3.13.14 without tkinter: the GUI test module fails to
# import, only 711 of 713 tests run, and the two resulting failures look like a
# language defect. The row below probes candidate interpreters and records the
# one it used, so the evidence says *who* ran the suite.
_TK_CHECK = (
    "import sys, tkinter; print(sys.executable); "
    "print(sys.version.split()[0]); print(tkinter.TkVersion)"
)
_TK_CACHE: dict[str, dict | None] = {}


def python_candidates() -> list[list[str]]:
    """Interpreters to try, in order; LWT_PYTHON wins over PATH discovery."""

    candidates: list[list[str]] = []
    explicit = os.environ.get("LWT_PYTHON")
    if explicit:
        candidates.append([explicit])
    candidates.append([sys.executable])
    if os.name == "nt":
        candidates.extend([["py", "-3.13"], ["py", "-3"]])
    candidates.extend([["python3"], ["python"]])
    unique: list[list[str]] = []
    for item in candidates:
        if item not in unique:
            unique.append(item)
    return unique


def _probe_tk(argv: list[str], timeout: int = 25) -> dict | None:
    """Return interpreter facts when *argv* can import tkinter, else None."""

    try:
        completed = subprocess.run(
            [*argv, "-c", _TK_CHECK], capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if len(lines) < 3:
        return None
    return {
        "argv": list(argv),
        "executable": lines[0],
        "version": lines[1],
        "tk_version": lines[2],
    }


def resolve_python(require_tkinter: bool = False) -> dict:
    """Pick the interpreter for a claim.

    ``require_tkinter=False`` keeps the historical behaviour (the interpreter
    running the probe). ``require_tkinter=True`` searches for one that can
    import tkinter and raises ``RuntimeError`` with the candidates when none
    exists, so the row fails as ``TK_UNAVAILABLE`` instead of as a fake
    unittest failure.
    """

    if not require_tkinter:
        return {
            "argv": [sys.executable],
            "executable": sys.executable,
            "version": platform.python_version(),
            "tk_version": None,
        }
    if "tk" not in _TK_CACHE:
        _TK_CACHE["tk"] = next(
            (facts for facts in (_probe_tk(candidate) for candidate in python_candidates())
             if facts is not None),
            None,
        )
    facts = _TK_CACHE["tk"]
    if facts is None:
        tried = ", ".join(" ".join(candidate) for candidate in python_candidates())
        raise RuntimeError(
            f"no interpreter with tkinter found (tried: {tried}); "
            "set LWT_PYTHON to a Tk-enabled Python"
        )
    return facts


def build_command(claim: dict, tmp: str = "<TMP>") -> tuple[list[str], dict]:
    """Expand a claim command and return it with the interpreter actually used."""

    requires = claim.get("requires") or {}
    interpreter = resolve_python(bool(requires.get("tkinter")))
    command = list(claim["command"])
    if command and command[0] == "python":
        command = [*interpreter["argv"], *command[1:]]
    return [part.replace("<TMP>", tmp) for part in command], interpreter


def run_claim(claim: dict, timeout: int = 1800) -> dict:
    tmp = tempfile.mkdtemp(prefix="lwt-defense-")
    requires = claim.get("requires") or {}
    try:
        command, interpreter = build_command(claim, tmp)
    except RuntimeError as error:
        return {
            "id": claim["id"],
            "area": claim["area"],
            "claim": claim["claim"],
            "command": list(claim["command"]),
            "exit_code": None,
            "expected_exit_code": (claim.get("expect") or {}).get("exit_code"),
            "stdout_contains": None,
            "stderr_contains": None,
            "stdout_head": "",
            "stdout_tail": "",
            "stderr_head": "",
            "stderr_tail": "",
            "seconds": 0.0,
            "heavy": claim.get("heavy", False),
            "checks": {"interpreter_available": False},
            "status": "FAIL",
            "error": "TK_UNAVAILABLE",
            "detail": str(error),
            "requires": requires,
            "precondition": claim.get("precondition"),
            "interpreter": None,
            "tests_ran": None,
            "evidence_path": claim.get("evidence_path"),
        }
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command, cwd=str(ROOT), capture_output=True, text=True,
            timeout=timeout, check=False,
        )
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        timed_out = False
    except subprocess.TimeoutExpired as error:
        exit_code = None
        stdout = (error.stdout or "") if isinstance(error.stdout, str) else ""
        stderr = f"timeout after {timeout}s"
        timed_out = True
    seconds = round(time.perf_counter() - started, 3)

    expect = claim.get("expect", {})
    want_code = expect.get("exit_code")
    want_text = expect.get("stdout_contains")
    want_err = expect.get("stderr_contains")
    checks = {
        "exit_code_matches": exit_code == want_code,
        "stdout_contains_matches": (want_text is None) or (want_text in stdout),
        "stderr_contains_matches": (want_err is None) or (want_err in stderr),
        "not_timed_out": not timed_out,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    ran_match = re.search(r"\bran=(\d+)\b", stdout) or re.search(
        r"^Ran (\d+) tests? in", stderr, re.M
    )
    return {
        "id": claim["id"],
        "area": claim["area"],
        "claim": claim["claim"],
        "command": command,
        "exit_code": exit_code,
        "expected_exit_code": want_code,
        "stdout_contains": want_text,
        "stderr_contains": want_err,
        "stdout_head": stdout[:1200],
        "stdout_tail": stdout[-600:],
        "stderr_head": stderr[:600],
        "stderr_tail": stderr[-1200:],
        "seconds": seconds,
        "heavy": claim.get("heavy", False),
        "checks": checks,
        "status": status,
        "requires": requires,
        "precondition": claim.get("precondition"),
        "interpreter": interpreter,
        "tests_ran": int(ran_match.group(1)) if ran_match else None,
        "evidence_path": claim.get("evidence_path"),
    }


def load_claims() -> list[dict]:
    return json.loads(CLAIMS.read_text(encoding="utf-8"))["claims"]


def render(doc: dict) -> str:
    lines = [
        "# S48 现场可质询证据探针结果",
        "",
        f"> 生成：{doc['generated_at_utc']}；运行 {doc['ran']} 条；"
        f"**PASS {doc['passed']} / FAIL {doc['failed']}**。每条都是真实子进程与真实退出码。",
        "",
        "| id | 断言 | 命令 | 退出码 | 结果 | 用时(s) |",
        "|---|---|---|---:|---|---:|",
    ]
    for row in doc["results"]:
        cmd = " ".join(row["command"])
        if len(cmd) > 90:
            cmd = cmd[:87] + "..."
        lines.append(
            f"| {row['id']} | {row['claim']} | `{cmd}` | {row['exit_code']} | "
            f"**{row['status']}** | {row['seconds']} |"
        )
    failed = [row for row in doc["results"] if row["status"] == "FAIL"]
    lines += ["", "## 失败明细", ""]
    if not failed:
        lines.append("无。")
    else:
        for row in failed:
            lines += [
                f"### {row['id']} — FAIL",
                f"- 断言：{row['claim']}",
                f"- 期望退出码 {row['expected_exit_code']}，实际 {row['exit_code']}",
                f"- 期望 stdout 含：`{row['stdout_contains']}`",
                f"- stdout 前段：`{row['stdout_head'][:300]}`",
                f"- stderr 前段：`{row['stderr_head'][:300]}`",
                "",
            ]
    lines += [
        "## 口径",
        "",
        "- `PASS` = 退出码匹配且 stdout 含预期片段；`FAIL` 如实记录，不写“基本通过”。",
        "- heavy 行（全量黑盒/全量 unittest/46×10 确定性）现场可用 `--claim` 抽一条，或 `--all --skip-heavy`。",
        "- 只读旧证据，不覆盖任何报告；结果写入 `reports/s48-defense/defense-probe.{json,md}`。",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claim", action="append", default=None,
                        help="claim id (repeatable)")
    parser.add_argument("--random", type=int, default=None,
                        help="randomly pick N non-heavy claims")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--skip-heavy", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--out", default=str(OUT_DIR / "defense-probe.json"))
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--merge", action="store_true",
                        help="merge this run into the existing evidence, replacing only the ids run now")
    args = parser.parse_args(argv)

    claims = load_claims()
    if args.list:
        for claim in claims:
            flag = "heavy" if claim.get("heavy") else "fast"
            print(f"{claim['id']:16s} [{flag}] {claim['claim']}")
        return 0

    if args.claim:
        wanted = set(args.claim)
        selected = [c for c in claims if c["id"] in wanted]
        missing = wanted - {c["id"] for c in selected}
        if missing:
            print(f"run_defense_probe: unknown claim(s): {sorted(missing)}", file=sys.stderr)
            return 2
    elif args.random:
        pool = [c for c in claims if not c.get("heavy")]
        rng = random.Random(args.seed)
        selected = rng.sample(pool, min(args.random, len(pool)))
    elif args.all:
        selected = [c for c in claims if not (args.skip_heavy and c.get("heavy"))]
    else:
        parser.error("choose --list, --claim, --random or --all")

    results = [run_claim(claim, timeout=args.timeout) for claim in selected]
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for row in results:
        row["recorded_at_utc"] = stamp

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    if args.merge and out.exists():
        previous = json.loads(out.read_text(encoding="utf-8"))
        by_id = {row["id"]: row for row in previous.get("results", [])}
        # Older rows (recorded before --merge existed) inherit the previous
        # document timestamp so every row still says when it was run.
        fallback = previous.get("generated_at_utc")
        for row in by_id.values():
            row.setdefault("recorded_at_utc", fallback)
        for row in results:
            by_id[row["id"]] = row
        merged = [by_id[key] for key in sorted(by_id)]
        results = merged
    passed = sum(1 for row in results if row["status"] == "PASS")
    doc = {
        "schema_version": 1,
        "tool": "tools/run_defense_probe.py",
        "generated_at_utc": stamp,
        "merged": bool(args.merge),
        "note": "Each row keeps its own recorded_at_utc; --merge replaces only the ids re-run.",
        "ran": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    out.with_suffix(".md").write_text(render(doc), encoding="utf-8", newline="\n")
    print(f"run_defense_probe: PASS {passed}/{len(results)} -> {out.relative_to(ROOT)}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
