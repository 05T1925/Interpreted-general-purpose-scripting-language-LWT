"""Compare S44 before/after performance evidence and apply acceptance gates.

Reads only the new ``reports/s44-performance/{before,after}/`` JSON files and
prints a structured verdict against the S44 task-book thresholds. It never
writes any file, never touches S11/S42/S43 evidence, and never invents numbers:
a missing evidence file is reported as ``MISSING`` (not treated as a pass).

Gates (spec S44 section 6):
  * startup: non-spawn programs must not import lwt.concurrency (asserted by
    tests/test_startup.py, not by timing); --help median >=15% faster; hello
    median >=10% faster.
  * pure execute (N=5000): >=2 of 3 workloads >=15% faster; no workload
    regresses >5%.
  * determinism / black-box / S28 are checked by run_tests.py,
    run_concurrency_determinism.py and the unittest suite -- not here.

Usage:
    python tools/compare_perf.py
    python tools/compare_perf.py --format json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "reports" / "s44-performance"
WORKLOADS = ("arithmetic", "array_scan", "dict_counts")
GATE_SIZE = 5000


def _load(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _ratio(before_ns: float, after_ns: float) -> float | None:
    return before_ns / after_ns if after_ns else None


def _fmt(value: float | None, suffix: str = "×") -> str:
    return "MISSING" if value is None else f"{value:.3f}{suffix}"


def compare() -> dict[str, Any]:
    startup_before = _load(BASE / "before" / "startup.json")
    startup_after = _load(BASE / "after" / "startup.json")
    micro_before = _load(BASE / "before" / "runtime-profile.json")
    micro_after = _load(BASE / "after" / "runtime-profile.json")

    startup: dict[str, Any] = {}
    for name, gate in (("lwt-help", 1.15), ("lwt-hello", 1.10)):
        if startup_before and startup_after:
            b = startup_before["summary"][name]["median_ms"]
            a = startup_after["summary"][name]["median_ms"]
            ratio = _ratio(b, a)
            startup[name] = {
                "before_ms": b, "after_ms": a, "ratio": ratio,
                "gate": gate, "pass": (ratio is not None and ratio >= gate),
            }
        else:
            startup[name] = {"before_ms": None, "after_ms": None, "ratio": None,
                             "gate": gate, "pass": False, "missing": True}

    execute: dict[str, Any] = {}
    passes = 0
    regressions: list[str] = []
    if micro_before and micro_after:
        bm = {(m["workload"], m["n"]): m for m in micro_before["measurements"]}
        am = {(m["workload"], m["n"]): m for m in micro_after["measurements"]}
    else:
        bm = am = {}
    for workload in WORKLOADS:
        key = (workload, GATE_SIZE)
        if key in bm and key in am:
            b = bm[key]["execute"]["median_ns"]
            a = am[key]["execute"]["median_ns"]
            ratio = _ratio(b, a)
            ok_15 = ratio is not None and ratio >= 1.15
            regressed = ratio is not None and ratio < 0.95
            if ok_15:
                passes += 1
            if regressed:
                regressions.append(workload)
            execute[workload] = {
                "before_ms": round(b / 1e6, 3), "after_ms": round(a / 1e6, 3),
                "ratio": ratio, "pass_15pct": ok_15, "regressed_gt5pct": regressed,
            }
        else:
            execute[workload] = {"before_ms": None, "after_ms": None, "ratio": None,
                                 "pass_15pct": False, "regressed_gt5pct": False, "missing": True}

    startup_ok = all(startup[n]["pass"] for n in ("lwt-help", "lwt-hello"))
    execute_ok = passes >= 2 and not regressions and all(
        not v.get("missing") for v in execute.values()
    )
    return {
        "schema_version": 1,
        "evidence_dir": str(BASE.relative_to(ROOT)),
        "gates": {
            "startup": {"pass": startup_ok, "detail": startup},
            "pure_execute": {
                "pass": execute_ok, "workloads_passing_15pct": passes,
                "required": 2, "regressed_gt5pct": regressions, "detail": execute,
            },
        },
        "all_pass": startup_ok and execute_ok,
        "note": "Non-spawn sys.modules (no lwt.concurrency) and 401/401 black-box / "
                "46x10 determinism / S28 event counts are verified by tests and "
                "runner commands, not by this timing comparator.",
    }


def render(doc: dict[str, Any]) -> str:
    g = doc["gates"]
    lines = [
        "S44 before/after 对照（新证据，同机 A/B）",
        "",
        "启动（新进程墙钟中位数，门槛 --help >=15%、hello >=10%）：",
    ]
    for name, label in (("lwt-help", "python -m lwt --help"), ("lwt-hello", "python -m lwt hello.lwt")):
        d = g["startup"]["detail"][name]
        if d.get("missing"):
            lines.append(f"  {label}: MISSING evidence")
        else:
            lines.append(
                f"  {label}: {d['before_ms']:.3f} -> {d['after_ms']:.3f} ms "
                f"= {_fmt(d['ratio'])} (gate {d['gate']:.2f}×) "
                f"{'PASS' if d['pass'] else 'FAIL'}"
            )
    lines += ["", f"纯执行 execute（N={GATE_SIZE}，门槛 >=2/3 负载 >=15%、无 >5% 回归）："]
    for workload in WORKLOADS:
        d = g["pure_execute"]["detail"][workload]
        if d.get("missing"):
            lines.append(f"  {workload}: MISSING evidence")
        else:
            flag = "PASS" if d["pass_15pct"] else ("REGRESSION" if d["regressed_gt5pct"] else "below gate")
            lines.append(
                f"  {workload}: {d['before_ms']:.3f} -> {d['after_ms']:.3f} ms "
                f"= {_fmt(d['ratio'])} [{flag}]"
            )
    lines += [
        "",
        f"判定：启动 {'PASS' if g['startup']['pass'] else 'FAIL'}；"
        f"纯执行 {'PASS' if g['pure_execute']['pass'] else 'FAIL'}"
        f"（{g['pure_execute']['workloads_passing_15pct']}/3 达 15%，"
        f"回归 {g['pure_execute']['regressed_gt5pct'] or '无'}）；"
        f"总体 {'PASS' if doc['all_pass'] else 'FAIL'}",
        "",
        doc["note"],
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    doc = compare()
    if args.format == "json":
        print(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render(doc))
    return 0 if doc["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
