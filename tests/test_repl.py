from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def run_repl(script: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "lwt", "--repl"],
        cwd=REPOSITORY_ROOT,
        input=script.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        timeout=15,
        check=False,
    )


class ReplTests(unittest.TestCase):
    def test_single_line_expression_and_emit(self) -> None:
        result = run_repl("emit 1 + 2;\n.exit\n")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"3\n")

    def test_variable_persistence_across_lines(self) -> None:
        result = run_repl("let x = 1;\nemit x;\nx = x + 2;\nemit x;\n.exit\n")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"1\n3\n")

    def test_function_definition_then_call(self) -> None:
        result = run_repl("fn twice(x) { return x * 2; }\nemit twice(21);\n.exit\n")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"42\n")

    def test_multiline_function_definition(self) -> None:
        script = (
            "fn add(a, b) {\n"
            "  return a + b;\n"
            "}\n"
            "emit add(3, 4);\n"
            ".exit\n"
        )
        result = run_repl(script)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"7\n")
        self.assertIn(b"...", result.stderr)

    def test_runtime_error_recovers_to_prompt(self) -> None:
        result = run_repl("emit missing;\nemit 7;\n.exit\n")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"7\n")
        self.assertIn(b"RuntimeError", result.stderr)
        self.assertIn(b"undefined variable", result.stderr)

    def test_syntax_error_clears_buffer_and_recovers(self) -> None:
        result = run_repl("let = 1;\nemit 9;\n.exit\n")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"9\n")
        self.assertIn(b"SyntaxError", result.stderr)

    def test_vars_lists_bindings(self) -> None:
        result = run_repl("let alpha = 1;\nlet beta = \"x\";\n.vars\n.exit\n")
        self.assertEqual(result.returncode, 0)
        err = result.stderr.decode("utf-8")
        self.assertIn("alpha = 1", err)
        # Top-level string display is unquoted, matching the runtime's emit form.
        self.assertIn("beta = x", err)

    def test_reset_discards_bindings_functions_and_records(self) -> None:
        script = (
            "record R { x }\nfn f() { return 1; }\nlet n = 5;\n"
            ".reset\n.vars\nemit f();\n.exit\n"
        )
        result = run_repl(script)
        self.assertEqual(result.returncode, 0)
        self.assertIn("(no bindings)", result.stderr.decode("utf-8"))
        self.assertIn(b"undefined function", result.stderr)

    def test_exit_and_eof_return_zero(self) -> None:
        by_exit = run_repl(".exit\n")
        self.assertEqual(by_exit.returncode, 0)
        by_eof = run_repl("emit 1;\n")
        self.assertEqual(by_eof.returncode, 0)
        self.assertEqual(by_eof.stdout, b"1\n")

    def test_stdout_carries_only_emit_output(self) -> None:
        result = run_repl("emit 1;\n.vars\n.help\n.exit\n")
        self.assertEqual(result.stdout, b"1\n")
        err = result.stderr.decode("utf-8")
        self.assertIn(">>> ", err)
        self.assertIn("LWT REPL commands", err)

    def test_help_lists_meta_commands(self) -> None:
        result = run_repl(".help\n.exit\n")
        self.assertEqual(result.returncode, 0)
        err = result.stderr.decode("utf-8")
        for command in (".help", ".vars", ".reset", ".exit"):
            self.assertIn(command, err)

    def test_meta_command_like_text_in_source_is_syntax_error(self) -> None:
        # A dot-prefixed token at top level is not a valid LWT statement; it
        # must be reported by the parser rather than treated as a meta command.
        result = run_repl(".unknown\n.emit\n.exit\n")
        self.assertEqual(result.returncode, 0)
        self.assertIn(b"SyntaxError", result.stderr)

    def test_repl_rejects_extra_arguments(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "lwt", "--repl", "extra.lwt"],
            cwd=REPOSITORY_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 4)
        self.assertIn(b"CliError", result.stderr)

    def test_dict_and_throw_work_in_repl(self) -> None:
        script = (
            'let d = dict{"a": 1};\nemit d;\n'
            'attempt { throw "x"; } recover (p) { emit p.category; } finally { emit "fin"; }\n'
            '.exit\n'
        )
        result = run_repl(script)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'dict{"a": 1}\nUser\nfin\n')


if __name__ == "__main__":
    unittest.main()
