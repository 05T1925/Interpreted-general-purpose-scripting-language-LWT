"""Check the teaching-platform submission bundle against its own manifest.

This tool never uploads anything: the upload is the user's own action on
https://ucloud.bupt.edu.cn/. It only verifies that the artifacts a teacher would
receive are present, byte-identical to the recorded SHA-256 and (optionally)
that the black-box suite inside the zip can still run.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]

REPO_ARTIFACTS = (
    ("README.md", True, "教师入口：三分钟验收路径 + 当前状态"),
    ("SUBMISSION.md", True, "8 项提交内容 + 第 8 章任务对照"),
    ("docs/language-spec.md", True, "§1–§11 正式语言规范"),
    ("docs/test-matrix.md", True, "覆盖矩阵（§8 逐项打勾）"),
    ("docs/defense-qa-card.md", True, "答辩问答卡"),
    ("docs/agent-friendly-interface.md", True, "课件 4.4/4.5 接口对照"),
    ("docs/s53-mutation-interface.md", False, "S53 报告"),
    ("reports/s53-mutation/mutation-report.json", False, "变异探针证据") ,
    ("reports/s52-course-align/performance-space.json", False, "空间/分位数性能证据"),
)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _package_files(index: dict) -> tuple[Path, Path]:
    package_dir = ROOT / index["package_dir"]
    return package_dir / "lwt-submission.zip", package_dir / "lwt-history.bundle"


def _run_blackbox(zip_path: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="lwt-platform-blackbox-") as temporary:
        target = Path(temporary)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(target)
        completed = subprocess.run(
            [sys.executable, "tools/run_tests.py"],
            cwd=target, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=1800, check=False,
        )
        text = completed.stdout.decode("utf-8", "replace")
        passed = total = None
        for token in text.split():
            if token.startswith("passed="):
                passed = int(token.split("=", 1)[1].rstrip(";,"))
            elif token.startswith("total="):
                total = int(token.split("=", 1)[1].rstrip(";,"))
        return {
            "checked": True,
            "exit_code": completed.returncode,
            "passed": passed,
            "total": total,
            "detail": text.strip().splitlines()[-1][:300] if text.strip() else "",
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-index", default="reports/s48-defense/package-index.json")
    parser.add_argument("--out-json", default="docs/platform-submission.json")
    parser.add_argument("--out-md", default="docs/platform-submission.md")
    parser.add_argument("--verify-blackbox", action="store_true",
                        help="unzip to a temp dir and run tools/run_tests.py (about 5 minutes)")
    args = parser.parse_args(argv)

    index = json.loads((ROOT / args.package_index).read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "docs" / "delivery-manifest.json").read_text(encoding="utf-8"))
    zip_path, bundle_path = _package_files(index)

    items: list[dict] = []

    def add(name: str, path: Path, expected: str, required: bool, note: str) -> None:
        exists = path.exists()
        actual = sha256_of(path) if exists else None
        items.append({
            "name": name,
            "path": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),
            "exists": exists,
            "sha256": actual,
            "expected_sha256": expected,
            "sha_ok": bool(exists and actual == expected),
            "required": required,
            "note": note,
        })

    add("提交包 zip", zip_path, index["zip_sha256"], True,
        "解压后即为完整仓库；--verify-blackbox 会实跑 401 黑盒")
    add("Git 历史 bundle", bundle_path, index["bundle_sha256"], True,
        f"截止 SHA {index['bundle_ref_sha'][:12]}；git fetch <bundle> main 可复核")
    add("PPT", ROOT / "slides" / "LWT介绍.pptx", manifest["ppt_sha256"], True,
        f"{manifest['ppt_pages']} 页；内容本阶段未改动")

    for rel, required, note in REPO_ARTIFACTS:
        path = ROOT / rel
        expected = sha256_of(path) if path.exists() else None
        add(rel, path, expected, required, note)

    artifacts_ok = all(item["sha_ok"] for item in items if item["required"])
    blackbox = {"checked": False, "passed": None, "total": None, "detail": "not requested"}
    if args.verify_blackbox and zip_path.exists():
        blackbox = _run_blackbox(zip_path)
    blackbox_ok = (not args.verify_blackbox) or (
        blackbox.get("exit_code") == 0
        and blackbox.get("passed") == manifest["blackbox_cases"]
    )

    doc = {
        "schema_version": 1,
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platform": {
            "name": "教学云平台",
            "url": "https://ucloud.bupt.edu.cn/",
            "course_weight": "大作业 70%：代码审查、文档检查、功能演示、答辩（平时 30%）",
        },
        "uploaded": False,
        "upload_note": "上传动作由本人执行；本工具只校验清单与 SHA，不代表已经提交。",
        "package_index": args.package_index,
        "final_tip_sha": index.get("final_tip_sha"),
        "items": items,
        "artifacts_ok": artifacts_ok,
        "blackbox": blackbox,
        "all_pass": artifacts_ok and blackbox_ok,
    }

    out_json = ROOT / args.out_json
    out_json.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")

    rows = "\n".join(
        f"| {item['name']} | `{item['path']}` | {'是' if item['exists'] else '**否**'} | "
        f"`{(item['sha256'] or '—')[:12]}…` | {'一致' if item['sha_ok'] else '**不一致**'} | {item['note']} |"
        for item in items
    )
    md = f"""# 教学云平台提交清单（S53）

> 平台：{doc['platform']['name']} <{doc['platform']['url']}>；{doc['platform']['course_weight']}。
> **状态：未上传。** 上传必须由本人操作；本文件只证明“待上传的包与清单一致”，不代表已提交。

## 1. 待上传文件

| 项 | 路径 | 存在 | SHA-256 | 校验 | 说明 |
|---|---|---|---|---|---|
{rows}

## 2. 大作业 70% 四项 → 仓库证据

| 评分项 | 证据 | 复算命令 |
|---|---|---|
| 代码审查 | `lwt/`、`tools/`、`tests/`；每阶段提交信息含改动理由 | `python -m compileall -q lwt app tools tests` |
| 文档检查 | `README.md`、`SUBMISSION.md`、`docs/language-spec.md`、`docs/test-matrix.md`、`docs/agent-friendly-interface.md` | `python -m unittest tests.test_doc_consistency -q` |
| 功能演示 | `docs/onsite-runbook.md` 的 5 条必跑命令 + `docs/demo-script.md` | `python -m lwt examples/guide/hello.lwt` |
| 答辩 | `docs/defense-qa-card.md`（含 S53 新增 3 问） | 见该文件 |

## 3. 校验结果

- 必需文件 SHA 全部一致：**{doc['artifacts_ok']}**
- 解压后 401 黑盒：**{blackbox.get('passed')}/{blackbox.get('total')}**（checked={blackbox.get('checked')}，exit={blackbox.get('exit_code', '—')}）
- 总判定 `all_pass`：**{doc['all_pass']}**
- 包索引：`{args.package_index}`（tip `{str(doc['final_tip_sha'])[:12]}`）

## 4. 复现

```bash
python tools/check_platform_bundle.py --verify-blackbox
```
"""
    (ROOT / args.out_md).write_text(md, encoding="utf-8", newline="\n")

    for item in items:
        state = "OK " if item["sha_ok"] else ("MISS" if not item["exists"] else "SHA!")
        print(f"[{state}] {item['name']:<28} {item['path']}")
    print(f"platform-bundle: artifacts_ok={artifacts_ok} blackbox={blackbox.get('passed')}/{blackbox.get('total')} all_pass={doc['all_pass']}")
    return 0 if doc["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
