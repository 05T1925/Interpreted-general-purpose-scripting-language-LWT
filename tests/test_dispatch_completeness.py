"""S44 WP2: completeness of the runtime's AST-node type dispatch.

P0-3 replaces the long ``isinstance`` chains in ``_execute_statement`` and
``_evaluate`` with exact ``type(x) is T`` dispatch (the AST dataclasses have no
subclasses, so this is semantically identical). This test is the structural
guard: every member of the ``Expression``/``Statement`` union must have a
matching dispatch branch, the unknown-type ``AssertionError`` fallbacks must
remain, and the parser's literal pre-decoding (P0-4) must be consistent with
the runtime's INT evaluation.

It reads the source as text rather than executing hand-built AST nodes, so it
stays independent of parser/runtime internals while catching the real failure
mode: a newly added AST node that the evaluator silently does not handle.
"""

from __future__ import annotations

from pathlib import Path
import re
import unittest

from lwt import ast_nodes
from lwt._decimal import format_decimal_integer, parse_decimal_integer

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SOURCE = (REPO_ROOT / "lwt" / "runtime.py").read_text(encoding="utf-8")


def _function_body(name: str) -> str:
    """Return the source slice of a top-level function ``name``."""
    match = re.search(rf"^def {name}\(", RUNTIME_SOURCE, re.MULTILINE)
    if match is None:
        raise AssertionError(f"function {name}() not found")
    following = re.search(r"^def \w+\(", RUNTIME_SOURCE[match.end():], re.MULTILINE)
    end = match.end() + following.start() if following else len(RUNTIME_SOURCE)
    return RUNTIME_SOURCE[match.start():end]


def _dispatched_types(body: str, variable: str) -> set[str]:
    """Collect class names from ``type(<variable>) is <Class>`` predicates."""
    return set(re.findall(rf"type\({variable}\) is (?:not )?([A-Z]\w+)", body))


def _union_names(union_value: object) -> set[str]:
    # PEP 604 unions expose their members via __args__.
    args = getattr(union_value, "__args__", None)
    if args is None:
        raise AssertionError("Expression/Statement is not a PEP 604 union")
    return {arg.__name__ for arg in args}


class DispatchCompletenessTests(unittest.TestCase):
    def test_every_statement_type_is_dispatched(self) -> None:
        body = _function_body("_execute_statement")
        dispatched = _dispatched_types(body, "statement")
        expected = _union_names(ast_nodes.Statement)
        missing = expected - dispatched
        self.assertEqual(missing, set(), f"statement types missing dispatch: {sorted(missing)}")

    def test_every_expression_type_is_dispatched(self) -> None:
        body = _function_body("_evaluate")
        dispatched = _dispatched_types(body, "expression")
        expected = _union_names(ast_nodes.Expression)
        missing = expected - dispatched
        self.assertEqual(missing, set(), f"expression types missing dispatch: {sorted(missing)}")

    def test_unknown_statement_raises_assertion(self) -> None:
        body = _function_body("_execute_statement")
        self.assertIn("unsupported statement passed to evaluator", body)
        self.assertIn("raise AssertionError", body)

    def test_unknown_expression_raises_assertion(self) -> None:
        body = _function_body("_evaluate")
        self.assertIn("unsupported expression passed to evaluator", body)
        self.assertIn("raise AssertionError", body)

    def test_no_value_type_predicates_were_converted(self) -> None:
        # Value classes (_DictValue, _ErrorValue, ...) may rely on isinstance
        # semantics; P0-3 must only touch AST-node dispatch. Ensure none of
        # the value predicates were rewritten to `type(...) is`.
        body = _function_body("_evaluate")
        for value_class in ("_DictValue", "_ErrorValue", "_RecordValue", "_TaskValue", "_ChannelValue"):
            self.assertNotIn(f"type(receiver) is {value_class}", body)
            self.assertNotIn(f"type(value) is {value_class}", body)


class DecimalHelperTests(unittest.TestCase):
    """P0-4: shared chunked converters keep arbitrary-precision semantics."""

    def test_roundtrip_small_and_leading_zeros(self) -> None:
        self.assertEqual(parse_decimal_integer("000000000000000123"), 123)
        self.assertEqual(parse_decimal_integer("0"), 0)

    def test_roundtrip_large(self) -> None:
        digits = "9" * 6000
        value = parse_decimal_integer(digits)
        self.assertEqual(format_decimal_integer(value), digits)
        self.assertEqual(format_decimal_integer(-value), "-" + digits)

    def test_runtime_reexports_shared_helpers(self) -> None:
        from lwt.runtime import format_decimal_integer as r_fmt
        from lwt.runtime import parse_decimal_integer as r_parse

        self.assertIs(r_parse, parse_decimal_integer)
        self.assertIs(r_fmt, format_decimal_integer)

    def test_int_literals_are_predecoded_in_parsed_ast(self) -> None:
        from lwt.lexer import scan
        from lwt.parser import parse

        program = parse(scan("let n = 00042;\n", "probe.lwt"))
        let_stmt = program.items[0]
        literal = let_stmt.initializer
        self.assertIs(literal.value, 42)
        self.assertEqual(literal.lexeme, "00042")


if __name__ == "__main__":
    unittest.main()
