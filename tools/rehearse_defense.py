"""Rehearse the 21-slide defense under a time box.

This is a **local rehearsal**, not the teacher's acceptance. It walks the slides
in ``docs/defense-pages.json``, prints the talking points and the claim each
slide defends, and (unless ``--dry-run``/``--offline``) really runs
``tools/run_defense_probe.py``'s command for that claim under a per-claim time
box. A claim that does not finish in time is recorded as ``TIMEOUT`` — never as
"basically passed".

Examples
--------
    python tools/rehearse_defense.py --pages 1-21 --dry-run
    python tools/rehearse_defense.py --random 5 --timeout 60
    python tools/rehearse_defense.py --pages 6,18 --allow-heavy --timeout 1800
    python tools/rehearse_defense.py --pages 1-21 --offline

Evidence: ``reports/s49-rehearsal/rehearsal-<UTC>.{json,md}``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import time

try:  # imported as a module (tests, other tools)
    from tools import run_defense_probe
except ModuleNotFoundError:  # run as a script: sys.path[0] is tools/
    import run_defense_probe

ROOT = Path(__file__).resolve().parents[1]
CLAIMS = ROOT / "docs" / "defense-claims.json"
PAGES = ROOT / "docs" / "defense-pages.json"
OUT_DIR = ROOT / "reports" / "s49-rehearsal"

# The one-line talking point per slide lives in the runbook; the tool only needs
# a short reminder, so it reuses the page title plus the claim's own wording.
MODES = {"live": "现场跑", "recorded": "只展示", "talk": "口播"}


def _stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _parse_pages(spec: str, total: int) -> list[int]:
    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            pages.extend(range(int(start), int(end) + 1))
        else:
            pages.append(int(part))
    bad = [p for p in pages if p < 1 or p > total]
    if bad:
        raise SystemExit(f"rehearse_defense: page out of range {bad} (1..{total})")
    return list(dict.fromkeys(pages))


def build_plan(pages_doc: dict, claims_doc: dict, page_spec: str | None,
               random_n: int | None, seed: int | None) -> list[dict]:
    by_id = {claim["id"]: claim for claim in claims_doc["claims"]}
    pages = pages_doc["pages"]
    plan: list[dict] = []
    if random_n:
        rng = random.Random(seed)
        picked = rng.sample(sorted(by_id), min(random_n, len(by_id)))
        for cid in picked:
            claim = by_id[cid]
            owner = next((p for p in pages if cid in p["claims"]), None)
            plan.append({
                "page": owner["page"] if owner else None,
                "page_title": owner["title"] if owner else "(随机抽问)",
                "mode": "random",
                "claim": claim,
            })
        return plan
    wanted = _parse_pages(page_spec, len(pages)) if page_spec else [p["page"] for p in pages]
    for page in pages:
        if page["page"] not in wanted:
            continue
        for cid in page["claims"]:
            plan.append({
                "page": page["page"],
                "page_title": page["title"],
                "mode": page["mode"],
                "claim": by_id[cid],
            })
    return plan


def render_markdown(doc: dict) -> str:
    lines = [
        "# S49 答辩彩排记录（本地彩排，不是教师验收）",
        "",
        f"> 生成：{doc['generated_at_utc']}｜模式：{doc['mode']}｜计划 {doc['planned']} 条，"
        f"PASS {doc['passed']}，FAIL {doc['failed']}，TIMEOUT {doc['timeouts']}，"
        f"SKIPPED {doc['skipped']}。",
        "",
        "| 页 | 幻灯片 | 断言 | 结果 | 退出码 | 用时 (s) | 证据 |",
        "|---:|---|---|---|---:|---:|---|",
    ]
    for row in doc["rows"]:
        page = row["page"] if row["page"] is not None else "—"
        lines.append(
            f"| {page} | {row['page_title']} | `{row['claim_id']}` | {row['status']} | "
            f"{row['exit_code'] if row['exit_code'] is not None else '—'} | "
            f"{row['seconds']:.1f} | `{row['evidence_path']}` |"
        )
    lines += [
        "",
        "## 口径",
        "",
        "- 超时记 `TIMEOUT`，命令失败记 `FAIL`，未提交记 `UNRUN`；没有“基本通过”。",
        "- `--dry-run` 只打印计划；`--offline` 不执行命令，只用已提交证据。",
        "- heavy 断言（400 黑盒、全量 unittest、46×10）默认 60 秒会超时，这是时间盒的真实结果；"
        "现场应改为只展示已记录证据，或用 `--allow-heavy` 单独排练。",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", default=None, help="e.g. 1-21 or 1,6,18")
    parser.add_argument("--random", type=int, default=None, help="sample N claims")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--timeout", type=int, default=60, help="per-claim seconds")
    parser.add_argument("--allow-heavy", action="store_true",
                        help="give heavy claims 1800 s instead of --timeout")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    pages_doc = json.loads(PAGES.read_text(encoding="utf-8"))
    claims_doc = json.loads(CLAIMS.read_text(encoding="utf-8"))
    plan = build_plan(pages_doc, claims_doc, args.pages, args.random, args.seed)

    started = time.perf_counter()
    rows: list[dict] = []
    for step in plan:
        claim = step["claim"]
        budget = 1800 if (args.allow_heavy and claim.get("heavy")) else args.timeout
        row = {
            "page": step["page"],
            "page_title": step["page_title"],
            "mode": step["mode"],
            "claim_id": claim["id"],
            "claim": claim["claim"],
            "heavy": bool(claim.get("heavy")),
            "timeout_s": budget,
            "evidence_path": claim["evidence_path"],
        }
        if args.dry_run:
            row.update(status="PLANNED", exit_code=None, seconds=0.0, timed_out=False,
                       started_at_utc=None, finished_at_utc=None)
        elif args.offline:
            row.update(status="SKIPPED_OFFLINE", exit_code=None, seconds=0.0, timed_out=False,
                       started_at_utc=_utc(), finished_at_utc=_utc())
        else:
            row["started_at_utc"] = _utc()
            result = run_defense_probe.run_claim(claim, timeout=budget)
            row["finished_at_utc"] = _utc()
            row.update(
                status="TIMEOUT" if result.get("timed_out") else result["status"],
                exit_code=result.get("exit_code"),
                seconds=result.get("seconds", 0.0),
                timed_out=bool(result.get("timed_out")),
                stdout_head=result.get("stdout_head"),
                stderr_head=result.get("stderr_head"),
            )
        rows.append(row)
        flag = row["status"]
        print(f"P{row['page'] if row['page'] is not None else '?'} {claim['id']:16s} {flag:16s} {row['seconds']:.1f}s")

    passed = sum(1 for row in rows if row["status"] == "PASS")
    failed = sum(1 for row in rows if row["status"] == "FAIL")
    timeouts = sum(1 for row in rows if row["status"] == "TIMEOUT")
    skipped = sum(1 for row in rows if row["status"] == "SKIPPED_OFFLINE")
    doc = {
        "schema_version": 1,
        "tool": "tools/rehearse_defense.py",
        "what": "local rehearsal of the 21-slide defense; NOT the teacher's acceptance",
        "generated_at_utc": _utc(),
        "mode": "dry-run" if args.dry_run else ("offline" if args.offline else "live"),
        "pages_spec": args.pages or "1-21",
        "random": args.random,
        "seed": args.seed,
        "timeout_s": args.timeout,
        "allow_heavy": args.allow_heavy,
        "planned": len(rows),
        "passed": passed,
        "failed": failed,
        "timeouts": timeouts,
        "skipped": skipped,
        "elapsed_s": round(time.perf_counter() - started, 2),
        "rows": rows,
    }

    mode_name = "dry-run" if args.dry_run else ("offline" if args.offline else "live")
    out = Path(args.out) if args.out else OUT_DIR / f"rehearsal-{_stamp()}-{mode_name}.json"
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    out.with_suffix(".md").write_text(render_markdown(doc), encoding="utf-8", newline="\n")
    try:
        shown = out.relative_to(ROOT)
    except ValueError:  # --out outside the repo (tests use a temp dir)
        shown = out
    print(f"rehearse_defense: {doc['mode']} planned={doc['planned']} PASS={passed} "
          f"FAIL={failed} TIMEOUT={timeouts} SKIPPED={skipped} -> {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
