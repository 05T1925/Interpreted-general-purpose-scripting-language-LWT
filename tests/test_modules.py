from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lwt.ast_nodes import FieldExpression, ImportDeclaration, ModuleCallExpression
from lwt.errors import LwtError
from lwt.lexer import scan
from lwt.modules import load_module_graph
from lwt.parser import parse
from lwt.runtime import execute


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def run_lwt(source_path: Path) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "lwt", str(source_path)],
        cwd=REPOSITORY_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={
            **os.environ,
            "PYTHONPATH": str(REPOSITORY_ROOT)
            + os.pathsep
            + os.environ.get("PYTHONPATH", ""),
        },
        timeout=5,
        check=False,
        shell=False,
    )


class ModuleCliBoundaryTests(unittest.TestCase):
    def test_absolute_import_path_is_rejected_at_import_site(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = root / "main.lwt"
            absolute = (root / "lib.lwt").as_posix()
            entry.write_text(f'import "{absolute}" as lib;\n', encoding="utf-8")
            (root / "lib.lwt").write_text('fn value() { return 1; }\n', encoding="utf-8")
            result = run_lwt(entry)
        self.assertEqual(result.returncode, 4)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{entry}:1:1: ImportError: module path must be relative\n",
        )
        self.assertNotIn(b"Traceback", result.stderr)

    def test_invalid_path_string_is_reported_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            entry = Path(directory) / "main.lwt"
            entry.write_text('import "bad\x00name.lwt" as bad;\n', encoding="utf-8")
            result = run_lwt(entry)

        self.assertEqual(result.returncode, 4)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"ImportError:", result.stderr)
        self.assertIn(b"module path", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)

    def test_invalid_utf8_dependency_is_load_error_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = root / "main.lwt"
            entry.write_text('import "bad.lwt" as bad;\nemit "not reached";\n', encoding="utf-8")
            (root / "bad.lwt").write_bytes(b"fn bad() { \xff }\n")
            result = run_lwt(entry)
        self.assertEqual(result.returncode, 4)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(
            result.stderr.decode("utf-8"),
            f"{entry}:1:1: ImportError: cannot load module 'bad.lwt': module file is not valid UTF-8\n",
        )

    def test_read_text_inside_module_keeps_process_cwd_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = root / "main.lwt"
            module = root / "lib.lwt"
            entry.write_text('import "lib.lwt" as lib; emit lib.read();', encoding="utf-8")
            module.write_text(
                'fn read() { return read_text("tests/cases/modules/fixtures/data.txt"); }',
                encoding="utf-8",
            )
            result = run_lwt(entry)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"cwd data\n\n")
        self.assertEqual(result.stderr, b"")

    def test_alias_and_canonical_module_loads_do_not_duplicate_namespaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = root / "main.lwt"
            (root / "lib.lwt").write_text('fn value() { return "ok"; }', encoding="utf-8")
            entry.write_text(
                'import "lib.lwt" as first; import "./lib.lwt" as second; '
                'emit first.value(); emit second.value();',
                encoding="utf-8",
            )
            result = run_lwt(entry)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"ok\nok\n")
        self.assertEqual(result.stderr, b"")


class ModuleParserTests(unittest.TestCase):
    def test_import_and_qualified_call_have_distinct_ast_from_record_field(self) -> None:
        program = parse(
            scan('import "lib.lwt" as lib; let x = lib.get(); emit item.name;')
        )

        self.assertIsInstance(program.items[0], ImportDeclaration)
        initializer = program.items[1].initializer
        self.assertIsInstance(initializer, ModuleCallExpression)
        field = program.items[2].value
        self.assertIsInstance(field, FieldExpression)

    def test_library_module_rejects_executable_top_level_with_its_path(self) -> None:
        tokens = scan('fn ok() {}\nemit "no";', "lib/unsafe.lwt")

        with self.assertRaises(LwtError) as caught:
            parse(tokens, module_mode=True)

        self.assertEqual(caught.exception.category, "SyntaxError")
        self.assertEqual(caught.exception.exit_code, 2)
        self.assertEqual(caught.exception.location.source_path, "lib/unsafe.lwt")
        self.assertEqual(caught.exception.location.line, 2)


class ModuleRuntimeTests(unittest.TestCase):
    def test_module_error_keeps_module_location_and_entry_output_is_not_preflighted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = root / "main.lwt"
            entry.write_text(
                'import "lib.lwt" as lib;\nemit "before";\nemit lib.explode();\n',
                encoding="utf-8",
            )
            (root / "lib.lwt").write_text(
                "fn explode() {\n  return 1 / 0;\n}\n", encoding="utf-8"
            )
            graph = load_module_graph(str(entry))
            output = io.StringIO()

            with self.assertRaises(LwtError) as caught:
                execute(graph.entry.program, io.BytesIO(), output, module_graph=graph)

        self.assertEqual(output.getvalue(), "before\n")
        self.assertEqual(caught.exception.category, "RuntimeError")
        self.assertEqual(caught.exception.exit_code, 3)
        self.assertEqual(caught.exception.location.source_path, "lib.lwt")
        self.assertEqual(caught.exception.location.line, 2)

    def test_canonical_module_is_loaded_once_but_can_have_two_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "lib.lwt").write_text("fn value() { return 1; }", encoding="utf-8")
            entry = root / "main.lwt"
            entry.write_text(
                'import "lib.lwt" as first; import "./lib.lwt" as second; '
                'emit first.value() + second.value();',
                encoding="utf-8",
            )
            graph = load_module_graph(str(entry))
            output = io.StringIO()
            execute(graph.entry.program, io.BytesIO(), output, module_graph=graph)

        self.assertEqual(len(graph.modules), 2)
        self.assertEqual(output.getvalue(), "2\n")


if __name__ == "__main__":
    unittest.main()
