"""Hand-written scanner for the LWT 0.1 lexical rules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NoReturn

from .errors import LwtError, SourceLocation


class TokenKind(str, Enum):
    EOF = "EOF"
    IDENT = "IDENT"
    INT = "INT"
    STRING = "STRING"

    RECORD = "record"
    FN = "fn"
    LET = "let"
    WHEN = "when"
    OTHERWISE = "otherwise"
    WHILE = "while"
    EACH = "each"
    IN = "in"
    RETURN = "return"
    EMIT = "emit"
    TRUE = "true"
    FALSE = "false"
    NULL = "null"
    AND = "and"
    OR = "or"
    NOT = "not"
    BREAK = "break"
    CONTINUE = "continue"

    PLUS = "+"
    MINUS = "-"
    STAR = "*"
    SLASH = "/"
    PERCENT = "%"
    EQUAL_EQUAL = "=="
    BANG_EQUAL = "!="
    LESS = "<"
    LESS_EQUAL = "<="
    GREATER = ">"
    GREATER_EQUAL = ">="
    EQUAL = "="
    LEFT_PAREN = "("
    RIGHT_PAREN = ")"
    LEFT_BRACE = "{"
    RIGHT_BRACE = "}"
    LEFT_BRACKET = "["
    RIGHT_BRACKET = "]"
    COMMA = ","
    COLON = ":"
    SEMICOLON = ";"
    DOT = "."


@dataclass(frozen=True, slots=True)
class Token:
    """A lexical token retaining its exact spelling and one-based position."""

    kind: TokenKind
    lexeme: str
    literal: object | None
    line: int
    column: int


_KEYWORDS: dict[str, TokenKind] = {
    "record": TokenKind.RECORD,
    "fn": TokenKind.FN,
    "let": TokenKind.LET,
    "when": TokenKind.WHEN,
    "otherwise": TokenKind.OTHERWISE,
    "while": TokenKind.WHILE,
    "each": TokenKind.EACH,
    "in": TokenKind.IN,
    "return": TokenKind.RETURN,
    "emit": TokenKind.EMIT,
    "true": TokenKind.TRUE,
    "false": TokenKind.FALSE,
    "null": TokenKind.NULL,
    "and": TokenKind.AND,
    "or": TokenKind.OR,
    "not": TokenKind.NOT,
    "break": TokenKind.BREAK,
    "continue": TokenKind.CONTINUE,
}

_SINGLE_CHARACTERS: dict[str, TokenKind] = {
    "+": TokenKind.PLUS,
    "-": TokenKind.MINUS,
    "*": TokenKind.STAR,
    "/": TokenKind.SLASH,
    "%": TokenKind.PERCENT,
    "<": TokenKind.LESS,
    ">": TokenKind.GREATER,
    "=": TokenKind.EQUAL,
    "(": TokenKind.LEFT_PAREN,
    ")": TokenKind.RIGHT_PAREN,
    "{": TokenKind.LEFT_BRACE,
    "}": TokenKind.RIGHT_BRACE,
    "[": TokenKind.LEFT_BRACKET,
    "]": TokenKind.RIGHT_BRACKET,
    ",": TokenKind.COMMA,
    ":": TokenKind.COLON,
    ";": TokenKind.SEMICOLON,
    ".": TokenKind.DOT,
}

_DOUBLE_CHARACTERS: dict[str, TokenKind] = {
    "==": TokenKind.EQUAL_EQUAL,
    "!=": TokenKind.BANG_EQUAL,
    "<=": TokenKind.LESS_EQUAL,
    ">=": TokenKind.GREATER_EQUAL,
}

_ESCAPES = {"\\": "\\", '"': '"', "n": "\n", "t": "\t"}
_WHITESPACE = {" ", "\t", "\n", "\f", "\v"}


def normalize_source(source: str) -> str:
    """Apply the S1 newline rule and remove exactly one leading BOM."""

    normalized = source.replace("\r\n", "\n").replace("\r", "\n")
    if normalized.startswith("\ufeff"):
        normalized = normalized[1:]
    return normalized


class Lexer:
    """Scan a source string into tokens, raising on the first lexical error."""

    def __init__(self, source: str) -> None:
        self.source = normalize_source(source)
        self.start = 0
        self.current = 0
        self.line = 1
        self.column = 1
        self.start_line = 1
        self.start_column = 1
        self.tokens: list[Token] = []

    def scan_tokens(self) -> list[Token]:
        while not self._at_end():
            self.start = self.current
            self.start_line = self.line
            self.start_column = self.column
            self._scan_one()

        self.tokens.append(
            Token(TokenKind.EOF, "", None, self.line, self.column)
        )
        return self.tokens

    def _scan_one(self) -> None:
        character = self._advance()

        if character in _WHITESPACE:
            return
        if character == "#":
            self._comment()
            return
        if self._is_ascii_letter(character) or character == "_":
            self._identifier()
            return
        if self._is_ascii_digit(character):
            self._integer()
            return
        if character == '"':
            self._string()
            return

        following = self._peek()
        if following:
            pair = character + following
            kind = _DOUBLE_CHARACTERS.get(pair)
            if kind is not None:
                self._advance()
                self._add_token(kind)
                return

        kind = _SINGLE_CHARACTERS.get(character)
        if kind is not None:
            self._add_token(kind)
            return

        self._error(
            f"unexpected character U+{ord(character):04X}",
            SourceLocation(self.start_line, self.start_column),
        )

    def _comment(self) -> None:
        while not self._at_end() and self._peek() != "\n":
            self._advance()

    def _identifier(self) -> None:
        while True:
            character = self._peek()
            if not (
                self._is_ascii_letter(character)
                or self._is_ascii_digit(character)
                or character == "_"
            ):
                break
            self._advance()

        lexeme = self.source[self.start : self.current]
        kind = _KEYWORDS.get(lexeme, TokenKind.IDENT)
        literal: object | None = None
        if kind is TokenKind.TRUE:
            literal = True
        elif kind is TokenKind.FALSE:
            literal = False
        self._add_token(kind, literal)

    def _integer(self) -> None:
        while self._is_ascii_digit(self._peek()):
            self._advance()
        # Keep the decimal spelling untouched. S2 must not call int() here.
        self._add_token(TokenKind.INT)

    def _string(self) -> None:
        opening = SourceLocation(self.start_line, self.start_column)
        value: list[str] = []

        while not self._at_end():
            character = self._advance()
            if character == '"':
                self._add_token(TokenKind.STRING, "".join(value))
                return
            if character == "\n":
                self._error("raw newline in string literal", opening)
            if character != "\\":
                value.append(character)
                continue

            escape_location = SourceLocation(self.line, self.column - 1)
            if self._at_end():
                self._error("incomplete string escape", escape_location)
            escape = self._advance()
            decoded = _ESCAPES.get(escape)
            if decoded is None:
                self._error("unknown string escape", escape_location)
            value.append(decoded)

        self._error("unterminated string literal", opening)

    def _add_token(self, kind: TokenKind, literal: object | None = None) -> None:
        lexeme = self.source[self.start : self.current]
        self.tokens.append(
            Token(kind, lexeme, literal, self.start_line, self.start_column)
        )

    def _error(self, message: str, location: SourceLocation) -> NoReturn:
        raise LwtError("LexError", message, 2, location)

    def _advance(self) -> str:
        character = self.source[self.current]
        self.current += 1
        if character == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return character

    def _peek(self) -> str:
        if self._at_end():
            return ""
        return self.source[self.current]

    def _at_end(self) -> bool:
        return self.current >= len(self.source)

    @staticmethod
    def _is_ascii_letter(character: str) -> bool:
        return "a" <= character <= "z" or "A" <= character <= "Z"

    @staticmethod
    def _is_ascii_digit(character: str) -> bool:
        return "0" <= character <= "9"


def scan(source: str) -> list[Token]:
    """Convenience API used by the CLI and lexer unit tests."""

    return Lexer(source).scan_tokens()
