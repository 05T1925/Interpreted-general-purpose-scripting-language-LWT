"""S4 scalar runtime for the LWT language.

This module deliberately executes only literals, variables, scalar operators,
explicit blocks, ``emit`` and the ``input()`` builtin. Unsupported but valid
syntax is detected before execution so it cannot produce partial output.
"""

from __future__ import annotations

import sys
from typing import BinaryIO, NoReturn, TextIO

from .ast_nodes import (
    ArrayExpression,
    AssignmentExpression,
    BinaryExpression,
    Block,
    CallExpression,
    EmitStatement,
    Expression,
    ExpressionStatement,
    FieldExpression,
    IndexExpression,
    LetStatement,
    LiteralExpression,
    Program,
    RecordConstructionExpression,
    RecordDeclaration,
    ReturnStatement,
    Statement,
    UnaryExpression,
    VariableExpression,
    WhenStatement,
    WhileStatement,
    EachStatement,
    FunctionDeclaration,
)
from .errors import LwtError, SourceLocation
from .lexer import TokenKind


_DECIMAL_CHUNK_DIGITS = 9
_DECIMAL_CHUNK_BASE = 10**_DECIMAL_CHUNK_DIGITS
_LITERAL_KINDS = frozenset(
    {
        TokenKind.INT,
        TokenKind.STRING,
        TokenKind.TRUE,
        TokenKind.FALSE,
        TokenKind.NULL,
    }
)


class Environment:
    """A lexical variable scope with an optional parent scope."""

    __slots__ = ("values", "parent")

    def __init__(self, parent: Environment | None = None) -> None:
        self.values: dict[str, object] = {}
        self.parent = parent

    def resolve(self, name: str) -> Environment | None:
        environment: Environment | None = self
        while environment is not None:
            if name in environment.values:
                return environment
            environment = environment.parent
        return None


def parse_decimal_integer(lexeme: str) -> int:
    """Convert decimal digits without passing a large string to ``int``."""

    value = 0
    for start in range(0, len(lexeme), _DECIMAL_CHUNK_DIGITS):
        chunk = lexeme[start : start + _DECIMAL_CHUNK_DIGITS]
        value = value * (10 ** len(chunk)) + int(chunk)
    return value


def format_decimal_integer(value: int) -> str:
    """Format an arbitrary-size integer using only small decimal chunks."""

    negative = value < 0
    remaining = -value if negative else value
    if remaining == 0:
        return "0"

    chunks: list[int] = []
    while remaining:
        remaining, chunk = divmod(remaining, _DECIMAL_CHUNK_BASE)
        chunks.append(chunk)

    rendered = str(chunks.pop())
    rendered += "".join(f"{chunk:0{_DECIMAL_CHUNK_DIGITS}d}" for chunk in reversed(chunks))
    return "-" + rendered if negative else rendered


def execute(
    program: Program,
    input_stream: BinaryIO | None = None,
    output_stream: TextIO | None = None,
) -> None:
    """Execute an S4 program or raise a located LWT error.

    A whole-program capability scan happens before any evaluation or output.
    ``input_stream`` is binary so LF and CRLF handling is independent of host
    text-mode newline conversion.
    """

    if input_stream is None:
        input_stream = sys.stdin.buffer
    if output_stream is None:
        output_stream = sys.stdout

    try:
        unsupported = _first_unsupported(program)
        if unsupported is not None:
            raise LwtError(
                "Incomplete",
                "runtime support for this syntax is not implemented yet",
                1,
                unsupported,
            )

        environment = Environment()
        for item in program.items:
            _execute_statement(item, environment, input_stream, output_stream)
    except RecursionError:
        # Report the host limit as a runtime failure without imposing a fixed
        # language-level depth limit or leaking a Python traceback.
        raise LwtError(
            "RuntimeError",
            "host recursion limit reached",
            3,
            program.location,
        ) from None


def _first_unsupported(program: Program) -> SourceLocation | None:
    for item in program.items:
        location = _unsupported_statement(item)
        if location is not None:
            return location
    return None


