from __future__ import annotations

from io import BytesIO, StringIO
import unittest

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


if __name__ == "__main__":
    unittest.main()
