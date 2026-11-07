"""Deterministic LWT AST inventory and runtime execution profile collector.

Profiles record LWT-level control flow only.  This module never inspects Python
frames or serializes runtime values.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

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
from .modules import ModuleGraph, ModuleUnit


def _display_entry_path(path: str) -> str:
    supplied = path.replace("\\", "/")
    candidate = Path(path)
    if candidate.is_absolute():
        try:
            return candidate.resolve().relative_to(Path.cwd().resolve()).as_posix()
        except (OSError, ValueError, RuntimeError):
            return candidate.name or "entry.lwt"
    return supplied or "entry.lwt"


def _stable_id(kind: str, source: str, line: int, column: int, label: str = "") -> str:
    material = f"{kind}\0{source}\0{line}\0{column}\0{label}".encode("utf-8")
    return f"{kind}-{hashlib.sha256(material).hexdigest()[:24]}"


def _summary(covered: int, total: int) -> dict[str, object]:
    return {
        "covered": covered,
        "total": total,
        "percentage": None if total == 0 else round(covered * 100.0 / total, 2),
    }


def _statement_kind(statement: Statement) -> str:
    return type(statement).__name__.removesuffix("Statement").lower()


class ProfileCollector:
    """Collect LWT events and compare them with the complete module AST."""

    def __init__(self, graph: ModuleGraph, entry_path: str) -> None:
        self.graph = graph
        self.entry = _display_entry_path(entry_path)
        self._source_by_unit: dict[ModuleUnit, str] = {}
        self._modules: list[dict[str, object]] = []
        self._statements: list[dict[str, object]] = []
        self._functions: list[dict[str, object]] = []
        self._decisions: list[dict[str, object]] = []
        self._statement_index: dict[str, dict[str, object]] = {}
        self._function_index: dict[str, dict[str, object]] = {}
        self._decision_index: dict[str, dict[str, object]] = {}
        self._events: list[dict[str, object]] = []
        self._sequence = 0
        self._depth = 0
        self._status = "success"
        self._exit_code = 0

        for unit in graph.modules:
            source = self.entry if unit is graph.entry else (unit.display_path or unit.canonical_path.name).replace("\\", "/")
            self._source_by_unit[unit] = source
            digest = unit.source_sha256
            if digest is None:
                try:
                    digest = hashlib.sha256(unit.canonical_path.read_bytes()).hexdigest()
                except OSError:
                    raise LwtError("FileError", "cannot read source for execution profile", 4) from None
            module = {
                "source": source,
                "sha256": digest,
                "entry": unit is graph.entry,
                "function_count": 0,
                "statement_count": 0,
                "decision_count": 0,
            }
            self._modules.append(module)
            self._scan_unit(unit, source, module)

        for category, records in (
            ("statement", self._statements),
            ("function", self._functions),
            ("decision", self._decisions),
        ):
            ids = [str(record["id"]) for record in records]
            if len(ids) != len(set(ids)):
                raise LwtError("FileError", f"duplicate {category} IDs in execution profile", 4)

    def source_for(self, unit: ModuleUnit) -> str:
        return self._source_by_unit[unit]

    def source_at(self, location: SourceLocation | None, fallback: str) -> str:
        if location is not None and location.source_path:
            return location.source_path.replace("\\", "/")
        return fallback

    def _scan_unit(
        self, unit: ModuleUnit, source: str, module: dict[str, object]
    ) -> None:
        def scan_expression(expression: Expression) -> None:
            if isinstance(expression, BinaryExpression):
                if expression.operator.name in {"AND", "OR"}:
                    label = expression.operator.name.lower()
                    self._add_decision(
                        source,
                        expression.operator_location,
                        label,
                        ["short_circuit", "evaluate_right"],
                    )
                    module["decision_count"] = int(module["decision_count"]) + 1
                scan_expression(expression.left)
                scan_expression(expression.right)
            elif isinstance(expression, UnaryExpression):
                scan_expression(expression.operand)
            elif isinstance(expression, AssignmentExpression):
                scan_expression(expression.target)
                scan_expression(expression.value)
            elif isinstance(expression, ArrayExpression):
                for child in expression.elements:
                    scan_expression(child)
            elif isinstance(expression, DictExpression):
                for entry in expression.entries:
                    scan_expression(entry.key)
                    scan_expression(entry.value)
            elif isinstance(expression, RecordConstructionExpression):
                for field in expression.fields:
                    scan_expression(field.value)
            elif isinstance(expression, CallExpression):
                for child in expression.arguments:
                    scan_expression(child)
            elif isinstance(expression, ModuleCallExpression):
                for child in expression.arguments:
                    scan_expression(child)
            elif isinstance(expression, IndexExpression):
                scan_expression(expression.object)
                scan_expression(expression.index)
            elif isinstance(expression, FieldExpression):
                scan_expression(expression.object)
            elif isinstance(expression, (LiteralExpression, VariableExpression)):
                return
            else:
                raise AssertionError(f"unhandled expression in profile scan: {type(expression)!r}")

        def scan_statement(statement: Statement) -> None:
            if isinstance(statement, Block):
                for child in statement.statements:
                    scan_statement(child)
                return

            kind = _statement_kind(statement)
            self._add_statement(source, statement.location, kind)
            module["statement_count"] = int(module["statement_count"]) + 1
            if isinstance(statement, LetStatement):
                scan_expression(statement.initializer)
            elif isinstance(statement, ExpressionStatement):
                scan_expression(statement.expression)
            elif isinstance(statement, EmitStatement):
                scan_expression(statement.value)
            elif isinstance(statement, ReturnStatement):
                if statement.value is not None:
                    scan_expression(statement.value)
            elif isinstance(statement, WhenStatement):
                self._add_decision(source, statement.location, "when", ["then", "otherwise"])
                module["decision_count"] = int(module["decision_count"]) + 1
                scan_expression(statement.condition)
                scan_statement(statement.then_branch)
                if statement.otherwise_branch is not None:
                    scan_statement(statement.otherwise_branch)
            elif isinstance(statement, WhileStatement):
                self._add_decision(source, statement.location, "while", ["true", "false"])
                module["decision_count"] = int(module["decision_count"]) + 1
                scan_expression(statement.condition)
                scan_statement(statement.body)
            elif isinstance(statement, EachStatement):
                self._add_decision(source, statement.location, "each", ["empty", "nonempty"])
                module["decision_count"] = int(module["decision_count"]) + 1
                scan_expression(statement.iterable)
                scan_statement(statement.body)
            elif isinstance(statement, AttemptStatement):
                self._add_decision(source, statement.location, "attempt", ["normal", "recovered"])
                module["decision_count"] = int(module["decision_count"]) + 1
                scan_statement(statement.body)
                scan_statement(statement.recover_body)
                if statement.finally_body is not None:
                    scan_statement(statement.finally_body)
            elif isinstance(statement, ThrowStatement):
                scan_expression(statement.value)
            elif isinstance(statement, (BreakStatement, ContinueStatement)):
                return
            else:
                raise AssertionError(f"unhandled statement in profile scan: {type(statement)!r}")

        for item in unit.program.items:
            if isinstance(item, FunctionDeclaration):
                function_source = self.source_at(item.name.location, source)
                function_id = _stable_id(
                    "function", function_source, item.name.location.line,
                    item.name.location.column, item.name.name,
                )
                self._functions.append(
                    {
                        "id": function_id,
                        "source": function_source,
                        "line": item.name.location.line,
                        "column": item.name.location.column,
                        "name": item.name.name,
                        "qualified_name": item.name.name if unit is self.graph.entry else f"{source}.{item.name.name}",
                        "call_count": 0,
                        "covered": False,
                        "explicit_returns": 0,
                        "natural_returns": 0,
                    }
                )
                self._function_index[function_id] = self._functions[-1]
                module["function_count"] = int(module["function_count"]) + 1
                for child in item.body.statements:
                    scan_statement(child)
            elif isinstance(item, (ImportDeclaration, RecordDeclaration)):
                continue
            else:
                scan_statement(item)

    def _add_statement(self, source: str, location: SourceLocation, kind: str) -> dict[str, object]:
        identifier = _stable_id("stmt", source, location.line, location.column, kind)
        record = {
            "id": identifier,
            "source": source,
            "line": location.line,
            "column": location.column,
            "kind": kind,
            "hit_count": 0,
            "covered": False,
        }
        self._statements.append(record)
        self._statement_index[identifier] = record
        return record

    def _add_decision(
        self, source: str, location: SourceLocation, kind: str, outcomes: list[str]
    ) -> dict[str, object]:
        identifier = _stable_id("decision", source, location.line, location.column, kind)
        record = {
            "id": identifier,
            "source": source,
            "line": location.line,
            "column": location.column,
            "kind": kind,
            "outcomes": [
                {"name": name, "count": 0, "covered": False} for name in outcomes
            ],
            "covered_outcomes": 0,
            "total_outcomes": len(outcomes),
            "percentage": 0.0,
            "covered": False,
        }
        self._decisions.append(record)
        self._decision_index[identifier] = record
        return record

    def _append_event(
        self,
        event: str,
        source: str,
        location: SourceLocation | None,
        **extra: object,
    ) -> None:
        self._sequence += 1
        record: dict[str, object] = {
            "sequence": self._sequence,
            "event": event,
            "source": source,
            "line": location.line if location is not None else None,
            "column": location.column if location is not None else None,
            "depth": self._depth,
        }
        record.update(extra)
        self._events.append(record)

    def program_start(self, program: Program) -> None:
        self._append_event("program_start", self.entry, program.location)

    def statement(self, statement: Statement, source: str) -> None:
        if isinstance(statement, Block):
            return
        kind = _statement_kind(statement)
        identifier = _stable_id("stmt", source, statement.location.line, statement.location.column, kind)
        record = self._statement_index[identifier]
        record["hit_count"] = int(record["hit_count"]) + 1
        record["covered"] = True
        self._append_event("statement", source, statement.location, node_id=identifier, kind=kind)

    def decision(self, source: str, location: SourceLocation, kind: str, outcome: str) -> None:
        identifier = _stable_id("decision", source, location.line, location.column, kind)
        record = self._decision_index[identifier]
        outcomes = record["outcomes"]
        assert isinstance(outcomes, list)
        selected = next((item for item in outcomes if item["name"] == outcome), None)
        if selected is None:
            raise AssertionError(f"unknown outcome {outcome!r} for {kind}")
        selected["count"] = int(selected["count"]) + 1
        selected["covered"] = True
        covered = sum(bool(item["covered"]) for item in outcomes)
        record["covered_outcomes"] = covered
        record["covered"] = covered == int(record["total_outcomes"])
        record["percentage"] = round(covered * 100.0 / int(record["total_outcomes"]), 2)
        self._append_event("decision", source, location, node_id=identifier, kind=kind, outcome=outcome)

    def function_call(
        self,
        declaration: FunctionDeclaration,
        qualified_name: str,
        module_source: str,
        caller_source: str,
        call_location: SourceLocation,
    ) -> None:
        source = self.source_at(declaration.name.location, module_source)
        identifier = _stable_id(
            "function", source, declaration.name.location.line,
            declaration.name.location.column, declaration.name.name,
        )
        record = self._function_index[identifier]
        record["call_count"] = int(record["call_count"]) + 1
        record["covered"] = True
        self._depth += 1
        self._append_event(
            "function_call",
            caller_source,
            call_location,
            function_id=identifier,
            module=source,
            function_name=declaration.name.name,
            qualified_name=qualified_name,
            declaration_line=declaration.name.location.line,
            declaration_column=declaration.name.location.column,
            call_source=caller_source,
            call_line=call_location.line,
            call_column=call_location.column,
        )

    def function_return(
        self,
        declaration: FunctionDeclaration,
        module_source: str,
        location: SourceLocation,
        return_kind: str,
        qualified_name: str,
    ) -> None:
        source = self.source_at(location, module_source)
        identifier = _stable_id(
            "function", self.source_at(declaration.name.location, module_source),
            declaration.name.location.line, declaration.name.location.column,
            declaration.name.name,
        )
        record = self._function_index[identifier]
        key = "explicit_returns" if return_kind == "explicit" else "natural_returns"
        record[key] = int(record[key]) + 1
        self._append_event(
            "function_return",
            source,
            location,
            function_id=identifier,
            module=self.source_at(declaration.name.location, module_source),
            function_name=declaration.name.name,
            qualified_name=qualified_name,
            return_kind=return_kind,
        )

    def leave_function(self) -> None:
        self._depth -= 1

    def recover(self, source: str, statement: AttemptStatement, error: LwtError) -> None:
        location = error.location
        self._append_event(
            "recover",
            source,
            statement.location,
            error_category=error.category,
            error_source=self.source_at(location, source),
            error_line=location.line if location is not None else None,
            error_column=location.column if location is not None else None,
        )

    def runtime_error(self, error: LwtError, fallback: str) -> None:
        location = error.location
        self._append_event(
            "runtime_error",
            self.source_at(location, fallback),
            location,
            category=error.category,
            message=getattr(error, "profile_message", error.message),
            message_redacted=hasattr(error, "profile_message"),
        )

    def program_end(self, source: str, location: SourceLocation, status: str, exit_code: int) -> None:
        self._status = status
        self._exit_code = exit_code
        self._append_event("program_end", source, location, status=status, exit_code=exit_code)

    def as_dict(self) -> dict[str, object]:
        statement_summary = _summary(sum(bool(row["covered"]) for row in self._statements), len(self._statements))
        function_summary = _summary(sum(bool(row["covered"]) for row in self._functions), len(self._functions))
        decision_summary = _summary(sum(int(row["covered_outcomes"]) for row in self._decisions), sum(int(row["total_outcomes"]) for row in self._decisions))

        per_module: list[dict[str, object]] = []
        for module in self._modules:
            source = str(module["source"])
            statements = [row for row in self._statements if row["source"] == source]
            functions = [row for row in self._functions if row["source"] == source]
            decisions = [row for row in self._decisions if row["source"] == source]
            per_module.append(
                {
                    "source": source,
                    "statements": _summary(sum(bool(row["covered"]) for row in statements), len(statements)),
                    "functions": _summary(sum(bool(row["covered"]) for row in functions), len(functions)),
                    "decisions": _summary(sum(int(row["covered_outcomes"]) for row in decisions), sum(int(row["total_outcomes"]) for row in decisions)),
                }
            )

        return {
            "schema_version": 1,
            "tool": "lwt-profile",
            "entry": self.entry,
            "status": self._status,
            "exit_code": self._exit_code,
            "modules": self._modules,
            "events": self._events,
            "coverage": {
                "summary": {
                    "statements": statement_summary,
                    "functions": function_summary,
                    "decisions": decision_summary,
                },
                "by_module": per_module,
                "statements": self._statements,
                "functions": self._functions,
                "decisions": self._decisions,
            },
        }
