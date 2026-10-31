"""Command-line entry point for the LWT source debugger."""

from __future__ import annotations

from dataclasses import dataclass
import io
import sys
from pathlib import Path
from typing import Sequence, TextIO

from .cli import _configure_standard_streams
from .debugger_core import DebugAbort, DebuggerController, _HELP
from .errors import LwtError, format_diagnostic
from .modules import load_module_graph
from .runtime import execute


_USAGE = (
    "usage: python -m lwt.debugger [--commands COMMAND_FILE] "
    "[--program-stdin INPUT_FILE] SOURCE [-- ARGS...]\n"
)


@dataclass(frozen=True, slots=True)
class DebuggerArguments:
    commands_path: str | None
    program_stdin_path: str | None
    source_path: str
    program_args: tuple[str, ...]


def parse_debugger_args(argv: Sequence[str]) -> DebuggerArguments | None:
    """Parse debugger options followed by SOURCE and optional LWT arguments."""

    if len(argv) == 1 and argv[0] in {"--help", "-h"}:
        return None
    commands_path: str | None = None
    program_stdin_path: str | None = None
    source_path: str | None = None
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument == "--":
            if source_path is None:
                raise LwtError("CliError", "expected a source path", 4)
            return DebuggerArguments(
                commands_path,
                program_stdin_path,
                source_path,
                tuple(argv[index + 1 :]),
            )
        if source_path is not None:
            raise LwtError("CliError", "program arguments must follow --", 4)
        if argument in {"--commands", "--program-stdin"}:
            if index + 1 >= len(argv) or argv[index + 1] in {"", "--"}:
                raise LwtError("CliError", f"{argument} requires a file path", 4)
            value = argv[index + 1]
            if argument == "--commands":
                if commands_path is not None:
                    raise LwtError("CliError", "--commands may be specified only once", 4)
                commands_path = value
            else:
                if program_stdin_path is not None:
                    raise LwtError("CliError", "--program-stdin may be specified only once", 4)
                program_stdin_path = value
            index += 2
            continue
        if argument.startswith("-"):
            raise LwtError("CliError", f"unknown debugger option {argument!r}", 4)
        source_path = argument
        index += 1
    if source_path is None:
        raise LwtError("CliError", "expected a source path", 4)
    return DebuggerArguments(
        commands_path, program_stdin_path, source_path, ()
    )


def _read_utf8_file(path_text: str, description: str) -> bytes:
    path = Path(path_text)
    try:
        data = path.read_bytes()
    except (OSError, ValueError, RuntimeError):
        raise LwtError("FileError", f"cannot read {description} file", 4) from None
    try:
        data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise LwtError("FileError", f"{description} file is not valid UTF-8", 4) from None
    return data


def _read_commands(path_text: str | None) -> tuple[TextIO, bool]:
    if path_text is None:
        return sys.stdin, False
    raw = _read_utf8_file(path_text, "debug command")
    text = raw.decode("utf-8", errors="strict")
    if text.startswith("\ufeff"):
        text = text[1:]
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return io.StringIO(text), True


def _read_program_stdin(path_text: str | None) -> io.BytesIO:
    if path_text is None:
        # In debug mode stdin belongs to the command reader; program input is EOF.
        return io.BytesIO(b"")
    return io.BytesIO(_read_utf8_file(path_text, "program stdin"))


def main(argv: Sequence[str] | None = None) -> int:
    _configure_standard_streams()
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        parsed = parse_debugger_args(arguments)
        if parsed is None:
            sys.stdout.write(_USAGE + "\n" + _HELP + "\n")
            return 0
        commands, scripted = _read_commands(parsed.commands_path)
        program_input = _read_program_stdin(parsed.program_stdin_path)
        graph = load_module_graph(parsed.source_path, include_sources=True)
    except LwtError as error:
        sys.stderr.write(format_diagnostic(error) + "\n")
        return error.exit_code

    controller = DebuggerController(
        graph, parsed.source_path, commands, sys.stderr, scripted=scripted
    )
    try:
        execute(
            graph.entry.program,
            program_input,
            sys.stdout,
            parsed.program_args,
            module_graph=graph,
            source_path=parsed.source_path,
            debug_hook=controller,
        )
    except DebugAbort as error:
        sys.stderr.write(f"lwt: DebugError: {error}\n")
        return 1
    except LwtError as error:
        sys.stderr.write(format_diagnostic(error, parsed.source_path) + "\n")
        return error.exit_code
    except Exception:
        # Debugger implementation failures are reported without a host traceback.
        sys.stderr.write("lwt: DebugError: internal debugger failure\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
