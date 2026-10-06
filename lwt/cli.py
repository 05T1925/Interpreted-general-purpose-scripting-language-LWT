"""Command-line argument handling and the currently supported runtime subset."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .errors import LwtError, format_diagnostic
from .lexer import scan
from .parser import parse
from .runtime import execute


@dataclass(frozen=True, slots=True)
class CliArguments:
    source_path: str
    program_args: tuple[str, ...]


def parse_cli_args(argv: Sequence[str]) -> CliArguments:
    """Parse ``SOURCE [-- PROGRAM_ARGS...]`` without argparse's output."""

    if not argv or argv[0] == "--":
        raise LwtError("CliError", "expected a source path", 4)

    source_path = argv[0]
    remaining = list(argv[1:])
    if not remaining:
        return CliArguments(source_path, ())
    if remaining[0] != "--":
        raise LwtError(
            "CliError", "program arguments must follow --", 4
        )
    return CliArguments(source_path, tuple(remaining[1:]))


def _configure_standard_streams() -> None:
    """Make the CLI's encoding and newline contract independent of Windows defaults."""

    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(
            encoding="utf-8", errors="backslashreplace", newline="\n"
        )


def _read_source(source_path: str) -> str:
    try:
        source_bytes = Path(source_path).read_bytes()
    except (OSError, ValueError) as error:
        raise LwtError("FileError", "cannot read source file", 4) from error

    try:
        return source_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise LwtError("FileError", "source file is not valid UTF-8", 4) from error


def main(argv: Sequence[str] | None = None) -> int:
    """Read, lex, parse, and execute the currently supported LWT subset."""

    _configure_standard_streams()
    arguments = list(sys.argv[1:] if argv is None else argv)
    source_path: str | None = None

    try:
        parsed = parse_cli_args(arguments)
        source_path = parsed.source_path
        # Program arguments remain reserved for a later args() implementation.
        _program_args = parsed.program_args
        source_text = _read_source(source_path)
        tokens = scan(source_text)
        program = parse(tokens)
    except LwtError as error:
        sys.stderr.write(format_diagnostic(error, source_path) + "\n")
        return error.exit_code

    try:
        execute(program, sys.stdin.buffer, sys.stdout)
    except LwtError as error:
        sys.stderr.write(format_diagnostic(error, source_path) + "\n")
        return error.exit_code
    return 0
