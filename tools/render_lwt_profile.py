"""Render a validated LWT execution profile as a deterministic offline HTML file."""

from __future__ import annotations

import argparse
import hashlib
import html
import os
from pathlib import Path
import tempfile
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lwt.profile_schema import ProfileFormatError, load_profile_json


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _percent(summary: dict[str, Any]) -> str:
    value = summary["percentage"]
    return "n/a" if value is None else f"{value:.2f}%"


def _summary_cell(summary: dict[str, Any]) -> str:
    return f"{summary['covered']} / {summary['total']} ({_percent(summary)})"


def _event_groups(profile: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    if "runs" in profile:
        return [
            (f"Run {run['run_index']} · {run['status']} · exit {run['exit_code']}", run["events"])
            for run in profile["runs"]
        ]
    return [(f"Execution · {profile['status']} · exit {profile['exit_code']}", profile["events"])]


def render_html(profile: dict[str, Any]) -> str:
    """Build a self-contained HTML document; no source files or network are read."""

    status = profile["status"]
    status_label = {
        "success": "✓ SUCCESS",
        "runtime_error": "! RUNTIME ERROR",
        "error": "! ERROR",
        "merged": "∑ MERGED RUNS",
    }[status]
    coverage = profile["coverage"]
    summary = coverage["summary"]
    pieces = [
        "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">",
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">",
        f"<title>LWT 执行档案：{_escape(profile['entry'])}</title>",
        "<style>"
        "*{box-sizing:border-box}body{margin:0;background:#f3f6fa;color:#172338;font:16px/1.5 system-ui,'Microsoft YaHei',sans-serif}"
        "main{max-width:1180px;margin:0 auto;padding:24px}h1,h2{line-height:1.2}h1{font-size:2rem;margin:.2em 0}h2{font-size:1.35rem;margin:1.5em 0 .6em}"
        ".card{background:white;border:1px solid #cad4e0;border-radius:10px;padding:18px;margin:12px 0;box-shadow:0 1px 3px #17233812}"
        ".status{display:inline-block;padding:4px 10px;border-radius:5px;font-weight:700}.success{background:#d5f4e3;color:#064c2c}.runtime_error,.error{background:#ffe1dc;color:#7d2014}.merged{background:#e5e9ff;color:#2d3479}"
        "table{width:100%;border-collapse:collapse;background:white}th,td{text-align:left;border-bottom:1px solid #d9e1ea;padding:9px;vertical-align:top}th{background:#eaf0f6}"
        "code,pre{font-family:ui-monospace,Consolas,monospace}code{overflow-wrap:anywhere}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}"
        ".metric strong{font-size:1.4rem;display:block}.hit{color:#075b34;font-weight:700}.miss{color:#7b3e04;font-weight:700}.event{white-space:pre-wrap;overflow-wrap:anywhere}"
        "details{margin:8px 0}summary{cursor:pointer;font-weight:650} .note{border-left:5px solid #244f7d;background:#eaf2fb;padding:12px}"
        "@media print{body{background:white}main{max-width:none;padding:0}.card{box-shadow:none;break-inside:avoid}details>*{display:block}details:not([open])>*:not(summary){display:block}}"
        "@media(max-width:640px){main{padding:12px}h1{font-size:1.5rem}table{font-size:.88rem}}"
        "</style></head><body><main>",
        f"<h1>LWT 源码级执行追踪</h1><p><span class=\"status {_escape(status)}\">{status_label}</span> "
        f"<code>{_escape(profile['entry'])}</code> · schema v{profile['schema_version']} · "
        f"exit {_escape(profile['exit_code'])}</p>",
        "<div class=\"note\"><strong>覆盖率边界：</strong>覆盖率只说明这些固定场景中哪些 LWT 节点执行过，不能证明程序正确、规范完全覆盖或解释器没有缺陷。</div>",
        "<section class=\"grid\">",
    ]
    for kind, label in (("statements", "语句覆盖"), ("functions", "函数覆盖"), ("decisions", "Decision outcome 覆盖")):
        pieces.append(
            f"<div class=\"card metric\"><span>{label}</span><strong>{_escape(_summary_cell(summary[kind]))}</strong></div>"
        )
    pieces.append("</section><h2>模块与源码摘要</h2><div class=\"card\"><table><thead><tr><th>模块</th><th>入口</th><th>SHA-256</th><th>函数</th><th>语句</th><th>决策</th></tr></thead><tbody>")
    modules = {module["source"]: module for module in profile["modules"]}
    module_coverage = {item["source"]: item for item in coverage["by_module"]}
    for source, module in modules.items():
        row = module_coverage[source]
        pieces.append(
            "<tr>"
            f"<td><code>{_escape(source)}</code></td><td>{'入口' if module['entry'] else '库模块'}</td>"
            f"<td><code>{_escape(module['sha256'])}</code></td>"
            f"<td>{_escape(_summary_cell(row['functions']))}</td>"
            f"<td>{_escape(_summary_cell(row['statements']))}</td>"
            f"<td>{_escape(_summary_cell(row['decisions']))}</td></tr>"
        )
    pieces.append("</tbody></table></div><h2>按源码位置的命中</h2><div class=\"card\"><table><thead><tr><th>状态</th><th>源码位置</th><th>节点</th><th>次数 / 分支</th></tr></thead><tbody>")
    rows: list[tuple[str, int, int, str, str, str]] = []
    for statement in coverage["statements"]:
        status_text = "✓ hit" if statement["covered"] else "○ not hit"
        rows.append((statement["source"], statement["line"], statement["column"], statement["kind"], str(statement["hit_count"]), status_text))
    for function in coverage["functions"]:
        status_text = "✓ called" if function["covered"] else "○ not called"
        rows.append((function["source"], function["line"], function["column"], f"fn {function['qualified_name']}", str(function["call_count"]), status_text))
    for decision in coverage["decisions"]:
        outcomes = ", ".join(f"{outcome['name']}={outcome['count']}" for outcome in decision["outcomes"])
        status_text = "✓ all outcomes" if decision["covered"] else "○ partial"
        rows.append((decision["source"], decision["line"], decision["column"], f"decision {decision['kind']}", outcomes, status_text))
    for source, line, column, kind, count, status_text in sorted(rows):
        css = "hit" if status_text.startswith("✓") else "miss"
        pieces.append(
            f"<tr><td class=\"{css}\">{_escape(status_text)}</td><td><code>{_escape(source)}:{line}:{column}</code></td>"
            f"<td>{_escape(kind)}</td><td>{_escape(count)}</td></tr>"
        )
    pieces.append("</tbody></table></div><h2>函数调用、恢复与运行错误</h2>")
    for heading, events in _event_groups(profile):
        pieces.append(f"<div class=\"card\"><h3>{_escape(heading)}</h3><ol>")
        relevant = [event for event in events if event["event"] in {"function_call", "function_return", "recover", "runtime_error"}]
        if not relevant:
            pieces.append("<li>没有相关事件</li>")
        for event in relevant:
            label = event["event"]
            if label == "function_call":
                detail = f"call {event['qualified_name']} depth={event['depth']} from {event['call_source']}:{event['call_line']}:{event['call_column']}"
            elif label == "function_return":
                detail = f"return {event['qualified_name']} ({event['return_kind']}) depth={event['depth']}"
            elif label == "recover":
                detail = f"recover {event['error_category']} at {event['error_source']}:{event['error_line']}:{event['error_column']}"
            else:
                detail = f"{event['category']}: {event['message']}"
            pieces.append(f"<li><code>{_escape(event['source'])}:{event['line']}:{event['column']}</code> — {_escape(detail)}</li>")
        pieces.append("</ol></div>")
    pieces.append("<h2>完整事件</h2>")
    for heading, events in _event_groups(profile):
        pieces.append(f"<details><summary>{_escape(heading)} · {len(events)} events</summary><div class=\"card event\"><ol>")
        for event in events:
            base_fields = {"sequence", "event", "source", "line", "column", "depth"}
            extra = ", ".join(f"{key}={value}" for key, value in event.items() if key not in base_fields)
            pieces.append(f"<li><code>{_escape(event['sequence'])} {_escape(event['event'])} {_escape(event['source'])}:{_escape(event['line'])}:{_escape(event['column'])} depth={_escape(event['depth'])}</code> {_escape(extra)}</li>")
        pieces.append("</ol></div></details>")
    pieces.append("</main></body></html>\n")
    return "".join(pieces)


def verify_available_source_hashes(profile: dict[str, Any], profile_path: Path) -> None:
    """Reject hashes that disagree with available local files; never display source text."""

    roots = (Path.cwd(), profile_path.resolve().parent)
    entry_candidates = [root / profile["entry"] for root in roots]
    entry_path = next((candidate.resolve() for candidate in entry_candidates if candidate.is_file()), None)
    resolved: dict[str, Path] = {}
    if entry_path is not None:
        resolved[profile["entry"]] = entry_path
        for module in profile["modules"]:
            if module["entry"]:
                continue
            candidate = (entry_path.parent / module["source"]).resolve()
            if candidate.is_file():
                resolved[module["source"]] = candidate
    for module in profile["modules"]:
        path = resolved.get(module["source"])
        if path is None:
            continue
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            raise ProfileFormatError(f"cannot verify source hash for {module['source']!r}: {error}") from None
        if digest != module["sha256"]:
            raise ProfileFormatError(f"source hash mismatch for {module['source']!r}")


def _write_atomic(path: Path, text: str) -> None:
    path = path.resolve()
    if not path.parent.is_dir():
        raise OSError("output directory does not exist")
    temporary: str | None = None
    descriptor = -1
    try:
        descriptor, temporary = tempfile.mkstemp(prefix=".lwt-report-", suffix=".tmp", dir=path.parent)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            descriptor = -1
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args(argv)
    try:
        profile = load_profile_json(arguments.profile.read_text(encoding="utf-8"))
        verify_available_source_hashes(profile, arguments.profile)
        document = render_html(profile)
        _write_atomic(arguments.output, document)
    except (OSError, UnicodeError, ProfileFormatError, KeyError, TypeError, ValueError) as error:
        print(f"lwt-profile-render: {error}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
