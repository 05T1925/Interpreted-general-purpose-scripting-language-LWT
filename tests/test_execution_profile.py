from __future__ import annotations

import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from lwt.errors import LwtError
from lwt.profile_schema import ProfileFormatError, load_profile_json, validate_profile
from lwt.cli import _profile_document, _run_profile
from tools.merge_lwt_profiles import merge_profiles
from tools.render_lwt_profile import render_html, verify_available_source_hashes


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_lwt(*arguments: str, stdin: bytes = b"") -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "lwt", *arguments], cwd=REPO_ROOT, input=stdin,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False, check=False,
    )


class ExecutionProfileCliTests(unittest.TestCase):
    def read_profile(self, path: Path) -> dict[str, object]:
        profile = json.loads(path.read_text(encoding="utf-8"))
        validate_profile(profile)
        return profile

    def test_module_profile_preserves_output_and_records_stable_module_calls(self) -> None:
        ordinary = run_lwt("examples/modules/main.lwt")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "modules.json"
            profiled = run_lwt("--profile", str(path), "examples/modules/main.lwt")
            self.assertEqual((profiled.returncode, profiled.stdout, profiled.stderr), (ordinary.returncode, ordinary.stdout, ordinary.stderr))
            self.assertEqual((ordinary.returncode, ordinary.stdout, ordinary.stderr), (0, b"demo:2\n", b""))
            profile = self.read_profile(path)
            self.assertEqual(profile["status"], "success")
            self.assertEqual(len(profile["modules"]), 3)
            self.assertEqual({item["source"] for item in profile["modules"]}, {"examples/modules/main.lwt", "stats_utils.lwt", "text_utils.lwt"})
            calls = [event for event in profile["events"] if event["event"] == "function_call"]
            returns = [event for event in profile["events"] if event["event"] == "function_return"]
            self.assertTrue(any(event["qualified_name"] == "stats.summarize" for event in calls))
            self.assertTrue(any(event["qualified_name"] == "stats.summarize" for event in returns))
            self.assertEqual([event["sequence"] for event in profile["events"]], list(range(1, len(profile["events"]) + 1)))
            for module in profile["modules"]:
                source = REPO_ROOT / module["source"] if module["entry"] else REPO_ROOT / "examples/modules" / module["source"]
                self.assertEqual(module["sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
    def test_profile_json_bytes_are_deterministic_for_same_invocation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "first.json", Path(directory) / "second.json"
            one = run_lwt("--profile", str(first), "examples/modules/main.lwt")
            two = run_lwt("--profile", str(second), "examples/modules/main.lwt")
            self.assertEqual((one.returncode, one.stdout, one.stderr), (two.returncode, two.stdout, two.stderr))
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_fixed_log_application_profiles_preserve_both_contract_outputs(self) -> None:
        default_expected = (REPO_ROOT / "app/fixtures/sample.expected.txt").read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")
        filtered_expected = (
            b"LWT log report\nTotal lines: 7\nValid records: 6\nMalformed lines: 1\n"
            b"Matched records: 1\nLevel counts:\nWARN|1\nTop modules:\ncache|1\n"
            b"Matching examples (first 3):\n2026-10-07T10:00:03Z|WARN|cache|retry scheduled\n"
        )
        scenarios = [(["app/fixtures/sample.log"], default_expected), (["app/fixtures/sample.log", "--level", "WARN", "--keyword", "retry", "--top", "2"], filtered_expected)]
        with tempfile.TemporaryDirectory() as directory:
            for index, (program_args, expected) in enumerate(scenarios):
                normal = run_lwt("app/log_report.lwt", "--", *program_args)
                profile_path = Path(directory) / f"app-{index}.json"
                profiled = run_lwt("--profile", str(profile_path), "app/log_report.lwt", "--", *program_args)
                self.assertEqual((normal.returncode, normal.stdout, normal.stderr), (0, expected, b""))
                self.assertEqual((profiled.returncode, profiled.stdout, profiled.stderr), (normal.returncode, normal.stdout, normal.stderr))
                self.read_profile(profile_path)

    def test_recovery_profile_captures_recover_and_original_cli_output(self) -> None:
        ordinary = run_lwt("examples/error_recovery/main.lwt")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recovery.json"
            profiled = run_lwt("--profile", str(path), "examples/error_recovery/main.lwt")
            self.assertEqual((profiled.returncode, profiled.stdout, profiled.stderr), (ordinary.returncode, ordinary.stdout, ordinary.stderr))
            self.assertEqual(profiled.stdout, b'2\ndivision by zero\nError{category: "RuntimeError", message: "division by zero", source: "math.lwt", line: 2, column: 17}\n4\nremaining values processed\n')
            profile = self.read_profile(path)
            self.assertEqual(profile["status"], "success")
            self.assertTrue(any(event["event"] == "recover" for event in profile["events"]))
            self.assertFalse(any(event["event"] == "runtime_error" for event in profile["events"]))

    def test_unhandled_runtime_error_keeps_original_status_and_profile_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "broken.lwt", root / "broken.json"
            source.write_text('emit "before";\nemit 1 / 0;\nemit "after";\n', encoding="utf-8", newline="\n")
            ordinary = run_lwt(str(source))
            profiled = run_lwt("--profile", str(output), str(source))
            self.assertEqual((profiled.returncode, profiled.stdout, profiled.stderr), (ordinary.returncode, ordinary.stdout, ordinary.stderr))
            self.assertEqual((profiled.returncode, profiled.stdout), (3, b"before\n"))
            profile = self.read_profile(output)
            self.assertEqual((profile["status"], profile["exit_code"]), ("runtime_error", 3))
            self.assertEqual(profile["events"][-2]["event"], "runtime_error")
            self.assertEqual(profile["events"][-1]["event"], "program_end")
            self.assertEqual(profile["coverage"]["statements"][-1]["hit_count"], 0)

    def test_each_profile_does_not_change_shallow_snapshot_and_uninvoked_function_is_uncovered(self) -> None:
        source_text = 'fn unused() { emit "never"; }\nlet values = [1, 2];\neach (value in values) { push(values, 9); emit value; }\nemit len(values);\n'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "snapshot.lwt", root / "snapshot.json"
            source.write_text(source_text, encoding="utf-8")
            ordinary = run_lwt(str(source))
            profiled = run_lwt("--profile", str(output), str(source))
            self.assertEqual((profiled.returncode, profiled.stdout, profiled.stderr), (ordinary.returncode, ordinary.stdout, ordinary.stderr))
            self.assertEqual(profiled.stdout, b"1\n2\n4\n")
            profile = json.loads(output.read_text(encoding="utf-8"))
            functions = {row["name"]: row for row in profile["coverage"]["functions"]}
            self.assertFalse(functions["unused"]["covered"])
            each = next(row for row in profile["coverage"]["decisions"] if row["kind"] == "each")
            self.assertEqual(each["outcomes"], [{"name": "empty", "count": 0, "covered": False}, {"name": "nonempty", "count": 1, "covered": True}])

    def test_nested_handler_failure_is_recovered_by_outer_attempt_in_order(self) -> None:
        source_text = 'attempt { attempt { fail("inner"); } recover (problem) { fail("handler"); } } recover (outer) { emit "outer recovered"; }\n'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "nested.lwt", root / "nested.json"
            source.write_text(source_text, encoding="utf-8")
            result = run_lwt("--profile", str(output), str(source))
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"outer recovered\n", b""))
            profile = json.loads(output.read_text(encoding="utf-8"))
            recovers = [event for event in profile["events"] if event["event"] == "recover"]
            self.assertEqual(len(recovers), 2)
            recover_indexes = [index for index, event in enumerate(profile["events"]) if event["event"] == "recover"]
            self.assertLess(recover_indexes[0], recover_indexes[1])
            self.assertEqual(profile["events"][-2]["event"], "statement")
            self.assertEqual(profile["events"][-2]["kind"], "emit")

    def test_attempt_normal_edge_includes_unmodified_return_and_break_transfers(self) -> None:
        source_text = 'fn stop() { attempt { return 7; } recover (problem) { emit "wrong"; } }\nlet value = stop();\nwhile (true) { attempt { break; } recover (problem) { emit "wrong"; } }\nemit value;\n'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "transfer.lwt", root / "transfer.json"
            source.write_text(source_text, encoding="utf-8")
            result = run_lwt("--profile", str(output), str(source))
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"7\n", b""))
            profile = self.read_profile(output)
            attempts = [row for row in profile["coverage"]["decisions"] if row["kind"] == "attempt"]
            self.assertEqual(len(attempts), 2)
            self.assertTrue(all(row["outcomes"][0]["count"] == 1 for row in attempts))

    def test_function_decision_loop_and_short_circuit_coverage(self) -> None:
        lines = [
            "fn descend(n) { when (n == 0) { return 0; } otherwise { return descend(n - 1); } }",
            'fn natural() { emit "natural"; }',
            "let depth = descend(2);", "natural();",
            'when (false) { emit "wrong"; } otherwise { emit "branch"; }',
            "while (true) { break; }", "while (false) {}",
            "each (item in []) { emit item; }", "each (item in [1, 2]) { continue; }",
            'let a = false and fail("short marker");', 'let b = true or fail("short marker");',
            "let c = true and true;", "let d = false or true;",
            "attempt { let ok = 1; } recover (problem) { emit \"wrong\"; }",
            'attempt { fail("recover marker"); } recover (problem) { emit "recovered"; }',
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "flow.lwt", root / "flow.json"
            source.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
            result = run_lwt("--profile", str(output), str(source))
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"natural\nbranch\nrecovered\n", b""))
            profile = self.read_profile(output)
            functions = {row["name"]: row for row in profile["coverage"]["functions"]}
            self.assertEqual(functions["descend"]["call_count"], 3)
            self.assertEqual(functions["descend"]["explicit_returns"], 3)
            self.assertEqual(functions["natural"]["natural_returns"], 1)
            calls = [event for event in profile["events"] if event["event"] == "function_call" and event["function_name"] == "descend"]
            self.assertEqual([event["depth"] for event in calls], [1, 2, 3])
            outcomes = {}
            for row in profile["coverage"]["decisions"]:
                outcomes.setdefault(row["kind"], []).append({item["name"]: item["count"] for item in row["outcomes"]})
            self.assertIn({"then": 1, "otherwise": 2}, outcomes["when"])
            self.assertIn({"true": 1, "false": 0}, outcomes["while"])
            self.assertIn({"true": 0, "false": 1}, outcomes["while"])
            self.assertIn({"empty": 1, "nonempty": 0}, outcomes["each"])
            self.assertIn({"empty": 0, "nonempty": 1}, outcomes["each"])
            for kind in ("and", "or"):
                totals = {"short_circuit": 0, "evaluate_right": 0}
                for decision in outcomes[kind]:
                    for name in totals:
                        totals[name] += decision[name]
                self.assertEqual(totals, {"short_circuit": 1, "evaluate_right": 1})
            self.assertIn({"normal": 1, "recovered": 0}, outcomes["attempt"])
            self.assertIn({"normal": 0, "recovered": 1}, outcomes["attempt"])

    def test_empty_profile_null_percentages_and_private_input_not_serialized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            empty, empty_profile = root / "empty.lwt", root / "empty.json"
            empty.write_text("", encoding="utf-8")
            run = run_lwt("--profile", str(empty_profile), str(empty))
            self.assertEqual((run.returncode, run.stdout, run.stderr), (0, b"", b""))
            profile = self.read_profile(empty_profile)
            for summary in profile["coverage"]["summary"].values():
                self.assertEqual(summary, {"covered": 0, "total": 0, "percentage": None})

            private, private_profile = root / "private.lwt", root / "private.json"
            private.write_text('record Box { value };\nlet token = input();\nlet items = [token];\nlet box = Box{value: token};\nemit len(items);\n', encoding="utf-8")
            result = run_lwt("--profile", str(private_profile), str(private), stdin=b"PRIVATE-STDIN\n")
            self.assertEqual(result.stdout, b"1\n")
            document = private_profile.read_text(encoding="utf-8")
            self.assertNotIn("PRIVATE-STDIN", document)
            self.assertNotIn('"token"', document)

            failing, failing_profile = root / "fail-input.lwt", root / "fail-input.json"
            failing.write_text("fail(input());\n", encoding="utf-8")
            failed = run_lwt("--profile", str(failing_profile), str(failing), stdin=b"PRIVATE-STDIN\n")
            self.assertEqual(failed.returncode, 3)
            self.assertIn(b"PRIVATE-STDIN", failed.stderr)
            failure_document = failing_profile.read_text(encoding="utf-8")
            self.assertNotIn("PRIVATE-STDIN", failure_document)
            failure_profile = json.loads(failure_document)
            error_event = next(event for event in failure_profile["events"] if event["event"] == "runtime_error")
            self.assertTrue(error_event["message_redacted"])
            self.assertEqual(error_event["message"], "program requested failure (user message redacted)")

    def test_profile_path_and_argv_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "源 file.lwt"
            target = root / "结果 file.json"
            source.write_text("emit args()[0];\n", encoding="utf-8")
            source_bytes = source.read_bytes()
            result = run_lwt("--profile", str(target), str(source), "--", "--profile")
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"--profile\n", b""))
            profile = self.read_profile(target)
            self.assertEqual(profile["entry"], source.name)
            self.assertNotIn(str(root), target.read_text(encoding="utf-8"))
            for args in (
                ("--profile",), ("--profile", "out.json"),
                ("--profile", "-", str(source)),
                ("--profile", str(root / "absent" / "out.json"), str(source)),
                ("--profile", str(source), str(source)),
                ("--check", "--profile", str(root / "x.json"), str(source)),
                (str(source), "--profile", str(root / "late.json")),
            ):
                failed = run_lwt(*args)
                self.assertEqual(failed.returncode, 4, args)
                self.assertNotIn(b"Traceback", failed.stderr)
            self.assertEqual(source.read_bytes(), source_bytes)
            self.assertFalse((root / "x.json").exists())

            directory_target = root / "profile-directory"
            directory_target.mkdir()
            output_probe = root / "probe.lwt"
            output_probe.write_text('emit "must not run";\n', encoding="utf-8")
            rejected = run_lwt("--profile", str(directory_target), str(output_probe))
            self.assertEqual((rejected.returncode, rejected.stdout), (4, b""))
            self.assertTrue(directory_target.is_dir())

            module_path = REPO_ROOT / "examples/modules/stats_utils.lwt"
            module_before = module_path.read_bytes()
            blocked = run_lwt("--profile", "examples/modules/stats_utils.lwt", "examples/modules/main.lwt")
            self.assertEqual(blocked.returncode, 4)
            self.assertEqual(module_path.read_bytes(), module_before)

            missing_output = root / "missing-source.json"
            missing = run_lwt("--profile", str(missing_output), str(root / "not-found.lwt"))
            self.assertEqual(missing.returncode, 4)
            self.assertFalse(missing_output.exists())
            malformed = root / "malformed.lwt"
            malformed.write_text("emit ;\n", encoding="utf-8")
            malformed_profile = root / "malformed.json"
            parse_error = run_lwt("--profile", str(malformed_profile), str(malformed))
            self.assertEqual(parse_error.returncode, 2)
            self.assertFalse(malformed_profile.exists())

    def test_normal_and_check_modes_do_not_create_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, absent = root / "simple.lwt", root / "absent.json"
            source.write_text('emit "ok";\n', encoding="utf-8")
            self.assertEqual(run_lwt(str(source)).returncode, 0)
            self.assertEqual(run_lwt("--check", str(source)).returncode, 0)
            self.assertFalse(absent.exists())


