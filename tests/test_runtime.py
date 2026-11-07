from __future__ import annotations

from io import BytesIO, StringIO
import unittest
from unittest import mock

from lwt.errors import LwtError, SourceLocation
from lwt.lexer import scan
from lwt.parser import parse
from lwt.runtime import (
    Environment,
    _RecordValue,
    _RuntimeContext,
    _evaluate,
    execute,
    format_decimal_integer,
    parse_decimal_integer,
)


class IntegerConversionTests(unittest.TestCase):
    def test_decimal_conversion_normalizes_leading_zeros_and_large_values(self) -> None:
        self.assertEqual(parse_decimal_integer("000000000000000123"), 123)
        digits = "9" * 6000
        value = parse_decimal_integer(digits)
        self.assertEqual(format_decimal_integer(value), digits)
        self.assertEqual(format_decimal_integer(-value), "-" + digits)
        self.assertEqual(format_decimal_integer(0), "0")


class LoopControlRuntimeTests(unittest.TestCase):
    def run_source(self, source: str) -> str:
        output = StringIO()
        execute(parse(scan(source)), BytesIO(), output)
        return output.getvalue()

    def test_continue_in_loop_does_not_swallow_return(self) -> None:
        source = (
            "fn find() { let n = 0; while (true) { n = n + 1; "
            "when (n == 2) { return n; } continue; } return 0; } "
            "emit find();"
        )
        self.assertEqual(self.run_source(source), "2\n")

    def test_runtime_error_inside_loop_propagates_after_prior_output(self) -> None:
        output = StringIO()
        source = 'emit "before"; while (true) { emit 1; emit 1 / 0; }'
        with self.assertRaises(LwtError) as caught:
            execute(parse(scan(source)), BytesIO(), output)
        self.assertEqual(caught.exception.category, "RuntimeError")
        self.assertEqual(caught.exception.exit_code, 3)
        self.assertEqual(output.getvalue(), "before\n1\n")


class InputErrorTests(unittest.TestCase):
    def test_input_read_failure_becomes_located_runtime_error(self) -> None:
        class BrokenInput:
            def readline(self) -> bytes:
                raise OSError("test read failure")

        program = parse(scan("emit input();"))
        output = StringIO()
        with self.assertRaises(LwtError) as caught:
            execute(program, BrokenInput(), output)  # type: ignore[arg-type]

        self.assertEqual(caught.exception.category, "RuntimeError")
        self.assertEqual(caught.exception.exit_code, 3)
        self.assertEqual(caught.exception.location, SourceLocation(1, 6))
        self.assertEqual(caught.exception.message, "could not read standard input")
        self.assertEqual(output.getvalue(), "")


class CompositeMutationFailureTests(unittest.TestCase):
    def make_context(self) -> _RuntimeContext:
        return _RuntimeContext(BytesIO(), StringIO(), {}, {})

    def evaluate_expression(self, source: str, environment: Environment) -> None:
        statement = parse(scan(source)).items[0]
        _evaluate(statement.expression, environment, self.make_context())  # type: ignore[attr-defined]

    def test_failed_index_assignment_rhs_does_not_write_target(self) -> None:
        environment = Environment()
        values = [7]
        environment.values["values"] = values

        with self.assertRaises(LwtError) as caught:
            self.evaluate_expression("values[0] = 1 / 0;", environment)

        self.assertEqual(caught.exception.category, "RuntimeError")
        self.assertEqual(values, [7])


