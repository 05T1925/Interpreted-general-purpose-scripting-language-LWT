"""Tree-walk runtime for LWT 0.1."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
import sys
from pathlib import Path
from typing import BinaryIO, NoReturn, TextIO

from .ast_nodes import (
    ArrayExpression,
    AttemptStatement,
    BreakStatement,
    AssignmentExpression,
    BinaryExpression,
    Block,
    CallExpression,
    ContinueStatement,
    DictEntry,
    DictExpression,
    EachStatement,
    EmitStatement,
    Expression,
    ExpressionStatement,
    FieldExpression,
    FunctionDeclaration,
    ImportDeclaration,
    IndexExpression,
    LetStatement,
    LiteralExpression,
    ModuleCallExpression,
    Program,
    RecordConstructionExpression,
    RecordDeclaration,
    ReturnStatement,
    Statement,
    ThrowStatement,
    UnaryExpression,
    VariableExpression,
    WhenStatement,
    WhileStatement,
)
from .errors import LwtError, SourceLocation
from .builtin_signatures import BUILTIN_NAMES
from .lexer import TokenKind
from .modules import ModuleGraph, ModuleUnit, resolve_module_call


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
_BUILTIN_NAMES = BUILTIN_NAMES


class _ReturnSignal(Exception):
    """Internal control transfer caught only by the active function call."""

    def __init__(self, value: object, location: SourceLocation) -> None:
        super().__init__()
        self.value = value
        self.location = location


class _BreakSignal(Exception):
    """Internal transfer caught only by the innermost active loop."""

    def __init__(self, location: SourceLocation) -> None:
        super().__init__()
        self.location = location


class _ContinueSignal(Exception):
    """Internal transfer caught only by the innermost active loop."""

    def __init__(self, location: SourceLocation) -> None:
        super().__init__()
        self.location = location


class _DebugHookFailure(Exception):
    """Keep debugger implementation failures out of the LWT error model."""


@dataclass(frozen=True, slots=True, eq=False)
class _ErrorValue:
    """An immutable, identity-compared LWT value made by a recover handler."""

    category: str
    message: str
    source: str | None
    line: int | None
    column: int | None


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


class _DictValue:
    """A mutable insertion-ordered map whose equality is object identity.

    Keys are restricted at runtime to LWT ``int`` or ``str``. Python's ``bool``
    is a subclass of ``int`` but is deliberately rejected as a key so that LWT's
    strict ``int`` type is preserved and a boolean can never alias integer 0/1.
    """

    __slots__ = ("entries",)

    def __init__(self) -> None:
        self.entries: dict[int | str, object] = {}

    def key_for(self, key: object, location: SourceLocation) -> int | str:
        if type(key) is int or type(key) is str:
            return key
        _runtime_error("dict key must be an integer or string", location)


class _RuntimeContext:
    """Per-source tables with process-level I/O shared by function calls."""

    __slots__ = (
        "input_stream",
        "output_stream",
        "program_args",
        "functions",
        "record_types",
        "imports",
        "global_environment",
        "source_path",
        "observer",
        "profile_source",
        "debug_hook",
        "module_unit",
    )

    def __init__(
        self,
        input_stream: BinaryIO,
        output_stream: TextIO,
        functions: dict[str, FunctionDeclaration],
        record_types: dict[str, tuple[str, ...]],
        program_args: tuple[str, ...] = (),
        imports: dict[str, _RuntimeContext] | None = None,
        source_path: str | None = None,
        observer: object | None = None,
        profile_source: str | None = None,
        debug_hook: object | None = None,
        module_unit: ModuleUnit | None = None,
    ) -> None:
        self.input_stream = input_stream
        self.output_stream = output_stream
        self.program_args = program_args
        self.functions = functions
        self.record_types = record_types
        self.imports = {} if imports is None else imports
        self.global_environment = Environment()
        self.source_path = source_path
        self.observer = observer
        self.profile_source = profile_source
        self.debug_hook = debug_hook
        self.module_unit = module_unit


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
    *,
    module_graph: ModuleGraph | None = None,
    source_path: str | None = None,
    observer: object | None = None,
    debug_hook: object | None = None,
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
        if module_graph is None:
            unit = ModuleUnit(Path.cwd() / "<memory>", None, program)
            graph = ModuleGraph(unit, (unit,))
        else:
            graph = module_graph
        profile_entry = getattr(observer, "entry", None) if observer is not None else None
        profile_entry = profile_entry or source_path or "entry.lwt"
        if observer is not None:
            _notify_observer(observer, "program_start", graph.entry.program)
        # Build every module table before execution. Each source owns a distinct
        # function/record namespace and a root variable environment.
        contexts: dict[ModuleUnit, _RuntimeContext] = {}
        for unit in graph.modules:
            functions: dict[str, FunctionDeclaration] = {}
            record_types: dict[str, tuple[str, ...]] = {}
            for item in unit.program.items:
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
            unsupported = _first_unsupported(unit.program)
            if unsupported is not None:
                raise LwtError(
                    "Incomplete",
                    "runtime support for this syntax is not implemented yet",
                    1,
                    unsupported,
                )
            contexts[unit] = _RuntimeContext(
                input_stream,
                output_stream,
                functions,
                record_types,
                program_args,
                source_path=source_path if unit is graph.entry else None,
                observer=observer,
                profile_source=(
                    observer.source_for(unit)
                    if observer is not None and hasattr(observer, "source_for")
                    else unit.display_path or source_path
                ),
                debug_hook=debug_hook,
                module_unit=unit,
            )

        for unit, context in contexts.items():
            context.imports.update(
                {alias: contexts[target] for alias, target in unit.imports.items()}
            )
        for unit in graph.modules:
            _validate_module_calls(unit.program, unit)

        runtime = contexts[graph.entry]
        if debug_hook is not None:
            _notify_debug_hook(debug_hook, "program_start", runtime)
        for item in program.items:
            if isinstance(
                item, (ImportDeclaration, FunctionDeclaration, RecordDeclaration)
            ):
                continue
            _execute_statement(item, runtime.global_environment, runtime)
    except LwtError as error:
        if observer is not None:
            status = "runtime_error" if error.category == "RuntimeError" and error.exit_code == 3 else "error"
            if status == "runtime_error":
                _notify_observer(observer, "runtime_error", error, profile_entry)
            _notify_observer(observer, "program_end", profile_entry, program.location, status, error.exit_code)
        raise
    except RecursionError:
        # Report the host limit as a runtime failure without imposing a fixed
        # language-level depth limit or leaking a Python traceback.
        error = LwtError(
            "RuntimeError",
            "host recursion limit reached",
            3,
            program.location,
        )
        if observer is not None:
            _notify_observer(observer, "runtime_error", error, profile_entry)
            _notify_observer(observer, "program_end", profile_entry, program.location, "runtime_error", 3)
        raise error from None
    else:
        if observer is not None:
            _notify_observer(observer, "program_end", profile_entry, program.location, "success", 0)


def _notify_observer(observer: object, method: str, *arguments: object) -> None:
    try:
        getattr(observer, method)(*arguments)
    except Exception:
        raise LwtError("FileError", "execution profile collection failed", 4) from None


def _notify_debug_hook(debug_hook: object, method: str, *arguments: object) -> None:
    try:
        getattr(debug_hook, method)(*arguments)
    except Exception as error:
        if getattr(error, "lwt_debugger_control", False):
            raise
        raise _DebugHookFailure from None


def _first_unsupported(program: Program) -> SourceLocation | None:
    for item in program.items:
        location = _unsupported_statement(item)
        if location is not None:
            return location
    return None


def _validate_module_calls(program: Program, unit: ModuleUnit) -> None:
    """Link every qualified call before any top-level statement can run."""

    visited: set[int] = set()

    def visit(value: object) -> None:
        if value is None or isinstance(
            value, (str, int, bool, TokenKind, SourceLocation)
        ):
            return
        identity = id(value)
        if identity in visited:
            return
        visited.add(identity)
        if isinstance(value, ModuleCallExpression):
            resolution = resolve_module_call(unit, value)
            if resolution.problem == "alias":
                _runtime_error(
                    f"undefined module alias {value.alias.name!r}",
                    value.alias.location,
                )
            if resolution.problem == "member":
                _runtime_error(
                    f"module {value.alias.name!r} has no function {value.member.name!r}",
                    value.member.location,
                )
        if isinstance(value, tuple):
            for child in value:
                visit(child)
            return
        if is_dataclass(value):
            for descriptor in fields(value):
                visit(getattr(value, descriptor.name))

    visit(program)


def _unsupported_statement(statement: object) -> SourceLocation | None:
    if isinstance(statement, (BreakStatement, ContinueStatement, ImportDeclaration)):
        return None
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
    if isinstance(statement, AttemptStatement):
        return (
            _unsupported_statement(statement.body)
            or _unsupported_statement(statement.recover_body)
            or (
                _unsupported_statement(statement.finally_body)
                if statement.finally_body is not None
                else None
            )
        )
    if isinstance(statement, ThrowStatement):
        return _unsupported_expression(statement.value)
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
    if isinstance(expression, ModuleCallExpression):
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
    if isinstance(expression, DictExpression):
        for entry in expression.entries:
            location = _unsupported_expression(entry.key) or _unsupported_expression(
                entry.value
            )
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
    if runtime.debug_hook is not None and not isinstance(statement, Block):
        _notify_debug_hook(
            runtime.debug_hook, "before_statement", statement, environment, runtime
        )
    if runtime.observer is not None and not isinstance(statement, Block):
        source = runtime.profile_source or runtime.source_path or "entry.lwt"
        _notify_observer(runtime.observer, "statement", statement, source)

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

    if isinstance(statement, BreakStatement):
        raise _BreakSignal(statement.location)

    if isinstance(statement, ContinueStatement):
        raise _ContinueSignal(statement.location)

    if isinstance(statement, AttemptStatement):
        attempt_outcome: str | None = None
        try:
            try:
                _execute_statement(statement.body, environment, runtime)
            except LwtError as error:
                # Any exit-code 3 error is recoverable: ordinary RuntimeErrors
                # plus errors produced by `throw` (category User or a custom
                # category carried by a thrown Error value). Lexical, syntax,
                # CLI and file errors keep their own exit codes and propagate.
                if error.exit_code != 3:
                    attempt_outcome = "error"
                    raise
                attempt_outcome = "recovered"
                location = error.location
                source = (
                    location.source_path
                    if location is not None and location.source_path is not None
                    else runtime.source_path
                )
                origin = getattr(error, "error_origin", None)
                if isinstance(origin, _ErrorValue):
                    # Re-throwing an Error value preserves its identity/fields.
                    error_value = origin
                else:
                    error_value = _ErrorValue(
                        error.category,
                        error.message,
                        source,
                        location.line if location is not None else None,
                        location.column if location is not None else None,
                    )
                handler_scope = Environment(environment)
                handler_scope.values[statement.error_name.name] = error_value
                if runtime.observer is not None:
                    _notify_observer(
                        runtime.observer,
                        "decision",
                        runtime.profile_source or "entry.lwt",
                        statement.location,
                        "attempt",
                        "recovered",
                    )
                    _notify_observer(
                        runtime.observer,
                        "recover",
                        runtime.profile_source or "entry.lwt",
                        statement,
                        error,
                    )
                # Keep handler failures outside this attempt's catch boundary.
                _execute_statement(statement.recover_body, handler_scope, runtime)
            else:
                attempt_outcome = "normal"
        finally:
            # Return/break/continue signals and unrecoverable errors pass
            # through unchanged. If a finally body raises its own error or
            # control-flow signal, Python replaces the in-flight transfer with
            # it — exactly the S42 "finally overrides pending outcome" rule.
            if attempt_outcome is None:
                attempt_outcome = "normal"
            if attempt_outcome == "normal" and runtime.observer is not None:
                _notify_observer(
                    runtime.observer,
                    "decision",
                    runtime.profile_source or "entry.lwt",
                    statement.location,
                    "attempt",
                    "normal",
                )
            if statement.finally_body is not None:
                # `problem` is bound only in the recover handler scope; a
                # finally body runs in a fresh child of the enclosing scope and
                # therefore cannot see it. It runs at most once per attempt.
                _execute_statement(
                    statement.finally_body, Environment(environment), runtime
                )
        return

    if isinstance(statement, ThrowStatement):
        value = _evaluate(statement.value, environment, runtime)
        if type(value) is str:
            error = LwtError("User", value, 3, statement.location)
        elif isinstance(value, _ErrorValue):
            error = LwtError(
                value.category,
                value.message,
                3,
                statement.location,
            )
            # Preserve the original Error value's fields and identity on
            # re-throw; the recover handler binds this exact object.
            error.error_origin = value
            if value.source is not None:
                error.location = SourceLocation(
                    value.line if value.line is not None else statement.location.line,
                    value.column if value.column is not None else statement.location.column,
                    value.source,
                )
        else:
            _runtime_error(
                "throw requires a string or an error value", statement.location
            )
        raise error

    if isinstance(statement, ReturnStatement):
        value = (
            _evaluate(statement.value, environment, runtime)
            if statement.value is not None
            else None
        )
        raise _ReturnSignal(value, statement.location)

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
        if runtime.observer is not None:
            _notify_observer(
                runtime.observer,
                "decision",
                runtime.profile_source or "entry.lwt",
                statement.location,
                "when",
                "then" if condition else "otherwise",
            )
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
            if runtime.observer is not None:
                _notify_observer(
                    runtime.observer,
                    "decision",
                    runtime.profile_source or "entry.lwt",
                    statement.location,
                    "while",
                    "true" if condition else "false",
                )
            if not condition:
                return
            # The Block creates a fresh child environment on each iteration.
            try:
                _execute_statement(statement.body, environment, runtime)
            except _ContinueSignal:
                continue
            except _BreakSignal:
                return

    if isinstance(statement, EachStatement):
        iterable = _evaluate(statement.iterable, environment, runtime)
        if type(iterable) is not list:
            _runtime_error("each requires an array", statement.location)
        snapshot = list(iterable)
        if runtime.observer is not None:
            _notify_observer(
                runtime.observer,
                "decision",
                runtime.profile_source or "entry.lwt",
                statement.location,
                "each",
                "nonempty" if snapshot else "empty",
            )
        for value in snapshot:
            iteration_scope = Environment(environment)
            # The loop binding intentionally shadows an outer binding.
            iteration_scope.values[statement.variable.name] = value
            # The body Block creates a second scope nested under the iteration scope.
            try:
                _execute_statement(statement.body, iteration_scope, runtime)
            except _ContinueSignal:
                continue
            except _BreakSignal:
                break
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

    if isinstance(expression, DictExpression):
        return _construct_dict(expression, environment, runtime)

    if isinstance(expression, RecordConstructionExpression):
        return _construct_record(expression, environment, runtime)

    if isinstance(expression, IndexExpression):
        receiver = _evaluate(expression.object, environment, runtime)
        index = _evaluate(expression.index, environment, runtime)
        if isinstance(receiver, _DictValue):
            return _dict_get(receiver, index, expression.access_location)
        checked_index = _checked_array_index(receiver, index, expression.access_location)
        return receiver[checked_index]

    if isinstance(expression, FieldExpression):
        receiver = _evaluate(expression.object, environment, runtime)
        if isinstance(receiver, _ErrorValue):
            if expression.field.name not in _ERROR_FIELDS:
                _runtime_error(
                    f"error value has no field {expression.field.name!r}",
                    expression.access_location,
                )
            return getattr(receiver, expression.field.name)
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
            if isinstance(receiver, _DictValue):
                key = receiver.key_for(index, target.access_location)
                value = _evaluate(expression.value, environment, runtime)
                receiver.entries[key] = value
                return value
            checked_index = _checked_array_index(
                receiver, index, target.access_location
            )
            value = _evaluate(expression.value, environment, runtime)
            receiver[checked_index] = value
            return value

        if isinstance(target, FieldExpression):
            receiver = _evaluate(target.object, environment, runtime)
            if isinstance(receiver, _ErrorValue):
                if target.field.name not in _ERROR_FIELDS:
                    _runtime_error(
                        f"error value has no field {target.field.name!r}",
                        target.access_location,
                    )
                _runtime_error("error fields are read-only", target.access_location)
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
                if runtime.observer is not None:
                    _notify_observer(runtime.observer, "decision", runtime.profile_source or "entry.lwt", expression.operator_location, "and", "short_circuit")
                return False
            if runtime.observer is not None:
                _notify_observer(runtime.observer, "decision", runtime.profile_source or "entry.lwt", expression.operator_location, "and", "evaluate_right")
            right = _evaluate(expression.right, environment, runtime)
            if type(right) is not bool:
                _runtime_error("'and' requires boolean operands", expression.operator_location)
            return right
        if expression.operator is TokenKind.OR:
            if type(left) is not bool:
                _runtime_error("'or' requires boolean operands", expression.operator_location)
            if left:
                if runtime.observer is not None:
                    _notify_observer(runtime.observer, "decision", runtime.profile_source or "entry.lwt", expression.operator_location, "or", "short_circuit")
                return True
            if runtime.observer is not None:
                _notify_observer(runtime.observer, "decision", runtime.profile_source or "entry.lwt", expression.operator_location, "or", "evaluate_right")
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
                caller_runtime=runtime,
                call_location=expression.location,
                qualified_name=name,
            )
        except RecursionError:
            _runtime_error("host recursion limit reached", expression.callee.location)

    if isinstance(expression, ModuleCallExpression):
        target_runtime = runtime.imports.get(expression.alias.name)
        if target_runtime is None:
            _runtime_error(
                f"undefined module alias {expression.alias.name!r}",
                expression.alias.location,
            )
        declaration = target_runtime.functions.get(expression.member.name)
        if declaration is None:
            _runtime_error(
                f"module {expression.alias.name!r} has no function {expression.member.name!r}",
                expression.member.location,
            )
        arguments = [
            _evaluate(argument, environment, runtime)
            for argument in expression.arguments
        ]
        if len(arguments) != len(declaration.parameters):
            _runtime_error(
                f"function {expression.alias.name}.{expression.member.name} expects "
                f"{len(declaration.parameters)} arguments, got {len(arguments)}",
                expression.location,
            )
        try:
            return _invoke_user_function(
                declaration,
                arguments,
                target_runtime.global_environment,
                target_runtime,
                caller_runtime=runtime,
                call_location=expression.location,
                qualified_name=f"{expression.alias.name}.{expression.member.name}",
            )
        except RecursionError:
            _runtime_error("host recursion limit reached", expression.location)

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
        if isinstance(value, _DictValue):
            return len(value.entries)
        # Keep the S8-era diagnostic text byte-for-byte stable for existing
        # error-recovery cases; dict is a valid new argument, but a wrong-type
        # argument still reports the original message.
        _runtime_error("len expects a string or array", location)

    if name in _DICT_BUILTINS:
        return _invoke_dict_builtin(name, arguments, location)

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
        _runtime_error(
            message,
            location,
            profile_message="program requested failure (user message redacted)",
        )

    if name == "error":
        if len(arguments) != 2:
            _runtime_error("error expects 2 arguments", location)
        category, message = arguments
        if type(category) is not str or type(message) is not str:
            _runtime_error("error expects two strings", location)
        return _ErrorValue(
            category,
            message,
            location.source_path or runtime.source_path,
            location.line,
            location.column,
        )

    raise AssertionError(f"unknown built-in function: {name!r}")


_DICT_BUILTINS = frozenset(
    {"keys", "values", "items", "has", "get", "put", "delete"}
)


def _expect_dict(value: object, name: str, location: SourceLocation) -> _DictValue:
    if not isinstance(value, _DictValue):
        _runtime_error(f"{name} first argument must be a dict", location)
    return value


def _invoke_dict_builtin(
    name: str, arguments: list[object], location: SourceLocation
) -> object:
    """Apply a dict built-in after its arguments have been evaluated."""

    if name == "keys":
        if len(arguments) != 1:
            _runtime_error("keys expects 1 argument", location)
        target = _expect_dict(arguments[0], name, location)
        return list(target.entries.keys())

    if name == "values":
        if len(arguments) != 1:
            _runtime_error("values expects 1 argument", location)
        target = _expect_dict(arguments[0], name, location)
        return list(target.entries.values())

    if name == "items":
        if len(arguments) != 1:
            _runtime_error("items expects 1 argument", location)
        target = _expect_dict(arguments[0], name, location)
        return [[key, value] for key, value in target.entries.items()]

    if name == "has":
        if len(arguments) != 2:
            _runtime_error("has expects 2 arguments", location)
        target = _expect_dict(arguments[0], name, location)
        key = target.key_for(arguments[1], location)
        return key in target.entries

    if name == "get":
        if len(arguments) != 3:
            _runtime_error("get expects 3 arguments", location)
        target = _expect_dict(arguments[0], name, location)
        key = target.key_for(arguments[1], location)
        return target.entries.get(key, arguments[2])

    if name == "put":
        if len(arguments) != 3:
            _runtime_error("put expects 3 arguments", location)
        target = _expect_dict(arguments[0], name, location)
        key = target.key_for(arguments[1], location)
        target.entries[key] = arguments[2]
        return None

    if name == "delete":
        if len(arguments) != 2:
            _runtime_error("delete expects 2 arguments", location)
        target = _expect_dict(arguments[0], name, location)
        key = target.key_for(arguments[1], location)
        if key not in target.entries:
            return False
        del target.entries[key]
        return True

    raise AssertionError(f"unknown dict built-in: {name!r}")


def _construct_dict(
    expression: DictExpression,
    environment: Environment,
    runtime: _RuntimeContext,
) -> _DictValue:
    result = _DictValue()
    for entry in expression.entries:
        key = _evaluate(entry.key, environment, runtime)
        checked = result.key_for(key, entry.location)
        if checked in result.entries:
            _runtime_error(
                f"duplicate dict key {_format_value(key, set(), nested=True)}",
                entry.location,
            )
        # Evaluate the value only after the key is validated and checked unique.
        value = _evaluate(entry.value, environment, runtime)
        result.entries[checked] = value
    return result


def _dict_get(target: _DictValue, index: object, location: SourceLocation) -> object:
    key = target.key_for(index, location)
    if key not in target.entries:
        _runtime_error(
            f"dict has no key {_format_value(index, set(), nested=True)}", location
        )
    return target.entries[key]


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
    *,
    caller_runtime: _RuntimeContext,
    call_location: SourceLocation,
    qualified_name: str,
) -> object:
    """Run a function with a fresh activation whose parent is always global."""

    activation = Environment(global_environment)
    for parameter, argument in zip(declaration.parameters, arguments):
        activation.values[parameter.name] = argument

    observer = runtime.observer
    debug_hook = runtime.debug_hook
    debug_entered = False
    if debug_hook is not None:
        _notify_debug_hook(
            debug_hook,
            "enter_function",
            declaration,
            activation,
            runtime,
            caller_runtime,
            call_location,
            qualified_name,
        )
        debug_entered = True
    if observer is not None:
        _notify_observer(
            observer,
            "function_call",
            declaration,
            qualified_name,
            runtime.profile_source or "entry.lwt",
            caller_runtime.profile_source or caller_runtime.source_path or "entry.lwt",
            call_location,
        )
    try:
        # The function's outer body shares its scope with the parameters.
        # Nested Block statements create child scopes in _execute_statement.
        for statement in declaration.body.statements:
            _execute_statement(statement, activation, runtime)
    except _ReturnSignal as returned:
        if observer is not None:
            _notify_observer(
                observer,
                "function_return",
                declaration,
                runtime.profile_source or "entry.lwt",
                returned.location,
                "explicit",
                qualified_name,
            )
        return returned.value
    else:
        if observer is not None:
            _notify_observer(
                observer,
                "function_return",
                declaration,
                runtime.profile_source or "entry.lwt",
                declaration.name.location,
                "natural",
                qualified_name,
            )
        return None
    finally:
        if debug_entered:
            _notify_debug_hook(debug_hook, "leave_function")
        if observer is not None:
            _notify_observer(observer, "leave_function")


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
        elif type(left) is list or isinstance(left, (_RecordValue, _ErrorValue, _DictValue)):
            # Never invoke Python's recursive container/record/dict equality.
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
    if isinstance(value, _DictValue):
        identity = id(value)
        if identity in active:
            return "<cycle>"
        active.add(identity)
        try:
            entries = ", ".join(
                f"{_format_value(key, active, nested=True)}: "
                f"{_format_value(item, active, nested=True)}"
                for key, item in value.entries.items()
            )
            return f"dict{{{entries}}}"
        finally:
            active.remove(identity)
    if isinstance(value, _ErrorValue):
        source = "null" if value.source is None else _quote_string(value.source)
        line = "null" if value.line is None else format_decimal_integer(value.line)
        column = "null" if value.column is None else format_decimal_integer(value.column)
        return (
            "Error{"
            f"category: {_quote_string(value.category)}, "
            f"message: {_quote_string(value.message)}, "
            f"source: {source}, line: {line}, column: {column}"
            "}"
        )
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


def _runtime_error(
    message: str,
    location: SourceLocation,
    *,
    profile_message: str | None = None,
) -> NoReturn:
    error = LwtError("RuntimeError", message, 3, location)
    if profile_message is not None:
        error.profile_message = profile_message
    raise error


_ERROR_FIELDS = frozenset({"category", "message", "source", "line", "column"})


class ReplSession:
    """A persistent top-level LWT session for the ``--repl`` tool.

    It reuses the ordinary runtime: one root variable environment plus a
    function/record namespace that survive across submitted source snippets.
    It is a development tool, not a new source-language construct; the normal
    ``python -m lwt SOURCE`` entry point is unchanged.
    """

    __slots__ = ("_context", "_source_name")

    def __init__(
        self,
        input_stream: BinaryIO,
        output_stream: TextIO,
        *,
        program_args: tuple[str, ...] = (),
        source_name: str = "<repl>",
    ) -> None:
        self._source_name = source_name
        self._context = self._new_context(input_stream, output_stream, program_args)

    def _new_context(
        self, input_stream: BinaryIO, output_stream: TextIO, program_args: tuple[str, ...]
    ) -> _RuntimeContext:
        unit = ModuleUnit(
            Path.cwd() / self._source_name, None, Program((), SourceLocation(1, 1))
        )
        return _RuntimeContext(
            input_stream,
            output_stream,
            {},
            {},
            program_args,
            source_path=self._source_name,
            module_unit=unit,
        )

    def reset(self) -> None:
        context = self._context
        self._context = self._new_context(
            context.input_stream, context.output_stream, context.program_args
        )

    @property
    def environment(self) -> Environment:
        return self._context.global_environment

    def visible_bindings(self) -> list[tuple[str, object]]:
        """Return the root-scope bindings in insertion order."""
        return list(self._context.global_environment.values.items())

    def submit(self, program: Program) -> None:
        """Register declarations and execute top-level statements of one snippet."""

        unsupported = _first_unsupported(program)
        if unsupported is not None:
            raise LwtError(
                "Incomplete",
                "runtime support for this syntax is not implemented yet",
                1,
                unsupported,
            )
        context = self._context
        for item in program.items:
            if isinstance(item, FunctionDeclaration):
                name = item.name.name
                if name in _BUILTIN_NAMES:
                    _runtime_error(
                        f"function name {name!r} conflicts with a built-in",
                        item.name.location,
                    )
                if name in context.functions:
                    _runtime_error(
                        f"duplicate function declaration {name!r}", item.name.location
                    )
                context.functions[name] = item
            elif isinstance(item, RecordDeclaration):
                name = item.name.name
                if name in context.record_types:
                    _runtime_error(
                        f"duplicate record declaration {name!r}", item.name.location
                    )
                context.record_types[name] = tuple(field.name for field in item.fields)
        for item in program.items:
            if isinstance(
                item, (ImportDeclaration, FunctionDeclaration, RecordDeclaration)
            ):
                continue
            _execute_statement(item, context.global_environment, context)
