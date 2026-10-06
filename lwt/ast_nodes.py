"""Source-located syntax tree nodes for LWT 0.1.

The tree records syntax only. It deliberately contains no evaluator, symbol
table, or name/type resolution.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import SourceLocation
from .lexer import TokenKind


@dataclass(frozen=True, slots=True)
class Identifier:
    """An identifier spelling and the position of its token."""

    name: str
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class Program:
    items: tuple[TopLevelItem, ...]
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class RecordDeclaration:
    name: Identifier
    fields: tuple[Identifier, ...]
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class FunctionDeclaration:
    name: Identifier
    parameters: tuple[Identifier, ...]
    body: Block
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class Block:
    statements: tuple[Statement, ...]
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class LetStatement:
    name: Identifier
    initializer: Expression
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class ReturnStatement:
    value: Expression | None
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class EmitStatement:
    value: Expression
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class ExpressionStatement:
    expression: Expression
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class WhenStatement:
    condition: Expression
    then_branch: Block
    otherwise_branch: Block | None
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class WhileStatement:
    condition: Expression
    body: Block
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class EachStatement:
    variable: Identifier
    iterable: Expression
    body: Block
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class LiteralExpression:
    """A literal token; INT values stay unconverted and retain their lexeme."""

    kind: TokenKind
    value: object | None
    lexeme: str
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class VariableExpression:
    name: Identifier
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class ArrayExpression:
    elements: tuple[Expression, ...]
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class RecordFieldInitializer:
    name: Identifier
    value: Expression
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class RecordConstructionExpression:
    type_name: Identifier
    fields: tuple[RecordFieldInitializer, ...]
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class CallExpression:
    callee: Identifier
    arguments: tuple[Expression, ...]
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class UnaryExpression:
    operator: TokenKind
    operand: Expression
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class BinaryExpression:
    left: Expression
    operator: TokenKind
    right: Expression
    operator_location: SourceLocation
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class AssignmentExpression:
    target: Expression
    value: Expression
    operator_location: SourceLocation
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class IndexExpression:
    object: Expression
    index: Expression
    access_location: SourceLocation
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class FieldExpression:
    object: Expression
    field: Identifier
    access_location: SourceLocation
    location: SourceLocation


Expression = (
    LiteralExpression
    | VariableExpression
    | ArrayExpression
    | RecordConstructionExpression
    | CallExpression
    | UnaryExpression
    | BinaryExpression
    | AssignmentExpression
    | IndexExpression
    | FieldExpression
)
Statement = (
    LetStatement
    | ReturnStatement
    | EmitStatement
    | ExpressionStatement
    | WhenStatement
    | WhileStatement
    | EachStatement
    | Block
)
TopLevelItem = RecordDeclaration | FunctionDeclaration | Statement
