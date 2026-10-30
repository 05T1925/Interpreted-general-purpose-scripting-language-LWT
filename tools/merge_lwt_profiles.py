"""Merge compatible, independent LWT execution profiles."""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lwt.profile_schema import ProfileFormatError, load_profile_json, validate_profile


def _definition(row: dict[str, Any], dynamic: set[str]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in dynamic}


def _summary(covered: int, total: int) -> dict[str, object]:
    return {
        "covered": covered,
        "total": total,
        "percentage": None if total == 0 else round(covered * 100.0 / total, 2),
    }


def merge_profiles(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    if len(profiles) < 2:
        raise ProfileFormatError("at least two individual profiles are required")
    for profile in profiles:
        validate_profile(profile)
        if "runs" in profile:
            raise ProfileFormatError("merge accepts individual runs, not an already merged profile")
    first = profiles[0]
    for index, profile in enumerate(profiles[1:], 2):
        if profile["entry"] != first["entry"]:
            raise ProfileFormatError(f"input {index} has a different entry source")
        first_modules = {item["source"]: item for item in first["modules"]}
        other_modules = {item["source"]: item for item in profile["modules"]}
        if set(first_modules) != set(other_modules):
            raise ProfileFormatError(f"input {index} has a different module set")
        for source, left in first_modules.items():
            right = other_modules[source]
            if left["sha256"] != right["sha256"]:
                raise ProfileFormatError(f"module hash conflict for {source!r}")
            if left != right:
                raise ProfileFormatError(f"module definition conflict for {source!r}")
        for collection, dynamic in (
            ("statements", {"hit_count", "covered"}),
            ("functions", {"call_count", "covered", "explicit_returns", "natural_returns"}),
            ("decisions", {"covered_outcomes", "percentage", "covered"}),
        ):
            left_rows = {row["id"]: row for row in first["coverage"][collection]}
            right_rows = {row["id"]: row for row in profile["coverage"][collection]}
            if set(left_rows) != set(right_rows):
                raise ProfileFormatError(f"input {index} has different {collection} IDs")
            for identifier, left in left_rows.items():
                right = right_rows[identifier]
                if collection == "decisions":
                    left_static = copy.deepcopy(left)
                    right_static = copy.deepcopy(right)
                    left_static["outcomes"] = [{"name": item["name"]} for item in left["outcomes"]]
                    right_static["outcomes"] = [{"name": item["name"]} for item in right["outcomes"]]
                    if _definition(left_static, dynamic) != _definition(right_static, dynamic):
                        raise ProfileFormatError(f"static decision definition conflict for {identifier}")
                elif _definition(left, dynamic) != _definition(right, dynamic):
                    raise ProfileFormatError(f"static {collection[:-1]} definition conflict for {identifier}")

    result = copy.deepcopy(first)
    result["tool"] = "lwt-profile-merge"
    result["status"] = "merged"
    result["exit_code"] = None
    result["events"] = []
    result["runs"] = [
        {
            "run_index": index,
            "status": profile["status"],
            "exit_code": profile["exit_code"],
            "event_count": len(profile["events"]),
            "events": copy.deepcopy(profile["events"]),
        }
        for index, profile in enumerate(profiles, 1)
    ]

    for collection, counter_fields in (
        ("statements", ("hit_count",)),
        ("functions", ("call_count", "explicit_returns", "natural_returns")),
    ):
        rows = {row["id"]: row for row in result["coverage"][collection]}
        for profile in profiles[1:]:
            other = {row["id"]: row for row in profile["coverage"][collection]}
            for identifier, row in rows.items():
                for key in counter_fields:
                    row[key] += other[identifier][key]
                if collection in {"statements", "functions"}:
                    row["covered"] = row[counter_fields[0]] > 0

    decisions = {row["id"]: row for row in result["coverage"]["decisions"]}
    for profile in profiles[1:]:
        other = {row["id"]: row for row in profile["coverage"]["decisions"]}
        for identifier, row in decisions.items():
            other_outcomes = {item["name"]: item for item in other[identifier]["outcomes"]}
            for outcome in row["outcomes"]:
                outcome["count"] += other_outcomes[outcome["name"]]["count"]
                outcome["covered"] = outcome["count"] > 0
            row["covered_outcomes"] = sum(item["covered"] for item in row["outcomes"])
            row["total_outcomes"] = len(row["outcomes"])
            row["percentage"] = round(row["covered_outcomes"] * 100.0 / row["total_outcomes"], 2)
            row["covered"] = row["covered_outcomes"] == row["total_outcomes"]

    coverage = result["coverage"]

    def recalc(collection: str, source: str | None = None) -> tuple[int, int]:
        rows = [row for row in coverage[collection] if source is None or row["source"] == source]
        if collection == "statements":
            return sum(row["covered"] for row in rows), len(rows)
        if collection == "functions":
            return sum(row["covered"] for row in rows), len(rows)
        return sum(row["covered_outcomes"] for row in rows), sum(row["total_outcomes"] for row in rows)

    coverage["summary"] = {collection: _summary(*recalc(collection)) for collection in ("statements", "functions", "decisions")}
    module_summaries = []
    for module in result["modules"]:
        source = module["source"]
        module_summaries.append(
            {
                "source": source,
                "statements": _summary(*recalc("statements", source)),
                "functions": _summary(*recalc("functions", source)),
                "decisions": _summary(*recalc("decisions", source)),
            }
        )
    coverage["by_module"] = module_summaries
    validate_profile(result)
    return result


def _write_atomic(path: Path, document: str) -> None:
    path = path.resolve()
    if not path.parent.is_dir():
        raise OSError("output directory does not exist")
    temporary: str | None = None
    descriptor = -1
    try:
        descriptor, temporary = tempfile.mkstemp(prefix=".lwt-merge-", suffix=".tmp", dir=path.parent)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            descriptor = -1
            stream.write(document)
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
    parser.add_argument("profiles", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args(argv)
    try:
        profiles = [load_profile_json(path.read_text(encoding="utf-8")) for path in arguments.profiles]
        merged = merge_profiles(profiles)
        document = json.dumps(merged, ensure_ascii=True, separators=(",", ":"), allow_nan=False) + "\n"
        _write_atomic(arguments.output, document)
    except (OSError, UnicodeError, ProfileFormatError, TypeError, ValueError) as error:
        print(f"lwt-profile-merge: {error}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
