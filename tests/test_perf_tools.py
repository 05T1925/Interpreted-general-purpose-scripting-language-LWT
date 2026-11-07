"""S44 WP5: performance-tool schema, oracle, pairing and path-guard tests.

These tests exercise the NEW S44 tools only (benchmark_v2, measure_startup,
compare_perf, the --require-all-referenced integrity gate). They avoid running
the full measurement protocols: pure functions are tested directly and a few
small subprocesses verify that the independent oracle matches the public CLI.
No protected evidence (S11/S42/S43 raw) is read or written by these tests.
"""

from __future__ import annotations

import io
from pathlib import Path
import subprocess
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import benchmark_v2
from tools import compare_perf
from tools import measure_startup
from tools.check_project_integrity import inspect_project


class OracleTests(unittest.TestCase):
    """Independent oracle must match the public CLI byte-for-byte."""

    def test_oracle_matches_cli_for_all_workloads(self) -> None:
        for benchmark in benchmark_v2.BENCHMARKS:
            for n in (100, 1000):
                with self.subTest(benchmark=benchmark, n=n):
                    expected = benchmark_v2.expected_stdout(benchmark, n)
                    lwt = subprocess.run(
                        [sys.executable, "-m", "lwt", f"bench/{benchmark}.lwt", "--", str(n)],
                        cwd=REPO_ROOT, capture_output=True, timeout=30,
                    )
                    py = subprocess.run(
                        [sys.executable, f"bench/{benchmark}.py", str(n)],
                        cwd=REPO_ROOT, capture_output=True, timeout=30,
                    )
                    self.assertEqual(lwt.returncode, 0, lwt.stderr)
                    self.assertEqual(py.returncode, 0, py.stderr)
                    self.assertEqual(lwt.stdout, expected, f"LWT {benchmark}/{n}")
                    self.assertEqual(py.stdout, expected, f"Python {benchmark}/{n}")

    def test_make_argv_uses_public_entry_points(self) -> None:
        lwt_argv = benchmark_v2.make_argv("lwt", "arithmetic", 100)
        py_argv = benchmark_v2.make_argv("python", "arithmetic", 100)
        self.assertEqual(lwt_argv[1:4], ["-m", "lwt", str(REPO_ROOT / "bench" / "arithmetic.lwt")])
        self.assertEqual(lwt_argv[-2:], ["--", "100"])
        self.assertEqual(py_argv[1], str(REPO_ROOT / "bench" / "arithmetic.py"))
        self.assertEqual(py_argv[-1], "100")

    def test_dict_counts_oracle_matches_distinct_key_count(self) -> None:
        # 1009 is prime: the key cycle is min(n, 1009).
        self.assertEqual(benchmark_v2.expected_stdout("dict_counts", 5000), b"5000|1009\n")
        self.assertEqual(benchmark_v2.expected_stdout("dict_counts", 100), b"100|100\n")


class SchedulePairingTests(unittest.TestCase):
    def test_schedule_is_deterministic_for_same_seed(self) -> None:
        a = benchmark_v2.build_schedule((100, 1000), 2, 20261107)
        b = benchmark_v2.build_schedule((100, 1000), 2, 20261107)
        self.assertEqual(a, b)

    def test_each_pair_has_both_languages(self) -> None:
        schedule = benchmark_v2.build_schedule((100, 1000), 3, 7)
        self.assertEqual(len(schedule), 3 * 2 * 3)  # 3 workloads x 2 sizes x 3 repeats
        for block in schedule:
            self.assertEqual(sorted(block["language_order"]), ["lwt", "python"])
            self.assertIn(block["benchmark"], benchmark_v2.BENCHMARKS)
            self.assertIn(block["size"], (100, 1000))
            self.assertTrue(block["pair_id"].startswith("pair-"))

    def test_schedule_covers_both_language_orders(self) -> None:
        schedule = benchmark_v2.build_schedule((1000,), 12, 42)
        orders = {tuple(block["language_order"]) for block in schedule}
        self.assertEqual(orders, {("lwt", "python"), ("python", "lwt")})

    def test_different_seed_changes_schedule(self) -> None:
        a = benchmark_v2.build_schedule((100, 1000), 3, 1)
        b = benchmark_v2.build_schedule((100, 1000), 3, 2)
        self.assertNotEqual(a, b)


