from __future__ import annotations

import unittest

from lwt.ast_nodes import (
    ArrayExpression,
    AssignmentExpression,
    BinaryExpression,
    Block,
    CallExpression,
    EachStatement,
    EmitStatement,
    ExpressionStatement,
    FieldExpression,
    FunctionDeclaration,
    IndexExpression,
    LetStatement,
    LiteralExpression,
    RecordConstructionExpression,
    RecordDeclaration,
    ReturnStatement,
    UnaryExpression,
    VariableExpression,
    WhenStatement,
    WhileStatement,
)
from lwt.errors import LwtError, SourceLocation
from lwt.lexer import TokenKind, scan
from lwt.parser import parse


def parse_source(source: str):
    return parse(scan(source))


class ParserStructureTests(unittest.TestCase):
    def test_empty_program_and_empty_nested_blocks(self) -> None:
        for source in ("", " \t\n# comment"):
            with self.subTest(source=source):
                program = parse_source(source)
                self.assertEqual(program.items, ())
                self.assertEqual(
                    program.location,
                    SourceLocation(source.count("\n") + 1, len(source.rsplit("\n", 1)[-1]) + 1),
                )

        program = parse_source("{} { { } }")
        self.assertIsInstance(program.items[0], Block)
        self.assertEqual(program.items[0].statements, ())
        outer = program.items[1]
        self.assertIsInstance(outer, Block)
        self.assertIsInstance(outer.statements[0], Block)
        self.assertEqual(outer.statements[0].statements, ())

    def test_top_level_declarations_and_statements_keep_source_order(self) -> None:
        program = parse_source(
            "record First {}; let before = 0; fn work() {} "
            "record Second { value }; emit missing; fn later(x) { return x; }"
        )
        self.assertEqual(
            [type(item) for item in program.items],
            [RecordDeclaration, LetStatement, FunctionDeclaration,
             RecordDeclaration, EmitStatement, FunctionDeclaration],
        )
        self.assertEqual(program.items[0].name.name, "First")
        self.assertEqual(program.items[3].name.name, "Second")
        self.assertEqual(program.items[4].value.name.name, "missing")
        later = program.items[5]
        self.assertEqual(later.parameters[0].name, "x")
        self.assertIsInstance(later.body.statements[0], ReturnStatement)

    def test_record_function_and_all_statement_forms(self) -> None:
        program = parse_source(
            "record Pair { left, right };"
            "fn visit(items) {"
            "let count = 0; return; emit count; count = count + 1;"
            "when (true) { emit items[0]; } otherwise { while (false) {} }"
            "each (item in items) { { emit item; } }"
            "}"
        )
        record, function = program.items
        self.assertEqual([field.name for field in record.fields], ["left", "right"])
        self.assertEqual([parameter.name for parameter in function.parameters], ["items"])
        body = function.body.statements
        self.assertEqual(
            [type(statement) for statement in body],
            [LetStatement, ReturnStatement, EmitStatement, ExpressionStatement,
             WhenStatement, EachStatement],
        )
        self.assertIsNone(body[1].value)
        self.assertIsInstance(body[3].expression, AssignmentExpression)
        branch = body[4]
        self.assertIsInstance(branch, WhenStatement)
        self.assertIsInstance(branch.otherwise_branch.statements[0], WhileStatement)
        loop = body[5]
        self.assertIsInstance(loop, EachStatement)
        self.assertEqual(loop.variable.name, "item")
        self.assertIsInstance(loop.body.statements[0], Block)

    def test_empty_lists_and_every_primary_expression_are_represented(self) -> None:
        program = parse_source(
            'fn empty() {} emit 12; emit "text"; emit true; emit false; emit null; '
            'emit []; emit [1, 2]; emit Empty{}; emit Empty{x: 1}; '
            'emit call(); emit call(1, 2); emit values[0]; emit value.field; '
            'emit call()[0].field;'
        )
        self.assertEqual(program.items[0].parameters, ())
        expressions = [item.value for item in program.items[1:]]
        self.assertEqual(expressions[0].kind, TokenKind.INT)
        self.assertEqual(expressions[0].lexeme, "12")
        self.assertEqual(expressions[1].value, "text")
        self.assertEqual(expressions[2].value, True)
        self.assertEqual(expressions[3].value, False)
        self.assertEqual(expressions[4].kind, TokenKind.NULL)
        self.assertIsNone(expressions[4].value)
        self.assertEqual(expressions[5].elements, ())
        self.assertEqual(len(expressions[6].elements), 2)
        self.assertIsInstance(expressions[7], RecordConstructionExpression)
        self.assertEqual(expressions[7].fields, ())
        self.assertIsInstance(expressions[8], RecordConstructionExpression)
        self.assertEqual(expressions[9].arguments, ())
        self.assertEqual(len(expressions[10].arguments), 2)
        self.assertIsInstance(expressions[11], IndexExpression)
        self.assertIsInstance(expressions[12], FieldExpression)
        self.assertIsInstance(expressions[13], FieldExpression)
        self.assertIsInstance(expressions[13].object, IndexExpression)
        self.assertIsInstance(expressions[13].object.object, CallExpression)

    def test_expression_precedence_and_associativity(self) -> None:
        program = parse_source(
            "emit -a * b; emit a = b = 1; emit a or b and c; "
            "emit a == b != c; emit a < b < c; emit a + b - c; "
            "emit a * b / c % d; emit not not ready; "
            "emit a <= b; emit a > b; emit a >= b;"
        )
        expressions = [item.value for item in program.items]

        negative_product = expressions[0]
        self.assertIsInstance(negative_product, BinaryExpression)
        self.assertEqual(negative_product.operator, TokenKind.STAR)
        self.assertIsInstance(negative_product.left, UnaryExpression)
        self.assertEqual(negative_product.left.operator, TokenKind.MINUS)

        assignment = expressions[1]
        self.assertIsInstance(assignment, AssignmentExpression)
        self.assertEqual(assignment.target.name.name, "a")
        self.assertIsInstance(assignment.value, AssignmentExpression)
        self.assertEqual(assignment.value.target.name.name, "b")
        self.assertEqual(assignment.operator_location, SourceLocation(1, 21))

        disjunction = expressions[2]
        self.assertEqual(disjunction.operator, TokenKind.OR)
        self.assertIsInstance(disjunction.right, BinaryExpression)
        self.assertEqual(disjunction.right.operator, TokenKind.AND)
        for chain in expressions[3:7]:
            self.assertIsInstance(chain, BinaryExpression)
            self.assertIsInstance(chain.left, BinaryExpression)
        double_not = expressions[7]
        self.assertEqual(double_not.operator, TokenKind.NOT)
        self.assertIsInstance(double_not.operand, UnaryExpression)
        self.assertEqual(
            [expression.operator for expression in expressions[8:]],
            [TokenKind.LESS_EQUAL, TokenKind.GREATER, TokenKind.GREATER_EQUAL],
        )

    def test_assignable_targets_and_postfix_chaining(self) -> None:
        program = parse_source(
            "x = 1; a[0] = 1; r.x = 2; get_array()[0].field = 3;"
        )
        assignments = [item.expression for item in program.items]
        self.assertTrue(all(isinstance(item, AssignmentExpression) for item in assignments))
        final_target = assignments[-1].target
        self.assertIsInstance(final_target, FieldExpression)
        self.assertIsInstance(final_target.object, IndexExpression)
        self.assertIsInstance(final_target.object.object, CallExpression)

    def test_token_locations_are_retained_for_names_and_expression_operators(self) -> None:
        program = parse_source("fn f(arg) { emit arg + 1; }")
        function = program.items[0]
        self.assertEqual(function.name.location, SourceLocation(1, 4))
        self.assertEqual(function.parameters[0].location, SourceLocation(1, 6))
        value = function.body.statements[0].value
        self.assertEqual(value.left.name.location, SourceLocation(1, 18))
        self.assertEqual(value.operator_location, SourceLocation(1, 22))

    def test_long_integer_is_retained_without_conversion(self) -> None:
        digits = "9" * 6000
        expression = parse_source(f"emit {digits};").items[0].value
        self.assertIsInstance(expression, LiteralExpression)
        self.assertEqual(expression.kind, TokenKind.INT)
        self.assertIsNone(expression.value)
        self.assertEqual(expression.lexeme, digits)

    def test_duplicate_constructor_fields_are_kept_in_order(self) -> None:
        fields = parse_source("emit Person{name: 1, name: 2};").items[0].value.fields
        self.assertEqual([field.name.name for field in fields], ["name", "name"])
        self.assertEqual([field.value.lexeme for field in fields], ["1", "2"])
        self.assertEqual([field.location.column for field in fields], [13, 22])

    def test_parser_does_not_resolve_names_or_top_level_registration(self) -> None:
        program = parse_source(
            "fn same() {} fn same() {} record T {}; record T {}; "
            "emit unknown_function(unknown_record{unknown_field: unknown_value});"
        )
        self.assertEqual(len(program.items), 5)
        self.assertIsInstance(program.items[-1].value, CallExpression)


