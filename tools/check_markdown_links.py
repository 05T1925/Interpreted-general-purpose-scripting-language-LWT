"""Check that repository Markdown links resolve (no network).

Scans every tracked ``*.md`` for inline links ``[text](target)`` and verifies
that relative targets exist on disk. External URLs (http/https/mailto) are not
fetched — the acceptance rule is "no broken local links", offline.

Also verifies that ``#anchor`` links inside docs/defense-index.html point at an
existing ``id="..."`` in the same file.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE_RE = re.compile(r"```.*?```", re.S)
HTML_ID_RE = re.compile(r'id="([^"]+)"')


def _tracked_markdown() -> list[Path]:
    result = subprocess.run(["git", "ls-files", "*.md"], cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit("check_markdown_links: git ls-files failed")
    return [ROOT / line for line in result.stdout.splitlines() if line.strip()]


def check_file(path: Path) -> list[str]:
    broken: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    text = FENCE_RE.sub("", text)
    for match in LINK_RE.finditer(text):
        target = match.group(1).strip()
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        clean = target.split("#", 1)[0]
        if not clean:
            continue
        resolved = (path.parent / clean).resolve()
        if not resolved.exists():
            broken.append(f"{path.relative_to(ROOT).as_posix()} -> {target}")
    return broken


def check_html_anchors(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    ids = set(HTML_ID_RE.findall(text))
    broken = []
    for href in re.findall(r'href="#([^"]+)"', text):
        if href not in ids:
            broken.append(f"{path.relative_to(ROOT).as_posix()} -> #{href}")
    return broken


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", default=None)
    args = parser.parse_args(argv)

    files = _tracked_markdown()
    broken: list[str] = []
    for path in files:
        if path.exists():
            broken.extend(check_file(path))
    broken.extend(check_html_anchors(ROOT / "docs" / "defense-index.html"))

    doc = {
        "schema_version": 1,
        "tool": "tools/check_markdown_links.py",
        "markdown_files": len(files),
        "broken": broken,
        "ok": not broken,
    }
    print(f"check_markdown_links: files={len(files)} broken={len(broken)}")
    for item in broken:
        print(f"  BROKEN {item}")
    if args.record:
        out = Path(args.record)
        if not out.is_absolute():
            out = ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8", newline="\n")
    return 0 if not broken else 1


if __name__ == "__main__":
    raise SystemExit(main())
