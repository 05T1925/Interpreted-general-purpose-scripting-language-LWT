"""Document overlays, file URIs, and LSP UTF-16 position conversion."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit


@dataclass(slots=True)
class TextDocument:
    uri: str
    key: str
    path: Path
    language_id: str
    version: int
    text: str


def canonical_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def path_key(path: Path) -> str:
    return os.path.normcase(str(canonical_path(path)))


def path_from_file_uri(uri: str) -> Path:
    parsed = urlsplit(uri)
    if parsed.scheme.lower() != "file" or parsed.netloc not in ("", "localhost"):
        raise ValueError("only local file URIs are supported")
    if parsed.query or parsed.fragment:
        raise ValueError("file URI cannot contain query or fragment")
    decoded = unquote(parsed.path, errors="strict")
    if os.name == "nt":
        if re.match(r"^/[A-Za-z]:", decoded):
            decoded = decoded[1:]
        decoded = decoded.replace("/", "\\")
    elif not decoded.startswith("/"):
        raise ValueError("file URI must contain an absolute path")
    path = Path(decoded)
    if not path.is_absolute():
        raise ValueError("file URI must contain an absolute path")
    return canonical_path(path)


def file_uri(path: Path) -> str:
    return canonical_path(path).as_uri()


def normalized_source_lines(text: str) -> list[str]:
    """Match the lexer newline normalization without treating U+2028 as a break."""
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def utf16_character_to_codepoint(line: str, character: int) -> int | None:
    """Convert a zero-based UTF-16 column to a zero-based codepoint offset."""
    if isinstance(character, bool) or not isinstance(character, int) or character < 0:
        return None
    units = 0
    for index, char in enumerate(line):
        if units == character:
            return index
        width = 2 if ord(char) > 0xFFFF else 1
        if units < character < units + width:
            return None  # position splits a surrogate pair
        units += width
    if units == character:
        return len(line)
    return len(line) if character > units else None


def codepoint_to_utf16_character(line: str, codepoint_offset: int) -> int:
    if codepoint_offset < 0:
        codepoint_offset = 0
    prefix = line[:codepoint_offset]
    return sum(2 if ord(char) > 0xFFFF else 1 for char in prefix)


def lsp_position_to_offset(text: str, line: int, character: int) -> tuple[int, int] | None:
    lines = normalized_source_lines(text)
    if isinstance(line, bool) or not isinstance(line, int) or line < 0 or line >= len(lines):
        return None
    column = utf16_character_to_codepoint(lines[line], character)
    if column is None:
        return None
    return line + 1, column + 1


def source_position(line: int, column: int, text: str) -> dict[str, int]:
    lines = normalized_source_lines(text)
    line_index = max(0, min(line - 1, len(lines) - 1))
    column_index = max(0, column - 1)
    character = codepoint_to_utf16_character(lines[line_index], column_index)
    return {"line": line_index, "character": character}


def text_position_to_utf16(text: str, line: int, codepoint_column: int) -> dict[str, int]:
    """Convert one-based LWT source coordinates to a zero-based LSP position."""
    return source_position(line, codepoint_column, text)


def make_range(
    text: str, line: int, column: int, length: int = 1
) -> dict[str, dict[str, int]]:
    start = source_position(line, column, text)
    end = source_position(line, column + max(0, length), text)
    if (end["line"], end["character"]) < (start["line"], start["character"]):
        end = dict(start)
    return {"start": start, "end": end}
