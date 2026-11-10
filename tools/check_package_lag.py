"""Check the committed package index against the real HEAD.

The bundle cannot contain the commit that records it, so the package index
declares ``bundle_ref_sha`` (X), the build-time ``final_tip_sha`` and a
``diff_whitelist``. This tool recomputes ``git diff --name-only X..HEAD`` and
classifies every path:

* ``in_whitelist`` — exact match or a whitelisted directory prefix;
* ``outside_whitelist`` — anything else. That is a hard failure: it means the
  delivered bundle is behind changes the index never declared.

Run it before claiming "the package is current", and again after a repack.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "reports" / "s48-defense" / "package-index.json"


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"check_package_lag: git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def classify(paths: list[str], whitelist: list[str]) -> tuple[list[str], list[str]]:
    def allowed(path: str) -> bool:
        return any(path == entry or (entry.endswith("/") and path.startswith(entry))
                   for entry in whitelist)

    inside = [p for p in paths if allowed(p)]
    outside = [p for p in paths if not allowed(p)]
    return inside, outside


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default=str(INDEX))
    parser.add_argument("--head", default=None, help="defaults to the real HEAD")
    parser.add_argument("--record", default=None, help="write a JSON record here")
    args = parser.parse_args(argv)

    index_path = Path(args.index)
    if not index_path.is_absolute():
        index_path = ROOT / index_path
    doc = json.loads(index_path.read_text(encoding="utf-8"))
    bundle_ref = doc["bundle_ref_sha"]
    head = args.head or _git("rev-parse", "HEAD")
    whitelist = list(doc.get("diff_whitelist") or [])
    paths = [p for p in _git("diff", "--name-only", f"{bundle_ref}..{head}").splitlines() if p]
    inside, outside = classify(paths, whitelist)

    record = {
        "schema_version": 1,
        "tool": "tools/check_package_lag.py",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "index": index_path.relative_to(ROOT).as_posix(),
        "bundle_ref_sha": bundle_ref,
        "declared_final_tip_sha": doc.get("final_tip_sha"),
        "head": head,
        "lag_paths": paths,
        "in_whitelist": inside,
        "outside_whitelist": outside,
        "ok": not outside,
    }
    print(f"check_package_lag: X={bundle_ref[:12]} HEAD={head[:12]} "
          f"lag={len(paths)} outside={len(outside)}")
    for path in inside:
        print(f"  ok       {path}")
    for path in outside:
        print(f"  OUTSIDE  {path}")
    if args.record:
        out = Path(args.record)
        if not out.is_absolute():
            out = ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8", newline="\n")
        print(f"  record -> {out.relative_to(ROOT)}")
    return 0 if record["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
