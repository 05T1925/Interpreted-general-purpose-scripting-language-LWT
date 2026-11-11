"""S47: verify a fresh clone made from the submission bundle.

Clones ``lwt-history.bundle`` into a temporary directory (a blank environment
with no reuse of this working tree's untracked files) and runs:

  1. ``python -m lwt --version``
  2. ``python -m lwt --check examples/modules/main.lwt``
  3. ``python tools/run_tests.py``            (expect 400/400)
  4. ``python -m compileall -q lwt tests tools``
  5. ``python tools/check_project_integrity.py --require-all-referenced``

S48 adds ``--package-index``: the clone's HEAD must equal the index's
``bundle_ref_sha`` and the commits between that SHA and the final tip may only
touch the declared whitelist (the index file itself), so "bundle tip verified"
is never reported as "final tip verified".

Every command's real exit code and key output is recorded in
``reports/s49-rehearsal/fresh-clone.{json,md}``.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "reports" / "s51-closeout" / "fresh-clone.json"
LATEST = ROOT / "dist" / "latest.json"


def _run(cmd: list[str], cwd: Path, timeout: int = 900) -> dict:
    started = time.perf_counter()
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    completed = subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, timeout=timeout, check=False, env=env
    )
    return {
        "command": cmd,
        "exit_code": completed.returncode,
        "stdout": completed.stdout.decode("utf-8", "replace"),
        "stderr": completed.stderr.decode("utf-8", "replace"),
        "seconds": round(time.perf_counter() - started, 3),
    }


def _blackbox_counts(stdout: str) -> dict:
    match = re.search(
        r"passed=(\d+) failed=(\d+) total=(\d+)", stdout
    )
    if not match:
        return {"parsed": False}
    return {
        "parsed": True,
        "passed": int(match.group(1)),
        "failed": int(match.group(2)),
        "total": int(match.group(3)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", default=None,
                        help="bundle path (default: dist/latest.json's bundle)")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--package-index", default=None,
                        help="committed package index to bound-check against")
    parser.add_argument("--final-tip", default=None,
                        help="final tip SHA (default: this workspace's HEAD)")
    parser.add_argument("--keep", action="store_true", help="keep the clone for inspection")
    args = parser.parse_args(argv)

    bundle = args.bundle
    if bundle is None:
        if not LATEST.exists():
            print("verify_fresh_clone: no --bundle and dist/latest.json is missing",
                  file=sys.stderr)
            return 2
        bundle = json.loads(LATEST.read_text(encoding="utf-8")).get("bundle")
        if not bundle:
            print("verify_fresh_clone: dist/latest.json has no bundle", file=sys.stderr)
            return 2
    bundle_path = Path(bundle)
    if not bundle_path.is_absolute():
        bundle_path = ROOT / bundle_path
    if not bundle_path.exists():
        print(f"verify_fresh_clone: bundle not found: {bundle_path}", file=sys.stderr)
        return 2

    started = time.monotonic()
    folder = tempfile.mkdtemp(prefix="lwt-s47-clone-")
    clone = Path(folder) / "lwt"
    steps: list[dict] = []
    try:
        cloned = _run(
            ["git", "clone", "--quiet", "-b", args.branch,
             str(bundle_path), str(clone)],
            ROOT,
            timeout=300,
        )
        steps.append({"name": "git clone", **cloned})
        if cloned["exit_code"] != 0:
            raise SystemExit(1)

        steps.append({"name": "version", **_run(
            [sys.executable, "-m", "lwt", "--version"], clone, timeout=120)})
        steps.append({"name": "check", **_run(
            [sys.executable, "-m", "lwt", "--check", "examples/modules/main.lwt"],
            clone, timeout=180)})
        blackbox = _run([sys.executable, "tools/run_tests.py"], clone, timeout=1200)
        blackbox["parsed"] = _blackbox_counts(blackbox["stdout"])
        steps.append({"name": "blackbox", **blackbox})
        steps.append({"name": "compileall", **_run(
            [sys.executable, "-m", "compileall", "-q", "lwt", "tests", "tools"],
            clone, timeout=300)})
        steps.append({"name": "integrity", **_run(
            [sys.executable, "tools/check_project_integrity.py",
             "--require-all-referenced"], clone, timeout=300)})

        blackbox_ok = (
            blackbox.get("parsed", {}).get("passed") == 400
            and blackbox.get("parsed", {}).get("failed") == 0
        )

        clone_head = (
            _run(["git", "rev-parse", "HEAD"], clone, timeout=30)["stdout"].strip()
            if clone.exists() else None
        )
        index_doc: dict = {}
        lag_paths: list[str] = []
        lag_ok = True
        final_tip = args.final_tip
        if args.package_index:
            index_path = Path(args.package_index)
            if not index_path.is_absolute():
                index_path = ROOT / index_path
            if not index_path.exists():
                raise SystemExit(f"verify_fresh_clone: package index missing: {index_path}")
            index_doc = json.loads(index_path.read_text(encoding="utf-8"))
            if clone_head != index_doc.get("bundle_ref_sha"):
                lag_ok = False
            # Y is the workspace's current HEAD (the real final tip); the SHA
            # stored in the index is only the build-time value and must not be
            # used to make the lag check trivially pass.
            workspace_head = _run(["git", "rev-parse", "HEAD"], ROOT, timeout=30)["stdout"].strip()
            tip = final_tip or workspace_head
            diff = _run(["git", "diff", "--name-only", f"{clone_head}..{tip}"], ROOT, timeout=60)
            lag_paths = [line for line in diff["stdout"].splitlines() if line.strip()]
            whitelist = list(index_doc.get("diff_whitelist") or [])

            def _allowed(path: str) -> bool:
                return any(
                    path == entry or (entry.endswith("/") and path.startswith(entry))
                    for entry in whitelist
                )

            lag_ok = lag_ok and all(_allowed(path) for path in lag_paths)
            final_tip = tip

        all_ok = all(step["exit_code"] == 0 for step in steps) and blackbox_ok and lag_ok
        document = {
            "schema_version": 1,
            "tool": "tools/verify_fresh_clone.py",
            "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "bundle": str(bundle_path),
            "branch": args.branch,
            "clone_dir": str(clone) if args.keep else "(temporary, removed)",
            "head": clone_head,
            "bundle_ref_sha": index_doc.get("bundle_ref_sha"),
            "final_tip_sha": final_tip,
            "index_declared_final_tip_sha": index_doc.get("final_tip_sha"),
            "lag_paths": lag_paths,
            "lag_whitelist": index_doc.get("diff_whitelist"),
            "lag_ok": lag_ok,
            "all_pass": all_ok,
            "blackbox_ok": blackbox_ok,
            "seconds": round(time.monotonic() - started, 2),
            "steps": steps,
        }
        out = Path(args.out)
        if not out.is_absolute():
            out = ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n",
        )

        lines = [
            "# S48 fresh-clone verification",
            "",
            f"- Bundle: `{bundle_path}`",
            f"- Branch: `{args.branch}`；bundle HEAD `{(document['head'] or '')[:12]}`",
        ]
        if args.package_index:
            lines.append(
                f"- 最终 tip `{(final_tip or '')[:12]}`；lag 白名单 "
                f"{'通过' if lag_ok else 'FAIL'}：{', '.join(lag_paths) or '(无差异)'}"
            )
        lines += [
            f"- Result: **{'PASS' if all_ok else 'FAIL'}**（{document['seconds']} s）",
            "",
            "| step | exit | seconds | key output |",
            "|---|---:|---:|---|",
        ]
        for step in steps:
            key = ""
            if step["name"] == "blackbox" and step.get("parsed", {}).get("parsed"):
                parsed = step["parsed"]
                key = f"passed={parsed['passed']} failed={parsed['failed']} total={parsed['total']}"
            elif step["name"] == "version":
                key = step["stdout"].strip()
            else:
                key = (step["stdout"].strip().splitlines() or [""])[-1][:120]
            lines.append(
                f"| {step['name']} | {step['exit_code']} | {step['seconds']} | {key} |"
            )
        out.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

        print(
            f"verify_fresh_clone: {'PASS' if all_ok else 'FAIL'} "
            f"(blackbox={'400/400' if blackbox_ok else 'FAIL'}) -> {out}"
        )
        return 0 if all_ok else 1
    finally:
        if not args.keep:
            shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
