"""Recursive-descent parser for the complete LWT 0.1 grammar."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Callable, NoReturn

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
    Identifier,
    IndexExpression,
    LetStatement,
    LiteralExpression,
    Program,
    RecordConstructionExpression,
    RecordDeclaration,
    RecordFieldInitializer,
    ReturnStatement,
    Statement,
    TopLevelItem,
    UnaryExpression,
    VariableExpression,
    WhenStatement,
    WhileStatement,
)
from .errors import LwtError, SourceLocation
from .lexer import Token, TokenKind


# Each group is left-associative; the groups' order is defined by the call chain.
_EQUALITY_OPERATORS = frozenset({TokenKind.EQUAL_EQUAL, TokenKind.BANG_EQUAL})
_COMPARISON_OPERATORS = frozenset(
    {TokenKind.LESS, TokenKind.LESS_EQUAL, TokenKind.GREATER, TokenKind.GREATER_EQUAL}
)
_ADDITIVE_OPERATORS = frozenset({TokenKind.PLUS, TokenKind.MINUS})
_MULTIPLICATIVE_OPERATORS = frozenset(
    {TokenKind.STAR, TokenKind.SLASH, TokenKind.PERCENT}
)


class Parser:
    """Build an ordered AST or raise one located ``SyntaxError`` diagnostic."""

    def __init__(self, tokens: Sequence[Token]) -> None:
        if not tokens or tokens[-1].kind is not TokenKind.EOF:
            raise ValueError("parser input must end with an EOF token")
        self.tokens = tokens
        self.current = 0

    def parse(self) -> Program:
        items: list[TopLevelItem] = []
        start = _token_location(self._peek())
        while not self._check(TokenKind.EOF):
            if self._match(TokenKind.RECORD):
                items.append(self._record_declaration(self._previous()))
            elif self._match(TokenKind.FN):
                items.append(self._function_declaration(self._previous()))
            else:
                items.append(self._statement(return_allowed=False))
        eof = self._consume(TokenKind.EOF, "expected end of file")
        return Program(tuple(items), start if items else _token_location(eof))

    def _record_declaration(self, keyword: Token) -> RecordDeclaration:
        name = self._identifier("expected record name")
        self._consume(TokenKind.LEFT_BRACE, "expected '{' after record name")
        fields: list[Identifier] = []
        seen: set[str] = set()
        if not self._check(TokenKind.RIGHT_BRACE):
            while True:
                field = self._identifier("expected record field name")
                if field.name in seen:
                    self._error("duplicate field name in record declaration", self._previous())
                seen.add(field.name)
                fields.append(field)
                if not self._match(TokenKind.COMMA):
                    break
        self._consume(TokenKind.RIGHT_BRACE, "expected '}' after record fields")
        self._consume(TokenKind.SEMICOLON, "expected ';' after record declaration")
        return RecordDeclaration(name, tuple(fields), _token_location(keyword))

    def _function_declaration(self, keyword: Token) -> FunctionDeclaration:
        name = self._identifier("expected function name")
        self._consume(TokenKind.LEFT_PAREN, "expected '(' after function name")
        parameters: list[Identifier] = []
        seen: set[str] = set()
        if not self._check(TokenKind.RIGHT_PAREN):
            while True:
                parameter = self._identifier("expected parameter name")
                if parameter.name in seen:
                    self._error("duplicate parameter name", self._previous())
                seen.add(parameter.name)
                parameters.append(parameter)
                if not self._match(TokenKind.COMMA):
                    break
        self._consume(TokenKind.RIGHT_PAREN, "expected ')' after parameters")
        body = self._block(return_allowed=True)
        return FunctionDeclaration(name, tuple(parameters), body, _token_location(keyword))

    def _statement(self, return_allowed: bool) -> Statement:
        if self._match(TokenKind.LET):
            keyword = self._previous()
            name = self._identifier("expected variable name after 'let'")
            self._consume(TokenKind.EQUAL, "expected '=' after variable name")
            initializer = self._expression()
            self._consume(TokenKind.SEMICOLON, "expected ';' after let statement")
            return LetStatement(name, initializer, _token_location(keyword))

        if self._match(TokenKind.RETURN):
            keyword = self._previous()
            if not return_allowed:
                self._error("return is only allowed inside a function", keyword)
            value = None if self._check(TokenKind.SEMICOLON) else self._expression()
            self._consume(TokenKind.SEMICOLON, "expected ';' after return statement")
            return ReturnStatement(value, _token_location(keyword))

        if self._match(TokenKind.EMIT):
            keyword = self._previous()
            value = self._expression()
            self._consume(TokenKind.SEMICOLON, "expected ';' after emit statement")
            return EmitStatement(value, _token_location(keyword))

        if self._match(TokenKind.WHEN):
            keyword = self._previous()
            self._consume(TokenKind.LEFT_PAREN, "expected '(' after 'when'")
            condition = self._expression()
            self._consume(TokenKind.RIGHT_PAREN, "expected ')' after when condition")
            then_branch = self._block(return_allowed=return_allowed)
            otherwise_branch = None
            if self._match(TokenKind.OTHERWISE):
                otherwise_branch = self._block(return_allowed=return_allowed)
            return WhenStatement(
                condition, then_branch, otherwise_branch, _token_location(keyword)
            )

        if self._match(TokenKind.WHILE):
            keyword = self._previous()
            self._consume(TokenKind.LEFT_PAREN, "expected '(' after 'while'")
            condition = self._expression()
            self._consume(TokenKind.RIGHT_PAREN, "expected ')' after while condition")
            body = self._block(return_allowed=return_allowed)
            return WhileStatement(condition, body, _token_location(keyword))

        if self._match(TokenKind.EACH):
            keyword = self._previous()
            self._consume(TokenKind.LEFT_PAREN, "expected '(' after 'each'")
            variable = self._identifier("expected loop variable after 'each('")
            self._consume(TokenKind.IN, "expected 'in' after each loop variable")
            iterable = self._expression()
            self._consume(TokenKind.RIGHT_PAREN, "expected ')' after each iterable")
            body = self._block(return_allowed=return_allowed)
            return EachStatement(variable, iterable, body, _token_location(keyword))

        if self._match(TokenKind.LEFT_BRACE):
            return self._block(self._previous(), return_allowed)

        if self._check(TokenKind.BREAK) or self._check(TokenKind.CONTINUE):
            token = self._advance()
            self._error(f"unsupported statement {token.lexeme!r}", token)

        expression = self._expression()
        self._consume(TokenKind.SEMICOLON, "expected ';' after expression")
        return ExpressionStatement(expression, expression.location)

    def _block(self, opening: Token | None = None, return_allowed: bool = False) -> Block:
        if opening is None:
            opening = self._consume(TokenKind.LEFT_BRACE, "expected '{' to begin block")
        statements: list[Statement] = []
        while not self._check(TokenKind.RIGHT_BRACE) and not self._check(TokenKind.EOF):
            statements.append(self._statement(return_allowed))
        self._consume(TokenKind.RIGHT_BRACE, "expected '}' after block")
        return Block(tuple(statements), _token_location(opening))

    def _expression(self) -> Expression:
        return self._assignment()

    def _assignment(self) -> Expression:
        target = self._logic_or()
        if self._match(TokenKind.EQUAL):
            equals = self._previous()
            if not isinstance(
                target, (VariableExpression, IndexExpression, FieldExpression)
            ):
                self._error("invalid assignment target", equals)
            value = self._assignment()
            return AssignmentExpression(
                target, value, _token_location(equals), target.location
            )
        return target

    def _logic_or(self) -> Expression:
        return self._left_associative(self._logic_and, frozenset({TokenKind.OR}))

    def _logic_and(self) -> Expression:
        return self._left_associative(self._equality, frozenset({TokenKind.AND}))

    def _equality(self) -> Expression:
        return self._left_associative(self._comparison, _EQUALITY_OPERATORS)

    def _comparison(self) -> Expression:
        return self._left_associative(self._additive, _COMPARISON_OPERATORS)

    def _additive(self) -> Expression:
        return self._left_associative(self._multiplicative, _ADDITIVE_OPERATORS)

    def _multiplicative(self) -> Expression:
        return self._left_associative(self._unary, _MULTIPLICATIVE_OPERATORS)

    def _left_associative(
        self,
        next_level: Callable[[], Expression],
        operators: frozenset[TokenKind],
    ) -> Expression:
        expression = next_level()
        while self._peek().kind in operators:
            operator = self._advance()
            right = next_level()
            expression = BinaryExpression(
                expression,
                operator.kind,
                right,
                _token_location(operator),
                expression.location,
            )
        return expression

    def _unary(self) -> Expression:
        if self._match(TokenKind.NOT, TokenKind.MINUS):
            operator = self._previous()
            return UnaryExpression(
                operator.kind, self._unary(), _token_location(operator)
            )
        return self._postfix()

    def _postfix(self) -> Expression:
        expression = self._atom()
        while True:
            if self._match(TokenKind.LEFT_BRACKET):
                index = self._expression()
                self._consume(TokenKind.RIGHT_BRACKET, "expected ']' after index")
                expression = IndexExpression(expression, index, expression.location)
            elif self._match(TokenKind.DOT):
                field = self._identifier("expected field name after '.'")
                expression = FieldExpression(expression, field, expression.location)
            else:
                return expression

    def _atom(self) -> Expression:
        if self._match(
            TokenKind.INT,
            TokenKind.STRING,
            TokenKind.TRUE,
            TokenKind.FALSE,
            TokenKind.NULL,
        ):
            token = self._previous()
            return LiteralExpression(
                token.kind, token.literal, token.lexeme, _token_location(token)
            )

        if self._match(TokenKind.LEFT_BRACKET):
            opening = self._previous()
            elements: list[Expression] = []
            if not self._check(TokenKind.RIGHT_BRACKET):
                while True:
                    elements.append(self._expression())
                    if not self._match(TokenKind.COMMA):
                        break
            self._consume(TokenKind.RIGHT_BRACKET, "expected ']' after array elements")
            return ArrayExpression(tuple(elements), _token_location(opening))

        if self._match(TokenKind.IDENT):
            name_token = self._previous()
            name = self._identifier_from_token(name_token)
            if self._match(TokenKind.LEFT_PAREN):
                arguments: list[Expression] = []
                if not self._check(TokenKind.RIGHT_PAREN):
                    while True:
                        arguments.append(self._expression())
                        if not self._match(TokenKind.COMMA):
                            break
                self._consume(TokenKind.RIGHT_PAREN, "expected ')' after arguments")
                return CallExpression(name, tuple(arguments), name.location)
            if self._match(TokenKind.LEFT_BRACE):
                fields: list[RecordFieldInitializer] = []
                if not self._check(TokenKind.RIGHT_BRACE):
                    while True:
                        field_token = self._consume(
                            TokenKind.IDENT, "expected field name in record constructor"
                        )
                        field = self._identifier_from_token(field_token)
                        self._consume(TokenKind.COLON, "expected ':' after field name")
                        value = self._expression()
                        fields.append(
                            RecordFieldInitializer(field, value, field.location)
                        )
                        if not self._match(TokenKind.COMMA):
                            break
                self._consume(
                    TokenKind.RIGHT_BRACE,
                    "expected '}' after record constructor fields",
                )
                return RecordConstructionExpression(name, tuple(fields), name.location)
            return VariableExpression(name, name.location)

        if self._match(TokenKind.LEFT_PAREN):
            expression = self._expression()
            self._consume(TokenKind.RIGHT_PAREN, "expected ')' after expression")
            return expression

        self._error("expected expression", self._peek())

    def _identifier(self, message: str) -> Identifier:
        return self._identifier_from_token(self._consume(TokenKind.IDENT, message))

    @staticmethod
    def _identifier_from_token(token: Token) -> Identifier:
        return Identifier(token.lexeme, _token_location(token))

    def _consume(self, kind: TokenKind, message: str) -> Token:
        if self._check(kind):
            return self._advance()
        self._error(message, self._peek())

    def _match(self, *kinds: TokenKind) -> bool:
        if any(self._check(kind) for kind in kinds):
            self._advance()
            return True
        return False

    def _check(self, kind: TokenKind) -> bool:
        return self._peek().kind is kind

    def _advance(self) -> Token:
        token = self._peek()
        if token.kind is not TokenKind.EOF:
            self.current += 1
        return token

    def _peek(self) -> Token:
        return self.tokens[self.current]

    def _previous(self) -> Token:
        return self.tokens[self.current - 1]

    @staticmethod
    def _error(message: str, token: Token) -> NoReturn:
        raise LwtError(
            "SyntaxError",
            message,
            2,
            SourceLocation(token.line, token.column),
        )


def parse(tokens: Sequence[Token]) -> Program:
    """Parse a complete lexer token stream, including its terminal EOF."""

    return Parser(tokens).parse()


def _token_location(token: Token) -> SourceLocation:
    return SourceLocation(token.line, token.column)