class RuntimeRecoveryTests(unittest.TestCase):
    def make_context(self) -> _RuntimeContext:
        return _RuntimeContext(BytesIO(), StringIO(), {}, {})

    def evaluate_expression(self, source: str, environment: Environment) -> None:
        statement = parse(scan(source)).items[0]
        _evaluate(statement.expression, environment, self.make_context())  # type: ignore[attr-defined]

    def run_source(self, source: str, *, source_path: str | None = None) -> str:
        output = StringIO()
        execute(parse(scan(source)), BytesIO(), output, source_path=source_path)
        return output.getvalue()

    def test_runtime_error_is_converted_to_readable_immutable_value(self) -> None:
        source = (
            'attempt { fail("bad"); } recover (problem) {'
            'emit problem.category; emit problem.message; emit problem.source; '
            'emit problem.line; emit problem.column; emit str(problem); emit problem;'
            '}'
        )
        expected = (
            "RuntimeError\nbad\nscript.lwt\n1\n11\n"
            'Error{category: "RuntimeError", message: "bad", source: "script.lwt", '
            "line: 1, column: 11}\n"
            'Error{category: "RuntimeError", message: "bad", source: "script.lwt", '
            "line: 1, column: 11}\n"
        )
        self.assertEqual(self.run_source(source, source_path="script.lwt"), expected)

    def test_error_value_uses_null_for_unavailable_source(self) -> None:
        source = 'attempt { fail("x"); } recover (e) { emit e.source; emit e; }'
        output = self.run_source(source)
        self.assertEqual(output, 'null\nError{category: "RuntimeError", message: "x", source: null, line: 1, column: 11}\n')

    def test_attempt_only_handles_runtime_category_with_exit_code_three(self) -> None:
        source = "attempt {} recover (e) {}"
        statement = parse(scan(source)).items[0]
        for category, exit_code in (("SyntaxError", 2), ("RuntimeError", 2), ("FileError", 3)):
            error = LwtError(category, "injected", exit_code, SourceLocation(1, 1))
            with self.subTest(category=category, exit_code=exit_code):
                with mock.patch("lwt.runtime._execute_statement", side_effect=error):
                    with self.assertRaises(LwtError) as caught:
                        execute(parse(scan(source)), BytesIO(), StringIO())
                self.assertIs(caught.exception, error)

    def test_attempt_catches_runtime_error_and_preserves_later_execution(self) -> None:
        source = 'attempt { emit "before"; 9 / 0; } recover (e) { emit e.message; } emit "after";'
        self.assertEqual(self.run_source(source), "before\ndivision by zero\nafter\n")

    def test_failed_field_assignment_rhs_does_not_write_target(self) -> None:
        environment = Environment()
        record = _RecordValue("Cell", ("value",), {"value": 7})
        environment.values["cell"] = record

        with self.assertRaises(LwtError) as caught:
            self.evaluate_expression("cell.value = 1 / 0;", environment)

        self.assertEqual(caught.exception.category, "RuntimeError")
        self.assertEqual(record.fields["value"], 7)

    def test_failed_push_argument_does_not_append(self) -> None:
        environment = Environment()
        values = [7]
        environment.values["values"] = values

        with self.assertRaises(LwtError) as caught:
            self.evaluate_expression("push(values, 1 / 0);", environment)

        self.assertEqual(caught.exception.category, "RuntimeError")
        self.assertEqual(values, [7])


class DictRuntimeTests(unittest.TestCase):
    def run_source(self, source: str) -> str:
        output = StringIO()
        execute(parse(scan(source)), BytesIO(), output)
        return output.getvalue()

    def test_dict_display_and_insertion_order(self) -> None:
        self.assertEqual(
            self.run_source('emit dict{"b": 1, "a": 2};'),
            'dict{"b": 1, "a": 2}\n',
        )

    def test_int_and_string_keys_are_distinct(self) -> None:
        source = 'let d = dict{1: "int", "1": "str"}; emit d[1]; emit d["1"];'
        self.assertEqual(self.run_source(source), "int\nstr\n")

    def test_put_append_and_update_keeps_position(self) -> None:
        source = (
            'let d = dict{"a": 1, "b": 2}; put(d, "a", 9); put(d, "c", 3); emit d;'
        )
        self.assertEqual(self.run_source(source), 'dict{"a": 9, "b": 2, "c": 3}\n')

    def test_index_assignment_appends(self) -> None:
        self.assertEqual(
            self.run_source('let d = dict{}; d["x"] = 1; emit d;'),
            'dict{"x": 1}\n',
        )

    def test_builtins(self) -> None:
        source = (
            'let d = dict{"a": 1, "b": 2}; emit len(d); emit keys(d); '
            'emit values(d); emit items(d); emit has(d, "a"); emit has(d, "z"); '
            'emit get(d, "z", 9); emit delete(d, "a"); emit delete(d, "a"); emit d;'
        )
        self.assertEqual(
            self.run_source(source),
            '2\n["a", "b"]\n[1, 2]\n[["a", 1], ["b", 2]]\ntrue\nfalse\n9\n'
            'true\nfalse\ndict{"b": 2}\n',
        )

    def test_duplicate_key_is_runtime_error(self) -> None:
        with self.assertRaises(LwtError) as caught:
            self.run_source('let d = dict{"a": 1, "a": 2}; emit d;')
        self.assertEqual(caught.exception.exit_code, 3)
        self.assertIn("duplicate dict key", caught.exception.message)

    def test_bad_key_type_is_runtime_error(self) -> None:
        with self.assertRaises(LwtError) as caught:
            self.run_source('let d = dict{true: 1}; emit d;')
        self.assertEqual(caught.exception.exit_code, 3)
        self.assertIn("dict key must be an integer or string", caught.exception.message)

    def test_missing_key_read_is_runtime_error(self) -> None:
        with self.assertRaises(LwtError) as caught:
            self.run_source('let d = dict{"a": 1}; emit d["z"];')
        self.assertEqual(caught.exception.exit_code, 3)
        self.assertIn("dict has no key", caught.exception.message)

    def test_dict_identity_equality(self) -> None:
        source = 'let d = dict{"a": 1}; emit d == d; emit dict{} == dict{};'
        self.assertEqual(self.run_source(source), "true\nfalse\n")

    def test_dict_cycle_display(self) -> None:
        source = 'let d = dict{}; put(d, "self", d); emit d;'
        self.assertEqual(self.run_source(source), 'dict{"self": <cycle>}\n')


