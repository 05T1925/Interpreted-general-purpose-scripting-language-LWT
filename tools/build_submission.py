"""S47: build the teacher-facing submission package.

Outputs (default ``dist/lwt-submission-<UTC>/``; ``dist/`` is git-ignored):

  SUBMISSION.md              canonical copy is also written to the repo root
  lwt-history.bundle         ``git bundle --branches --tags HEAD`` (all branches,
                             tags and HEAD; temporary worktree refs excluded)
  lwt-history.graph.txt      ``git log --graph --oneline --decorate --all``
  lwt-submission.zip         tracked HEAD tree + SUBMISSION.md + bundle
  manifest.sha256            per-file SHA-256 for every zip entry
  build.json                 machine-readable build record
  ../latest.json             pointer used by the acceptance selfcheck

``--package-index`` additionally writes ``reports/s48-defense/package-index.json``
(committed) recording the bundle tip and the whitelist of paths allowed between
that tip and the final commit, so the package never has to contain its own hash.

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
import re
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
INDEX_REL = Path("reports/s48-defense/package-index.json")

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
         f"400/400；矩阵 `referenced_cases=400/400`；426 个 `*.lwt` 脚本（用 LWT 测试 LWT）", "完成"),
        ("4", "性能测试报告", "10", "reports/performance.md、bench/results.json",
         "`python tools/compare_perf.py`", "S11 正式报告 + S44 分层对照", "完成"),
        ("5", "开发指南（人 + AI）", "20", "docs/developer-guide.md、.agents/skills/lwt-app/SKILL.md",
         "`python -m lwt --check examples/modules/main.lwt`", "S42–S46 已按指南实现", "完成"),
        ("6", "Agent 应用与开发记录", "30", "app/log_report.lwt、app/concurrent_log_report.lwt、app/lwt_snake/game.lwt、docs/agent-dev-log.md",
         "`python -m lwt app/log_report.lwt -- app/fixtures/sample.log`",
         "有效行数 243 / 233 / 313（`tools/count_lwt_lines.py`）", "完成"),
        ("7", "Git 历史", "—", "dist/ 内的 lwt-history.bundle、lwt-history.graph.txt",
         "`python tools/build_submission.py`（索引 `reports/s48-defense/package-index.json`）",
         "bundle 含全部 branches/tags/HEAD；verify=0；索引记录截止 SHA", "完成"),
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

> **解释器陷阱（现场复现必读）**：全量 unittest 必须用 `py -3.13`（3.13.7 + **Tk 8.6**）。本机 `python` 是 WorkBuddy 内置 3.13.14，**没有 tkinter**：GUI 测试模块在 import 阶段就失败，只会跑 **711** 项并出现 2 个假失败，不是语言缺陷。根因、两份日志与哈希见 `reports/s50-closeout/unittest-interpreter-root-cause.json`；`docs/defense-claims.json` 的 unittest 行也声明了 `requires.tkinter`。

> 离线提交件：bundle/zip 位于 `dist/`（默认 gitignore，不入库），索引见 `reports/s48-defense/package-index.json`。老师 clone 仓库后若 `dist/` 为空，请现场运行 `python tools/build_submission.py`，或直接携带 `dist/` 目录。

## 课程第 8 章口径对照（任务 1–5）

| 课件任务 | 仓库证据 | 一条复算命令 |
|---|---|---|
| 任务 1 解释器 | `lwt/`、`docs/language-spec.md` | `python -m lwt examples/guide/hello.lwt` |
| 任务 2 黑盒测试集（用 LWT 测试 LWT、逐项打勾） | `tests/cases/`（426 个 `.lwt`）、`docs/test-matrix.md` §8 表 | `python tools/run_tests.py` |
| 任务 3 性能测试（基线 + 分位数 + 空间） | `reports/performance.md`、`reports/s44-performance/`、`reports/s52-course-align/performance-space.json` | `python tools/compare_perf.py` |
| 任务 4 Agent 开发指南 | `.agents/skills/lwt-app/SKILL.md`、`docs/developer-guide.md` | `python -m lwt --check examples/modules/main.lwt` |
| 任务 5 Agent 应用（≥200 行，重功能与协作） | `app/log_report.lwt`、`app/concurrent_log_report.lwt`、`app/lwt_snake/game.lwt`、`docs/agent-dev-log.md` | `python -m lwt app/log_report.lwt -- app/fixtures/sample.log` |

> **第 4 章口径对照**：CLI 的退出码合同、stdout/stderr 分流、结构化输出（`--check --format=json`、`--profile`、`--schedule-log`）与“只增不改”的兼容做法，逐条见 [docs/agent-friendly-interface.md](docs/agent-friendly-interface.md)。
> **第 5 章口径对照**：测试不是“永真断言”——18 条语义变异探针全部被判红，证据见 [reports/s53-mutation/mutation-report.json](reports/s53-mutation/mutation-report.json)；边界与本机解释器陷阱见 [docs/s53-mutation-interface.md](docs/s53-mutation-interface.md)。
'''
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
| S48 Agent 盲测 | 60 会话（6 题 × T/C 两组 × 5 样本）：T **30/30**、C **29/30**；T−C=+0.033，95% 区间 [−0.031, +0.098] | `reports/s48-defense/ablation.json`、`docs/s48-agent-eval.md` |

## 未验证项（如实）

- 现场人工 GUI A–E 验收未执行（语义实验室、日志工作台、LWT Snake、S41 查看器、PPT 逐页播放、桌面无遮挡/输入归属）。
- 教师线下验收与评分未发生。
- Agent 盲测为 60 会话的观察性对照（6 题 × 2 组 × 5 样本）；T−C 区间含 0，不是因果证明。
- CI 结论按精确 SHA 记录；功能分支与 `main` 的 CI 分开写，不互相推断。

## 交付包

- `lwt-history.bundle`：`git bundle --branches --tags HEAD`，含全部分支/标签与历史（排除临时 worktree refs）；`git bundle verify` 见 `reports/s48-defense/package-index.json`。
- `lwt-submission.zip`：HEAD 跟踪树 + 本文件 + bundle；`manifest.sha256` 逐文件摘要。
- 包不入库：`dist/` 被 gitignore，入库的是索引 `reports/s48-defense/package-index.json`（记录 bundle 截止 SHA 与允许的差异白名单）。
- 重新生成：`python tools/build_submission.py --package-index reports/s48-defense/package-index.json`；新克隆验证：`python tools/verify_fresh_clone.py --package-index reports/s48-defense/package-index.json`。
- S47 盲测派生说明：`reports/s47-submission/agent-eval.json` 的 `note` 是历史快照，与后续执行状态不一致；以 `reports/s48-defense/agent-eval-s47-derivation.json` 为准（记录原始 overall、失败题判定与澄清单列）。
"""


