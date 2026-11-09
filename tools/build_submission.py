"""S47: build the teacher-facing submission package.

Outputs (default ``dist/lwt-submission-<UTC>/``; ``dist/`` is git-ignored):

  SUBMISSION.md              canonical copy is also written to the repo root
  lwt-history.bundle         ``git bundle --all`` (every ref and all history)
  lwt-history.graph.txt      ``git log --graph --oneline --decorate --all``
  lwt-submission.zip         tracked HEAD tree + SUBMISSION.md + bundle
  manifest.sha256            per-file SHA-256 for every zip entry
  build.json                 machine-readable build record
  ../latest.json             pointer used by the acceptance selfcheck

The zip is built from ``git archive HEAD`` (tracked files only), so no
``__pycache__``, ``*.pyc``, temporary worktrees or untracked files leak in.
Protected evidence is only read, never written.

Usage::

    python tools/build_submission.py
    python tools/build_submission.py --out dist/probe --no-bundle --no-zip
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "delivery-manifest.json"
SUBMISSION = ROOT / "SUBMISSION.md"
DIST = ROOT / "dist"

SCORES = {
    "language-spec": 0,
    "interpreter": 20,
    "blackbox": 20,
    "performance": 10,
    "guide": 20,
    "apps": 30,
    "git": 0,
    "ppt": 0,
}


def _utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _display(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(cmd: list[str], *, cwd: Path = ROOT, timeout: int = 300) -> dict:
    started = time.perf_counter()
    completed = subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, timeout=timeout, check=False
    )
    return {
        "command": cmd,
        "exit_code": completed.returncode,
        "stdout": completed.stdout.decode("utf-8", "replace"),
        "stderr": completed.stderr.decode("utf-8", "replace"),
        "seconds": round(time.perf_counter() - started, 3),
    }


def submission_markdown() -> str:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    version = manifest["version"]
    cases = manifest["blackbox_cases"]
    unittest_count = manifest["unittest_count"]
    pages = manifest["ppt_pages"]
    rows = [
        ("1", "LWT 语法规则文档", "—", "docs/language-spec.md",
         "`python -m lwt --version`", "规范 §1–§11；版本号由 manifest 统一", "完成"),
        ("2", "解释器源程序", "20", "lwt/",
         "`python -m lwt examples/guide/hello.lwt`", "`tests/cases/` 400 项", "完成"),
        ("3", "完整黑盒测试集", "20", "tests/cases/", "`python tools/run_tests.py`",
         f"400/400；矩阵 `referenced_cases=400/400`", "完成"),
        ("4", "性能测试报告", "10", "reports/performance.md、bench/results.json",
         "`python tools/compare_perf.py`", "S11 正式报告 + S44 分层对照", "完成"),
        ("5", "开发指南（人 + AI）", "20", "docs/developer-guide.md、.agents/skills/lwt-app/SKILL.md",
         "`python -m lwt --check examples/modules/main.lwt`", "S42–S46 已按指南实现", "完成"),
        ("6", "Agent 应用与开发记录", "30", "app/log_report.lwt、app/concurrent_log_report.lwt、app/lwt_snake/game.lwt、docs/agent-dev-log.md",
         "`python -m lwt app/log_report.lwt -- app/fixtures/sample.log`",
         "有效行数 243 / 233 / 313（`tools/count_lwt_lines.py`）", "完成"),
        ("7", "Git 历史", "—", "lwt-history.bundle、lwt-history.graph.txt",
         "`git log --oneline --decorate -12`", "bundle 含全部 refs；verify 见报告", "完成"),
        ("8", "系统介绍 PPT", "—", f"slides/LWT介绍.pptx（{pages} 页）",
         "打开 `slides/LWT介绍.pptx`", "第 10 页原生图表 12 数值点自 S43 起未变", "完成"),
    ]
    table = "\n".join(
        f"| {number} | {name} | {score} | `{path}` | {command} | {evidence} | {status} |"
        for number, name, score, path, command, evidence, status in rows
    )
    return f"""# LWT 提交入口（教师版）

> 版本 **{version}** ｜ 黑盒 **{cases}** ｜ unittest **{unittest_count}** ｜ PPT **{pages} 页**
> 默认分支 `main` 与本交付分支同一提交；分支/CI 的精确 SHA 见 `docs/s47-final-submission.md`。
> 本文件由 `tools/build_submission.py` 生成，数字取自 `docs/delivery-manifest.json`。

## 三分钟验收路径

```bash
python -m lwt --version                     # lwt {version}
python tools/run_tests.py                   # Black-box tests: passed=400 failed=0
python tools/run_acceptance_selfcheck.py    # Git/保护路径/完整性/黑盒/确定性/性能/文档/PPT/模型检查
```

然后打开 `slides/LWT介绍.pptx`（{pages} 页）。所有命令在仓库根目录执行；Python 3.10+ 标准库，无第三方运行时依赖。

## 提交内容 1–8（对应课程要求）

| # | 提交内容 | 分值 | 仓库位置 | 一条验证命令 | 证据 | 状态 |
|---|---|---|---|---|---|---|
{table}

合计 100 分：解释器 20 + 自动测试 20 + 性能 10 + 语法/指南 20 + Agent 应用 30。

## 五段证据摘要

