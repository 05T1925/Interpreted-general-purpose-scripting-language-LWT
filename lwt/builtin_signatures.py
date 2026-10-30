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
}

BUILTIN_NAMES = frozenset(BUILTIN_ARITIES)