def _unsupported_statement(statement: object) -> SourceLocation | None:
    if isinstance(statement, LetStatement):
        return _unsupported_expression(statement.initializer)
    if isinstance(statement, EmitStatement):
        return _unsupported_expression(statement.value)
    if isinstance(statement, ExpressionStatement):
        return _unsupported_expression(statement.expression)
    if isinstance(statement, Block):
        for child in statement.statements:
            location = _unsupported_statement(child)
            if location is not None:
                return location
        return None
    if isinstance(
        statement,
        (
            RecordDeclaration,
            FunctionDeclaration,
            ReturnStatement,
            WhenStatement,
            WhileStatement,
            EachStatement,
        ),
    ):
        return statement.location
    # A future AST node remains unsupported until this checker explicitly
    # admits it.
    return getattr(statement, "location", SourceLocation(1, 1))


def _unsupported_expression(expression: Expression) -> SourceLocation | None:
    if isinstance(expression, LiteralExpression):
        return None if expression.kind in _LITERAL_KINDS else expression.location
    if isinstance(expression, VariableExpression):
        return None
    if isinstance(expression, UnaryExpression):
        return _unsupported_expression(expression.operand)
    if isinstance(expression, BinaryExpression):
        return _unsupported_expression(expression.left) or _unsupported_expression(
            expression.right
        )
    if isinstance(expression, AssignmentExpression):
        if not isinstance(expression.target, VariableExpression):
            return expression.target.location
        return _unsupported_expression(expression.value)
    if isinstance(expression, CallExpression):
        if expression.callee.name != "input":
            return expression.location
        for argument in expression.arguments:
            location = _unsupported_expression(argument)
            if location is not None:
                return location
        return None
    if isinstance(
        expression,
        (ArrayExpression, RecordConstructionExpression, IndexExpression, FieldExpression),
    ):
        return expression.location
    return expression.location


def _execute_statement(
    statement: Statement,
    environment: Environment,
    input_stream: BinaryIO,
    output_stream: TextIO,
) -> None:
    if isinstance(statement, LetStatement):
        name = statement.name.name
        if name in environment.values:
            _runtime_error(
                f"variable {name!r} is already declared in this scope",
                statement.name.location,
            )
        value = _evaluate(statement.initializer, environment, input_stream)
        environment.values[name] = value
        return

    if isinstance(statement, EmitStatement):
        value = _evaluate(statement.value, environment, input_stream)
        output_stream.write(_display_scalar(value) + "\n")
        return

    if isinstance(statement, ExpressionStatement):
        _evaluate(statement.expression, environment, input_stream)
        return

    if isinstance(statement, Block):
        nested = Environment(environment)
        for child in statement.statements:
            _execute_statement(child, nested, input_stream, output_stream)
        return

    # The capability scan must reject every other statement before execution.
    raise AssertionError(f"unsupported statement passed to evaluator: {type(statement)!r}")


def _evaluate(
    expression: Expression,
    environment: Environment,
    input_stream: BinaryIO,
) -> object:
    if isinstance(expression, LiteralExpression):
        if expression.kind is TokenKind.INT:
            return parse_decimal_integer(expression.lexeme)
        return expression.value

    if isinstance(expression, VariableExpression):
        binding = environment.resolve(expression.name.name)
        if binding is None:
            _runtime_error(
                f"undefined variable {expression.name.name!r}",
                expression.name.location,
            )
        return binding.values[expression.name.name]

    if isinstance(expression, AssignmentExpression):
        # S4's whole-program scan admits only simple variable targets.
        if not isinstance(expression.target, VariableExpression):
            raise AssertionError("unsupported assignment target passed to evaluator")
        identifier = expression.target.name
        binding = environment.resolve(identifier.name)
        if binding is None:
            _runtime_error(
                f"undefined variable {identifier.name!r}",
                expression.operator_location,
            )
        value = _evaluate(expression.value, environment, input_stream)
        binding.values[identifier.name] = value
        return value

    if isinstance(expression, UnaryExpression):
        value = _evaluate(expression.operand, environment, input_stream)
        if expression.operator is TokenKind.MINUS:
            if type(value) is not int:
                _runtime_error("unary '-' requires an integer", expression.location)
            return -value
        if expression.operator is TokenKind.NOT:
            if type(value) is not bool:
                _runtime_error("'not' requires a boolean", expression.location)
            return not value
        raise AssertionError(f"unknown unary operator: {expression.operator!r}")

    if isinstance(expression, BinaryExpression):
        left = _evaluate(expression.left, environment, input_stream)
        if expression.operator is TokenKind.AND:
            if type(left) is not bool:
                _runtime_error("'and' requires boolean operands", expression.operator_location)
            if not left:
                return False
            right = _evaluate(expression.right, environment, input_stream)
            if type(right) is not bool:
                _runtime_error("'and' requires boolean operands", expression.operator_location)
            return right
        if expression.operator is TokenKind.OR:
            if type(left) is not bool:
                _runtime_error("'or' requires boolean operands", expression.operator_location)
            if left:
                return True
            right = _evaluate(expression.right, environment, input_stream)
            if type(right) is not bool:
                _runtime_error("'or' requires boolean operands", expression.operator_location)
            return right

        # Every non-short-circuit binary operation evaluates left then right.
        right = _evaluate(expression.right, environment, input_stream)
        return _evaluate_binary(expression, left, right)

    if isinstance(expression, CallExpression):
        arguments = [
            _evaluate(argument, environment, input_stream)
            for argument in expression.arguments
        ]
        if expression.callee.name == "input":
            if arguments:
                _runtime_error(
                    "input expects 0 arguments", expression.callee.location
                )
            return _read_input_line(input_stream, expression.callee.location)
        raise AssertionError("unsupported function call passed to evaluator")

    # Unsupported nodes are rejected by _first_unsupported before execution.
    raise AssertionError(f"unsupported expression passed to evaluator: {type(expression)!r}")


