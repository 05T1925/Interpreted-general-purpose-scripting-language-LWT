"""Command-line argument handling and the public LWT interpreter entry point."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
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


@dataclass(frozen=True, slots=True)
class ProfileArguments:
    profile_path: str
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


def parse_profile_cli_args(argv: Sequence[str]) -> ProfileArguments:
    """Parse ``--profile OUTPUT SOURCE [-- PROGRAM_ARGS...]``."""

    if not argv or argv[0] != "--profile":
        raise LwtError("CliError", "expected --profile", 4)
    if len(argv) < 3 or argv[1] in {"", "--"} or argv[2] in {"", "--"}:
        raise LwtError("CliError", "expected a profile path and source path", 4)
    if argv[1] == "-":
        raise LwtError("CliError", "profile output cannot be stdout ('-')", 4)
    remaining = list(argv[3:])
    if remaining and remaining[0] != "--":
        raise LwtError("CliError", "program arguments must follow --", 4)
    return ProfileArguments(argv[1], argv[2], tuple(remaining[1:]) if remaining else ())


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
        if "--profile" in argv[1:]:
            raise LwtError("CliError", "--check cannot be combined with --profile", 4)
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


def _preflight_profile_target(profile_path: str, graph: object) -> Path:
    target = Path(profile_path)
    try:
        resolved = target.resolve()
    except (OSError, ValueError, RuntimeError):
        raise LwtError("FileError", "invalid execution profile path", 4) from None
    modules = getattr(graph, "modules")
    for unit in modules:
        try:
            if resolved == unit.canonical_path.resolve():
                raise LwtError(
                    "CliError", "profile output cannot replace a source module", 4
                )
        except (OSError, ValueError, RuntimeError):
            continue
    try:
        if resolved.exists() and resolved.is_dir():
            raise LwtError("FileError", "profile output path is a directory", 4)
    except (OSError, ValueError, RuntimeError):
        raise LwtError("FileError", "invalid execution profile path", 4) from None
    parent = target.parent if str(target.parent) else Path(".")
    if not parent.is_dir():
        raise LwtError("FileError", "profile output directory does not exist", 4)
    descriptor = -1
    temporary: str | None = None
    try:
        descriptor, temporary = tempfile.mkstemp(
            prefix=".lwt-profile-check-", suffix=".tmp", dir=parent
        )
        os.close(descriptor)
        descriptor = -1
        os.unlink(temporary)
    except OSError:
        raise LwtError("FileError", "cannot write execution profile", 4) from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary is not None and os.path.exists(temporary):
            try:
                os.unlink(temporary)
            except OSError:
                pass
    return target


def _write_profile_atomic(target: Path, profile: dict[str, object]) -> None:
    temporary: str | None = None
    descriptor = -1
    try:
        payload = json.dumps(
            profile, ensure_ascii=True, separators=(",", ":"), allow_nan=False
        ) + "\n"
        encoded = payload.encode("utf-8", errors="strict")
        descriptor, temporary = tempfile.mkstemp(
            prefix=".lwt-profile-", suffix=".tmp", dir=target.parent
        )
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        temporary = None
    except (OSError, TypeError, ValueError, UnicodeError):
        raise LwtError("FileError", "cannot write execution profile", 4) from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def _profile_document(collector: object) -> dict[str, object]:
    try:
        document = getattr(collector, "as_dict")()
        from .profile_schema import validate_profile

        validate_profile(document)
        return document
    except LwtError:
        raise
    except Exception:
        # Collector/schema failures are tool failures, never user RuntimeErrors.
        raise LwtError("FileError", "execution profile collection failed", 4) from None


def _run_profile(argv: Sequence[str]) -> int:
    source_path: str | None = None
    try:
        arguments = parse_profile_cli_args(argv)
        source_path = arguments.source_path
        graph = load_module_graph(source_path, include_hashes=True)
        target = _preflight_profile_target(arguments.profile_path, graph)
        from .observability import ProfileCollector

        collector = ProfileCollector(graph, source_path)
    except LwtError as error:
        sys.stderr.write(format_diagnostic(error, source_path) + "\n")
        return error.exit_code
    except Exception:
        error = LwtError("FileError", "execution profile collection failed", 4)
        sys.stderr.write(format_diagnostic(error, source_path) + "\n")
        return error.exit_code

    program_error: LwtError | None = None
    try:
        execute(
            graph.entry.program,
            sys.stdin.buffer,
            sys.stdout,
            arguments.program_args,
            module_graph=graph,
            source_path=source_path,
            observer=collector,
        )
    except LwtError as error:
        program_error = error

    try:
        _write_profile_atomic(target, _profile_document(collector))
    except LwtError as profile_error:
        if program_error is not None:
            sys.stderr.write(format_diagnostic(program_error, source_path) + "\n")
            sys.stderr.write(format_diagnostic(profile_error, arguments.profile_path) + "\n")
            return program_error.exit_code
        sys.stderr.write(format_diagnostic(profile_error, arguments.profile_path) + "\n")
        return profile_error.exit_code

    if program_error is not None:
        sys.stderr.write(format_diagnostic(program_error, source_path) + "\n")
        return program_error.exit_code
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Read, lex, parse, and execute one LWT source file."""

    _configure_standard_streams()
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "--check":
        return _run_check(arguments)
    if arguments and arguments[0] == "--profile":
        return _run_profile(arguments)
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
