"""Command-line argument handling and the public LWT interpreter entry point."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

from .errors import LwtError, format_diagnostic
from .modules import load_module_graph
from .runtime import execute

if TYPE_CHECKING:
    from .analyzer import Diagnostic


@dataclass(frozen=True, slots=True)
class CliArguments:
    source_path: str
    program_args: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CheckArguments:
    source_path: str
    format: str


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


def parse_check_cli_args(argv: Sequence[str]) -> CheckArguments:
    """Parse the check-only command without changing normal CLI parsing."""

    if not argv or argv[0] != "--check":
        raise LwtError("CliError", "expected --check", 4)
    remaining = list(argv[1:])
    output_format = "text"
    if remaining and remaining[0].startswith("--format="):
        value = remaining.pop(0).partition("=")[2]
        if value != "json":
            raise LwtError("CliError", "check format must be json", 4)
        output_format = "json"
    if len(remaining) != 1 or remaining[0] == "--":
        raise LwtError("CliError", "expected one source path after --check", 4)
    return CheckArguments(remaining[0], output_format)


def _configure_standard_streams() -> None:
    """Make the CLI's encoding and newline contract independent of Windows defaults."""

    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(
            encoding="utf-8", errors="backslashreplace", newline="\n"
        )


def _error_code(category: str) -> str:
    return {
        "CliError": "CLI001",
        "FileError": "SRC001",
        "ImportError": "MOD001",
        "LexError": "LEX001",
        "SyntaxError": "PAR001",
    }.get(category, "CLI001")


def _json_document(
    *,
    ok: bool,
    files_checked: int | None,
    diagnostics: list[dict[str, object]],
) -> str:
    import json

    return json.dumps(
        {
            "schema_version": 1,
            "ok": ok,
            "files_checked": files_checked,
            "diagnostics": diagnostics,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ) + "\n"


def _diagnostic_object(diagnostic: Diagnostic) -> dict[str, object]:
    return {
        "code": diagnostic.code,
        "severity": diagnostic.severity,
        "category": diagnostic.category,
        "message": diagnostic.message,
        "source": diagnostic.source,
        "line": diagnostic.line,
        "column": diagnostic.column,
    }


def _check_error_object(error: LwtError, source_path: str | None) -> dict[str, object]:
    location = error.location
    return {
        "code": _error_code(error.category),
        "severity": "error",
        "category": error.category,
        "message": error.message,
        "source": (
            location.source_path or source_path if location is not None else source_path
        ),
        "line": location.line if location is not None else None,
        "column": location.column if location is not None else None,
    }


def _format_static_diagnostic(diagnostic: Diagnostic) -> str:
    location = ""
    if diagnostic.source is not None and diagnostic.line is not None and diagnostic.column is not None:
        source = diagnostic.source.replace("\r", "\\r").replace("\n", "\\n")
        location = f"{source}:{diagnostic.line}:{diagnostic.column}: "
    message = diagnostic.message.replace("\r", "\\r").replace("\n", "\\n")
    return f"{location}{diagnostic.category}[{diagnostic.code}]: {message}"


def _run_check(argv: Sequence[str]) -> int:
    json_requested = "--format=json" in argv[1:]
    try:
        arguments = parse_check_cli_args(argv)
        json_requested = arguments.format == "json"
    except LwtError as error:
        if json_requested:
            sys.stdout.write(
                _json_document(
                    ok=False,
                    files_checked=None,
                    diagnostics=[_check_error_object(error, None)],
                )
            )
        else:
            sys.stderr.write(format_diagnostic(error) + "\n")
        return error.exit_code

    try:
        graph = load_module_graph(arguments.source_path)
        from .analyzer import analyze_module_graph

        diagnostics = analyze_module_graph(graph, arguments.source_path)
    except LwtError as error:
        if json_requested:
            sys.stdout.write(
                _json_document(
                    ok=False,
                    files_checked=None,
                    diagnostics=[
                        _check_error_object(error, arguments.source_path)
                    ],
                )
            )
        else:
            sys.stderr.write(
                format_diagnostic(error, arguments.source_path) + "\n"
            )
        return error.exit_code

    if json_requested:
        sys.stdout.write(
            _json_document(
                ok=not diagnostics,
                files_checked=len(graph.modules),
                diagnostics=[_diagnostic_object(item) for item in diagnostics],
            )
        )
    elif diagnostics:
        for diagnostic in diagnostics:
            sys.stderr.write(_format_static_diagnostic(diagnostic) + "\n")
    else:
        sys.stdout.write(f"Check passed: {len(graph.modules)} source file(s).\n")
    return 2 if diagnostics else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Read, lex, parse, and execute one LWT source file."""

    _configure_standard_streams()
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "--check":
        return _run_check(arguments)
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
