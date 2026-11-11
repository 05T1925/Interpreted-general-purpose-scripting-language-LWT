"""Run a small, explicit semantic-mutant audit in disposable project copies.

Each probe first runs its selected existing black-box case on a correct copy,
then applies one unique runtime source patch in a separate temporary copy and
runs the same case through the copied project runner and public LWT CLI.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_RELATIVE = Path("lwt") / "runtime.py"
RUNNER_RELATIVE = Path("tools") / "run_tests.py"
TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class Probe:
    name: str
    target_ids: tuple[str, ...]
    patch_note: str
    old: str
    new: str
    area: str = "core"
    note: str = ""
    target_file: str = "lwt/runtime.py"


PROBES = (
    Probe(
        "division-truncates-toward-zero",
        ("negative-floor-division-modulo",),
        "Replace floor division with truncation toward zero.",
        "if operator is TokenKind.SLASH:\n            return left // right",
        "if operator is TokenKind.SLASH:\n"
        "            return (abs(left) // abs(right)) * (1 if (left < 0) == (right < 0) else -1)",
    ),
    Probe(
        "modulo-loses-divisor-sign",
        ("negative-floor-division-modulo",),
        "Return a nonnegative magnitude remainder for every divisor sign.",
        "return left % right",
        "return abs(left) % abs(right)",
    ),
    Probe(
        "and-evaluates-skipped-right-side",
        ("short-circuit-and",),
        "Remove the false-left early return for and.",
        "if not left:\n                if runtime.observer is not None:",
        "if False and not left:\n                if runtime.observer is not None:",
    ),
    Probe(
        "or-evaluates-skipped-right-side",
        ("short-circuit-or",),
        "Remove the true-left early return for or.",
        "if left:\n                if runtime.observer is not None:",
        "if False and left:\n                if runtime.observer is not None:",
    ),
    Probe(
        "composite-values-use-structural-equality",
        ("arrays-identity-equality", "record-instance-identity"),
        "Use list value equality and record type/field equality instead of object identity.",
        "        elif type(left) is list or isinstance(left, (_RecordValue, _ErrorValue, _DictValue, _TaskValue, _ChannelValue)):\n"
        "            # Never invoke Python's recursive container/record/dict equality.\n"
        "            equal = left is right",
        "        elif type(left) is list:\n"
        "            # Probe mutation: lists use structural equality.\n"
        "            equal = left == right\n"
        "        elif isinstance(left, _RecordValue):\n"
        "            # Probe mutation: records use structural equality.\n"
        "            equal = left.type_name == right.type_name and left.fields == right.fields\n"
        "        elif isinstance(left, (_ErrorValue, _DictValue, _TaskValue, _ChannelValue)):\n"
        "            equal = left is right",
        note="S53 re-anchored: S42 added _DictValue/_TaskValue/_ChannelValue to the "
             "isinstance tuple, so the S23 anchor no longer matched (it had become invalid).",
    ),
    Probe(
        "each-iterates-live-array",
        ("each-snapshot-replacement",),
        "Iterate the mutable source array directly instead of an entry snapshot.",
        "snapshot = list(iterable)",
        "snapshot = iterable",
    ),
    Probe(
        "call-arguments-reversed",
        ("argument-evaluation-order", "argument-evaluation-order-distinct-effects"),
        "Evaluate user-call arguments in reversed source order.",
        "# Both user and built-in calls evaluate all arguments left-to-right\n"
        "        # before checking arity, once the callee has been found.\n"
        "        arguments = [\n"
        "            _evaluate(argument, environment, runtime)\n"
        "            for argument in expression.arguments\n"
        "        ]",
        "# Both user and built-in calls evaluate all arguments left-to-right\n"
        "        # before checking arity, once the callee has been found.\n"
        "        arguments = [\n"
        "            _evaluate(argument, environment, runtime)\n"
        "            for argument in reversed(expression.arguments)\n"
        "        ]",
        note="S23 listed this patch twice, once per target case. The symmetric-effects "
             "case alone stayed green for eight phases - the weak-case trap chapter 5.5 "
             "warns about; the distinct-effects case kills the patch. They are merged into "
             "one probe with both targets so the report shows which case discriminates.",
    ),
    Probe(
        "and-accepts-host-truthiness",
        ("boolean-left-is-strict",),
        "Skip the strict boolean type check for the left and operand.",
        "if expression.operator is TokenKind.AND:\n"
        "            if type(left) is not bool:\n"
        "                _runtime_error(\"'and' requires boolean operands\", expression.operator_location)",
        "if expression.operator is TokenKind.AND:",
    ),
    Probe(
        "len-counts-utf8-bytes",
        ("len-unicode-codepoints",),
        "Count UTF-8 bytes rather than Unicode code points for strings.",
        "if type(value) is str or type(value) is list:\n"
        "            return len(value)",
        "if type(value) is str:\n"
        "            return len(value.encode(\"utf-8\"))\n"
        "        if type(value) is list:\n"
        "            return len(value)",
    ),
    # -- S53: semantics added by S42 (dict / throw / finally) -----------------
    Probe(
        "dict-display-sorts-keys",
        ("dict-display-insertion-order",),
        "Sort dict entries by key text instead of preserving insertion order.",
        "for key, item in value.entries.items()",
        "for key, item in sorted(value.entries.items(), key=lambda pair: str(pair[0]))",
        area="dict",
        note="S53 recorded this mutation as a genuine blind spot: every display case "
             "inserted keys in lexical order, so sorting was unobservable. S54 adds "
             "dict-display-insertion-order (b, a, c) and this probe is now killed.",
    ),
    Probe(
        "dict-display-reverses-insertion-order",
        ("dict-literal-display-order", "dict-nested-display", "dict-put-update-keeps-position"),
        "Format dict entries in reverse insertion order.",
        "for key, item in value.entries.items()",
        "for key, item in reversed(list(value.entries.items()))",
        area="dict",
        note="Sorted-by-key display was tried first and survived: every existing display case "
             "happens to insert keys in lexical order, so the suite cannot see sorting. That "
             "is a real blind spot in the display cases; the reverse-order mutation is "
             "observable on the same cases, so it is kept and the blind spot is recorded here.",
    ),
    Probe(
        "dict-get-missing-returns-null",
        ("dict-missing-key-read",),
        "Return null for an absent key instead of raising a runtime error.",
        "    if key not in target.entries:\n"
        "        _runtime_error(\n"
        "            f\"dict has no key {_format_value(index, set(), nested=True)}\", location\n"
        "        )\n"
        "    return target.entries[key]",
        "    if key not in target.entries:\n"
        "        return None\n"
        "    return target.entries[key]",
        area="dict",
    ),
    Probe(
        "dict-delete-missing-reports-true",
        ("dict-delete-missing",),
        "Report success when deleting a key that is not present.",
        "        if key not in target.entries:\n"
        "            return False\n"
        "        del target.entries[key]\n"
        "        return True",
        "        if key not in target.entries:\n"
        "            return True\n"
        "        del target.entries[key]\n"
        "        return True",
        area="dict",
    ),
    Probe(
        "finally-runs-only-on-unrecovered-error",
        ("finally-on-normal-flow", "finally-return-in-body-runs-first", "finally-break-passes"),
        "Run the finally body only when the attempt ended in an unrecovered error.",
        "            if statement.finally_body is not None:\n"
        "                # `problem` is bound only in the recover handler scope; a\n"
        "                # finally body runs in a fresh child of the enclosing scope and\n"
        "                # therefore cannot see it. It runs at most once per attempt.\n"
        "                _execute_statement(\n"
        "                    statement.finally_body, Environment(environment), runtime\n"
        "                )",
        "            if statement.finally_body is not None and attempt_outcome == \"error\":\n"
        "                # Probe mutation: finally only runs for an unrecovered error.\n"
        "                _execute_statement(\n"
        "                    statement.finally_body, Environment(environment), runtime\n"
        "                )",
        area="finally",
        note="§10.6 requires finally to run on normal, return, break, continue and "
             "recovered paths, at most once per attempt.",
    ),
    Probe(
        "throw-rethrow-loses-category",
        ("throw-error-rethrow", "uncaught-throw-error-category"),
        "Re-throw every Error value as category User instead of preserving its category.",
        "error = LwtError(\n"
        "                value.category,",
        "error = LwtError(\n"
        "                \"User\",",
        area="throw",
    ),
    # -- S53: semantics added by S43 (deterministic concurrency §11) ----------
    Probe(
        "channel-receive-is-lifo",
        ("channel-fifo",),
        "Pop the newest queued channel value instead of the oldest.",
        "return False, self.items.popleft()",
        "return False, self.items.pop()",
        area="concurrency",
        target_file="lwt/concurrency.py",
        note="§11.5 fixes channel order as FIFO; the 46-case concurrency suite is the "
             "only black-box evidence for it, so this probe is its first mutation check.",
    ),
    Probe(
        "send-skips-blocked-receiver",
        ("channel-block-receive", "channel-multi-producer"),
        "Queue a sent value instead of handing it to a receiver that is already blocked.",
        "            receiver = channel.waiting.popleft()\n"
        "            state = self.tasks[receiver]\n"
        "            state.injected = value",
        "            receiver = channel.waiting.popleft()\n"
        "            state = self.tasks[receiver]\n"
        "            channel.items.append(value)",
        area="concurrency",
        target_file="lwt/concurrency.py",
        note="This is the S45 defect shape: send appears to succeed but the blocked "
             "receiver never receives the value.",
    ),
    Probe(
        "scheduler-picks-last-ready",
        ("fifo-order", "yield-three-tasks"),
        "Pick the most recently queued ready task instead of the queue head (FIFO -> LIFO).",
        "chosen = self._queue[0]",
        "chosen = self._queue[-1]",
        area="concurrency",
        target_file="lwt/concurrency.py",
        note="§11.4 fixes the ready queue as FIFO; the choice must stay pure so a "
             "recorded schedule still replays.",
    ),
    Probe(
        "join-returns-before-completion",
        ("spawn-join-return", "join-preserves-output"),
        "Let join return immediately instead of blocking until the target is done.",
        "                if state.status == \"done\":\n"
        "                    state.joined = True",
        "                if True:\n"
        "                    state.joined = True",
        area="concurrency",
        target_file="lwt/runtime.py",
        note="join lives in runtime.py's built-in dispatch, not in concurrency.py.",
    ),
)


def _load_runner(root: Path) -> ModuleType:
    runner_path = root / RUNNER_RELATIVE
    module_name = f"_s23_runner_{hashlib.sha1(str(root).encode('utf-8')).hexdigest()[:12]}"
    spec = importlib.util.spec_from_file_location(module_name, runner_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load temporary project runner: {runner_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    return module


def _copy_minimal_project(destination: Path, case_sources: dict[str, Path]) -> None:
    destination.mkdir(parents=True)
    shutil.copytree(
        REPO_ROOT / "lwt",
        destination / "lwt",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    runner_target = destination / RUNNER_RELATIVE
    runner_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / RUNNER_RELATIVE, runner_target)
    for case_id, source in case_sources.items():
        relative_source = source.relative_to(REPO_ROOT / "tests" / "cases")
        source_target = destination / "tests" / "cases" / relative_source
        source_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, source_target)
        metadata_target = source_target.with_suffix(".json")
        shutil.copy2(source.with_suffix(".json"), metadata_target)


def _verify_runtime_import(root: Path) -> tuple[bool, str]:
    command = [
        sys.executable,
        "-c",
        "import lwt.runtime; print(lwt.runtime.__file__)",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=TIMEOUT_SECONDS,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, f"import-path verification failed: {error}"
    if completed.returncode != 0:
        return False, f"import-path verification exited {completed.returncode}: {completed.stderr!r}"
    try:
        imported_path = Path(completed.stdout.decode("utf-8").strip()).resolve()
        expected_root = (root / "lwt").resolve()
        imported_path.relative_to(expected_root)
    except (UnicodeError, ValueError, OSError):
        return False, f"runtime import escaped temporary copy: {completed.stdout!r}"
    return True, str(imported_path)


def _run_cases(root: Path, case_ids: tuple[str, ...]) -> tuple[bool, list[object], str]:
    runner = _load_runner(root)
    cases = runner.discover_cases(root / "tests" / "cases")
    selected = [case for case in cases if case.case_id in set(case_ids)]
    found = {case.case_id for case in selected}
    if found != set(case_ids):
        return False, [], f"target case inventory mismatch: expected={case_ids!r}, found={sorted(found)!r}"
    results = [runner.run_case(case) for case in selected]
    return True, results, ""


def _patch_runtime(root: Path, probe: Probe) -> tuple[bool, str]:
    target_path = root / probe.target_file
    original = target_path.read_text(encoding="utf-8")
    matches = original.count(probe.old)
    if matches != 1:
        return False, f"patch target must occur once; found {matches} in {probe.target_file}"
    mutated = original.replace(probe.old, probe.new, 1)
    if mutated == original or probe.new not in mutated:
        return False, "patch did not change the target source"
    target_path.write_text(mutated, encoding="utf-8", newline="")
    return True, hashlib.sha256(mutated.encode("utf-8")).hexdigest()


def _result_summary(results: list[object]) -> str:
    return "; ".join(
        f"{result.case.case_id}: exit={result.actual_exit_code!r} "
        f"stdout={result.actual_stdout!r} stderr={result.actual_stderr!r}"
        for result in results
    )


def audit_probe(probe: Probe) -> dict[str, object]:
    """Run one probe in disposable copies and return its full record."""

    record: dict[str, object] = {
        "name": probe.name,
        "area": probe.area,
        "targets": list(probe.target_ids),
        "mutation": probe.patch_note,
        "status": "invalid",
        "killed_by": [],
        "passed_targets": [],
        "evidence": "",
        "note": probe.note,
    }
    original_runner = _load_runner(REPO_ROOT)
    inventory = original_runner.discover_cases()
    case_sources = {
        case.case_id: case.source
        for case in inventory
        if case.case_id in set(probe.target_ids)
    }
    if set(case_sources) != set(probe.target_ids):
        record["evidence"] = "no patch applied: target case IDs absent from the inventory"
        return record

    with tempfile.TemporaryDirectory(prefix="lwt-s23-mutant-audit-") as temporary:
        temporary_root = Path(temporary)
        baseline_root = temporary_root / "baseline-project"
        mutant_root = temporary_root / "mutant-project"
        _copy_minimal_project(baseline_root, case_sources)
        _copy_minimal_project(mutant_root, case_sources)

        baseline_import_ok, baseline_import = _verify_runtime_import(baseline_root)
        mutant_import_ok, mutant_import = _verify_runtime_import(mutant_root)
        if not baseline_import_ok or not mutant_import_ok:
            record["evidence"] = (
                f"no patch applied: temporary import verification failed: "
                f"baseline={baseline_import}; mutant={mutant_import}"
            )
            return record

        baseline_inventory_ok, baseline_results, baseline_error = _run_cases(
            baseline_root, probe.target_ids
        )
        if not baseline_inventory_ok:
            record["evidence"] = f"no patch applied: {baseline_error}"
            return record
        baseline_failures = [result for result in baseline_results if result.failures]
        if baseline_failures:
            record["evidence"] = (
                "no patch applied: correct-copy target failed: " + _result_summary(baseline_failures)
            )
            return record

        patch_ok, patch_evidence = _patch_runtime(mutant_root, probe)
        if not patch_ok:
            record["evidence"] = f"no patch applied: {patch_evidence}"
            return record

        mutant_inventory_ok, mutant_results, mutant_error = _run_cases(
            mutant_root, probe.target_ids
        )
        if not mutant_inventory_ok:
            record["evidence"] = f"patch_sha256={patch_evidence}; {mutant_error}"
            return record

        failed_results = [result for result in mutant_results if result.failures]
        record["killed_by"] = [result.case.case_id for result in failed_results]
        record["passed_targets"] = [
            result.case.case_id for result in mutant_results if not result.failures
        ]
        if not failed_results:
            record["status"] = "survived"
            record["evidence"] = (
                f"patch_sha256={patch_evidence}; runtime_import={mutant_import}; "
                f"mutant_results={_result_summary(mutant_results)}"
            )
            return record

        if any(
            b"Traceback (most recent call last)" in result.actual_stderr
            or b"ModuleNotFoundError" in result.actual_stderr
            for result in failed_results
        ):
            record["evidence"] = (
                f"patch_sha256={patch_evidence}; mutant produced an unrelated host/import "
                f"failure; results={_result_summary(failed_results)}"
            )
            return record

        record["status"] = "killed"
        record["evidence"] = (
            f"correct baseline passed; patch_sha256={patch_evidence}; "
            f"runtime_import={mutant_import}; mutant_results={_result_summary(failed_results)}"
        )
        return record


INVARIANTS = {
    "objective": (
        "每处最小语义变异都必须被至少一个既有黑盒用例判红；用来量化 400 项黑盒的判别力，"
        "而不是证明解释器正确。"
    ),
    "baseline": (
        "S23 的 10 条探针（9 killed / 1 survived / 0 invalid 的历史快照）；S53 复跑时发现 "
        "1 条补丁锚点因 S42 改动失效（invalid），另 1 条 survived 与另一条探针同补丁。"
    ),
    "stop_rule": (
        "任何探针出现 invalid、或补丁锚点不再唯一匹配、或工作树被改动，立即停止并修正；"
        "不为了 killed 数量伪造用例。"
    ),
}


def _git_clean() -> bool:
    completed = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    return completed.returncode == 0 and not completed.stdout.strip()


def render_markdown(doc: dict[str, object]) -> str:
    probes = doc["probes"]
    lines = [
        "# S53 语义变异探针报告",
        "",
        "> 本报告只说明**这些探针**能否被既有黑盒用例判红。有限探针的 killed 比例"
        "**不是总体正确率**，也不是质量保证；等价变异与测试缺口需要人工判断"
        "（S23 计划的口径，见 `docs/s23-test-adequacy-plan.md`）。",
        "",
        "## 1. 目标、基线与停手判据",
        "",
        f"- **目标**：{doc['invariants']['objective']}",
        f"- **基线**：{doc['invariants']['baseline']}",
        f"- **停手**：{doc['invariants']['stop_rule']}",
        "",
        "## 2. 隔离与还原核验",
        "",
        f"- 每个探针只修改 `TemporaryDirectory` 中的项目副本，主工作树从不写入；"
        f"运行前 `git status --porcelain` 为空：**{doc['repo_clean_before']}**；"
        f"运行后仍为空：**{doc['repo_clean_after']}**。",
        "- 补丁只有在源码片段**唯一匹配**时才应用（`patch target must occur once`）；"
        "基线副本先跑同一用例确认原本是绿的，否则记为 invalid 而不是 killed。",
        "",
        "## 3. 探针结果",
        "",
        "| 区域 | 探针 | 状态 | 判红用例 | 未判红的目标用例 |",
        "|---|---|---|---|---|",
    ]
    for probe in probes:
        killed = ", ".join(f"`{case}`" for case in probe["killed_by"]) or "—"
        passed = ", ".join(f"`{case}`" for case in probe["passed_targets"]) or "—"
        lines.append(
            f"| {probe['area']} | {probe['name']} | **{probe['status']}** | {killed} | {passed} |"
        )
    totals = doc["totals"]
    lines += [
        "",
        f"合计：**{totals['total']}** 条探针，killed **{totals['killed']}**、"
        f"survived **{totals['survived']}**、equivalent **{totals['equivalent']}**、"
        f"invalid **{totals['invalid']}**。",
        "",
        "## 4. 覆盖到的新语义",
        "",
        "| 区域 | 语义点 | 为什么此前没有验证 |",
        "|---|---|---|",
        "| dict | 插入序 / 缺键 / delete 返回值 | S42 引入 `dict`，S23 的探针集早于它 |",
        "| finally | finally 在正常、return、break 路径上的执行 | S42 引入 `finally`（§10.6） |",
        "| throw | 重抛保留 category | S42 引入 `throw` |",
        "| concurrency | 通道 FIFO、send 交接、就绪队列 FIFO、join 阻塞 | S43 引入 §11；46 项并发用例从未被变异验证 |",
        "",
        "## 5. 边界（必须与数字一起读）",
        "",
        "- 探针是**人工挑选的有限语义点**，不是对 `lwt/` 的穷举变异；killed 比例不能外推为"
        "“解释器正确率”，也不能当作“测试充分”的证明（Just et al., ICSE/FSE 2018 指出"
        "变异测试受等价变异与测试集规模影响）。",
        "- 等价变异不存在于本报告：每条 survived 都必须写出书面理由；S53 的处理是把"
        "同补丁的重复探针合并，并在 `passed_targets` 里保留“这条用例单独不判别”的证据。",
        "- 探针只跑**目标用例**，不跑全量 400；因此它回答“是否至少有一条用例能判红”，"
        "不回答“有多少条能判红”。",
        "",
        "## 6. 复现",
        "",
        "```bash",
        "python tools/audit_semantic_mutants.py --out-dir reports/s53-mutation",
        "```",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    import argparse
    import datetime
    import json

    parser = argparse.ArgumentParser(description="Run the semantic-mutant audit.")
    parser.add_argument("--out-dir", default="reports/s53-mutation",
                        help="directory for mutation-report.json/.md")
    args = parser.parse_args(argv)

    clean_before = _git_clean()
    totals = {status: 0 for status in ("killed", "survived", "equivalent", "invalid")}
    records = []
    for probe in PROBES:
        record = audit_probe(probe)
        records.append(record)
        totals[str(record["status"])] += 1
        print(f"[{str(record['status']).upper()}] {record['name']}")
        print(f"  targets={','.join(record['targets'])}")
        print(f"  mutation={record['mutation']}")
        print(f"  killed_by={','.join(record['killed_by']) or '-'}")
        print(f"  evidence={record['evidence']}")
    clean_after = _git_clean()

    doc = {
        "schema_version": 1,
        "tool": "tools/audit_semantic_mutants.py",
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "invariants": INVARIANTS,
        "isolation": "TemporaryDirectory copies only; the working tree is never patched",
        "repo_clean_before": clean_before,
        "repo_clean_after": clean_after,
        "totals": {**totals, "total": len(records)},
        "probes": records,
    }
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "mutation-report.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (out_dir / "mutation-report.md").write_text(
        render_markdown(doc), encoding="utf-8", newline="\n")

    print(
        "probe-summary: "
        + " ".join(f"{status}={totals[status]}" for status in totals)
        + f" total={len(records)}"
        + f" repo_clean={clean_before and clean_after}"
    )
    return 0 if totals["invalid"] == 0 and clean_before and clean_after else 1


if __name__ == "__main__":
    raise SystemExit(main())
