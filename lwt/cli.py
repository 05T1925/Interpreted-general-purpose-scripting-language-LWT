"""Command-line argument handling and the public LWT interpreter entry point."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Sequence

from .errors import LwtError, format_diagnostic
from .modules import load_module_graph
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


def main(argv: Sequence[str] | None = None) -> int:
    """Read, lex, parse, and execute one LWT source file."""

    _configure_standard_streams()
    arguments = list(sys.argv[1:] if argv is None else argv)
    source_path: str | None = None

    try:
        parsed = parse_cli_args(arguments)
        source_path = parsed.source_path
        graph = load_module_graph(source_path)
    except LwtError as error:
        sys.stderr.write(format_diagnostic(error, source_path) + "\n")
        return error.exit_code

    try:
        execute(
            graph.entry.program,
            sys.stdin.buffer,
            sys.stdout,
            parsed.program_args,
            module_graph=graph,
            source_path=source_path,
        )
    except LwtError as error:
        sys.stderr.write(format_diagnostic(error, source_path) + "\n")
        return error.exit_code
    return 0