def _evaluate_binary(
    expression: BinaryExpression, left: object, right: object
) -> object:
    operator = expression.operator
    location = expression.operator_location

    if operator is TokenKind.EQUAL_EQUAL:
        return type(left) is type(right) and left == right
    if operator is TokenKind.BANG_EQUAL:
        return not (type(left) is type(right) and left == right)

    if operator is TokenKind.PLUS:
        if type(left) is int and type(right) is int:
            return left + right
        if type(left) is str and type(right) is str:
            return left + right
        _runtime_error("'+' requires two integers or two strings", location)

    if operator in {
        TokenKind.MINUS,
        TokenKind.STAR,
        TokenKind.SLASH,
        TokenKind.PERCENT,
    }:
        if type(left) is not int or type(right) is not int:
            _runtime_error(
                f"operator {operator.value!r} requires integer operands", location
            )
        if operator is TokenKind.MINUS:
            return left - right
        if operator is TokenKind.STAR:
            return left * right
        if right == 0:
            _runtime_error("division by zero", location)
        if operator is TokenKind.SLASH:
            return left // right
        return left % right

    if operator in {
        TokenKind.LESS,
        TokenKind.LESS_EQUAL,
        TokenKind.GREATER,
        TokenKind.GREATER_EQUAL,
    }:
        same_supported_type = (
            type(left) is int and type(right) is int
        ) or (type(left) is str and type(right) is str)
        if not same_supported_type:
            _runtime_error(
                f"operator {operator.value!r} requires two integers or two strings",
                location,
            )
        if operator is TokenKind.LESS:
            return left < right
        if operator is TokenKind.LESS_EQUAL:
            return left <= right
        if operator is TokenKind.GREATER:
            return left > right
        return left >= right

    raise AssertionError(f"unknown binary operator: {operator!r}")


def _read_input_line(input_stream: BinaryIO, location: SourceLocation) -> str | None:
    try:
        line = input_stream.readline()
    except (OSError, ValueError):
        _runtime_error("could not read standard input", location)

    if not line:
        return None
    if line.endswith(b"\n"):
        line = line[:-1]
        if line.endswith(b"\r"):
            line = line[:-1]
    try:
        return line.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        _runtime_error("standard input is not valid UTF-8", location)


def _display_scalar(value: object) -> str:
    if type(value) is int:
        return format_decimal_integer(value)
    if type(value) is str:
        return value
    if type(value) is bool:
        return "true" if value else "false"
    if value is None:
        return "null"
    raise AssertionError(f"non-scalar value reached S4 emit: {type(value)!r}")


def _runtime_error(message: str, location: SourceLocation) -> NoReturn:
    raise LwtError("RuntimeError", message, 3, location)
