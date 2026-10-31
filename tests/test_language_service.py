from __future__ import annotations

import tempfile
import unittest
import os
from pathlib import Path

from lwt.language_service import LanguageService
from lwt.lsp_documents import (
    codepoint_to_utf16_character,
    file_uri,
    path_from_file_uri,
    path_key,
    utf16_character_to_codepoint,
)


def position_of(text: str, marker: str, occurrence: int = 0) -> tuple[int, int]:
    start = -1
    for _ in range(occurrence + 1):
        start = text.index(marker, start + 1)
    prefix = text[:start]
    line = prefix.count("\n")
    line_text = prefix.rsplit("\n", 1)[-1].replace("\r", "")
    return line, codepoint_to_utf16_character(line_text, len(line_text))


class LanguageServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="lwt lsp 雪 ")
        self.root = Path(self.temporary.name)
        self.service = LanguageService()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def open(self, name: str, text: str, version: int = 1):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="")
        return self.service.open_document(file_uri(path), "lwt", version, text)

    def test_empty_diagnostics_symbols_hover_and_definition(self) -> None:
        text = 'record Task { title };\nfn greet(person) { return person; }\nlet task = Task{title: "雪"};\nlet result = greet(task.title);\nemit len(result);\n'
        doc = self.open("notes with space.lwt", text)
        diagnostics = self.service.analyze_open_documents()
        self.assertEqual(diagnostics[doc.uri], [])
        symbols = self.service.symbols(doc.uri)
        self.assertEqual([(item["name"], item["kind"]) for item in symbols], [("Task", 23), ("greet", 12), ("task", 13), ("result", 13)])
        line, character = position_of(text, "greet", 1)
        hover = self.service.hover(doc.uri, line, character)
        self.assertEqual(hover["contents"]["value"], "fn greet(person)")
        definition = self.service.definition(doc.uri, line, character)
        self.assertEqual(definition["uri"], doc.uri)
        self.assertEqual(definition["range"]["start"], {"line": 1, "character": 3})
        line, character = position_of(text, "len")
        self.assertEqual(self.service.hover(doc.uri, line, character)["contents"]["value"], "built-in len(string_or_array) -> integer")
        line, character = position_of(text, "Task", 1)
        self.assertEqual(self.service.definition(doc.uri, line, character)["range"]["start"], {"line": 0, "character": 7})
        line, character = position_of(text, "person", 1)
        self.assertEqual(self.service.definition(doc.uri, line, character)["range"]["start"], {"line": 1, "character": 9})
        line, character = position_of(text, "task", 1)
        self.assertEqual(self.service.definition(doc.uri, line, character)["range"]["start"], {"line": 2, "character": 4})

    def test_lexer_parser_and_static_diagnostics(self) -> None:
        cases = [
            ("lex.lwt", "emit @;\n", "LEX001"),
            ("syntax.lwt", "let x = 1\n", "PAR001"),
            ("static.lwt", "missing();\n", "STC010"),
        ]
        for filename, text, code in cases:
            with self.subTest(filename=filename):
                self.service = LanguageService()
                doc = self.open(filename, text)
                diagnostics = self.service.analyze_open_documents()[doc.uri]
                self.assertEqual([item["code"] for item in diagnostics], [code])
                self.assertEqual(diagnostics[0]["severity"], 1)
                self.assertEqual(diagnostics[0]["source"], "lwt")

    def test_syntax_error_clears_features_and_static_diagnostics(self) -> None:
        valid = "fn hello() { return 1; }\nhello();\n"
        doc = self.open("edit.lwt", valid + "missing();\n")
        self.assertEqual([item["code"] for item in self.service.analyze_open_documents()[doc.uri]], ["STC010"])
        self.assertEqual(len(self.service.symbols(doc.uri)), 1)
        self.service.change_document(doc.uri, 2, "fn hello( {\n")
        diagnostics = self.service.analyze_open_documents()[doc.uri]
        self.assertEqual([item["code"] for item in diagnostics], ["PAR001"])
        self.assertEqual(self.service.symbols(doc.uri), [])
        self.assertIsNone(self.service.hover(doc.uri, 0, 3))
        self.service.change_document(doc.uri, 3, valid)
        self.assertEqual(self.service.analyze_open_documents()[doc.uri], [])

    def test_module_overlay_overrides_disk_and_can_be_unsaved(self) -> None:
        main = self.open('main.lwt', 'import "lib.lwt" as m;\nm.fresh();\n')
        dep_path = self.root / "lib.lwt"
        dep = self.service.open_document(file_uri(dep_path), "lwt", 1, "fn fresh() { return 3; }\n")
        result = self.service.analyze_open_documents()
        self.assertEqual(result[main.uri], [])
        self.assertEqual(result[dep.uri], [])
        # No file was ever written to disk; successful import proves the overlay is authoritative.
        self.assertFalse(dep_path.exists())
        line, character = position_of(main.text, "fresh")
        definition = self.service.definition(main.uri, line, character)
        self.assertEqual(definition["uri"], dep.uri)
        self.assertEqual(definition["range"]["start"], {"line": 0, "character": 3})
        line, character = position_of(main.text, "m.fresh")
        alias_definition = self.service.definition(main.uri, line, character)
        self.assertEqual(alias_definition["range"]["start"], {"line": 0, "character": 20})
        self.assertEqual(self.service.hover(main.uri, line, character)["contents"]["value"], "module m -> lib.lwt")

    def test_did_close_restores_disk_dependency_version(self) -> None:
        dep_path = self.root / "lib.lwt"
        dep_path.write_text("fn disk() { return 1; }\n", encoding="utf-8")
        main = self.open('main.lwt', 'import "lib.lwt" as m;\nm.edited();\n')
        dep = self.service.open_document(file_uri(dep_path), "lwt", 1, "fn edited() { return 2; }\n")
        self.assertEqual(self.service.analyze_open_documents()[main.uri], [])
        self.service.close_document(dep.uri)
        diagnostics = self.service.analyze_open_documents()[main.uri]
        self.assertEqual([item["code"] for item in diagnostics], ["STC031"])

    def test_module_static_diagnostic_is_owned_by_dependency_uri(self) -> None:
        main = self.open('main.lwt', 'import "lib.lwt" as m;\nm.bad();\n')
        dep = self.open("lib.lwt", "fn bad() { missing(); }\n")
        diagnostics = self.service.analyze_open_documents()
        self.assertEqual(diagnostics[main.uri], [])
        self.assertEqual([item["code"] for item in diagnostics[dep.uri]], ["STC010"])

    def test_module_cycles_are_reported_without_traceback_or_absolute_path(self) -> None:
        a = self.open('a.lwt', 'import "b.lwt" as b;\n')
        b = self.open('b.lwt', 'import "a.lwt" as a;\n')
        diagnostics = self.service.analyze_open_documents()
        all_diagnostics = diagnostics[a.uri] + diagnostics[b.uri]
        self.assertTrue(any(item["code"] == "MOD001" for item in all_diagnostics))
        self.assertNotIn(str(self.root), str(all_diagnostics))

    def test_utf16_non_bmp_columns_in_diagnostic_hover_and_definition(self) -> None:
        text = 'let emoji = "😀"; emit missing();\n'
        doc = self.open("unicode.lwt", text)
        diagnostic = self.service.analyze_open_documents()[doc.uri][0]
        expected = len(text[: text.index("missing")].encode("utf-16-le")) // 2
        self.assertEqual(diagnostic["range"]["start"]["character"], expected)

        text = 'let emoji = "😀"; target();\nfn target() { return 1; }\n'
        self.service = LanguageService()
        doc = self.open("utf16.lwt", text)
        self.service.analyze_open_documents()
        line, character = position_of(text, "target")
        expected = len(text.splitlines()[0][:text.splitlines()[0].index("target")].encode("utf-16-le")) // 2
        self.assertEqual(character, expected)
        definition = self.service.definition(doc.uri, line, character)
        self.assertEqual(definition["range"]["start"], {"line": 1, "character": 3})
        self.assertEqual(self.service.hover(doc.uri, line, character)["contents"]["value"], "fn target()")
        # A position in the middle of the emoji's surrogate pair cannot hit a token.
        self.assertIsNone(self.service.hover(doc.uri, 0, text.splitlines()[0].index("😀") + 1))

    def test_each_recover_and_block_scopes_link_to_their_own_declarations(self) -> None:
        text = (
            "let outer = 1;\n"
            "fn f(arg) { { let local = arg; emit local; } return arg; }\n"
            "let values = [1]; each (item in values) { emit item; }\n"
            "attempt { fail(\"bad\"); } recover (problem) { emit problem.message; }\n"
            "f(outer);\n"
        )
        doc = self.open("scope.lwt", text)
        self.assertEqual(self.service.analyze_open_documents()[doc.uri], [])
        line, character = position_of(text, "local", 1)
        self.assertEqual(self.service.definition(doc.uri, line, character)["range"]["start"]["line"], 1)
        line, character = position_of(text, "local")
        self.assertEqual(self.service.definition(doc.uri, line, character)["range"]["start"]["line"], 1)
        line, character = position_of(text, "item", 1)
        self.assertEqual(self.service.definition(doc.uri, line, character)["range"]["start"]["line"], 2)
        line, character = position_of(text, "problem", 1)
        self.assertEqual(self.service.definition(doc.uri, line, character)["range"]["start"]["line"], 3)

    def test_analysis_is_static_for_io_and_runtime_builtins(self) -> None:
        doc = self.open('no-execute.lwt', 'emit input(); emit read_text("absent.txt"); fail("must not run");\n')
        before = self.service.analyze_open_documents()
        after = self.service.analyze_open_documents()
        self.assertEqual(before, after)
        self.assertEqual(before[doc.uri], [])

    def test_uri_unicode_spaces_and_path_equivalence(self) -> None:
        path = self.root / "中文 space #.lwt"
        uri = file_uri(path)
        self.assertEqual(path_key(path_from_file_uri(uri)), path_key(path))
        self.assertIn("%20", uri)
        self.assertIn("%E4%B8%AD", uri)

    @unittest.skipUnless(os.name == "nt", "Windows drive URI behavior is platform-specific")
    def test_windows_drive_file_uri(self) -> None:
        path = path_from_file_uri("file:///C:/Program%20Files/LWT%20%E9%9B%AA/main.lwt")
        self.assertEqual(path.drive.lower(), "c:")
        self.assertIn("Program Files", str(path))
        self.assertIn("雪", str(path))

    def test_crlf_and_lf_positions_agree(self) -> None:
        for ending in ("\n", "\r\n"):
            with self.subTest(ending=repr(ending)):
                self.service = LanguageService()
                text = f"let one = 1;{ending}emit missing();{ending}"
                doc = self.open(f"line-{len(ending)}.lwt", text)
                diag = self.service.analyze_open_documents()[doc.uri][0]
                self.assertEqual(diag["range"]["start"]["line"], 1)
                self.assertEqual(diag["code"], "STC010")

    def test_version_must_increase(self) -> None:
        doc = self.open("version.lwt", "emit 1;\n")
        with self.assertRaises(ValueError):
            self.service.change_document(doc.uri, 1, "emit 2;\n")
        with self.assertRaises(ValueError):
            self.service.change_document(doc.uri, 0, "emit 3;\n")
        self.assertEqual(doc.text, "emit 1;\n")

    def test_duplicate_open_does_not_replace_existing_overlay(self) -> None:
        doc = self.open("duplicate.lwt", "emit 1;\n")
        with self.assertRaises(ValueError):
            self.service.open_document(doc.uri, "lwt", 9, "emit 9;\n")
        self.assertIs(self.service.documents[doc.key], doc)
        self.assertEqual(doc.text, "emit 1;\n")

    def test_utf16_helpers(self) -> None:
        self.assertEqual(utf16_character_to_codepoint("a😀b", 3), 2)
        self.assertIsNone(utf16_character_to_codepoint("a😀b", 2))
        self.assertEqual(codepoint_to_utf16_character("a😀b", 2), 3)


if __name__ == "__main__":
    unittest.main()