class ParserErrorTests(unittest.TestCase):
    def assert_syntax_error(
        self, source: str, expected: SourceLocation | None = None
    ) -> LwtError:
        with self.assertRaises(LwtError) as caught:
            parse_source(source)
        error = caught.exception
        self.assertEqual(error.category, "SyntaxError")
        self.assertEqual(error.exit_code, 2)
        if expected is not None:
            self.assertEqual(error.location, expected)
        return error

    def test_record_declaration_duplicate_field_points_to_second_name(self) -> None:
        source = "record Person {name, name};"
        self.assert_syntax_error(source, SourceLocation(1, source.rfind("name") + 1))
        self.assertEqual(
            parse_source("record Person {name, age};").items[0].fields[1].name,
            "age",
        )

    def test_duplicate_parameter_points_to_second_name(self) -> None:
        source = "fn f(first, second, first) {}"
        self.assert_syntax_error(source, SourceLocation(1, source.rfind("first") + 1))

    def test_duplicate_lists_are_rejected_but_duplicate_top_level_names_are_not(self) -> None:
        source = "fn f(x, x) {}"
        self.assert_syntax_error(source, SourceLocation(1, source.rfind("x") + 1))
        source = "record A {}; record A {}; fn g() {} fn g() {}"
        self.assertEqual(len(parse_source(source).items), 4)

    def test_semicolons_and_unexpected_eof(self) -> None:
        for source, expected in (
            ("let value = 1", SourceLocation(1, 14)),
            (";", SourceLocation(1, 1)),
            ("emit (1;", SourceLocation(1, 8)),
            ("emit [1;", SourceLocation(1, 8)),
            ("when (true) { emit 1;", SourceLocation(1, 22)),
        ):
            with self.subTest(source=source):
                self.assert_syntax_error(source, expected)

    def test_each_list_rejects_a_trailing_comma_at_its_closing_token(self) -> None:
        cases = (
            ("record R {field,};", "}"),
            ("fn f(value,) {}", ")"),
            ("emit [1,];", "]"),
            ("emit f(1,);", ")"),
            ("emit R{field: 1,};", "}"),
        )
        for source, closing in cases:
            with self.subTest(source=source):
                column = source.index(closing) + 1
                self.assert_syntax_error(source, SourceLocation(1, column))

    def test_invalid_assignment_targets_point_to_equals(self) -> None:
        for source in ("emit (a + b) = 1;", "emit f() = 1;", "emit a + b = 1;"):
            with self.subTest(source=source):
                self.assert_syntax_error(
                    source, SourceLocation(1, source.index("=") + 1)
                )

    def test_repeated_call_is_rejected_but_result_postfix_is_allowed(self) -> None:
        source = "emit f()(1);"
        self.assert_syntax_error(source, SourceLocation(1, source.index("(", 7) + 1))
        parse_source("emit f()[0].field;")

    def test_reserved_unsupported_statements_and_return_context(self) -> None:
        for source in ("break;", "continue;", "return;", "{ return 1; }"):
            with self.subTest(source=source):
                self.assert_syntax_error(source, SourceLocation(1, 1 if not source.startswith("{") else 3))
        parse_source("fn f() { { when (true) { return; } } }")

    def test_nested_declarations_and_otherwise_when_are_rejected(self) -> None:
        cases = (
            ("{ fn f() {} }", "fn"),
            ("fn outer() { fn inner() {} }", "fn"),
            ("{ record R {}; }", "record"),
            ("fn outer() { record R {}; }", "record"),
            ("when (true) {} otherwise when (false) {}", "when"),
        )
        for source, bad_token in cases:
            with self.subTest(source=source):
                bad_index = source.rfind(bad_token)
                self.assert_syntax_error(
                    source, SourceLocation(1, bad_index + 1)
                )

    def test_partial_parse_is_never_returned(self) -> None:
        source = "let complete = 1; emit ("
        error = self.assert_syntax_error(source, SourceLocation(1, len(source) + 1))
        self.assertEqual(error.message, "expected expression")


if __name__ == "__main__":
    unittest.main()
