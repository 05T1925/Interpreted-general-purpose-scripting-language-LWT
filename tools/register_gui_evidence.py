"""S48 WP2: register the human GUI evidence without judging it.

Scans ``evidence/gui/`` for A–E screenshots/recordings, computes SHA-256,
byte size and mtime, and writes ``reports/s48-defense/gui-acceptance.{json,md}``.

The tool never marks a step as PASS: a file's presence only means the material
was registered. Missing items stay ``NOT_RUN``; a step the user had to stop
because of occlusion/input-attribution is recorded as ``BLOCKED`` when a
``<item>-BLOCKED-*`` file is present.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "gui"
DEFAULT_OUT = ROOT / "reports" / "s48-defense" / "gui-acceptance.json"

ITEMS = {
    "A": "语义实验室（预测/运行/解释/重置/缩放/输入法/焦点）",
    "B": "日志工作台（WARN/retry/top=2、原始报告、坏文件恢复）",
    "C": "LWT Snake（方向键/提示/自动驾驶/失焦/录制回放）",
    "D": "S41 只读 Tk 查看器",
    "E": "PPT 逐页播放 + 桌面无遮挡/输入归属",
}
SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan() -> dict:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    items: dict[str, dict] = {}
    for key, label in ITEMS.items():
        files = []
        blocked = False
        for path in sorted(EVIDENCE.iterdir()):
            if not path.is_file() or path.suffix.lower() not in SUFFIXES:
                continue
            if not path.name.startswith(key):
                continue
            if "BLOCKED" in path.name.upper():
                blocked = True
            stat = path.stat()
            files.append({
                "name": path.name,
                "bytes": stat.st_size,
                "mtime_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_mtime)),
                "sha256": _sha256(path),
            })
        items[key] = {
            "label": label,
            "files": files,
            "registered": bool(files),
            "status": "REGISTERED" if files else ("BLOCKED" if blocked else "NOT_RUN"),
            "pass": None,
            "note": "登记不等于通过；PASS 必须由本人现场确认",
        }
    registered = sum(1 for item in items.values() if item["registered"])
    return {
        "schema_version": 1,
        "tool": "tools/register_gui_evidence.py",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "evidence_dir": "evidence/gui",
        "items": items,
        "registered": registered,
        "total": len(ITEMS),
        "overall": f"REGISTERED {registered}/{len(ITEMS)}",
        "pass": None,
        "not_automated": True,
        "warning": "人工 GUI 验收不能由本工具判定；未登记项为 NOT_RUN，遮挡/不可归因为 BLOCKED。",
    }


def render(doc: dict) -> str:
    lines = [
        "# S48 现场人工 GUI 证据登记",
        "",
        f"> 生成：{doc['generated_at_utc']}；**{doc['overall']}**。本工具只登记材料与 SHA-256，不判定通过。",
        "",
        "| 项 | 内容 | 状态 | 文件数 | 证据 |",
        "|---|---|---|---:|---|",
    ]
    for key, item in doc["items"].items():
        names = ", ".join(f"`{f['name']}`" for f in item["files"]) or "—"
        lines.append(f"| {key} | {item['label']} | {item['status']} | {len(item['files'])} | {names} |")
    lines += [
        "",
        "## 口径",
        "",
        "- `REGISTERED n/5` 只表示材料已登记；`PASS` 必须由本人在现场确认并口头说明。",
        "- 缺项为 `NOT_RUN`；出现遮挡或输入无法归因时停止该项并记 `BLOCKED`，不绕过、不补拍。",
        "- 自动 GUI 测试（Tk 回调/无头）不能替代本目录的人工证据。",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--require-all", action="store_true",
                        help="exit 1 when fewer than 5 items are registered")
    args = parser.parse_args(argv)
    doc = scan()
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    out.with_suffix(".md").write_text(render(doc), encoding="utf-8", newline="\n")
    print(f"register_gui_evidence: {doc['overall']} -> {out.relative_to(ROOT)}")
    if args.require_all and doc["registered"] < doc["total"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