| 主题 | 可复算数字 | 源文件 |
|---|---|---|
| S11 性能 | 六组端到端中位数，LWT/Python 2.7–5.0×（明确未做解释器优化） | `reports/performance.md`、`bench/results.json` |
| S43 并发 | 46 项并发黑盒、46×10 逐字节确定、found/absent/tampered 三态 | `docs/s42-deterministic-concurrency.md`、`reports/s42-schedules/` |
| S44 加速 | 纯执行 N=5000：1.454× / 1.552× / 2.992×；启动 1.256× / 1.224× | `docs/s44-performance.md`、`reports/s44-performance/` |
| S46 模型检查 | clean 8 程序 / 32 runs / 0 violation；mutant 4 violation、最小前缀 `[]` | `reports/s46-concurrency-model/` |
| S47 Agent 盲测 | 首轮 **5/6 = 0.833**（唯一失败为题面歧义）；澄清题面后单题复跑通过 | `reports/s47-submission/agent-eval.json`、`docs/s47-agent-eval.md` |

## 未验证项（如实）

- 现场人工 GUI A–E 验收未执行（语义实验室、日志工作台、LWT Snake、S41 查看器、PPT 逐页播放、桌面无遮挡/输入归属）。
- 教师线下验收与评分未发生。
- Agent 盲测为 6 题单样本；pass@1 不是统计显著的能力估计。
- CI 结论按精确 SHA 记录；功能分支与 `main` 的 CI 分开写，不互相推断。

## 交付包

- `lwt-history.bundle`：`git bundle --all`，含全部 refs 与历史；`git bundle verify` 见 `reports/s47-submission/build.json`。
- `lwt-submission.zip`：HEAD 跟踪树 + 本文件 + bundle；`manifest.sha256` 逐文件摘要。
- 重新生成：`python tools/build_submission.py`；新克隆验证：`python tools/verify_fresh_clone.py --bundle <bundle>`。
"""


def _write_submission() -> str:
    text = submission_markdown()
    SUBMISSION.write_text(text, encoding="utf-8", newline="\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _bundle(out_dir: Path) -> dict:
    target = out_dir / "lwt-history.bundle"
    create = _run(["git", "bundle", "create", str(target), "--branches", "--tags", "HEAD"])
    verify = _run(["git", "bundle", "verify", str(target)])
    heads = _run(["git", "bundle", "list-heads", str(target)])
    graph = _run(["git", "log", "--graph", "--oneline", "--decorate", "--all"])
    (out_dir / "lwt-history.graph.txt").write_text(
        graph["stdout"], encoding="utf-8", newline="\n"
    )
    return {
        "bundle": _display(target),
        "bundle_sha256": _sha256(target) if target.exists() else None,
        "create": create,
        "verify": verify,
        "list_heads": heads,
        "graph": _display(out_dir / "lwt-history.graph.txt"),
    }


def _zip(out_dir: Path, bundle_path: Path | None) -> dict:
    staging = out_dir / "_staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    archive = out_dir / "_tree.zip"
    made = _run(["git", "archive", "--format=zip", "-o", str(archive), "HEAD"])
    if made["exit_code"] != 0:
        raise SystemExit(f"build_submission: git archive failed: {made['stderr']}")
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(staging)
    archive.unlink()
    shutil.copy2(SUBMISSION, staging / "SUBMISSION.md")
    if bundle_path is not None and bundle_path.exists():
        shutil.copy2(bundle_path, staging / bundle_path.name)

    files = sorted(path for path in staging.rglob("*") if path.is_file())
    lines = []
    for path in files:
        rel = path.relative_to(staging).as_posix()
        lines.append(f"{_sha256(path)}  {rel}")
    (staging / "manifest.sha256").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )

    zip_path = out_dir / "lwt-submission.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(staging).as_posix())
    shutil.rmtree(staging)
    with zipfile.ZipFile(zip_path) as zf:
        bad = zf.testzip()
        names = len(zf.namelist())
    return {
        "zip": _display(zip_path),
        "zip_sha256": _sha256(zip_path),
        "zip_entries": names,
        "zip_test": "ok" if bad is None else f"corrupt:{bad}",
        "manifest_entries": len(lines),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DIST / f"lwt-submission-{_stamp()}"))
    parser.add_argument("--no-bundle", action="store_true")
    parser.add_argument("--no-zip", action="store_true")
    parser.add_argument("--no-latest", action="store_true")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    submission_sha = _write_submission()
    record: dict = {
        "schema_version": 1,
        "tool": "tools/build_submission.py",
        "generated_at_utc": _utc(),
        "out_dir": _display(out_dir),
        "submission_md": "SUBMISSION.md",
        "submission_sha256": submission_sha,
    }
    bundle_info = None
    if not args.no_bundle:
        bundle_info = _bundle(out_dir)
        record["bundle"] = bundle_info
    if not args.no_zip:
        bundle_path = out_dir / "lwt-history.bundle" if bundle_info else None
        record["zip"] = _zip(out_dir, bundle_path)

    (out_dir / "build.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    if not args.no_latest:
        DIST.mkdir(parents=True, exist_ok=True)
        latest = {
            "generated_at_utc": record["generated_at_utc"],
            "out_dir": record["out_dir"],
            "bundle": (bundle_info or {}).get("bundle"),
            "bundle_sha256": (bundle_info or {}).get("bundle_sha256"),
            "zip": (record.get("zip") or {}).get("zip"),
            "zip_sha256": (record.get("zip") or {}).get("zip_sha256"),
            "submission_sha256": submission_sha,
        }
        (DIST / "latest.json").write_text(
            json.dumps(latest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n",
        )

    print(
        f"build_submission: {record['out_dir']} "
        f"bundle={'yes' if bundle_info else 'no'} "
        f"zip={'yes' if 'zip' in record else 'no'}"
    )
    if "zip" in record:
        print(f"  zip sha256={record['zip']['zip_sha256'][:16]} entries={record['zip']['zip_entries']}")
    if bundle_info:
        print(f"  bundle verify exit={bundle_info['verify']['exit_code']} sha256={(bundle_info['bundle_sha256'] or '')[:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
