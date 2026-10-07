"""Tree-walk runtime for LWT 0.1."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import BinaryIO, NoReturn, TextIO

from .ast_nodes import (
    ArrayExpression,
    AssignmentExpression,
    BinaryExpression,
    Block,
    CallExpression,
    EachStatement,
    EmitStatement,
    Expression,
    ExpressionStatement,
    FieldExpression,
    FunctionDeclaration,
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
_BUILTIN_NAMES = frozenset(
    {
        "input",
        "args",
        "read_text",
        "len",
        "split",
        "trim",
        "to_int",
        "str",
        "push",
        "fail",
    }
)


class _ReturnSignal(Exception):
    """Internal control transfer caught only by the active function call."""

    def __init__(self, value: object) -> None:
        super().__init__()
        self.value = value


class _RecordValue:
    """A mutable record instance whose equality is object identity."""

    __slots__ = ("type_name", "field_names", "fields")

    def __init__(
        self, type_name: str, field_names: tuple[str, ...], fields: dict[str, object]
    ) -> None:
        self.type_name = type_name
        self.field_names = field_names
        # Insert in declaration order so display is deterministic.
        self.fields = {name: fields[name] for name in field_names}


class _RuntimeContext:
    """Per-program tables and I/O streams shared by nested function calls."""

    __slots__ = (
        "input_stream",
        "output_stream",
        "program_args",
        "functions",
        "record_types",
    )

    def __init__(
        self,
        input_stream: BinaryIO,
        output_stream: TextIO,
        functions: dict[str, FunctionDeclaration],
        record_types: dict[str, tuple[str, ...]],
        program_args: tuple[str, ...] = (),
    ) -> None:
        self.input_stream = input_stream
        self.output_stream = output_stream
        self.program_args = program_args
        self.functions = functions
        self.record_types = record_types


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

    def global_scope(self) -> Environment:
        environment = self
        while environment.parent is not None:
            environment = environment.parent
        return environment


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
    program_args: tuple[str, ...] = (),
) -> None:
    """Execute a supported LWT program or raise a located LWT error.

    Function and record registration plus the whole-program capability scan
    happen before any evaluation or output.
    ``input_stream`` is binary so LF and CRLF handling is independent of host
    text-mode newline conversion.
    """

    if input_stream is None:
        input_stream = sys.stdin.buffer
    if output_stream is None:
        output_stream = sys.stdout

    try:
        functions: dict[str, FunctionDeclaration] = {}
        record_types: dict[str, tuple[str, ...]] = {}
        for item in program.items:
            if isinstance(item, FunctionDeclaration):
                name = item.name.name
                if name in _BUILTIN_NAMES:
                    _runtime_error(
                        f"function name {name!r} conflicts with a built-in",
                        item.name.location,
                    )
                if name in functions:
                    _runtime_error(
                        f"duplicate function declaration {name!r}",
                        item.name.location,
                    )
                functions[name] = item
            elif isinstance(item, RecordDeclaration):
                name = item.name.name
                if name in record_types:
                    _runtime_error(
                        f"duplicate record declaration {name!r}",
                        item.name.location,
                    )
                record_types[name] = tuple(field.name for field in item.fields)

        unsupported = _first_unsupported(program)
        if unsupported is not None:
            raise LwtError(
                "Incomplete",
                "runtime support for this syntax is not implemented yet",
                1,
                unsupported,
            )

        runtime = _RuntimeContext(
            input_stream, output_stream, functions, record_types, program_args
        )
        environment = Environment()
        for item in program.items:
            if isinstance(item, (FunctionDeclaration, RecordDeclaration)):
                continue
            _execute_statement(item, environment, runtime)
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
    if isinstance(statement, FunctionDeclaration):
        return _unsupported_statement(statement.body)
    if isinstance(statement, RecordDeclaration):
        return None
    if isinstance(statement, LetStatement):
        return _unsupported_expression(statement.initializer)
    if isinstance(statement, ReturnStatement):
        return (
            _unsupported_expression(statement.value)
            if statement.value is not None
            else None
        )
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

    if isinstance(statement, WhenStatement):
        return (
            _unsupported_expression(statement.condition)
            or _unsupported_statement(statement.then_branch)
            or (
                _unsupported_statement(statement.otherwise_branch)
                if statement.otherwise_branch is not None
                else None
            )
        )
    if isinstance(statement, WhileStatement):
        return _unsupported_expression(statement.condition) or _unsupported_statement(
            statement.body
        )
    if isinstance(statement, EachStatement):
        return _unsupported_expression(statement.iterable) or _unsupported_statement(
            statement.body
        )
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
        if isinstance(expression.target, VariableExpression):
            pass
        elif isinstance(expression.target, IndexExpression):
            return (
                _unsupported_expression(expression.target.object)
                or _unsupported_expression(expression.target.index)
                or _unsupported_expression(expression.value)
            )
        elif isinstance(expression.target, FieldExpression):
            return (
                _unsupported_expression(expression.target.object)
                or _unsupported_expression(expression.value)
            )
        else:
            return expression.target.location
        return _unsupported_expression(expression.value)
    if isinstance(expression, CallExpression):
        for argument in expression.arguments:
            location = _unsupported_expression(argument)
            if location is not None:
                return location
        return None
    if isinstance(expression, ArrayExpression):
        for element in expression.elements:
            location = _unsupported_expression(element)
            if location is not None:
                return location
        return None
    if isinstance(expression, RecordConstructionExpression):
        for field in expression.fields:
            location = _unsupported_expression(field.value)
            if location is not None:
                return location
        return None
    if isinstance(expression, IndexExpression):
        return _unsupported_expression(expression.object) or _unsupported_expression(
            expression.index
        )
    if isinstance(expression, FieldExpression):
        return _unsupported_expression(expression.object)
    return expression.location


def _execute_statement(
    statement: Statement, environment: Environment, runtime: _RuntimeContext
) -> None:
    if isinstance(statement, LetStatement):
        name = statement.name.name
        if name in environment.values:
            _runtime_error(
                f"variable {name!r} is already declared in this scope",
                statement.name.location,
            )
        value = _evaluate(statement.initializer, environment, runtime)
        environment.values[name] = value
        return

    if isinstance(statement, ReturnStatement):
        value = (
            _evaluate(statement.value, environment, runtime)
            if statement.value is not None
            else None
        )
        raise _ReturnSignal(value)

    if isinstance(statement, EmitStatement):
        value = _evaluate(statement.value, environment, runtime)
        try:
            rendered = _display_value(value)
        except RecursionError:
            _runtime_error("host recursion limit reached while displaying value", statement.location)
        # Render fully before writing so a failed formatter cannot emit a partial line.
        runtime.output_stream.write(rendered + "\n")
        return

    if isinstance(statement, ExpressionStatement):
        _evaluate(statement.expression, environment, runtime)
        return

    if isinstance(statement, Block):
        nested = Environment(environment)
        for child in statement.statements:
            _execute_statement(child, nested, runtime)
        return

    if isinstance(statement, WhenStatement):
        condition = _evaluate(statement.condition, environment, runtime)
        if type(condition) is not bool:
            _runtime_error("when condition must be a boolean", statement.location)
        if condition:
            _execute_statement(statement.then_branch, environment, runtime)
        elif statement.otherwise_branch is not None:
            _execute_statement(statement.otherwise_branch, environment, runtime)
        return

    if isinstance(statement, WhileStatement):
        while True:
            condition = _evaluate(statement.condition, environment, runtime)
            if type(condition) is not bool:
                _runtime_error("while condition must be a boolean", statement.location)
            if not condition:
                return
            # The Block creates a fresh child environment on each iteration.
            _execute_statement(statement.body, environment, runtime)

    if isinstance(statement, EachStatement):
        iterable = _evaluate(statement.iterable, environment, runtime)
        if type(iterable) is not list:
            _runtime_error("each requires an array", statement.location)
        snapshot = list(iterable)
        for value in snapshot:
            iteration_scope = Environment(environment)
            # The loop binding intentionally shadows an outer binding.
            iteration_scope.values[statement.variable.name] = value
            # The body Block creates a second scope nested under the iteration scope.
            _execute_statement(statement.body, iteration_scope, runtime)
        return

    # Top-level record declarations are registered before execution and skipped
    # by execute(); all remaining syntax must have passed the capability scan.
    raise AssertionError(f"unsupported statement passed to evaluator: {type(statement)!r}")


def _evaluate(
    expression: Expression, environment: Environment, runtime: _RuntimeContext
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

    if isinstance(expression, ArrayExpression):
        # A list comprehension evaluates each element exactly once, left-to-right.
        return [_evaluate(element, environment, runtime) for element in expression.elements]

    if isinstance(expression, RecordConstructionExpression):
        return _construct_record(expression, environment, runtime)

    if isinstance(expression, IndexExpression):
        receiver = _evaluate(expression.object, environment, runtime)
        index = _evaluate(expression.index, environment, runtime)
        checked_index = _checked_array_index(receiver, index, expression.access_location)
        return receiver[checked_index]

    if isinstance(expression, FieldExpression):
        receiver = _evaluate(expression.object, environment, runtime)
        if not isinstance(receiver, _RecordValue):
            _runtime_error("field access requires a record", expression.access_location)
        field_name = expression.field.name
        if field_name not in receiver.fields:
            _runtime_error(
                f"record {receiver.type_name!r} has no field {field_name!r}",
                expression.access_location,
            )
        return receiver.fields[field_name]

    if isinstance(expression, AssignmentExpression):
        target = expression.target
        if isinstance(target, VariableExpression):
            identifier = target.name
            binding = environment.resolve(identifier.name)
            if binding is None:
                # Preserve the S4/S5 assignment diagnostic location.
                _runtime_error(
                    f"undefined variable {identifier.name!r}",
                    expression.operator_location,
                )
            value = _evaluate(expression.value, environment, runtime)
            binding.values[identifier.name] = value
            return value

        if isinstance(target, IndexExpression):
            receiver = _evaluate(target.object, environment, runtime)
            index = _evaluate(target.index, environment, runtime)
            checked_index = _checked_array_index(
                receiver, index, target.access_location
            )
            value = _evaluate(expression.value, environment, runtime)
            receiver[checked_index] = value
            return value

        if isinstance(target, FieldExpression):
            receiver = _evaluate(target.object, environment, runtime)
            if not isinstance(receiver, _RecordValue):
                _runtime_error("field assignment requires a record", target.access_location)
            field_name = target.field.name
            if field_name not in receiver.fields:
                _runtime_error(
                    f"record {receiver.type_name!r} has no field {field_name!r}",
                    target.access_location,
                )
            value = _evaluate(expression.value, environment, runtime)
            receiver.fields[field_name] = value
            return value

        raise AssertionError("parser admitted an invalid assignment target")

    if isinstance(expression, UnaryExpression):
        value = _evaluate(expression.operand, environment, runtime)
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
        left = _evaluate(expression.left, environment, runtime)
        if expression.operator is TokenKind.AND:
            if type(left) is not bool:
                _runtime_error("'and' requires boolean operands", expression.operator_location)
            if not left:
                return False
            right = _evaluate(expression.right, environment, runtime)
            if type(right) is not bool:
                _runtime_error("'and' requires boolean operands", expression.operator_location)
            return right
        if expression.operator is TokenKind.OR:
            if type(left) is not bool:
                _runtime_error("'or' requires boolean operands", expression.operator_location)
            if left:
                return True
            right = _evaluate(expression.right, environment, runtime)
            if type(right) is not bool:
                _runtime_error("'or' requires boolean operands", expression.operator_location)
            return right

        # Every non-short-circuit binary operation evaluates left then right.
        right = _evaluate(expression.right, environment, runtime)
        return _evaluate_binary(expression, left, right)

    if isinstance(expression, CallExpression):
        name = expression.callee.name
        is_builtin = name in _BUILTIN_NAMES
        declaration = None if is_builtin else runtime.functions.get(name)
        if not is_builtin and declaration is None:
            _runtime_error(f"undefined function {name!r}", expression.callee.location)

        # Both user and built-in calls evaluate all arguments left-to-right
        # before checking arity, once the callee has been found.
        arguments = [
            _evaluate(argument, environment, runtime)
            for argument in expression.arguments
        ]
        if name == "input":
            if arguments:
                _runtime_error("input expects 0 arguments", expression.callee.location)
            return _read_input_line(runtime.input_stream, expression.callee.location)
        if name == "push":
            if len(arguments) != 2:
                _runtime_error("push expects 2 arguments", expression.callee.location)
            array, value = arguments
            if type(array) is not list:
                _runtime_error("push first argument must be an array", expression.callee.location)
            array.append(value)
            return None
        if is_builtin:
            return _invoke_builtin(
                name, arguments, expression.callee.location, runtime
            )

        assert declaration is not None
        if len(arguments) != len(declaration.parameters):
            _runtime_error(
                f"function {name!r} expects {len(declaration.parameters)} arguments, "
                f"got {len(arguments)}",
                expression.callee.location,
            )
        try:
            return _invoke_user_function(
                declaration,
                arguments,
                environment.global_scope(),
                runtime,
            )
        except RecursionError:
            _runtime_error("host recursion limit reached", expression.callee.location)

    # Unsupported nodes are rejected by _first_unsupported before execution.
    raise AssertionError(f"unsupported expression passed to evaluator: {type(expression)!r}")


def _checked_array_index(
    receiver: object, index: object, location: SourceLocation
) -> int:
    # Check in this order to keep diagnostics stable when several values are bad.
    if type(receiver) is not list:
        _runtime_error("indexing requires an array", location)
    if type(index) is not int:
        _runtime_error("array index must be an integer", location)
    if index < 0 or index >= len(receiver):
        _runtime_error("array index is out of range", location)
    return index


def _invoke_builtin(
    name: str,
    arguments: list[object],
    location: SourceLocation,
    runtime: _RuntimeContext,
) -> object:
    """Apply a built-in after all of its arguments have been evaluated."""

    if name == "args":
        if arguments:
            _runtime_error("args expects 0 arguments", location)
        # Each call owns a distinct mutable LWT array.
        return list(runtime.program_args)

    if name == "read_text":
        if len(arguments) != 1:
            _runtime_error("read_text expects 1 argument", location)
        path = arguments[0]
        if type(path) is not str:
            _runtime_error("read_text expects a string path", location)
        try:
            contents = Path(path).read_bytes()
        except (OSError, ValueError):
            _runtime_error("could not read text file", location)
        try:
            text = contents.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            _runtime_error("text file is not valid UTF-8", location)
        if text.startswith("\ufeff"):
            text = text[1:]
        return text.replace("\r\n", "\n").replace("\r", "\n")

    if name == "len":
        if len(arguments) != 1:
            _runtime_error("len expects 1 argument", location)
        value = arguments[0]
        if type(value) is str or type(value) is list:
            return len(value)
        _runtime_error("len expects a string or array", location)

    if name == "split":
        if len(arguments) != 2:
            _runtime_error("split expects 2 arguments", location)
        text, separator = arguments
        if type(text) is not str or type(separator) is not str:
            _runtime_error("split expects two strings", location)
        if separator == "":
            _runtime_error("split separator must not be empty", location)
        # Python's explicit-separator split is literal, left-to-right,
        # non-overlapping, and preserves leading/trailing empty fields.
        return text.split(separator)

    if name == "trim":
        if len(arguments) != 1:
            _runtime_error("trim expects 1 argument", location)
        text = arguments[0]
        if type(text) is not str:
            _runtime_error("trim expects a string", location)
        return text.strip(" \t\n\r\v\f")

    if name == "to_int":
        if len(arguments) != 1:
            _runtime_error("to_int expects 1 argument", location)
        text = arguments[0]
        if type(text) is not str:
            _runtime_error("to_int expects a string", location)
        negative = text.startswith("-")
        digits = text[1:] if negative else text
        if not digits or any(character < "0" or character > "9" for character in digits):
            _runtime_error("to_int expects text matching -?[0-9]+", location)
        value = parse_decimal_integer(digits)
        return -value if negative else value

    if name == "str":
        if len(arguments) != 1:
            _runtime_error("str expects 1 argument", location)
        try:
            return _display_value(arguments[0])
        except RecursionError:
            _runtime_error("host recursion limit reached while displaying value", location)

    if name == "fail":
        if len(arguments) != 1:
            _runtime_error("fail expects 1 argument", location)
        message = arguments[0]
        if type(message) is not str:
            _runtime_error("fail expects a string message", location)
        _runtime_error(message, location)

    raise AssertionError(f"unknown built-in function: {name!r}")


def _construct_record(
    expression: RecordConstructionExpression,
    environment: Environment,
    runtime: _RuntimeContext,
) -> _RecordValue:
    type_name = expression.type_name.name
    declared_fields = runtime.record_types.get(type_name)
    if declared_fields is None:
        _runtime_error(f"undefined record type {type_name!r}", expression.type_name.location)

    supplied_names = [field.name.name for field in expression.fields]
    seen: set[str] = set()
    for name in supplied_names:
        if name in seen:
            _runtime_error(
                f"record construction for {type_name!r} repeats field {name!r}",
                expression.type_name.location,
            )
        seen.add(name)

    declared_set = set(declared_fields)
    for name in supplied_names:
        if name not in declared_set:
            _runtime_error(
                f"record type {type_name!r} has no field {name!r}",
                expression.type_name.location,
            )
    missing = [name for name in declared_fields if name not in seen]
    if missing:
        _runtime_error(
            f"record construction for {type_name!r} is missing field {missing[0]!r}",
            expression.type_name.location,
        )

    # Field expressions run only after the complete field set is validated.
    values: dict[str, object] = {}
    for field in expression.fields:
        values[field.name.name] = _evaluate(field.value, environment, runtime)
    return _RecordValue(type_name, declared_fields, values)


def _invoke_user_function(
    declaration: FunctionDeclaration,
    arguments: list[object],
    global_environment: Environment,
    runtime: _RuntimeContext,
) -> object:
    """Run a function with a fresh activation whose parent is always global."""

    activation = Environment(global_environment)
    for parameter, argument in zip(declaration.parameters, arguments):
        activation.values[parameter.name] = argument

    try:
        # The function's outer body shares its scope with the parameters.
        # Nested Block statements create child scopes in _execute_statement.
        for statement in declaration.body.statements:
            _execute_statement(statement, activation, runtime)
    except _ReturnSignal as returned:
        return returned.value
    return None


def _evaluate_binary(
    expression: BinaryExpression, left: object, right: object
) -> object:
    operator = expression.operator
    location = expression.operator_location

    if operator in {TokenKind.EQUAL_EQUAL, TokenKind.BANG_EQUAL}:
        if type(left) is not type(right):
            equal = False
        elif type(left) in {int, str, bool} or left is None:
            equal = left == right
        elif type(left) is list or isinstance(left, _RecordValue):
            # Never invoke Python's recursive container/record equality.
            equal = left is right
        else:
            raise AssertionError(f"unknown LWT value in equality: {type(left)!r}")
        return equal if operator is TokenKind.EQUAL_EQUAL else not equal

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


def _display_value(value: object) -> str:
    """Return a complete, deterministic emit representation of any LWT value."""

    return _format_value(value, set(), nested=False)


def _format_value(value: object, active: set[int], nested: bool) -> str:
    if type(value) is int:
        return format_decimal_integer(value)
    if type(value) is str:
        return _quote_string(value) if nested else value
    if type(value) is bool:
        return "true" if value else "false"
    if value is None:
        return "null"
    if type(value) is list:
        identity = id(value)
        if identity in active:
            return "<cycle>"
        active.add(identity)
        try:
            return "[" + ", ".join(
                _format_value(element, active, nested=True) for element in value
            ) + "]"
        finally:
            active.remove(identity)
    if isinstance(value, _RecordValue):
        identity = id(value)
        if identity in active:
            return "<cycle>"
        active.add(identity)
        try:
            fields = ", ".join(
                f"{name}: {_format_value(value.fields[name], active, nested=True)}"
                for name in value.field_names
            )
            return f"{value.type_name}{{{fields}}}"
        finally:
            active.remove(identity)
    raise AssertionError(f"unknown LWT value in display: {type(value)!r}")


def _quote_string(value: str) -> str:
    escaped: list[str] = ['"']
    for character in value:
        codepoint = ord(character)
        if character == '"':
            escaped.append('\\"')
        elif character == "\\":
            escaped.append("\\\\")
        elif character == "\n":
            escaped.append("\\n")
        elif character == "\r":
            escaped.append("\\r")
        elif character == "\t":
            escaped.append("\\t")
        elif codepoint < 0x20 or codepoint == 0x7F:
            escaped.append(f"\\u{codepoint:04X}")
        else:
            escaped.append(character)
    escaped.append('"')
    return "".join(escaped)


def _runtime_error(message: str, location: SourceLocation) -> NoReturn:
    raise LwtError("RuntimeError", message, 3, location)
