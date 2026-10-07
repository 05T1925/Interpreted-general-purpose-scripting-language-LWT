import base64
import subprocess
import unittest

from tools import benchmark


def attempt(attempt_id, stdout, return_code=0, stderr=b""):
    expected = b"3|6\n"
    execution = {
        "elapsed_ns": 100,
        "return_code": return_code,
        "timed_out": False,
        "launch_error": None,
        "stdout_bytes": stdout,
        "stderr_bytes": stderr,
    }
    return benchmark.make_attempt_record(
        attempt_id=attempt_id,
        kind="formal",
        order=1,
        benchmark="arithmetic",
        language="lwt" if attempt_id == "lwt-1" else "python",
        n=3,
        argv=["python", "example", "3"],
        execution=execution,
        expected=expected,
        timeout_seconds=60,
        pair_id="pair-0001",
        repeat_index=1,
    )


class BenchmarkStatisticsTests(unittest.TestCase):
    def test_statistics_and_ratio(self):
        stats = benchmark.summarize_samples([10, 20, 30, 40])
        self.assertEqual(stats, {"count": 4, "median_ns": 25.0, "min_ns": 10, "max_ns": 40, "range_ns": 30})
        self.assertEqual(benchmark.ratio(50, 25), 2)


class BenchmarkValidationTests(unittest.TestCase):
    def test_pair_mismatch_is_invalid(self):
        pair = benchmark.make_pair_record(
            "pair-0001", "arithmetic", 3, 1,
            {"lwt": attempt("lwt-1", b"3|6\n"), "python": attempt("python-1", b"3|7\n")},
            b"3|6\n",
        )
        self.assertFalse(pair["paired_output_match"])
        self.assertFalse(pair["independent_expected_match"])
        self.assertFalse(pair["valid"])

    def test_nonzero_exit_is_invalid_even_with_expected_output(self):
        failed = attempt("python-1", b"3|6\n", return_code=3)
        self.assertFalse(failed["verification"]["passed"])
        self.assertIn("nonzero_or_missing_return_code", failed["verification"]["failure_reasons"])

    def test_stderr_is_a_failure(self):
        failed = attempt("python-1", b"3|6\n", stderr=b"warning\n")
        self.assertFalse(failed["verification"]["passed"])
        self.assertIn("stderr_not_empty", failed["verification"]["failure_reasons"])

    def test_timeout_and_launch_error_are_failures(self):
        for result, expected_reason in (
            ({"timed_out": True, "launch_error": None, "return_code": None,
              "stdout_bytes": b"", "stderr_bytes": b""}, "timeout"),
            ({"timed_out": False, "launch_error": {"type": "OSError", "message": "missing"},
              "return_code": None, "stdout_bytes": b"", "stderr_bytes": b""}, "launch_error"),
        ):
            verification = benchmark.verify_process(result, b"3|6\n")
            self.assertFalse(verification["passed"])
            self.assertIn(expected_reason, verification["failure_reasons"])

    def test_schedule_is_seeded_and_records_pair_order(self):
        first = benchmark.build_schedule([100, 1000], repeats=2, seed=29)
        second = benchmark.build_schedule([100, 1000], repeats=2, seed=29)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 8)
        self.assertTrue(all(set(block["language_order"]) == {"lwt", "python"} for block in first))


class BenchmarkReportTests(unittest.TestCase):
    def test_attempt_preserves_time_command_and_output_evidence(self):
        record = attempt("lwt-1", b"3|6\n")
        self.assertEqual(record["elapsed_ns"], 100)
        self.assertEqual(record["argv"], ["python", "example", "3"])
        self.assertEqual(base64.b64decode(record["stdout"]["base64"]), b"3|6\n")
        self.assertEqual(record["stdout"]["byte_length"], 4)
        self.assertEqual(len(record["timestamp_utc"]), 27)

    def test_calibration_never_enters_formal_summaries(self):
        run = {
            "mode": "calibration", "status": "valid", "sizes": [3], "formal_repeats": 0,
            "trials": [], "pairs": [],
        }
        self.assertEqual(benchmark.formal_summaries(run), [])

    def test_report_references_run_identity_raw_and_command_schema(self):
        run = {
            "run_id": "run-test-01", "mode": "formal", "status": "invalid",
            "started_at_utc": "2026-10-07T00:00:00.000000Z", "finished_at_utc": "2026-10-07T00:01:00.000000Z",
            "git": {"commit_sha": "abc123", "working_tree_clean_at_start": True},
            "environment": {"platform": "Windows", "machine": "AMD64", "python_version": "3.13.7", "python_executable": "python.exe", "processor": "CPU"},
            "seed": 42, "sizes": [100], "formal_repeats": 10, "timeout_seconds": 60,
            "source_sha256": {"bench/arithmetic.lwt": "a", "bench/arithmetic.py": "b", "bench/array_scan.lwt": "c", "bench/array_scan.py": "d"},
            "trials": [], "pairs": [], "warmups": [], "failure_count": 1,
        }
        report = benchmark.render_report({"schema_version": 1, "runs": [run]})
        self.assertIn("run-test-01", report)
        self.assertIn("abc123", report)
        self.assertIn("2026-10-07T00:00:00.000000Z", report)
        self.assertIn("bench/results.json", report)
        self.assertIn("正式样本 `0` 条", report)
        self.assertIn("无效正式运行", report)


class BenchmarkWorkloadTests(unittest.TestCase):
    def test_paired_workloads_emit_identical_exact_bytes(self):
        for name, size in (("arithmetic", 100), ("array_scan", 100)):
            expected = benchmark.expected_stdout(name, size)
            outputs = []
            for language in benchmark.LANGUAGES:
                completed = subprocess.run(
                    benchmark.make_argv(language, name, size),
                    cwd=str(benchmark.ROOT),
                    shell=False,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=30,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0)
                self.assertEqual(completed.stderr, b"")
                self.assertEqual(completed.stdout, expected)
                outputs.append(completed.stdout)
            self.assertEqual(outputs[0], outputs[1])


if __name__ == "__main__":
    unittest.main()
