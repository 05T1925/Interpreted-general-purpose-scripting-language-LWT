from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]


def run_debugger(
    *arguments: str, input_data: bytes | None = None
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "lwt.debugger", *arguments],
        cwd=REPOSITORY,
        input=input_data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        timeout=8,
        check=False,
    )


def run_lwt(
    source: Path, *, stdin: bytes = b"", arguments: tuple[str, ...] = ()
) -> subprocess.CompletedProcess[bytes]:
    command = [sys.executable, "-m", "lwt", str(source)]
    if arguments:
        command.extend(("--", *arguments))
    return subprocess.run(
        command,
        cwd=REPOSITORY,
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        timeout=8,
        check=False,
    )


class DebuggerCliTests(unittest.TestCase):
    def make_workspace(
        self,
        directory: Path,
        source: str,
        commands: str,
        *,
        filename: str = "main.lwt",
        files: dict[str, str | bytes] | None = None,
        program_stdin: bytes | None = None,
        program_args: tuple[str, ...] = (),
    ) -> subprocess.CompletedProcess[bytes]:
        source_path = directory / filename
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(source, encoding="utf-8", newline="\n")
        for name, content in (files or {}).items():
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content, encoding="utf-8", newline="\n")
        command_path = directory / "debug commands.txt"
        command_text = commands.replace("{source}", str(source_path))
        command_text = command_text.replace(
            "{files}", str(directory)
        )
        command_path.write_text(command_text, encoding="utf-8", newline="\n")
        arguments = [
            "--commands",
            str(command_path),
        ]
        if program_stdin is not None:
            stdin_path = directory / "program input.txt"
            stdin_path.write_bytes(program_stdin)
            arguments.extend(("--program-stdin", str(stdin_path)))
        arguments.append(str(source_path))
        if program_args:
            arguments.extend(("--", *program_args))
        return run_debugger(*arguments)

    def test_help_is_stable_and_does_not_require_source(self) -> None:
        result = run_debugger("--help")
        self.assertEqual(result.returncode, 0)
        help_text = result.stdout.decode("utf-8")
        for command in ("continue | c", "step | s", "next | n", "finish | out", "break | b", "print | p"):
            self.assertIn(command, help_text)
        self.assertNotIn(b"Traceback", result.stderr)

    def test_checked_in_example_matches_the_normal_lwt_cli(self) -> None:
        example = REPOSITORY / "examples" / "debugger"
        source = example / "main.lwt"
        commands = example / "session.txt"
        program_stdin = example / "program-input.txt"
        debug = run_debugger(
            "--commands",
            str(commands),
            "--program-stdin",
            str(program_stdin),
            str(source),
        )
        normal = run_lwt(source, stdin=program_stdin.read_bytes())
        self.assertEqual(debug.returncode, 0)
        self.assertEqual(debug.returncode, normal.returncode)
        self.assertEqual(debug.stdout, normal.stdout)
        self.assertEqual(debug.stdout, b"demo:5\n")
        self.assertIn(b"Stopped (breakpoint 1)", debug.stderr)
        self.assertNotIn(b"Stopped", debug.stdout)

    def test_cli_and_utf8_input_file_errors_use_exit_four(self) -> None:
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            directory = Path(temp)
            bad_commands = directory / "bad commands.txt"
            bad_commands.write_bytes(b"\xff")
            bad_input = directory / "bad input.txt"
            bad_input.write_bytes(b"\xff")
            source = directory / "main.lwt"
            source.write_text('emit "ok";\n', encoding="utf-8")

            no_source = run_debugger()
            missing_source = run_debugger(str(directory / "missing source.lwt"))
            invalid_commands = run_debugger("--commands", str(bad_commands), str(source))
            (directory / "valid.txt").write_text("continue\n", encoding="utf-8")
            invalid_input = run_debugger(
                "--commands",
                str(directory / "valid.txt"),
                "--program-stdin",
                str(bad_input),
                str(source),
            )
            missing_commands = run_debugger(
                "--commands", str(directory / "missing.txt"), str(source)
            )
        self.assertEqual(no_source.returncode, 4)
        self.assertIn(b"expected a source path", no_source.stderr)
        self.assertEqual(missing_source.returncode, 4)
        self.assertIn(b"cannot read source file", missing_source.stderr)
        self.assertEqual(invalid_commands.returncode, 4)
        self.assertIn(b"not valid UTF-8", invalid_commands.stderr)
        self.assertEqual(invalid_input.returncode, 4)
        self.assertIn(b"program stdin file is not valid UTF-8", invalid_input.stderr)
        self.assertEqual(missing_commands.returncode, 4)
        for result in (
            no_source,
            missing_source,
            invalid_commands,
            invalid_input,
            missing_commands,
        ):
            self.assertNotIn(b"Traceback", result.stderr)

    def test_empty_command_unknown_command_and_bad_arity_are_recoverable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            result = self.make_workspace(
                Path(temp),
                'emit "ok";\n',
                "\nwat\nlocals extra\ncontinue\n",
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"ok\n")
        self.assertIn(b"DebugError: empty command", result.stderr)
        self.assertIn(b"DebugError: unknown command 'wat'", result.stderr)
        self.assertIn(b"DebugError: locals takes no arguments", result.stderr)

    def test_utf8_command_script_bom_and_cr_only_lines(self) -> None:
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            result = self.make_workspace(
                Path(temp), 'emit "ok";\n', "\ufeffhelp\rcontinue\r"
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"ok\n")
        self.assertIn(b"LWT source debugger commands:", result.stderr)
        self.assertNotIn(b"unknown command", result.stderr)

    def test_empty_command_script_and_quit_cancel_without_running_program(self) -> None:
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            root = Path(temp)
            empty = self.make_workspace(root, 'emit "not run";\n', "")
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            quit_result = self.make_workspace(
                Path(temp), 'emit "not run";\n', "quit\n"
            )
        self.assertEqual(empty.returncode, 1)
        self.assertIn(b"command input ended while the program was paused", empty.stderr)
        self.assertEqual(quit_result.returncode, 1)
        self.assertIn(b"session cancelled by user", quit_result.stderr)
        self.assertEqual(empty.stdout, b"")
        self.assertEqual(quit_result.stdout, b"")
        self.assertNotIn(b"Traceback", empty.stderr + quit_result.stderr)

    def test_exact_entry_breakpoint_continue_does_not_rehit_current_node(self) -> None:
        with tempfile.TemporaryDirectory(prefix="LWT debugger path ") as temp:
            result = self.make_workspace(
                Path(temp),
                'emit "once";\nemit "twice";\n',
                'break "{source}:1"\nbreak "{source}:99"\nbreakpoints\ncontinue\n',
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"once\ntwice\n")
        diagnostics = result.stderr.decode("utf-8")
        self.assertIn("Breakpoint 1 verified", diagnostics)
        self.assertIn("Breakpoint 2 unmapped", diagnostics)
        self.assertIn("line has no executable statement", diagnostics)
        self.assertEqual(diagnostics.count("Stopped (breakpoint"), 0)
        self.assertNotIn(b"Traceback", result.stderr)

    def test_breakpoint_pauses_before_exact_entry_statement(self) -> None:
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            result = self.make_workspace(
                Path(temp),
                'let first = 1;\nemit first;\n',
                'break "{source}:2"\ncontinue\ncontinue\n',
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"1\n")
        self.assertIn(b"Stopped (breakpoint 1)", result.stderr)
        self.assertIn(b"=> 2 | emit first;", result.stderr)

    def test_same_line_breakpoint_maps_only_first_executable_statement(self) -> None:
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            result = self.make_workspace(
                Path(temp),
                "let value = 6; emit value;\n",
                'break "{source}:1"\nstep\ncontinue\n',
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"6\n")
        self.assertIn(b"Stopped (step)", result.stderr)
        self.assertNotIn(b"Stopped (breakpoint 1)", result.stderr)

    def test_breakpoint_delete_and_nonexistent_id(self) -> None:
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            result = self.make_workspace(
                Path(temp),
                'emit "one";\nemit "two";\n',
                'break "{source}:2"\ndelete 1\ndelete 1\nbreakpoints\ncontinue\n',
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"one\ntwo\n")
        self.assertIn(b"Deleted breakpoint 1", result.stderr)
        self.assertIn(b"no breakpoint with id 1", result.stderr)
        self.assertIn(b"Breakpoints: <none>", result.stderr)

    def test_loop_breakpoint_repeats_when_control_flow_reenters_statement(self) -> None:
        source = (
            "let i = 0;\n"
            "while (i < 2) {\n"
            "  emit i;\n"
            "  i = i + 1;\n"
            "}\n"
            'emit "done";\n'
        )
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            result = self.make_workspace(
                Path(temp), source, 'break "{source}:3"\ncontinue\nwhere\ncontinue\ncontinue\n'
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"0\n1\ndone\n")
        self.assertEqual(result.stderr.count(b"Stopped (breakpoint 1)"), 2)
        self.assertIn(b"<entry>", result.stderr)

    def test_step_next_finish_and_frame_local_scope_match_normal_execution(self) -> None:
        source = (
            "fn add(n) {\n"
            "  let x = n + 1;\n"
            "  emit x;\n"
            "  return x;\n"
            "}\n"
            "let initial = 2;\n"
            "let result = add(initial);\n"
            "emit result;\n"
        )
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            root = Path(temp)
            debug = self.make_workspace(
                root,
                source,
                "next\nstep\nlocals\nwhere\nfinish\nglobals\ncontinue\n",
            )
            source_path = root / "main.lwt"
            normal = run_lwt(source_path)
        self.assertEqual(debug.returncode, normal.returncode)
        self.assertEqual(debug.stdout, normal.stdout)
        self.assertEqual(debug.stdout, b"3\n3\n")
        self.assertIn(b"Stopped (step)", debug.stderr)
        self.assertIn(b"  n = 2", debug.stderr)
        self.assertIn(b"fn add", debug.stderr)
        self.assertIn(b"Stopped (finish)", debug.stderr)
        self.assertIn(b"initial = 2", debug.stderr)
        self.assertIn(b"result = 3", debug.stderr)

    def test_next_skips_called_function_and_stops_in_caller(self) -> None:
        source = (
            'fn announce() { emit "inside"; }\n'
            "let result = announce();\n"
            'emit "after";\n'
        )
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            root = Path(temp)
            debug = self.make_workspace(root, source, "next\ncontinue\n")
            normal = run_lwt(root / "main.lwt")
        self.assertEqual(debug.returncode, normal.returncode)
        self.assertEqual(debug.stdout, normal.stdout)
        self.assertEqual(debug.stdout, b"inside\nafter\n")
        self.assertIn(b"Stopped (next)", debug.stderr)
        self.assertIn(b"=> 3 | emit \"after\";", debug.stderr)

    def test_finish_is_rejected_in_entry_frame_without_ending_session(self) -> None:
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            result = self.make_workspace(
                Path(temp), 'emit "done";\n', "finish\ncontinue\n"
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"done\n")
        self.assertIn(b"finish is unavailable in the entry frame", result.stderr)

    def test_finish_at_program_end_completes_without_synthetic_stop(self) -> None:
        source = "fn answer() {\n  return 42;\n}\nlet result = answer();\n"
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            result = self.make_workspace(
                Path(temp), source, 'break "{source}:2"\ncontinue\nfinish\n'
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"Stopped (breakpoint 1)", result.stderr)
        self.assertNotIn(b"Stopped (finish)", result.stderr)

    def test_module_breakpoint_supports_windows_colon_unicode_path_and_stack(self) -> None:
        with tempfile.TemporaryDirectory(prefix="LWT 调试 space ") as temp:
            root = Path(temp)
            source = (
                'import "雪 helpers.lwt" as lib;\n'
                "let input = 4;\n"
                "let output = lib.bump(input);\n"
                "emit output;\n"
            )
            library = "fn bump(value) {\n  let result = value + 1;\n  return result;\n}\n"
            result = self.make_workspace(
                root,
                source,
                'break "{files}/雪 helpers.lwt:2"\ncontinue\nwhere\nlocals\ncontinue\n',
                files={"雪 helpers.lwt": library},
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"5\n")
        self.assertIn(b"Breakpoint 1 verified", result.stderr)
        self.assertIn(b"fn lib.bump", result.stderr)
        self.assertIn(b"value = 4", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)

    def test_locals_globals_shadowing_and_print_are_read_only(self) -> None:
        source = (
            'let shared = "global";\n'
            "fn inspect(parameter) {\n"
            "  let local = 7;\n"
            "  {\n"
            "    let shadow = 9;\n"
            "    emit shadow;\n"
            "  }\n"
            "  return parameter;\n"
            "}\n"
            "let result = inspect(shared);\n"
            "emit result;\n"
        )
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            result = self.make_workspace(
                Path(temp),
                source,
                'break "{source}:6"\ncontinue\nlocals\nglobals\nprint shared\nprint parameter + 1\nprint unknown\ncontinue\n',
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"9\nglobal\n")
        text = result.stderr.decode("utf-8")
        self.assertIn("  local = 7", text)
        self.assertIn("  parameter = \"global\"", text)
        self.assertIn("  shadow = 9", text)
        self.assertIn("Globals:", text)
        self.assertIn('shared = "global"', text)
        self.assertNotIn("  result = ", text)
        self.assertIn("usage: print IDENTIFIER", text)
        self.assertIn("variable 'unknown' is not visible here", text)

    def test_module_globals_are_independent_from_entry_globals(self) -> None:
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            result = self.make_workspace(
                Path(temp),
                'import "lib.lwt" as lib;\nlet main_value = 3;\nlet answer = lib.read(main_value);\nemit answer;\n',
                'break "{files}/lib.lwt:2"\ncontinue\nglobals\nlocals\nprint main_value\ncontinue\n',
                files={
                    "lib.lwt": "fn read(input) {\n  return input;\n}\n"
                },
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"3\n")
        self.assertIn(b"Globals:\n  <empty>", result.stderr)
        self.assertIn(b"input = 3", result.stderr)
        self.assertIn(b"variable 'main_value' is not visible here", result.stderr)

    def test_recursive_stack_has_only_lwt_frames(self) -> None:
        source = (
            "fn descend(n) {\n"
            "  when (n > 0) { return descend(n - 1); }\n"
            "  return n;\n"
            "}\n"
            "let result = descend(2);\n"
            "emit result;\n"
        )
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            result = self.make_workspace(
                Path(temp), source, 'break "{source}:3"\ncontinue\nwhere\nlocals\ncontinue\n'
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"0\n")
        stack = result.stderr.decode("utf-8")
        self.assertGreaterEqual(stack.count("fn descend"), 3)
        self.assertIn("n = 0", stack)
        self.assertNotIn("runtime.py", stack)
        self.assertNotIn("Traceback", stack)

    def test_each_and_recover_bindings_are_visible_only_in_their_active_scope(self) -> None:
        source = (
            "let values = [2];\n"
            "each (item in values) {\n"
            "  emit item;\n"
            "}\n"
            'attempt { fail("bad"); } recover (problem) {\n'
            "  emit problem.category;\n"
            "}\n"
        )
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            root = Path(temp)
            source_path = root / "main.lwt"
            result = self.make_workspace(
                root,
                source,
                'break "{source}:3"\nbreak "{source}:6"\ncontinue\nlocals\ncontinue\nlocals\ncontinue\n',
            )
            normal = run_lwt(source_path)
        self.assertEqual(result.returncode, normal.returncode)
        self.assertEqual(result.stdout, normal.stdout)
        stderr = result.stderr.decode("utf-8")
        self.assertIn("item = 2", stderr)
        self.assertIn("problem = Error{category: \"RuntimeError\"", stderr)

    def test_composite_error_cycle_and_long_values_are_safely_displayed(self) -> None:
        long_text = "x" * 400
        source = (
            "record Box { value };\n"
            "let cycle = [];\n"
            "push(cycle, cycle);\n"
            "let box = Box{value: cycle};\n"
            f'let long_text = "{long_text}";\n'
            'attempt { fail("bad"); } recover (problem) {\n'
            '  emit "ready";\n'
            "}\n"
            'emit "done";\n'
        )
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            result = self.make_workspace(
                Path(temp),
                source,
                'break "{source}:7"\ncontinue\nlocals\nglobals\nprint box\nprint cycle\nprint problem\nprint long_text\ncontinue\n',
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"ready\ndone\n")
        text = result.stderr.decode("utf-8")
        self.assertIn("problem = Error{category: \"RuntimeError\"", text)
        self.assertIn("Box{value: [<cycle>]}", text)
        self.assertIn("[<cycle>]", text)
        self.assertIn("[truncated]", text)
        self.assertNotIn("Traceback", text)

    def test_program_stdin_is_separate_and_debug_output_never_uses_stdout(self) -> None:
        source = 'let line = input();\nemit line;\n'
        payload = "program input 雪\r\n".encode("utf-8")
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            root = Path(temp)
            debug = self.make_workspace(
                root, source, "continue\n", program_stdin=payload
            )
            normal = run_lwt(root / "main.lwt", stdin=payload)
        self.assertEqual(debug.returncode, normal.returncode)
        self.assertEqual(debug.stdout, normal.stdout)
        self.assertEqual(debug.stdout, "program input 雪\n".encode("utf-8"))
        self.assertNotIn(b"Stopped", debug.stdout)
        self.assertIn(b"Stopped (entry)", debug.stderr)

    def test_missing_program_stdin_is_eof_not_debug_command_input(self) -> None:
        source = "emit input();\n"
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            root = Path(temp)
            debug = self.make_workspace(root, source, "continue\n")
            normal = run_lwt(root / "main.lwt")
        self.assertEqual(debug.returncode, normal.returncode)
        self.assertEqual(debug.stdout, normal.stdout)
        self.assertEqual(debug.stdout, b"null\n")

    def test_console_stdin_is_for_commands_and_program_input_defaults_to_eof(self) -> None:
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            source = Path(temp) / "main.lwt"
            source.write_text("emit input();\n", encoding="utf-8")
            debug = run_debugger(str(source), input_data=b"continue\n")
            normal = run_lwt(source)
        self.assertEqual(debug.returncode, normal.returncode)
        self.assertEqual(debug.stdout, normal.stdout)
        self.assertEqual(debug.stdout, b"null\n")
        self.assertIn(b"Stopped (entry)", debug.stderr)

    def test_args_after_separator_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            root = Path(temp)
            debug = self.make_workspace(
                root,
                "emit args();\n",
                "continue\n",
                program_args=("two words", "--", "雪"),
            )
            normal = run_lwt(
                root / "main.lwt", arguments=("two words", "--", "雪")
            )
        self.assertEqual(debug.returncode, normal.returncode)
        self.assertEqual(debug.stdout, normal.stdout)
        self.assertEqual(debug.stdout, '["two words", "--", "雪"]\n'.encode("utf-8"))

    def test_runtime_error_exit_and_program_output_match_normal_cli(self) -> None:
        source = 'emit "before";\nemit 1 / 0;\n'
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            root = Path(temp)
            debug = self.make_workspace(root, source, "continue\n")
            normal = run_lwt(root / "main.lwt")
        self.assertEqual(debug.returncode, 3)
        self.assertEqual(debug.returncode, normal.returncode)
        self.assertEqual(debug.stdout, normal.stdout)
        self.assertEqual(debug.stdout, b"before\n")
        self.assertTrue(debug.stderr.decode("utf-8").rstrip().endswith("RuntimeError: division by zero"))
        self.assertNotIn(b"Traceback", debug.stderr)

    def test_parser_error_keeps_exit_two_and_never_shows_traceback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            result = self.make_workspace(
                Path(temp), 'emit "unterminated\n', "continue\n"
            )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"LexError:", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)

    def test_complex_control_flow_and_recovery_keep_normal_output(self) -> None:
        source = (
            "let items = [1, 2, 3];\n"
            "let total = 0;\n"
            "each (item in items) {\n"
            "  when (item == 2) { continue; }\n"
            "  total = total + item;\n"
            "}\n"
            'attempt { fail("handled"); } recover (problem) {\n'
            "  emit problem.category;\n"
            "}\n"
            "emit total;\n"
        )
        with tempfile.TemporaryDirectory(prefix="LWT debugger ") as temp:
            root = Path(temp)
            debug = self.make_workspace(root, source, "continue\n")
            normal = run_lwt(root / "main.lwt")
        self.assertEqual(debug.returncode, normal.returncode)
        self.assertEqual(debug.stdout, normal.stdout)
        self.assertEqual(debug.stdout, b"RuntimeError\n4\n")
        self.assertNotIn(b"Traceback", debug.stderr)


if __name__ == "__main__":
    unittest.main()
