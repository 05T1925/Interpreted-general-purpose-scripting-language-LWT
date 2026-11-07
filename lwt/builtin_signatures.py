"""Shared names and arities for LWT's built-in functions."""

from __future__ import annotations


BUILTIN_ARITIES: dict[str, int] = {
    "input": 0,
    "args": 0,
    "read_text": 1,
    "len": 1,
    "split": 2,
    "trim": 1,
    "to_int": 1,
    "str": 1,
    "push": 2,
    "fail": 1,
    "keys": 1,
    "values": 1,
    "items": 1,
    "has": 2,
    "get": 3,
    "put": 3,
    "delete": 2,
    "error": 2,
}

BUILTIN_NAMES = frozenset(BUILTIN_ARITIES)