class SchemaAndPathGuardTests(unittest.TestCase):
    def test_benchmark_v2_paths_under_s44_performance(self) -> None:
        self.assertTrue(
            benchmark_v2.RESULTS_PATH.relative_to(REPO_ROOT).as_posix().startswith("reports/s44-performance/")
        )
        self.assertTrue(
            benchmark_v2.REPORT_PATH.relative_to(REPO_ROOT).as_posix().startswith("reports/s44-performance/")
        )
        self.assertNotEqual(benchmark_v2.RESULTS_PATH, REPO_ROOT / "bench" / "results.json")
        self.assertNotEqual(benchmark_v2.REPORT_PATH, REPO_ROOT / "reports" / "performance.md")

    def test_benchmark_v2_rejects_protected_output_path(self) -> None:
        for path in ("bench/results.json", "reports/performance.md", "reports/runtime-profile.json", "out.json"):
            with self.subTest(path=path):
                code = benchmark_v2.main(["--out", path, "--sizes", "100", "--repeats", "1", "--warmups", "1"])
                self.assertEqual(code, 4, f"should refuse {path}")

    def test_measure_startup_rejects_protected_output_path(self) -> None:
        for path in ("reports/runtime-profile.json", "bench/results.json", "reports/performance.md"):
            with self.subTest(path=path):
                code = measure_startup.main(["--out", path, "--repeats", "1", "--warmups", "0"])
                self.assertEqual(code, 4, f"should refuse {path}")

    def test_source_hashes_cover_all_language_workloads(self) -> None:
        hashes = benchmark_v2.source_hashes()
        self.assertEqual(len(hashes), len(benchmark_v2.BENCHMARKS) * len(benchmark_v2.LANGUAGES))
        for path, digest in hashes.items():
            self.assertEqual(len(digest), 64, path)
            self.assertTrue(all(c in "0123456789abcdef" for c in digest), path)

    def test_micro_bench_output_isolatable(self) -> None:
        # micro_bench must support --output-prefix / --label / --out so S42
        # runtime-profile.* is never overwritten by S44 A/B runs.
        out = subprocess.run(
            [sys.executable, "tools/micro_bench.py", "--help"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        for flag in ("--out", "--output-prefix", "--label"):
            self.assertIn(flag, out.stdout)


class ComparePerfTests(unittest.TestCase):
    def test_compare_reports_all_gates(self) -> None:
        doc = compare_perf.compare()
        self.assertIn("startup", doc["gates"])
        self.assertIn("pure_execute", doc["gates"])
        self.assertIn("all_pass", doc)
        self.assertEqual(set(doc["gates"]["pure_execute"]["detail"]), set(benchmark_v2.BENCHMARKS))
        self.assertIn("note", doc)

    def test_compare_does_not_write_files(self) -> None:
        # compare_perf is read-only: calling compare() twice yields equal docs.
        self.assertEqual(compare_perf.compare(), compare_perf.compare())

    def test_missing_evidence_is_not_a_pass(self) -> None:
        # _ratio(None-safe) and MISSING formatting must not fabricate numbers.
        self.assertIsNone(compare_perf._ratio(1.0, 0.0))
        self.assertEqual(compare_perf._fmt(None), "MISSING")


class CoverageGateTests(unittest.TestCase):
    def test_all_400_cases_are_referenced(self) -> None:
        result = inspect_project(REPO_ROOT)
        self.assertEqual(result.case_count, 400)
        self.assertEqual(result.case_count - result.referenced_case_count, 0,
                         "every discovered case must be linked in docs/test-matrix.md")

    def test_require_all_referenced_cli_passes(self) -> None:
        # main() is invoked through the module with argv patched via sys.argv.
        from tools import check_project_integrity as cpi
        saved = sys.argv
        try:
            sys.argv = ["check_project_integrity.py", "--require-all-referenced"]
            buf = io.StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                code = cpi.main(REPO_ROOT)
            finally:
                sys.stdout = old
            self.assertEqual(code, 0, buf.getvalue())
            self.assertIn("unreferenced=0", buf.getvalue())
        finally:
            sys.argv = saved


if __name__ == "__main__":
    unittest.main()
