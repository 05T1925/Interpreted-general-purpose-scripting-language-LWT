"""Conservative, module-aware static name and shape analysis for LWT."""

from __future__ import annotations

from dataclasses import dataclass, field

from .ast_nodes import (
    ArrayExpression,
    AssignmentExpression,
    AttemptStatement,
    BinaryExpression,
    Block,
    BreakStatement,
    CallExpression,
    ContinueStatement,
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
from .builtin_signatures import BUILTIN_ARITIES, BUILTIN_NAMES
from .errors import SourceLocation
from .lexer import TokenKind
from .modules import ModuleGraph, ModuleUnit, resolve_module_call


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    severity: str
    category: str
    message: str
    source: str | None
    line: int | None
    column: int | None


@dataclass(slots=True)
class _Scope:
    parent: _Scope | None
    names: set[str] = field(default_factory=set)

    def contains(self, name: str, *, hidden_here: str | None = None) -> bool:
        scope: _Scope | None = self
        first = True
        while scope is not None:
            if name in scope.names and not (first and hidden_here == name):
                return True
            first = False
            scope = scope.parent
        return False


@dataclass(slots=True)
class _ModuleSymbols:
    functions: dict[str, FunctionDeclaration] = field(default_factory=dict)
    records: dict[str, tuple[str, ...]] = field(default_factory=dict)
    globals: set[str] = field(default_factory=set)


class _Analyzer:
    def __init__(self, graph: ModuleGraph, entry_source_path: str | None) -> None:
        self.graph = graph
        self.entry_source_path = entry_source_path
        self.diagnostics: list[tuple[int, int, int, int, Diagnostic]] = []
        self._sequence = 0
        self._module_indexes = {unit: index for index, unit in enumerate(graph.modules)}
        self._symbols = {unit: _ModuleSymbols() for unit in graph.modules}
        self._collect_symbols()

    def analyze(self) -> list[Diagnostic]:
        for unit in self.graph.modules:
            symbols = self._symbols[unit]
            top_statements = [
                item
                for item in unit.program.items
                if not isinstance(item, (ImportDeclaration, FunctionDeclaration, RecordDeclaration))
            ]
            root = _Scope(None)
            self._analyze_statement_list(top_statements, root, unit, symbols)

            function_parent = _Scope(None, set(symbols.globals))
            for item in unit.program.items:
                if isinstance(item, FunctionDeclaration):
                    activation = _Scope(
                        function_parent, {parameter.name for parameter in item.parameters}
                    )
                    self._analyze_function_body(item.body, activation, unit, symbols)

        ordered = sorted(self.diagnostics, key=lambda entry: entry[:4])
        return [entry[4] for entry in ordered]

    def _collect_symbols(self) -> None:
        for unit in self.graph.modules:
            symbols = self._symbols[unit]
            symbols.globals.update(
                item.name.name
                for item in unit.program.items
                if isinstance(item, LetStatement)
            )
            for item in unit.program.items:
                if isinstance(item, FunctionDeclaration):
                    name = item.name.name
                    if name in BUILTIN_NAMES:
                        self._report(
                            unit,
                            "STC003",
                            f"function name {name!r} conflicts with a built-in",
                            item.name.location,
                        )
                    if name in symbols.functions:
                        self._report(
                            unit,
                            "STC001",
                            f"duplicate function declaration {name!r}",
                            item.name.location,
                        )
                    else:
                        symbols.functions[name] = item
                elif isinstance(item, RecordDeclaration):
                    name = item.name.name
                    if name in symbols.records:
                        self._report(
                            unit,
                            "STC002",
                            f"duplicate record declaration {name!r}",
                            item.name.location,
                        )
                    else:
                        symbols.records[name] = tuple(field.name for field in item.fields)

    def _report(
        self,
        unit: ModuleUnit,
        code: str,
        message: str,
        location: SourceLocation | None,
    ) -> None:
        source = (
            location.source_path
            if location is not None and location.source_path is not None
            else unit.display_path or self.entry_source_path
        )
        line = location.line if location is not None else None
        column = location.column if location is not None else None
        diagnostic = Diagnostic(
            code, "error", "StaticError", message, source, line, column
        )
        self.diagnostics.append(
            (
                self._module_indexes[unit],
                line if line is not None else 0,
                column if column is not None else 0,
                self._sequence,
                diagnostic,
            )
        )
        self._sequence += 1

    def _analyze_function_body(
        self,
        body: Block,
        activation: _Scope,
        unit: ModuleUnit,
        symbols: _ModuleSymbols,
    ) -> None:
        # A function's outer body shares its activation scope with parameters.
        self._analyze_statement_list(body.statements, activation, unit, symbols)

    def _analyze_block(
        self,
        block: Block,
        parent: _Scope,
        unit: ModuleUnit,
        symbols: _ModuleSymbols,
    ) -> None:
        scope = _Scope(parent)
        self._analyze_statement_list(block.statements, scope, unit, symbols)

    def _analyze_statement_list(
        self,
        statements: list[Statement] | tuple[Statement, ...],
        scope: _Scope,
        unit: ModuleUnit,
        symbols: _ModuleSymbols,
    ) -> None:
        let_names = [statement.name.name for statement in statements if isinstance(statement, LetStatement)]
        preexisting_names = set(scope.names)
        scope.names.update(let_names)
        # Parameters/loop/recover bindings are pre-existing; all let names are
        # then encountered in source order for duplicate detection.
        seen = preexisting_names
        encountered_lets: set[str] = set()

        for statement in statements:
            if isinstance(statement, LetStatement):
                name = statement.name.name
                is_duplicate = name in seen or name in encountered_lets
                if is_duplicate:
                    self._report(
                        unit,
                        "STC041",
                        f"variable {name!r} is already declared in this scope",
                        statement.name.location,
                    )
                else:
                    # The initializer is evaluated before this binding exists.
                    self._analyze_expression(
                        statement.initializer, scope, unit, symbols, hidden_here=name
                    )
                if is_duplicate:
                    self._analyze_expression(statement.initializer, scope, unit, symbols)
                encountered_lets.add(name)
                seen.add(name)
                continue
            self._analyze_statement(statement, scope, unit, symbols)

    def _analyze_statement(
        self,
        statement: Statement,
        scope: _Scope,
        unit: ModuleUnit,
        symbols: _ModuleSymbols,
    ) -> None:
        if isinstance(statement, (BreakStatement, ContinueStatement)):
            return
        if isinstance(statement, LetStatement):
            return
        if isinstance(statement, Block):
            self._analyze_block(statement, scope, unit, symbols)
        elif isinstance(statement, AttemptStatement):
            self._analyze_block(statement.body, scope, unit, symbols)
            handler_scope = _Scope(scope, {statement.error_name.name})
            self._analyze_block(
                statement.recover_body, handler_scope, unit, symbols
            )
            if statement.finally_body is not None:
                # `problem` is not visible in a finally body.
                self._analyze_block(statement.finally_body, scope, unit, symbols)
        elif isinstance(statement, ThrowStatement):
            self._analyze_expression(statement.value, scope, unit, symbols)
        elif isinstance(statement, ReturnStatement):
            if statement.value is not None:
                self._analyze_expression(statement.value, scope, unit, symbols)
        elif isinstance(statement, EmitStatement):
            self._analyze_expression(statement.value, scope, unit, symbols)
        elif isinstance(statement, ExpressionStatement):
            self._analyze_expression(statement.expression, scope, unit, symbols)
        elif isinstance(statement, WhenStatement):
            self._analyze_expression(statement.condition, scope, unit, symbols)
            self._analyze_block(statement.then_branch, scope, unit, symbols)
            if statement.otherwise_branch is not None:
                self._analyze_block(statement.otherwise_branch, scope, unit, symbols)
        elif isinstance(statement, WhileStatement):
            self._analyze_expression(statement.condition, scope, unit, symbols)
            self._analyze_block(statement.body, scope, unit, symbols)
        elif isinstance(statement, EachStatement):
            self._analyze_expression(statement.iterable, scope, unit, symbols)
            iteration_scope = _Scope(scope, {statement.variable.name})
            self._analyze_block(statement.body, iteration_scope, unit, symbols)

    def _analyze_expression(
        self,
        expression: Expression,
        scope: _Scope,
        unit: ModuleUnit,
        symbols: _ModuleSymbols,
        *,
        hidden_here: str | None = None,
    ) -> None:
        if isinstance(expression, LiteralExpression):
            return
        if isinstance(expression, VariableExpression):
            name = expression.name.name
            if not scope.contains(name, hidden_here=hidden_here):
                self._report(
                    unit,
                    "STC040",
                    f"undefined variable {name!r}",
                    expression.name.location,
                )
        elif isinstance(expression, ArrayExpression):
            for element in expression.elements:
                self._analyze_expression(
                    element, scope, unit, symbols, hidden_here=hidden_here
                )
        elif isinstance(expression, DictExpression):
            seen_literal_keys: set[tuple[str, str]] = set()
            for entry in expression.entries:
                self._analyze_expression(
                    entry.key, scope, unit, symbols, hidden_here=hidden_here
                )
                self._analyze_expression(
                    entry.value, scope, unit, symbols, hidden_here=hidden_here
                )
                literal = _static_literal_key(entry.key)
                if literal is None:
                    # A statically-known non int/str literal key is a definite
                    # runtime type error; dynamic keys are left to runtime.
                    if isinstance(entry.key, LiteralExpression):
                        self._report(
                            unit,
                            "STC043",
                            "dict key must be an integer or string",
                            entry.key.location,
                        )
                    continue
                if literal in seen_literal_keys:
                    self._report(
                        unit,
                        "STC042",
                        f"duplicate dict key {literal[1]!r}",
                        entry.location,
                    )
                else:
                    seen_literal_keys.add(literal)
        elif isinstance(expression, RecordConstructionExpression):
            name = expression.type_name.name
            fields = symbols.records.get(name) if unit is self.graph.entry else None
            if fields is None:
                self._report(
                    unit,
                    "STC020",
                    f"undefined record type {name!r}",
                    expression.type_name.location,
                )
            else:
                seen: set[str] = set()
                known = set(fields)
                for initializer in expression.fields:
                    field_name = initializer.name.name
                    if field_name in seen:
                        self._report(
                            unit,
                            "STC021",
                            f"record construction for {name!r} repeats field {field_name!r}",
                            initializer.name.location,
                        )
                    elif field_name not in known:
                        self._report(
                            unit,
                            "STC023",
                            f"record type {name!r} has no field {field_name!r}",
                            initializer.name.location,
                        )
                    seen.add(field_name)
                for field_name in fields:
                    if field_name not in seen:
                        self._report(
                            unit,
                            "STC022",
                            f"record construction for {name!r} is missing field {field_name!r}",
                            expression.type_name.location,
                        )
            for initializer in expression.fields:
                self._analyze_expression(
                    initializer.value, scope, unit, symbols, hidden_here=hidden_here
                )
        elif isinstance(expression, CallExpression):
            name = expression.callee.name
            declaration = symbols.functions.get(name)
            expected = (
                BUILTIN_ARITIES[name]
                if name in BUILTIN_ARITIES
                else len(declaration.parameters) if declaration is not None else None
            )
            if name not in BUILTIN_NAMES and declaration is None:
                self._report(
                    unit,
                    "STC010",
                    f"undefined function {name!r}",
                    expression.callee.location,
                )
            elif expected is not None and expected != len(expression.arguments):
                self._report(
                    unit,
                    "STC011",
                    f"function {name!r} expects {expected} arguments, got {len(expression.arguments)}",
                    expression.callee.location,
                )
            for argument in expression.arguments:
                self._analyze_expression(
                    argument, scope, unit, symbols, hidden_here=hidden_here
                )
        elif isinstance(expression, ModuleCallExpression):
            resolution = resolve_module_call(unit, expression)
            if resolution.problem == "alias":
                self._report(
                    unit,
                    "STC030",
                    f"undefined module alias {expression.alias.name!r}",
                    expression.alias.location,
                )
            elif resolution.problem == "member":
                self._report(
                    unit,
                    "STC031",
                    f"module {expression.alias.name!r} has no function {expression.member.name!r}",
                    expression.member.location,
                )
            elif resolution.declaration is not None and len(resolution.declaration.parameters) != len(expression.arguments):
                self._report(
                    unit,
                    "STC011",
                    f"function {expression.alias.name}.{expression.member.name} expects "
                    f"{len(resolution.declaration.parameters)} arguments, got {len(expression.arguments)}",
                    expression.location,
                )
            for argument in expression.arguments:
                self._analyze_expression(
                    argument, scope, unit, symbols, hidden_here=hidden_here
                )
        elif isinstance(expression, UnaryExpression):
            self._analyze_expression(
                expression.operand, scope, unit, symbols, hidden_here=hidden_here
            )
        elif isinstance(expression, BinaryExpression):
            self._analyze_expression(
                expression.left, scope, unit, symbols, hidden_here=hidden_here
            )
            self._analyze_expression(
                expression.right, scope, unit, symbols, hidden_here=hidden_here
            )
        elif isinstance(expression, AssignmentExpression):
            if isinstance(expression.target, VariableExpression):
                self._analyze_expression(
                    expression.target, scope, unit, symbols, hidden_here=hidden_here
                )
            elif isinstance(expression.target, IndexExpression):
                self._analyze_expression(
                    expression.target.object, scope, unit, symbols, hidden_here=hidden_here
                )
                self._analyze_expression(
                    expression.target.index, scope, unit, symbols, hidden_here=hidden_here
                )
            elif isinstance(expression.target, FieldExpression):
                self._analyze_expression(
                    expression.target.object, scope, unit, symbols, hidden_here=hidden_here
                )
            self._analyze_expression(
                expression.value, scope, unit, symbols, hidden_here=hidden_here
            )
        elif isinstance(expression, IndexExpression):
            self._analyze_expression(
                expression.object, scope, unit, symbols, hidden_here=hidden_here
            )
            self._analyze_expression(
                expression.index, scope, unit, symbols, hidden_here=hidden_here
            )
        elif isinstance(expression, FieldExpression):
            self._analyze_expression(
                expression.object, scope, unit, symbols, hidden_here=hidden_here
            )


def _static_literal_key(expression: Expression) -> tuple[str, str] | None:
    """Return a stable ``(kind, value)`` for a statically-known int/str key.

    Returns ``None`` for dynamic keys or literal kinds that are not valid map
    keys. The caller distinguishes a non-key literal (definite type error) from
    a dynamic expression (deferred to runtime) with an ``isinstance`` check.
    """

    if not isinstance(expression, LiteralExpression):
        return None
    if expression.kind is TokenKind.INT:
        return ("int", str(int(expression.lexeme)))
    if expression.kind is TokenKind.STRING:
        return ("str", str(expression.value))
    return None


def analyze_module_graph(
    graph: ModuleGraph, entry_source_path: str | None = None
) -> list[Diagnostic]:
    """Return deterministic diagnostics without evaluating any LWT expression."""

    return _Analyzer(graph, entry_source_path).analyze()