class ProfileRendererAndMergeTests(unittest.TestCase):
    def test_collector_internal_failure_is_a_tool_error_not_a_traceback(self) -> None:
        class BrokenCollector:
            def as_dict(self) -> dict[str, object]:
                raise RuntimeError("internal detail must not leak")

        with self.assertRaises(LwtError) as raised:
            _profile_document(BrokenCollector())
        self.assertEqual(raised.exception.category, "FileError")
        self.assertEqual(raised.exception.exit_code, 4)
        self.assertEqual(raised.exception.message, "execution profile collection failed")

    def test_profile_setup_and_serialization_failures_are_single_line_cli_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.lwt"
            setup_profile = root / "setup.json"
            serialize_profile = root / "serialize.json"
            source.write_text('emit "ran";\n', encoding="utf-8")

            setup_error = io.StringIO()
            with patch("lwt.observability.ProfileCollector.__init__", side_effect=RuntimeError("private detail")):
                with patch("sys.stderr", setup_error):
                    setup_exit = _run_profile(["--profile", str(setup_profile), str(source)])
            self.assertEqual(setup_exit, 4)
            self.assertEqual(setup_error.getvalue(), "lwt: FileError: execution profile collection failed\n")
            self.assertFalse(setup_profile.exists())

            stdout, stderr = io.StringIO(), io.StringIO()
            with patch("lwt.observability.ProfileCollector.as_dict", side_effect=RuntimeError("private detail")):
                with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                    serialization_exit = _run_profile(["--profile", str(serialize_profile), str(source)])
            self.assertEqual(serialization_exit, 4)
            self.assertEqual(stdout.getvalue(), "ran\n")
            self.assertEqual(stderr.getvalue(), "lwt: FileError: execution profile collection failed\n")
            self.assertFalse(serialize_profile.exists())

    def make_profile(self, root: Path, name: str, source_text: str) -> Path:
        source, output = root / f"{name}.lwt", root / f"{name}.json"
        source.write_text(source_text, encoding="utf-8", newline="\n")
        result = run_lwt("--profile", str(output), str(source))
        if result.returncode not in (0, 3):
            self.fail(result.stderr.decode("utf-8", errors="replace"))
        return output

    def test_renderer_is_deterministic_offline_and_escapes_error_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.make_profile(Path(directory), "unsafe", 'fail("<script>alert(1)</script>");\n')
            profile = load_profile_json(path.read_text(encoding="utf-8"))
            verify_available_source_hashes(profile, path)
            profile = copy.deepcopy(profile)
            runtime_event = next(event for event in profile["events"] if event["event"] == "runtime_error")
            runtime_event["message"] = "<script>alert(1)</script>"
            runtime_event["message_redacted"] = False
            validate_profile(profile)
            first, second = render_html(profile).encode("utf-8"), render_html(profile).encode("utf-8")
            self.assertEqual(first, second)
            self.assertIn(b"&lt;script&gt;", first)
            self.assertNotIn(b"<script>", first)
            self.assertNotIn(b"https://", first)
            self.assertIn("覆盖率只说明".encode("utf-8"), first)

    def test_renderer_rejects_available_source_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.make_profile(root, "hashed", 'emit "original";\n')
            profile = load_profile_json(path.read_text(encoding="utf-8"))
            changed = copy.deepcopy(profile)
            changed["modules"][0]["sha256"] = "0" * 64
            with self.assertRaisesRegex(ProfileFormatError, "source hash mismatch"):
                verify_available_source_hashes(changed, path)

    def test_schema_rejects_duplicate_keys_unknown_version_ids_and_bad_summaries(self) -> None:
        with self.assertRaisesRegex(ProfileFormatError, "duplicate JSON key"):
            load_profile_json('{"schema_version":1,"schema_version":1}')
        with self.assertRaisesRegex(ProfileFormatError, "invalid profile JSON"):
            load_profile_json("{broken json")
        with tempfile.TemporaryDirectory() as directory:
            path = self.make_profile(Path(directory), "good", 'emit "x";\n')
            profile = load_profile_json(path.read_text(encoding="utf-8"))
            bad = copy.deepcopy(profile)
            bad["schema_version"] = 2
            with self.assertRaisesRegex(ProfileFormatError, "unsupported profile schema"):
                validate_profile(bad)
            bad = copy.deepcopy(profile)
            bad["coverage"]["statements"].append(copy.deepcopy(bad["coverage"]["statements"][0]))
            with self.assertRaisesRegex(ProfileFormatError, "duplicate statements ID"):
                validate_profile(bad)
            bad = copy.deepcopy(profile)
            bad["coverage"]["summary"]["statements"]["covered"] += 1
            with self.assertRaisesRegex(ProfileFormatError, "summary.statements"):
                validate_profile(bad)

    def test_merge_aggregates_counts_and_keeps_run_sequences_separate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile_path = self.make_profile(root, "sample", 'when (true) { emit "yes"; } otherwise { emit "no"; }\n')
            first = load_profile_json(profile_path.read_text(encoding="utf-8"))
            second = copy.deepcopy(first)
            merged = merge_profiles([first, second])
            validate_profile(merged)
            self.assertEqual((merged["status"], merged["exit_code"], merged["events"]), ("merged", None, []))
            self.assertEqual([run["events"][0]["sequence"] for run in merged["runs"]], [1, 1])
            for original, combined in zip(first["coverage"]["statements"], merged["coverage"]["statements"]):
                self.assertEqual(combined["hit_count"], original["hit_count"] * 2)

    def test_merge_rejects_module_hash_and_static_definition_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.make_profile(Path(directory), "sample", 'emit "x";\n')
            first = load_profile_json(path.read_text(encoding="utf-8"))
            changed_hash = copy.deepcopy(first)
            changed_hash["modules"][0]["sha256"] = "0" * 64
            with self.assertRaisesRegex(ProfileFormatError, "module hash conflict"):
                merge_profiles([first, changed_hash])
            changed_definition = copy.deepcopy(first)
            changed_definition["coverage"]["statements"][0]["kind"] = "changed"
            node_id = changed_definition["coverage"]["statements"][0]["id"]
            for event in changed_definition["events"]:
                if event["event"] == "statement" and event["node_id"] == node_id:
                    event["kind"] = "changed"
            validate_profile(changed_definition)
            with self.assertRaisesRegex(ProfileFormatError, "static statement definition conflict"):
                merge_profiles([first, changed_definition])


if __name__ == "__main__":
    unittest.main()
