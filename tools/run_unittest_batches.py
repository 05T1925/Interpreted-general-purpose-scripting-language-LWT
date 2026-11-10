"""Run the full unittest suite in batches and aggregate the result.

Why: the whole suite takes ~20 minutes on this machine and one GUI test can keep
a grandchild process alive, which makes ``subprocess.run(capture_output=True)``
wait for EOF forever (the probe hung that way once). This runner

* splits ``tests/test_*.py`` into a non-GUI batch and a GUI batch (or ``--batches N``),
* redirects each batch to a temporary file instead of a pipe,
* parses ``Ran N tests`` / ``OK`` / ``FAILED``,
* exits 0 only when every batch passed **and** the total matches the expected
  count (``docs/delivery-manifest.json`` by default).

It is equivalent coverage, not a subset: every discovered module runs exactly
once. The report must still say "two batches", never "one command".
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "delivery-manifest.json"


def _modules() -> list[str]:
    files = sorted((ROOT / "tests").glob("test_*.py"))
    return [f"tests.{path.stem}" for path in files]


def _split(modules: list[str], batches: int) -> list[list[str]]:
    gui = [m for m in modules if "gui" in m]
    rest = [m for m in modules if "gui" not in m]
    if batches <= 2:
        return [rest, gui]
    size = max(1, len(rest) // (batches - 1))
    chunks = [rest[i:i + size] for i in range(0, len(rest), size)]
    return chunks + [gui]


def _run_batch(modules: list[str], timeout: int) -> dict:
    started = time.perf_counter()
    with tempfile.NamedTemporaryFile("w+", suffix=".log", delete=False, encoding="utf-8") as handle:
        log_path = Path(handle.name)
    try:
        with log_path.open("w", encoding="utf-8") as log:
            completed = subprocess.run(
                [sys.executable, "-m", "unittest", *modules, "-q"],
                cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=timeout, check=False,
            )
        text = log_path.read_text(encoding="utf-8", errors="replace")
        ran = re.search(r"^Ran (\d+) tests?", text, re.M)
        failed = "FAILED" in text
        ok = completed.returncode == 0 and ran is not None and not failed
        tail = "\n".join(text.strip().splitlines()[-6:])
        return {
            "modules": len(modules),
            "exit_code": completed.returncode,
            "tests": int(ran.group(1)) if ran else None,
            "ok": ok,
            "seconds": round(time.perf_counter() - started, 1),
            "tail": tail,
        }
    except subprocess.TimeoutExpired:
        return {
            "modules": len(modules), "exit_code": None, "tests": None, "ok": False,
            "seconds": round(time.perf_counter() - started, 1),
            "tail": f"timeout after {timeout}s",
        }
    finally:
        log_path.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batches", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=1200, help="per batch")
    parser.add_argument("--expect", type=int, default=None,
                        help="expected total (default: manifest unittest_count)")
    parser.add_argument("--json", default=None)
    args = parser.parse_args(argv)

    expected = args.expect
    if expected is None:
        expected = json.loads(MANIFEST.read_text(encoding="utf-8"))["unittest_count"]

    modules = _modules()
    plan = _split(modules, args.batches)
    results = [_run_batch(batch, args.timeout) for batch in plan if batch]
    total = sum(row["tests"] or 0 for row in results)
    all_ok = all(row["ok"] for row in results)
    doc = {
        "schema_version": 1,
        "tool": "tools/run_unittest_batches.py",
        "modules": len(modules),
        "batches": len(results),
        "expected": expected,
        "total": total,
        "all_ok": all_ok and total == expected,
        "results": results,
    }
    for index, row in enumerate(results, 1):
        print(f"batch {index}: modules={row['modules']} tests={row['tests']} "
              f"ok={row['ok']} {row['seconds']}s")
        if not row["ok"]:
            print("  " + row["tail"].replace("\n", "\n  "))
    print(f"run_unittest_batches: total={total}/{expected} all_ok={doc['all_ok']}")
    if args.json:
        out = Path(args.json)
        if not out.is_absolute():
            out = ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0 if doc["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