def _write_submission() -> str:
    text = submission_markdown()
    SUBMISSION.write_text(text, encoding="utf-8", newline="\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _git_rev(rev: str = "HEAD") -> str:
    return _run(["git", "rev-parse", rev]).get("stdout", "").strip()


def _bundle_main_sha(list_heads_stdout: str) -> str | None:
    """Return the SHA recorded for refs/heads/main in ``git bundle list-heads``."""

    for line in list_heads_stdout.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == "refs/heads/main":
            return parts[0]
    return None


def _package_index(
    out_dir: Path,
    *,
    bundle_ref_sha: str,
    final_tip_sha: str,
    bundle_sha256: str | None,
    zip_sha256: str | None,
    rebuild_command: str,
) -> dict:
    """S48 WP0-1: a committed index that never contains its own hash.

    The bundle cannot contain the commit that records the bundle (that is a
    self-reference), so the index declares the bundle tip and the whitelist of
    paths allowed between that tip and the final tip.
    """

    lag = _run(["git", "diff", "--name-only", f"{bundle_ref_sha}..{final_tip_sha}"])
    diff_paths = [line for line in lag["stdout"].splitlines() if line.strip()]
    document = {
        "schema_version": 1,
        "tool": "tools/build_submission.py",
        "bundle_ref_sha": bundle_ref_sha,
        "final_tip_sha": final_tip_sha,
        "bundle_ref_matches_final_tip": bundle_ref_sha == final_tip_sha,
        "diff_paths": diff_paths,
        "diff_whitelist": [
            INDEX_REL.as_posix(),
            "reports/s53-mutation/fresh-clone.json",
            "reports/s53-mutation/fresh-clone.md",
            "reports/s53-mutation/selfcheck/",
            "reports/s53-mutation/defense-probe.json",
            "reports/s53-mutation/defense-probe.md",
            "reports/s53-mutation/mutation-report.json",
            "reports/s53-mutation/mutation-report.md",
            "reports/s49-rehearsal/ci-cells.json",
            "docs/s53-mutation-interface.md",
        ],
        "generated_at_utc": _utc(),
        "rebuild_command": rebuild_command,
        "package_dir": _display(out_dir),
        "bundle_sha256": bundle_sha256,
        "zip_sha256": zip_sha256,
        "note": (
            "bundle 截止 SHA 见 bundle_ref_sha；本索引提交是其后唯一允许的差异"
            "（diff_whitelist）。复核：git fetch <bundle> main && git log <bundle_ref_sha>..<final_tip_sha>"
        ),
    }
    return document


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
    # Stage outside the repository: bulk deletion inside dist/ may be blocked
    # by host safe-delete guards, and a leftover staging tree would pollute the
    # delivered package directory.
    staging = Path(tempfile.mkdtemp(prefix="lwt-submission-stage-"))
    archive = Path(tempfile.mkdtemp(prefix="lwt-archive-")) / "tree.zip"
    made = _run(["git", "archive", "--format=zip", "-o", str(archive), "HEAD"])
    if made["exit_code"] != 0:
        raise SystemExit(f"build_submission: git archive failed: {made['stderr']}")
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(staging)
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
    shutil.rmtree(staging, ignore_errors=True)
    shutil.rmtree(archive.parent, ignore_errors=True)
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
    parser.add_argument("--final-tip", default=None,
                        help="SHA the delivered history must reach (default: HEAD)")
    parser.add_argument("--allow-ref-lag", action="store_true",
                        help="allow bundle main != final tip, printing the lag diff")
    parser.add_argument("--package-index", default=None,
                        help=f"write a committed index (suggested: {INDEX_REL})")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    head_sha = _git_rev("HEAD")
    final_tip = args.final_tip or head_sha
    if args.final_tip and not re.fullmatch(r"[0-9a-f]{7,40}", args.final_tip):
        print(f"build_submission: --final-tip is not a SHA: {args.final_tip}", file=sys.stderr)
        return 2
    if args.final_tip and not head_sha.startswith(args.final_tip):
        print(
            f"build_submission: --final-tip {args.final_tip} != HEAD {head_sha}; "
            "checkout the final tip first",
            file=sys.stderr,
        )
        return 2

    submission_sha = _write_submission()
    record: dict = {
        "schema_version": 1,
        "tool": "tools/build_submission.py",
        "generated_at_utc": _utc(),
        "out_dir": _display(out_dir),
        "submission_md": "SUBMISSION.md",
        "submission_sha256": submission_sha,
        "final_tip_sha": final_tip,
    }
    bundle_info = None
    if not args.no_bundle:
        bundle_info = _bundle(out_dir)
        record["bundle"] = bundle_info
        bundle_main = _bundle_main_sha(bundle_info["list_heads"]["stdout"])
        record["bundle_main_sha"] = bundle_main
        if bundle_main != final_tip:
            lag = _run(["git", "log", "--oneline", f"{bundle_main}..{final_tip}"])
            print(
                f"build_submission: REF LAG: bundle main {bundle_main} != final tip {final_tip}\n"
                + lag["stdout"],
                file=sys.stderr,
            )
            if not args.allow_ref_lag:
                print(
                    "build_submission: refusing to claim the final tip is packaged; "
                    "re-run at the final tip or pass --allow-ref-lag",
                    file=sys.stderr,
                )
                return 2
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
            "bundle_main_sha": record.get("bundle_main_sha"),
            "final_tip_sha": final_tip,
            "package_index": args.package_index,
            "zip": (record.get("zip") or {}).get("zip"),
            "zip_sha256": (record.get("zip") or {}).get("zip_sha256"),
            "submission_sha256": submission_sha,
        }
        (DIST / "latest.json").write_text(
            json.dumps(latest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n",
        )

    if args.package_index:
        index_path = Path(args.package_index)
        if not index_path.is_absolute():
            index_path = ROOT / index_path
        index_path.parent.mkdir(parents=True, exist_ok=True)
        document = _package_index(
            out_dir,
            bundle_ref_sha=record.get("bundle_main_sha") or final_tip,
            final_tip_sha=final_tip,
            bundle_sha256=(bundle_info or {}).get("bundle_sha256"),
            zip_sha256=(record.get("zip") or {}).get("zip_sha256"),
            rebuild_command="python tools/build_submission.py",
        )
        index_path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n",
        )
        print(f"  package index -> {_display(index_path)}")

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
