"""Headless report-contract tests for the LWT-backed analysis workbench."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from app.log_detective_core import AnalyzerError
from app.log_report_view import (
    CountRow,
    WorkbenchQuery,
    WorkbenchSession,
    analyze_workbench,
    parse_report,
)


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "app" / "fixtures" / "sample.log"


def report(
    total: int,
    valid: int,
    malformed: int,
    matched: int,
    *,
    levels: tuple[str, ...] = (),
    modules: tuple[str, ...] = (),
    examples: tuple[str, ...] = (),
) -> str:
    return "\n".join((
        "LWT log report",
        f"Total lines: {total}",
        f"Valid records: {valid}",
        f"Malformed lines: {malformed}",
        f"Matched records: {matched}",
        "Level counts:",
        *levels,
        "Top modules:",
        *modules,
        "Matching examples (first 3):",
        *examples,
    )) + "\n"


class ReportContractTests(unittest.TestCase):
    def test_default_sample_report_is_parsed_from_real_cli(self) -> None:
        parsed = analyze_workbench(WorkbenchQuery.from_fields(SAMPLE))
        self.assertEqual(
            (parsed.total_lines, parsed.valid_records, parsed.malformed_lines, parsed.matched_records),
            (7, 6, 1, 6),
        )
        self.assertEqual(
            parsed.level_counts,
            (CountRow("ERROR", 2), CountRow("INFO", 2), CountRow("WARN", 2)),
        )
        self.assertEqual(parsed.top_modules[0], CountRow("cache", 2))
        self.assertEqual(len(parsed.matching_examples), 3)
        self.assertEqual(parsed.raw, (ROOT / "app" / "fixtures" / "sample.expected.txt").read_text(encoding="utf-8"))

    def test_combined_filter_is_parsed_from_real_cli(self) -> None:
        query = WorkbenchQuery.from_fields(SAMPLE, level="WARN", keyword="retry", top="2")
        self.assertEqual(
            query.filter_args,
            ("--level", "WARN", "--keyword", "retry", "--top", "2"),
        )
        parsed = analyze_workbench(query)
        self.assertEqual(parsed.matched_records, 1)
        self.assertEqual(parsed.level_counts, (CountRow("WARN", 1),))
        self.assertEqual(parsed.top_modules, (CountRow("cache", 1),))
        self.assertEqual(
            parsed.matching_examples,
            ("2026-10-07T10:00:03Z|WARN|cache|retry scheduled",),
        )

    def test_empty_zero_match_and_top_zero(self) -> None:
        empty = parse_report(report(0, 0, 0, 0))
        self.assertEqual(empty.top_modules, ())
        self.assertEqual(empty.matching_examples, ())
        zero = analyze_workbench(WorkbenchQuery.from_fields(SAMPLE, level="TRACE", top="0"))
        self.assertEqual((zero.total_lines, zero.valid_records, zero.matched_records), (7, 6, 0))
        self.assertEqual(zero.level_counts, ())
        self.assertEqual(zero.top_modules, ())
        top_zero = analyze_workbench(WorkbenchQuery.from_fields(SAMPLE, top="0"))
        self.assertEqual(top_zero.matched_records, 6)
        self.assertEqual(top_zero.top_modules, ())
        self.assertEqual(len(top_zero.matching_examples), 3)

    def test_empty_level_and_module_names_are_valid(self) -> None:
        parsed = parse_report(
            report(1, 1, 0, 1, levels=("|1",), modules=("|1",), examples=("|||",))
        )
        self.assertEqual(parsed.level_counts, (CountRow("", 1),))
        self.assertEqual(parsed.top_modules, (CountRow("", 1),))

    def test_example_text_may_begin_like_a_fixed_field(self) -> None:
        parsed = parse_report(
            report(
                1, 1, 0, 1,
                levels=("INFO|1",),
                modules=("app|1",),
                examples=("Total lines: 1|INFO|app|message",),
            )
        )
        self.assertEqual(parsed.matching_examples[0], "Total lines: 1|INFO|app|message")

    def test_top_may_be_large_without_host_int_limit(self) -> None:
        parsed = parse_report(
            report(1, 1, 0, 1, levels=("INFO|1",), modules=("app|1",), examples=("t|INFO|app|ok",)),
            top="9" * 6000,
        )
        self.assertEqual(parsed.top_modules, (CountRow("app", 1),))

    def test_invalid_query_and_missing_file_are_readable(self) -> None:
        for top in ("", "-1", "+1", " 1", "1x", "１"):
            with self.subTest(top=top), self.assertRaisesRegex(AnalyzerError, "Top"):
                WorkbenchQuery.from_fields(SAMPLE, top=top)
        for kwargs in ({"level": "--WARN"}, {"keyword": "--retry"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(AnalyzerError):
                WorkbenchQuery.from_fields(SAMPLE, **kwargs)
        with self.assertRaisesRegex(AnalyzerError, "日志分析失败"):
            analyze_workbench(WorkbenchQuery.from_fields(ROOT / "app" / "fixtures" / "missing-s18.log"))

    def test_unicode_space_path_uses_public_cli(self) -> None:
        with tempfile.TemporaryDirectory(prefix="LWT 工作台 ") as directory:
            path = Path(directory) / "演示 日志.log"
            path.write_text("t|WARN|模块|重试 retry\n", encoding="utf-8")
            parsed = analyze_workbench(
                WorkbenchQuery.from_fields(path, level="WARN", keyword="retry", top="2")
            )
        self.assertEqual(parsed.matched_records, 1)
        self.assertEqual(parsed.top_modules, (CountRow("模块", 1),))

    def test_rejects_missing_duplicate_or_out_of_order_structure(self) -> None:
        good = report(1, 1, 0, 1, levels=("INFO|1",), modules=("app|1",), examples=("t|INFO|app|ok",))
        variants = (
            good.replace("Valid records: 1\n", ""),
            good.replace("Valid records: 1\n", "Valid records: 1\nValid records: 1\n"),
            good.replace("Level counts:\nINFO|1\nTop modules:", "Top modules:\nINFO|1\nLevel counts:"),
            good.replace("Top modules:\n", "Top modules:\nTop modules:\n"),
            good.removesuffix("\n"),
        )
        for broken in variants:
            with self.subTest(broken=broken), self.assertRaises(AnalyzerError):
                parse_report(broken)

    def test_rejects_invalid_counts_and_inconsistencies(self) -> None:
        good = report(2, 2, 0, 2, levels=("INFO|2",), modules=("app|2",),
                      examples=("t1|INFO|app|a", "t2|INFO|app|b"))
        variants = (
            good.replace("Total lines: 2", "Total lines: -2"),
            good.replace("Total lines: 2", "Total lines: 3"),
            good.replace("Matched records: 2", "Matched records: 3"),
            good.replace("INFO|2", "INFO|1"),
            good.replace("INFO|2", "INFO|2\nINFO|1"),
            good.replace("app|2", "app|3"),
            good.replace("app|2", "app|2\napp|1"),
            good.replace("app|2", "app|x"),
            good.replace("app|2", "app|extra|2"),
            good.replace("t2|INFO|app|b\n", ""),
            good.replace("t2|INFO|app|b", "broken example"),
        )
        for broken in variants:
            with self.subTest(broken=broken), self.assertRaises(AnalyzerError):
                parse_report(broken)

    def test_top_is_truncated_and_not_required_to_sum_to_matched(self) -> None:
        parsed = parse_report(
            report(3, 3, 0, 3, levels=("INFO|3",), modules=("app|2",),
                   examples=("t1|INFO|app|a", "t2|INFO|app|b", "t3|INFO|other|c")),
            top="1",
        )
        self.assertEqual(sum(row.count for row in parsed.top_modules), 2)
        with self.assertRaisesRegex(AnalyzerError, "Top"):
            parse_report(parsed.raw, top="0")

    def test_changed_conditions_discard_inflight_result_and_allow_retry(self) -> None:
        state = WorkbenchSession()
        first = WorkbenchQuery.from_fields(SAMPLE, level="INFO")
        stale_report = parse_report(report(0, 0, 0, 0))
        revision = state.begin(first)
        with self.assertRaises(RuntimeError):
            state.begin(first)
        state.invalidate()
        self.assertFalse(state.complete(revision, stale_report))
        self.assertIsNone(state.report)
        self.assertIsNone(state.pending)
        next_query = WorkbenchQuery.from_fields(SAMPLE, level="WARN")
        next_revision = state.begin(next_query)
        self.assertTrue(state.complete(next_revision, stale_report))
        self.assertEqual(state.query, next_query)
        self.assertIs(state.report, stale_report)

    def test_failed_result_does_not_leave_an_old_report_visible(self) -> None:
        state = WorkbenchSession()
        query = WorkbenchQuery.from_fields(SAMPLE)
        first = state.begin(query)
        self.assertTrue(state.complete(first, parse_report(report(0, 0, 0, 0))))
        second = state.begin(query)
        self.assertIsNone(state.report)
        self.assertTrue(state.complete(second, None, "文件不存在"))
        self.assertIsNone(state.report)
        self.assertEqual(state.error, "文件不存在")


if __name__ == "__main__":
    unittest.main()