class ThrowFinallyTests(unittest.TestCase):
    def run_source(self, source: str) -> str:
        output = StringIO()
        execute(parse(scan(source)), BytesIO(), output)
        return output.getvalue()

    def test_throw_string_becomes_user_error_and_finally_runs(self) -> None:
        source = (
            'attempt { throw "boom"; emit "no"; } recover (p) { '
            'emit p.category; emit p.message; } finally { emit "clean"; } emit "after";'
        )
        self.assertEqual(self.run_source(source), "User\nboom\nclean\nafter\n")

    def test_throw_error_value_preserves_category_and_finally(self) -> None:
        source = (
            'attempt { attempt { throw error("Validation", "bad"); } '
            'recover (i) { emit i.category; throw i; } finally { emit "inner"; } } '
            'recover (o) { emit o.category + ":" + o.message; }'
        )
        self.assertEqual(self.run_source(source), "Validation\ninner\nValidation:bad\n")

    def test_finally_return_overrides_handler_return(self) -> None:
        source = (
            'fn f() { attempt { throw "x"; } recover (p) { return 7; } '
            'finally { return 9; } return 0; } emit f();'
        )
        self.assertEqual(self.run_source(source), "9\n")

    def test_finally_runs_on_normal_flow_without_handler(self) -> None:
        source = (
            'attempt { emit "body"; } recover (p) { emit "no"; } '
            'finally { emit "fin"; }'
        )
        self.assertEqual(self.run_source(source), "body\nfin\n")

    def test_finally_cannot_see_problem(self) -> None:
        source = (
            'attempt { throw "x"; } recover (p) { emit p.message; } '
            'finally { emit p; }'
        )
        with self.assertRaises(LwtError) as caught:
            self.run_source(source)
        self.assertEqual(caught.exception.exit_code, 3)
        self.assertIn("undefined variable 'p'", caught.exception.message)

    def test_uncaught_throw_string_uses_user_category(self) -> None:
        with self.assertRaises(LwtError) as caught:
            self.run_source('emit "before"; throw "kaboom";')
        self.assertEqual(caught.exception.category, "User")
        self.assertEqual(caught.exception.exit_code, 3)

    def test_throw_non_string_non_error_is_runtime_error(self) -> None:
        with self.assertRaises(LwtError) as caught:
            self.run_source("throw 42;")
        self.assertEqual(caught.exception.category, "RuntimeError")
        self.assertIn("throw requires a string or an error value", caught.exception.message)

    def test_legacy_attempt_without_finally_unchanged(self) -> None:
        source = 'attempt { fail("bad"); } recover (p) { emit p.category; emit p.message; } emit "ok";'
        self.assertEqual(self.run_source(source), "RuntimeError\nbad\nok\n")


if __name__ == "__main__":
    unittest.main()
