"""S45 WP5: one-command acceptance self-check with machine-readable evidence.

Runs, in order, and records a real exit code + parsed summary for each step:

  1. git status / HEAD / branch / main..HEAD commit count
  2. protected-path diff (must be empty)
  3. ``check_project_integrity --require-all-referenced``
  4. ``tools/run_tests.py`` (400 black-box)
  5. ``tools/run_concurrency_determinism.py --repeat 10`` with an independent
     ``--out`` path, so ``reports/s42-determinism.json`` is never touched
  6. ``tools/compare_perf.py --format json``
  7. ``tests.test_doc_consistency``
  8. PPT static check via zip/xml (slide count, native chart value points, SHA-256)
  9. Agent-eval status (executed vs NOT_RUN; never fabricated)
 10. S46 bounded concurrency model check (clean corpus; BUDGET_EXHAUSTED is FAIL)
 11. S47 submission package: SUBMISSION.md, dist/latest.json, bundle verify, zip manifest
 12. S48 GUI evidence registration (counts only; never auto-PASS)
 13. S48 defense probe results (PASS only when every recorded row passed)

Writes ``reports/s45-acceptance/selfcheck-<UTC>.json`` and ``.md`` and prints the
manual GUI checklist. It never rewrites S10/S11/S37-S44 evidence; a failing step
is recorded as FAIL, never "basically passed".
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
from typing import Any
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "reports" / "s45-acceptance"
OUT_DIR = DEFAULT_OUT_DIR
PPT = ROOT / "slides" / "LWT介绍.pptx"
MANIFEST = ROOT / "docs" / "delivery-manifest.json"

PROTECTED = [
    "bench/results.json", "reports/performance.md", "reports/app-concurrency.json",
    "docs/app-concurrency.md", "reports/app-lwt-profile.json", "reports/app-lwt-profile.html",
    "reports/lsp-smoke.json", "reports/runtime-profile.json", "reports/runtime-profile.md",
    "reports/concurrency-performance.json", "reports/concurrency-performance.md",
    "reports/s42-determinism.json", "reports/s42-schedules", "tests/cases",
    "app/log_report.lwt", "app/lwt_snake/game.lwt",
]

GUI_CHECKLIST = [
    "语义实验室：python -m app.language_lab，提交预测→运行→对照反馈",
    "日志工作台：python -m app.lwt_workbench（若存在），真实鼠标选择/滚动/切换",
    "LWT Snake：python -m app.lwt_snake，方向键、吃食物、结束重开、失焦恢复",
    "S41 策略查看器：真实 Tk 窗口打开见证目录并逐步解释",
    "PPT 逐页播放：18/19 页在放映模式下无溢出、图表可读",
    "桌面无遮挡与输入归属：窗口置顶/焦点/输入法不误触",
]


def utc_stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def run(cmd: list[str], *, timeout: int, cwd: Path = ROOT) -> dict[str, Any]:
    started = time.perf_counter_ns()
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=timeout)
        elapsed = (time.perf_counter_ns() - started) / 1e9
        return {
            "command": cmd, "exit_code": proc.returncode, "seconds": round(elapsed, 3),
            "stdout": proc.stdout.decode("utf-8", "replace"),
            "stderr": proc.stderr.decode("utf-8", "replace"),
        }
    except subprocess.TimeoutExpired:
        return {"command": cmd, "exit_code": None, "seconds": None,
                "stdout": "", "stderr": f"timeout after {timeout}s"}


def _step_git() -> dict[str, Any]:
    status = run(["git", "status", "-sb"], timeout=15)
    head = run(["git", "rev-parse", "HEAD"], timeout=15)
    branch = run(["git", "branch", "--show-current"], timeout=15)
    count = run(["git", "rev-list", "--count", "5027860..HEAD"], timeout=15)
    # The selfcheck's own evidence directory is untracked by design; counting it
    # as a dirty tree would make every run fail on itself (S49).
    try:
        out_rel = OUT_DIR.relative_to(ROOT).as_posix()
    except ValueError:
        out_rel = None
    lines = status["stdout"].strip().splitlines()
    dirty = [
        line for line in lines[1:]
        if line.strip() and not (out_rel and line.startswith("?? " + out_rel))
    ]
    return {
        "status_porcelain": status["stdout"].strip(),
        "head": head["stdout"].strip(),
        "branch": branch["stdout"].strip(),
        "commits_since_main": int(count["stdout"].strip() or 0),
        "clean": not dirty,
        "pass": not dirty,
    }


def _step_protected_diff() -> dict[str, Any]:
    proc = run(["git", "status", "--porcelain", "--", *PROTECTED], timeout=20)
    lines = [line for line in proc["stdout"].splitlines() if line.strip()]
    return {"exit_code": proc["exit_code"], "dirty": lines, "pass": not lines}


def _parse_integrity(out: str) -> dict[str, Any]:
    match = re.search(
        r"cases=(\d+); matrix_links=(\d+); referenced_cases=(\d+)(?:; unreferenced=(\d+))?",
        out,
    )
    if not match:
        return {}
    return {
        "cases": int(match.group(1)), "matrix_links": int(match.group(2)),
        "referenced_cases": int(match.group(3)),
        "unreferenced": int(match.group(4)) if match.group(4) is not None else None,
    }


def _parse_blackbox(out: str) -> dict[str, Any]:
    match = re.search(r"passed=(\d+) failed=(\d+) total=(\d+)", out)
    return (
        {"passed": int(match.group(1)), "failed": int(match.group(2)), "total": int(match.group(3))}
        if match else {}
    )


def _step_ppt() -> dict[str, Any]:
    """Static PPT inspection (zip/xml, no PowerPoint)."""
    if not PPT.exists():
        return {"pass": False, "detail": "PPT missing"}
    sha = hashlib.sha256(PPT.read_bytes()).hexdigest()
    with zipfile.ZipFile(PPT) as archive:
        slides = sorted(
            name for name in archive.namelist()
            if re.match(r"ppt/slides/slide\d+\.xml$", name)
        )
        chart_points = 0
        chart_series = 0
        for name in archive.namelist():
            if not re.match(r"ppt/(?:slides/)?charts/chart\d+\.xml$", name):
                continue
            xml = archive.read(name).decode("utf-8", "replace")
            for series in re.findall(r"<c:ser>.*?</c:ser>", xml, re.S):
                chart_series += 1
                # Count only the value cache; the category cache would double it.
                values_block = re.search(r"<c:val>.*?</c:val>", series, re.S)
                if values_block:
                    num_cache = re.search(r"<c:numCache>.*?</c:numCache>", values_block.group(0), re.S)
                    if num_cache:
                        chart_points += len(re.findall(r"<c:pt\b", num_cache.group(0)))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {
        "pass": len(slides) == manifest["ppt_pages"] and chart_points == manifest["ppt_chart_points"],
        "slides": len(slides), "chart_series": chart_series, "chart_points": chart_points,
        "sha256": sha, "manifest_pages": manifest["ppt_pages"],
        "manifest_chart_points": manifest["ppt_chart_points"],
        "sha_matches_manifest": sha == manifest["ppt_sha256"],
    }


def _step_agent_eval() -> dict[str, Any]:
    path = ROOT / "reports" / "s47-submission" / "agent-eval.json"
    if not path.exists():
        path = OUT_DIR / "agent-eval.json"
    if not path.exists():
        return {"status": "NOT_RUN", "pass": None, "detail": "no agent-eval.json"}
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {
        "status": doc.get("overall"), "pass": None,
        "submitted": doc.get("submitted"), "passed": doc.get("passed"),
        "pass_at_1": doc.get("pass_at_1"),
        "detail": f"{path.relative_to(ROOT)}; blind eval is not a pass/fail gate, "
                  f"and a clarified post-hoc re-run is recorded separately",
    }


def _step_defense_probe() -> dict[str, Any]:
    """S48: summarize the last defense-probe run; never invent a pass."""

    # Each phase keeps its own merged probe; prefer the newest and fall back to
    # the frozen S50/S49/S48 files when a phase directory is absent.
    candidates = [
        ROOT / "reports" / "s53-mutation" / "defense-probe.json",
        ROOT / "reports" / "s50-closeout" / "defense-probe-merge.json",
        ROOT / "reports" / "s49-rehearsal" / "defense-probe.json",
        ROOT / "reports" / "s48-defense" / "defense-probe.json",
    ]
    path = next((item for item in candidates if item.exists()), None)
    if path is None:
        return {"status": "NOT_RUN", "pass": None,
                "detail": "run tools/run_defense_probe.py --claim unittest --merge "
                          "--out reports/s50-closeout/defense-probe-merge.json"}
    doc = json.loads(path.read_text(encoding="utf-8"))
    passed = doc.get("passed", 0)
    ran = doc.get("ran", 0)
    failed = doc.get("failed", 0)
    return {
        "status": "PASS" if ran and failed == 0 else "FAIL",
        "pass": bool(ran and failed == 0),
        "ran": ran,
        "passed": passed,
        "failed": failed,
        "detail": f"last probe PASS {passed}/{ran}; rerun --all to include heavy rows",
    }


def _step_gui_evidence() -> dict[str, Any]:
    """S48: report registered GUI material; presence is never a pass."""

    doc = ROOT / "reports" / "s48-defense" / "gui-acceptance.json"
    if not doc.exists():
        return {"status": "NOT_RUN", "pass": None, "registered": 0, "total": 5,
                "detail": "run tools/register_gui_evidence.py after the on-site session"}
    data = json.loads(doc.read_text(encoding="utf-8"))
    return {
        "status": data.get("overall"),
        "pass": None,
        "registered": data.get("registered"),
        "total": data.get("total"),
        "not_automated": True,
        "detail": "GUI A-E must be confirmed by the user; this step only counts registered evidence",
    }


def _step_submission() -> dict[str, Any]:
    """S47: the teacher-facing package must exist, verify and be self-consistent."""

    submission = ROOT / "SUBMISSION.md"
    latest_path = ROOT / "dist" / "latest.json"
    if not submission.exists():
        return {"pass": False, "detail": "SUBMISSION.md missing"}
    if not latest_path.exists():
        return {"pass": False, "detail": "dist/latest.json missing; run tools/build_submission.py"}
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    bundle = ROOT / str(latest.get("bundle") or "")
    zip_path = ROOT / str(latest.get("zip") or "")
    if not bundle.is_file() or not zip_path.is_file():
        return {"pass": False, "detail": f"bundle/zip missing: {bundle} / {zip_path}"}
    verify = run(["git", "bundle", "verify", str(bundle)], timeout=180)
    zip_ok = False
    entries = 0
    try:
        with zipfile.ZipFile(zip_path) as archive:
            names = set(archive.namelist())
            entries = len(names)
            manifest_lines = archive.read("manifest.sha256").decode("utf-8").splitlines()
            listed = {}
            for line in manifest_lines:
                digest, rel = line.split("  ", 1)
                listed[rel] = digest
            zip_ok = (
                archive.testzip() is None
                and "SUBMISSION.md" in names
                and "lwt-history.bundle" in names
                and set(listed) == names - {"manifest.sha256"}
                and all(
                    hashlib.sha256(archive.read(rel)).hexdigest() == digest
                    for rel, digest in listed.items()
                )
            )
    except (OSError, ValueError, KeyError):
        zip_ok = False
    passed = verify["exit_code"] == 0 and zip_ok
    return {
        "pass": passed,
        "submission_md": str(submission.relative_to(ROOT)),
        "bundle": str(bundle.relative_to(ROOT)),
        "zip": str(zip_path.relative_to(ROOT)),
        "bundle_verify_exit": verify["exit_code"],
        "zip_entries": entries,
        "zip_manifest_ok": zip_ok,
        "seconds": verify["seconds"],
    }


def _step_model_check(budget: float) -> dict[str, Any]:
    """S46: bounded schedule exploration; budget exhaustion is never a pass."""

    out = OUT_DIR / "model-check"
    completed = run(
        [sys.executable, "tools/model_check_concurrency.py",
         "--corpus", "tests/concurrency-model",
         "--max-runs", "300", "--time-budget", str(budget),
         "--require-clean", "--out", str(out.relative_to(ROOT))],
        timeout=int(budget) + 180,
    )
    summary: dict[str, Any] = {}
    path = out / "summary.json"
    if path.exists():
        try:
            summary = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            summary = {}
    totals = summary.get("totals", {})
    budget_exhausted = totals.get("budget_exhausted")
    if completed["exit_code"] == 0 and summary.get("all_pass") is True:
        status = "PASS"
    elif budget_exhausted:
        status = "BUDGET_EXHAUSTED"
    else:
        status = "FAIL"
    return {
        "exit_code": completed["exit_code"],
        "pass": status == "PASS",
        "status": status,
        "runs": totals.get("runs"),
        "violations": totals.get("violations"),
        "budget_exhausted": budget_exhausted,
        "invalid_prefixes": totals.get("invalid_prefixes"),
        "output": str(path.relative_to(ROOT)),
        "seconds": completed["seconds"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--out", default=str(DEFAULT_OUT_DIR),
                        help="output directory for selfcheck evidence")
    parser.add_argument("--model-budget", type=float, default=60.0,
                        help="S46 model-check wall-clock budget (seconds)")
    parser.add_argument("--skip-heavy", action="store_true",
                        help="skip black-box and determinism (fast structural check only)")
    args = parser.parse_args(argv)

    global OUT_DIR
    OUT_DIR = Path(args.out)
    if not OUT_DIR.is_absolute():
        OUT_DIR = ROOT / OUT_DIR

    stamp = utc_stamp()
    steps: dict[str, Any] = {}
    steps["git"] = _step_git()
    steps["protected_diff"] = _step_protected_diff()

    integrity = run([sys.executable, "tools/check_project_integrity.py", "--require-all-referenced"], timeout=60)
    steps["integrity"] = {
        "exit_code": integrity["exit_code"], "pass": integrity["exit_code"] == 0,
        "parsed": _parse_integrity(integrity["stdout"]),
        "stderr": integrity["stderr"][:400],
    }

    if not args.skip_heavy:
        blackbox = run([sys.executable, "tools/run_tests.py"], timeout=args.timeout)
        parsed = _parse_blackbox(blackbox["stdout"])
        steps["blackbox"] = {
            "exit_code": blackbox["exit_code"], "pass": blackbox["exit_code"] == 0,
            "parsed": parsed, "seconds": blackbox["seconds"],
        }
        det_out = OUT_DIR / "determinism.json"
        determinism = run(
            [sys.executable, "tools/run_concurrency_determinism.py", "--repeat", "10",
             "--out", str(det_out.relative_to(ROOT))],
            timeout=args.timeout,
        )
        steps["determinism"] = {
            "exit_code": determinism["exit_code"], "pass": determinism["exit_code"] == 0,
            "output": str(det_out.relative_to(ROOT)),
            "stable": "stable=True" in determinism["stdout"],
            "failures_zero": "failures=0" in determinism["stdout"],
            "seconds": determinism["seconds"],
        }
    else:
        steps["blackbox"] = {"skipped": True, "pass": None}
        steps["determinism"] = {"skipped": True, "pass": None}

    compare = run([sys.executable, "tools/compare_perf.py", "--format", "json"], timeout=120)
    compare_doc: dict[str, Any] = {}
    try:
        compare_doc = json.loads(compare["stdout"])
    except ValueError:
        pass
    steps["compare_perf"] = {
        "exit_code": compare["exit_code"], "pass": bool(compare_doc.get("all_pass")),
        "all_pass": compare_doc.get("all_pass"),
    }

    doc_consistency = run(
        [sys.executable, "-m", "unittest", "tests.test_doc_consistency", "-q"], timeout=180
    )
    steps["doc_consistency"] = {
        "exit_code": doc_consistency["exit_code"], "pass": doc_consistency["exit_code"] == 0,
    }

    steps["ppt"] = _step_ppt()
    if args.skip_heavy:
        steps["model_check"] = {"skipped": True, "pass": None}
    else:
        steps["model_check"] = _step_model_check(args.model_budget)
    steps["submission"] = _step_submission()
    steps["gui_evidence"] = _step_gui_evidence()
    steps["defense_probe"] = _step_defense_probe()
    steps["agent_eval"] = _step_agent_eval()

    graded = [v for v in steps.values() if isinstance(v, dict) and v.get("pass") is not None]
    all_pass = all(v.get("pass") is True for v in graded) and bool(graded)
    report = {
        "schema_version": 1,
        "tool": "lwt-acceptance-selfcheck",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": {
            "python": sys.version, "executable": sys.executable,
            "platform": platform.platform(),
        },
        "all_pass": all_pass,
        "steps": steps,
        "gui_checklist": GUI_CHECKLIST,
        "note": "Agent blind eval and on-site GUI acceptance are separate: NOT_RUN / "
                "未验证 is never a pass. Heavy steps can be skipped only with --skip-heavy, "
                "and show as null, not true.",
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / f"selfcheck-{stamp}.json"
    md_path = OUT_DIR / f"selfcheck-{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8", newline="\n")
    md_path.write_text(render(report), encoding="utf-8", newline="\n")
    try:
        shown = json_path.relative_to(ROOT).as_posix()
    except ValueError:  # --out outside the repo (baseline runs into a temp dir)
        shown = str(json_path)
    print(f"selfcheck: {'PASS' if all_pass else 'FAIL'} -> {shown}")
    for name, value in steps.items():
        state = ("SKIP" if value.get("skipped") else
                 ("PASS" if value.get("pass") else ("N/A" if value.get("pass") is None else "FAIL")))
        print(f"  {name:16s} {state}")
    print("manual GUI checklist: see the .md output (not automated, not claimed as passed)")
    return 0 if all_pass else 1


def render(doc: dict[str, Any]) -> str:
    lines = [
        "# S45 交付自检包",
        "",
        f"> 生成：{doc['generated_at_utc']}；Python `{doc['environment']['python'].split()[0]}`；"
        f"平台 `{doc['environment']['platform']}`。失败项写 FAIL，未执行写 SKIP/N/A，不写「基本通过」。",
        "",
        f"**总判定：{'PASS' if doc['all_pass'] else 'FAIL'}**",
        "",
        "| 步骤 | 结果 | 关键数字 |",
        "|---|---|---|",
    ]
    for name, value in doc["steps"].items():
        if value.get("skipped"):
            state, detail = "SKIP", "未运行（--skip-heavy）"
        elif value.get("pass") is True:
            state, detail = "PASS", ""
        elif value.get("pass") is False:
            state, detail = "FAIL", ""
        else:
            state, detail = "N/A", str(value.get("status", ""))
        if name == "git":
            detail = f"HEAD `{value['head'][:12]}` 分支 `{value['branch']}` 提交 {value['commits_since_main']}"
        elif name == "protected_diff":
            detail = "保护路径差异空" if value["pass"] else f"脏文件 {value['dirty']}"
        elif name == "integrity":
            p = value.get("parsed", {})
            detail = f"cases={p.get('cases')} referenced={p.get('referenced_cases')} unref={p.get('unreferenced')}"
        elif name == "blackbox":
            p = value.get("parsed", {})
            detail = f"passed={p.get('passed')} failed={p.get('failed')} total={p.get('total')}"
        elif name == "determinism":
            detail = f"stable={value.get('stable')} failures_zero={value.get('failures_zero')} out={value.get('output')}"
        elif name == "compare_perf":
            detail = f"all_pass={value.get('all_pass')}"
        elif name == "ppt":
            detail = (f"slides={value.get('slides')} chart_points={value.get('chart_points')} "
                      f"sha={str(value.get('sha256'))[:12]}")
        elif name == "model_check":
            detail = (f"{value.get('status')} runs={value.get('runs')} "
                      f"violations={value.get('violations')} "
                      f"budget_exhausted={value.get('budget_exhausted')}")
        elif name == "submission":
            detail = (f"bundle_verify={value.get('bundle_verify_exit')} "
                      f"zip_entries={value.get('zip_entries')} "
                      f"manifest_ok={value.get('zip_manifest_ok')}")
        elif name == "defense_probe":
            detail = f"{value.get('status')} {value.get('passed')}/{value.get('ran')} (failed {value.get('failed')})"
        elif name == "gui_evidence":
            detail = f"{value.get('status')} (registered {value.get('registered')}/{value.get('total')})"
        elif name == "agent_eval":
            detail = f"{value.get('status')} (submitted={value.get('submitted')})"
        lines.append(f"| {name} | {state} | {detail} |")
    lines += [
        "",
        "## 人工 GUI 验收清单（未自动化、未声称通过）",
        "",
    ]
    lines += [f"- {item}" for item in doc["gui_checklist"]]
    lines += ["", f"> {doc['note']}", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
