"""Arbitrary-precision decimal <-> int helpers with no external dependencies.

Kept dependency-free so both the parser (S44 P0-4 literal pre-decoding) and the
runtime can share one implementation. The chunked algorithms are deliberately
kept from ``lwt.runtime``: they avoid handing a very long decimal string
directly to ``int``/``str`` so CPython 3.11+'s ``sys.set_int_max_str_digits``
limit does not affect LWT integers (no fixed width in the language spec).
"""

from __future__ import annotations

_DECIMAL_CHUNK_DIGITS = 9
_DECIMAL_CHUNK_BASE = 10**_DECIMAL_CHUNK_DIGITS


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
