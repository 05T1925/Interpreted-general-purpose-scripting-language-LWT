"""Strict schema validation shared by LWT profile tools."""

from __future__ import annotations

import json
import math
from pathlib import PureWindowsPath
from typing import Any


class ProfileFormatError(ValueError):
    """A profile is malformed or inconsistent with schema version 1."""


def _object_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProfileFormatError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def load_profile_json(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text, object_pairs_hook=_object_no_duplicates)
    except ProfileFormatError:
        raise
    except (json.JSONDecodeError, UnicodeError) as error:
        raise ProfileFormatError(f"invalid profile JSON: {error}") from None
    if not isinstance(value, dict):
        raise ProfileFormatError("profile root must be an object")
    validate_profile(value)
    return value


def _keys(value: Any, required: set[str], optional: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProfileFormatError(f"{label} must be an object")
    missing = required - set(value)
    unknown = set(value) - required - optional
    if missing:
        raise ProfileFormatError(f"{label} is missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise ProfileFormatError(f"{label} has unknown fields: {', '.join(sorted(unknown))}")
    return value


def _string(value: Any, label: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        raise ProfileFormatError(f"{label} must be {'a non-empty' if nonempty else 'a'} string")
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        raise ProfileFormatError(f"{label} is not valid Unicode") from None
    return value


def _display_path(value: Any, label: str) -> str:
    path = _string(value, label)
    windows = PureWindowsPath(path)
    if "\\" in path or path.startswith("/") or windows.is_absolute() or windows.drive:
        raise ProfileFormatError(f"{label} must be a relative slash-normalized path")
    return path


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ProfileFormatError(f"{label} must be an integer >= {minimum}")
    return value


def _nullable_integer(value: Any, label: str, *, minimum: int = 1) -> int | None:
    if value is None:
        return None
    return _integer(value, label, minimum=minimum)


def _percentage(covered: int, total: int) -> float | None:
    return None if total == 0 else round(covered * 100.0 / total, 2)


def _validate_summary(value: Any, label: str) -> tuple[int, int]:
    item = _keys(value, {"covered", "total", "percentage"}, set(), label)
    covered = _integer(item["covered"], f"{label}.covered")
    total = _integer(item["total"], f"{label}.total")
    if covered > total:
        raise ProfileFormatError(f"{label}.covered exceeds total")
    percentage = item["percentage"]
    expected = _percentage(covered, total)
    if expected is None:
        if percentage is not None:
            raise ProfileFormatError(f"{label}.percentage must be null when total is zero")
    elif type(percentage) not in {int, float} or not math.isfinite(float(percentage)) or float(percentage) != expected:
        raise ProfileFormatError(f"{label}.percentage is inconsistent")
    return covered, total


EVENT_FIELDS: dict[str, set[str]] = {
    "program_start": set(),
    "statement": {"node_id", "kind"},
    "function_call": {
        "function_id", "module", "function_name", "qualified_name",
        "declaration_line", "declaration_column", "call_source", "call_line", "call_column",
    },
    "function_return": {
        "function_id", "module", "function_name", "qualified_name", "return_kind",
    },
    "decision": {"node_id", "kind", "outcome"},
    "recover": {"error_category", "error_source", "error_line", "error_column"},
    "runtime_error": {"category", "message", "message_redacted"},
    "program_end": {"status", "exit_code"},
}
EVENT_BASE = {"sequence", "event", "source", "line", "column", "depth"}


def _validate_events(events: Any, label: str, module_sources: set[str]) -> list[dict[str, Any]]:
    if not isinstance(events, list):
        raise ProfileFormatError(f"{label} must be an array")
    output: list[dict[str, Any]] = []
    for index, event_value in enumerate(events, 1):
        event = _keys(event_value, EVENT_BASE, set().union(*EVENT_FIELDS.values()), f"{label}[{index - 1}]")
        kind = _string(event["event"], f"{label}[{index - 1}].event")
        if kind not in EVENT_FIELDS:
            raise ProfileFormatError(f"{label}[{index - 1}] has unknown event {kind!r}")
        expected = EVENT_BASE | EVENT_FIELDS[kind]
        if set(event) != expected:
            raise ProfileFormatError(f"{label}[{index - 1}] fields do not match event {kind!r}")
        sequence = _integer(event["sequence"], f"{label}[{index - 1}].sequence", minimum=1)
        if sequence != index:
            raise ProfileFormatError(f"{label} sequence must be continuous from 1")
        source = _string(event["source"], f"{label}[{index - 1}].source")
        if source not in module_sources:
            raise ProfileFormatError(f"{label}[{index - 1}].source is not a module")
        _nullable_integer(event["line"], f"{label}[{index - 1}].line")
        _nullable_integer(event["column"], f"{label}[{index - 1}].column")
        _integer(event["depth"], f"{label}[{index - 1}].depth")
        for key in ("node_id", "function_id"):
            if key in event:
                _string(event[key], f"{label}[{index - 1}].{key}")
        if kind == "statement":
            _string(event["kind"], f"{label}[{index - 1}].kind")
        elif kind == "decision":
            _string(event["kind"], f"{label}[{index - 1}].kind")
            _string(event["outcome"], f"{label}[{index - 1}].outcome")
        elif kind == "function_call":
            for key in ("module", "function_name", "qualified_name", "call_source"):
                _string(event[key], f"{label}[{index - 1}].{key}")
            if event["module"] not in module_sources or event["call_source"] not in module_sources:
                raise ProfileFormatError(f"{label}[{index - 1}] names an unknown module")
            for key in ("declaration_line", "declaration_column", "call_line", "call_column"):
                _integer(event[key], f"{label}[{index - 1}].{key}", minimum=1)
        elif kind == "function_return":
            for key in ("module", "function_name", "qualified_name"):
                _string(event[key], f"{label}[{index - 1}].{key}")
            if event["module"] not in module_sources:
                raise ProfileFormatError(f"{label}[{index - 1}].module is not a module")
            if event["return_kind"] not in {"explicit", "natural"}:
                raise ProfileFormatError(f"{label}[{index - 1}].return_kind is invalid")
        elif kind == "recover":
            _string(event["error_category"], f"{label}[{index - 1}].error_category")
            error_source = event["error_source"]
            if error_source is not None and error_source not in module_sources:
                raise ProfileFormatError(f"{label}[{index - 1}].error_source is not a module")
            _nullable_integer(event["error_line"], f"{label}[{index - 1}].error_line")
            _nullable_integer(event["error_column"], f"{label}[{index - 1}].error_column")
        elif kind == "runtime_error":
            _string(event["category"], f"{label}[{index - 1}].category")
            _string(event["message"], f"{label}[{index - 1}].message", nonempty=False)
            if type(event["message_redacted"]) is not bool:
                raise ProfileFormatError(f"{label}[{index - 1}].message_redacted must be boolean")
        elif kind == "program_end":
            end_status = _string(event["status"], f"{label}[{index - 1}].status")
            if end_status not in {"success", "runtime_error", "error"}:
                raise ProfileFormatError(f"{label}[{index - 1}].status is invalid")
            _integer(event["exit_code"], f"{label}[{index - 1}].exit_code")
        output.append(event)
    return output


def _validate_profile_events(profile: dict[str, Any], module_sources: set[str]) -> list[list[dict[str, Any]]]:
    event_groups = [_validate_events(profile["events"], "events", module_sources)]
    if "runs" in profile:
        runs = profile["runs"]
        if not isinstance(runs, list) or not runs:
            raise ProfileFormatError("runs must be a non-empty array")
        event_groups = []
        for index, run_value in enumerate(runs, 1):
            run = _keys(run_value, {"run_index", "status", "exit_code", "event_count", "events"}, set(), f"runs[{index - 1}]")
            if _integer(run["run_index"], f"runs[{index - 1}].run_index", minimum=1) != index:
                raise ProfileFormatError("run_index values must be continuous from 1")
            run_status = _string(run["status"], f"runs[{index - 1}].status")
            if run_status not in {"success", "runtime_error", "error"}:
                raise ProfileFormatError(f"runs[{index - 1}].status is invalid")
            _integer(run["exit_code"], f"runs[{index - 1}].exit_code")
            run_events = _validate_events(run["events"], f"runs[{index - 1}].events", module_sources)
            if _integer(run["event_count"], f"runs[{index - 1}].event_count") != len(run_events):
                raise ProfileFormatError(f"runs[{index - 1}].event_count is inconsistent")
            if (
                not run_events
                or run_events[-1].get("event") != "program_end"
                or run_events[-1].get("status") != run["status"]
                or run_events[-1].get("exit_code") != run["exit_code"]
            ):
                raise ProfileFormatError(f"runs[{index - 1}] status disagrees with its program_end event")
            event_groups.append(run_events)
        if profile["events"]:
            raise ProfileFormatError("merged profiles keep independent events under runs, not top-level events")
    return event_groups


def validate_profile(profile: dict[str, Any]) -> None:
    profile = _keys(
        profile,
        {"schema_version", "tool", "entry", "status", "exit_code", "modules", "events", "coverage"},
        {"runs"},
        "profile",
    )
    if type(profile["schema_version"]) is not int or profile["schema_version"] != 1:
        raise ProfileFormatError("unsupported profile schema_version; expected 1")
    if profile["tool"] not in {"lwt-profile", "lwt-profile-merge"}:
        raise ProfileFormatError("profile.tool is invalid")
    _display_path(profile["entry"], "profile.entry")
    status = _string(profile["status"], "profile.status")
    if status not in {"success", "runtime_error", "error", "merged"}:
        raise ProfileFormatError("profile.status is invalid")
    exit_code = profile["exit_code"]
    if status == "merged":
        if exit_code is not None or "runs" not in profile:
            raise ProfileFormatError("merged profiles require runs and a null top-level exit_code")
    else:
        _integer(exit_code, "profile.exit_code")
        if "runs" in profile:
            raise ProfileFormatError("only merged profiles may contain runs")
        if status == "success" and exit_code != 0:
            raise ProfileFormatError("success profiles must have exit_code 0")
        if status == "runtime_error" and exit_code != 3:
            raise ProfileFormatError("runtime_error profiles must have exit_code 3")

    modules = profile["modules"]
    if not isinstance(modules, list) or not modules:
        raise ProfileFormatError("profile.modules must be a non-empty array")
    module_sources: set[str] = set()
    for index, module_value in enumerate(modules):
        module = _keys(module_value, {"source", "sha256", "entry", "function_count", "statement_count", "decision_count"}, set(), f"modules[{index}]")
        source = _display_path(module["source"], f"modules[{index}].source")
        if source in module_sources:
            raise ProfileFormatError(f"duplicate module source {source!r}")
        module_sources.add(source)
        digest = _string(module["sha256"], f"modules[{index}].sha256")
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ProfileFormatError(f"modules[{index}].sha256 must be a lowercase SHA-256 digest")
        if type(module["entry"]) is not bool:
            raise ProfileFormatError(f"modules[{index}].entry must be boolean")
        for key in ("function_count", "statement_count", "decision_count"):
            _integer(module[key], f"modules[{index}].{key}")
    if sum(bool(item["entry"]) for item in modules) != 1:
        raise ProfileFormatError("exactly one module must be the entry")
    if profile["entry"] not in module_sources:
        raise ProfileFormatError("profile.entry must match an entry module source")

    event_groups = _validate_profile_events(profile, module_sources)
    coverage = _keys(profile["coverage"], {"summary", "by_module", "statements", "functions", "decisions"}, set(), "coverage")
    summary = _keys(coverage["summary"], {"statements", "functions", "decisions"}, set(), "coverage.summary")
    summary_values = {key: _validate_summary(summary[key], f"coverage.summary.{key}") for key in summary}

    static_records: dict[str, dict[str, dict[str, Any]]] = {}
    all_node_ids: set[str] = set()
    for collection, required in (
        ("statements", {"id", "source", "line", "column", "kind", "hit_count", "covered"}),
        ("functions", {"id", "source", "line", "column", "name", "qualified_name", "call_count", "covered", "explicit_returns", "natural_returns"}),
        ("decisions", {"id", "source", "line", "column", "kind", "outcomes", "covered_outcomes", "total_outcomes", "percentage", "covered"}),
    ):
        values = coverage[collection]
        if not isinstance(values, list):
            raise ProfileFormatError(f"coverage.{collection} must be an array")
        index: dict[str, dict[str, Any]] = {}
        for row_number, row_value in enumerate(values):
            row = _keys(row_value, required, set(), f"coverage.{collection}[{row_number}]")
            identifier = _string(row["id"], f"coverage.{collection}[{row_number}].id")
            if identifier in index:
                raise ProfileFormatError(f"duplicate {collection} ID {identifier!r}")
            if identifier in all_node_ids:
                raise ProfileFormatError(f"duplicate node ID {identifier!r}")
            all_node_ids.add(identifier)
            source = _display_path(row["source"], f"coverage.{collection}[{row_number}].source")
            if source not in module_sources:
                raise ProfileFormatError(f"coverage.{collection}[{row_number}].source is not a module")
            _integer(row["line"], f"coverage.{collection}[{row_number}].line", minimum=1)
            _integer(row["column"], f"coverage.{collection}[{row_number}].column", minimum=1)
            if type(row["covered"]) is not bool:
                raise ProfileFormatError(f"coverage.{collection}[{row_number}].covered must be boolean")
            if collection == "statements":
                _string(row["kind"], f"coverage.{collection}[{row_number}].kind")
                hits = _integer(row["hit_count"], f"coverage.{collection}[{row_number}].hit_count")
                if row["covered"] != (hits > 0):
                    raise ProfileFormatError(f"coverage.{collection}[{row_number}].covered disagrees with hit_count")
            elif collection == "functions":
                _string(row["name"], f"coverage.{collection}[{row_number}].name")
                _string(row["qualified_name"], f"coverage.{collection}[{row_number}].qualified_name")
                calls = _integer(row["call_count"], f"coverage.{collection}[{row_number}].call_count")
                explicit = _integer(row["explicit_returns"], f"coverage.{collection}[{row_number}].explicit_returns")
                natural = _integer(row["natural_returns"], f"coverage.{collection}[{row_number}].natural_returns")
                if explicit + natural > calls or row["covered"] != (calls > 0):
                    raise ProfileFormatError(f"coverage.{collection}[{row_number}] counts are inconsistent")
            else:
                _string(row["kind"], f"coverage.{collection}[{row_number}].kind")
                outcomes = row["outcomes"]
                if not isinstance(outcomes, list) or not outcomes:
                    raise ProfileFormatError(f"coverage.{collection}[{row_number}].outcomes must be non-empty")
                outcome_names: set[str] = set()
                for outcome_value in outcomes:
                    outcome = _keys(outcome_value, {"name", "count", "covered"}, set(), "decision outcome")
                    name = _string(outcome["name"], "decision outcome.name")
                    if name in outcome_names:
                        raise ProfileFormatError("duplicate decision outcome")
                    outcome_names.add(name)
                    count = _integer(outcome["count"], "decision outcome.count")
                    if type(outcome["covered"]) is not bool or outcome["covered"] != (count > 0):
                        raise ProfileFormatError("decision outcome covered flag is inconsistent")
                covered_outcomes = sum(bool(outcome["covered"]) for outcome in outcomes)
                if row["covered_outcomes"] != covered_outcomes or row["total_outcomes"] != len(outcomes):
                    raise ProfileFormatError("decision outcome totals are inconsistent")
                percentage = row["percentage"]
                expected_percentage = round(covered_outcomes * 100.0 / len(outcomes), 2)
                if type(percentage) not in {int, float} or float(percentage) != expected_percentage:
                    raise ProfileFormatError("decision percentage is inconsistent")
                if row["covered"] != (covered_outcomes == len(outcomes)):
                    raise ProfileFormatError("decision covered flag is inconsistent")
            index[identifier] = row
        static_records[collection] = index

    expected_counts = {
        "functions": len(static_records["functions"]),
        "statements": len(static_records["statements"]),
        "decisions": len(static_records["decisions"]),
    }
    module_counts = {module["source"]: module for module in modules}
    for collection, key in (("functions", "function_count"), ("statements", "statement_count"), ("decisions", "decision_count")):
        actual_by_module = {source: sum(row["source"] == source for row in static_records[collection].values()) for source in module_sources}
        for source, module in module_counts.items():
            if actual_by_module[source] != module[key]:
                raise ProfileFormatError(f"module {source!r} {key} disagrees with coverage inventory")

    def recalc(collection: str, source: str | None = None) -> tuple[int, int]:
        rows = [row for row in static_records[collection].values() if source is None or row["source"] == source]
        if collection == "statements":
            return sum(bool(row["covered"]) for row in rows), len(rows)
        if collection == "functions":
            return sum(bool(row["covered"]) for row in rows), len(rows)
        return sum(int(row["covered_outcomes"]) for row in rows), sum(int(row["total_outcomes"]) for row in rows)

    for collection, pair in summary_values.items():
        if pair != recalc(collection):
            raise ProfileFormatError(f"coverage.summary.{collection} is inconsistent with node inventory")
    by_module = coverage["by_module"]
    if not isinstance(by_module, list) or len(by_module) != len(modules):
        raise ProfileFormatError("coverage.by_module must have one entry per module")
    seen_module_summary: set[str] = set()
    for module_summary_value in by_module:
        module_summary = _keys(module_summary_value, {"source", "statements", "functions", "decisions"}, set(), "coverage.by_module entry")
        source = _string(module_summary["source"], "coverage.by_module.source")
        if source not in module_sources or source in seen_module_summary:
            raise ProfileFormatError("coverage.by_module has an unknown or duplicate source")
        seen_module_summary.add(source)
        for collection in ("statements", "functions", "decisions"):
            if _validate_summary(module_summary[collection], f"coverage.by_module.{collection}") != recalc(collection, source):
                raise ProfileFormatError(f"coverage.by_module.{collection} is inconsistent")

    statement_event_counts: dict[str, int] = {}
    function_event_counts: dict[str, int] = {}
    function_return_counts: dict[tuple[str, str], int] = {}
    decision_event_counts: dict[tuple[str, str], int] = {}
    function_definitions = static_records["functions"]
    decision_definitions = static_records["decisions"]
    for events in event_groups:
        if events and (events[0]["event"] != "program_start" or events[-1]["event"] != "program_end"):
            raise ProfileFormatError("each event group must start with program_start and end with program_end")
        for event in events:
            if event["event"] == "statement":
                identifier = event["node_id"]
                definition = static_records["statements"].get(identifier)
                if definition is None or (definition["source"], definition["line"], definition["column"], definition["kind"]) != (event["source"], event["line"], event["column"], event["kind"]):
                    raise ProfileFormatError("statement event does not match its static node")
                statement_event_counts[identifier] = statement_event_counts.get(identifier, 0) + 1
            elif event["event"] == "function_call":
                identifier = event["function_id"]
                definition = function_definitions.get(identifier)
                if definition is None or (definition["source"], definition["line"], definition["column"], definition["name"]) != (event["module"], event["declaration_line"], event["declaration_column"], event["function_name"]):
                    raise ProfileFormatError("function_call event does not match its declaration")
                function_event_counts[identifier] = function_event_counts.get(identifier, 0) + 1
            elif event["event"] == "function_return":
                identifier = event["function_id"]
                definition = function_definitions.get(identifier)
                if definition is None or (definition["source"], definition["name"]) != (event["module"], event["function_name"]):
                    raise ProfileFormatError("function_return event does not match its declaration")
                key = (identifier, event["return_kind"])
                function_return_counts[key] = function_return_counts.get(key, 0) + 1
            elif event["event"] == "decision":
                identifier = event["node_id"]
                definition = decision_definitions.get(identifier)
                allowed = {item["name"] for item in definition["outcomes"]} if definition is not None else set()
                if definition is None or (definition["source"], definition["line"], definition["column"], definition["kind"]) != (event["source"], event["line"], event["column"], event["kind"]) or event["outcome"] not in allowed:
                    raise ProfileFormatError("decision event does not match its static node")
                key = (identifier, event["outcome"])
                decision_event_counts[key] = decision_event_counts.get(key, 0) + 1
        if events:
            end = events[-1]
            if "runs" not in profile and (end["status"] != status or end["exit_code"] != exit_code):
                raise ProfileFormatError("program_end event disagrees with profile status")
    for identifier, row in static_records["statements"].items():
        if row["hit_count"] != statement_event_counts.get(identifier, 0):
            raise ProfileFormatError(f"statement hit count does not match events for {identifier}")
    for identifier, row in static_records["functions"].items():
        if row["call_count"] != function_event_counts.get(identifier, 0):
            raise ProfileFormatError(f"function call count does not match events for {identifier}")
        if row["explicit_returns"] != function_return_counts.get((identifier, "explicit"), 0) or row["natural_returns"] != function_return_counts.get((identifier, "natural"), 0):
            raise ProfileFormatError(f"function return counts do not match events for {identifier}")
    for identifier, row in static_records["decisions"].items():
        for outcome in row["outcomes"]:
            if outcome["count"] != decision_event_counts.get((identifier, outcome["name"]), 0):
                raise ProfileFormatError(f"decision outcome count does not match events for {identifier}")

    if status == "merged" and profile["events"]:
        raise ProfileFormatError("merged top-level events must be empty")
    if status == "runtime_error" and not any(event["event"] == "runtime_error" for event in profile["events"]):
        raise ProfileFormatError("runtime_error profile must contain a runtime_error event")
    if status == "success" and any(event["event"] == "runtime_error" for event in profile["events"]):
        raise ProfileFormatError("success profile cannot contain an unhandled runtime_error event")
