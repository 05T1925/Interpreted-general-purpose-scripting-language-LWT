"""Command-line argument handling and the public LWT interpreter entry point."""

from __future__ import annotations

import io
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO, Sequence, TextIO

# S44 P0-1/P0-2: keep the common CLI startup light. The scheduling exception
# is tiny (lives in _sched_support); the heavy tracer/digest helpers and
# hashlib/json/tempfile are imported only inside the commands that need them.
from ._sched_support import ScheduleReplayMismatch
from .errors import LwtError, format_diagnostic
from .lexer import scan
from .modules import load_module_graph
from .parser import parse
from .runtime import ReplSession, _program_has_spawn, execute

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


@dataclass(frozen=True, slots=True)
class ScheduleArguments:
    source_path: str
    program_args: tuple[str, ...]
    policy: str
    log_path: str | None
    replay_path: str | None


def parse_schedule_cli_args(argv: Sequence[str]) -> ScheduleArguments:
    """Parse ``[--schedule=P] [--schedule-log=F | --schedule-replay=F] SOURCE
    [-- ARGS...]``. Unknown flags and conflicting switches are CliError/4.
    """

    remaining = list(argv)
    policy = "fifo"
    log_path: str | None = None
    replay_path: str | None = None
    while remaining and remaining[0].startswith("--schedule"):
        token = remaining.pop(0)
        if token == "--schedule" or token.startswith("--schedule="):
            value = token.partition("=")[2] if "=" in token else ""
            if token == "--schedule":
                if not remaining:
                    raise LwtError("CliError", "--schedule needs a policy", 4)
                value = remaining.pop(0)
            if value != "fifo" and not (
                value.startswith("random:") and value[7:].lstrip("-").isdigit()
            ):
                raise LwtError(
                    "CliError", f"unknown schedule policy {value!r}", 4
                )
            policy = value
        elif token.startswith("--schedule-log="):
            log_path = token.partition("=")[2]
        elif token.startswith("--schedule-replay="):
            replay_path = token.partition("=")[2]
        else:
            raise LwtError("CliError", f"unknown schedule option {token!r}", 4)
    if log_path is not None and replay_path is not None:
        raise LwtError(
            "CliError", "--schedule-log and --schedule-replay are mutually exclusive", 4
        )
    if log_path == "" or replay_path == "":
        raise LwtError("CliError", "schedule trace path cannot be empty", 4)
    if not remaining or remaining[0] == "--":
        raise LwtError("CliError", "expected a source path", 4)
    source_path = remaining.pop(0)
    program_args: tuple[str, ...] = ()
    if remaining:
        if remaining[0] != "--":
            raise LwtError("CliError", "program arguments must follow --", 4)
        program_args = tuple(remaining[1:])
    return ScheduleArguments(source_path, program_args, policy, log_path, replay_path)


class _TeeTextIO(io.TextIOBase):
    """Forward writes to a real stream while capturing raw text bytes."""

    def __init__(self, target: TextIO) -> None:
        self._target = target
        self.buffer = io.BytesIO()

    def write(self, text: str) -> int:  # type: ignore[override]
        self._target.write(text)
        self.buffer.write(text.encode("utf-8"))
        return len(text)

    def flush(self) -> None:  # type: ignore[override]
        self._target.flush()

    def isatty(self) -> bool:  # type: ignore[override]
        return False


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
    import tempfile

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
    import json
    import tempfile

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
        # Tool boundary (spec 11.8): reject spawn before any task starts and
        # before a profile target is preflighted/written, so no partial profile
        # or breakpoint state can appear.
        if any(_program_has_spawn(unit.program) for unit in graph.modules):
            raise LwtError(
                "CliError", "profile does not support spawn programs", 4
            )
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


_REPL_HELP = (
    "LWT REPL commands:\n"
    "  .help     show this help\n"
    "  .vars     list visible top-level bindings\n"
    "  .reset    discard session bindings, functions and records\n"
    "  .exit     exit the REPL (also .quit or end of input)\n"
    "Enter LWT statements; multi-line blocks are read until complete.\n"
)

_REPL_META = frozenset({".help", ".vars", ".reset", ".exit", ".quit"})


def _is_incomplete(source: str) -> tuple[bool, LwtError | None]:
    """Return whether ``source`` is an incomplete snippet awaiting more lines.

    A snippet is incomplete when lexing reports an unterminated string, or when
    parsing reaches EOF while expecting a token (unclosed block/paren/list or a
    statement still needing its semicolon). A genuine syntax error elsewhere is
    reported immediately and clears the buffer.
    """

    try:
        tokens = scan(source, "<repl>")
    except LwtError as error:
        if error.category == "LexError" and (
            "unterminated" in error.message or "incomplete" in error.message
        ):
            return True, None
        return False, error
    try:
        parse(tokens)
        return False, None
    except LwtError as error:
        eof = tokens[-1]
        # EOF sits at the end of normalized source; if the parser failed there
        # while expecting something, the user is still typing a construct.
        if error.location is not None and error.location.line >= eof.line:
            if "expected" in error.message:
                return True, None
        return False, error


def _run_repl(input_stream: BinaryIO, output_stream: TextIO) -> int:
    """Interactive read-eval-print loop over a persistent LWT session."""

    session = ReplSession(input_stream, output_stream)
    buffer: list[str] = []

    def prompt(text: str) -> None:
        sys.stderr.write(text)
        sys.stderr.flush()

    prompt("LWT 0.2 REPL — .help for commands, .exit to quit\n")
    while True:
        prompt("..." if buffer else ">>> ")
        raw = sys.stdin.readline()
        if raw == "":
            # End of input: if a partial snippet is pending, do not execute it
            # silently; report it and exit deterministically with 0.
            if buffer:
                sys.stderr.write("\n")
            return 0
        line = raw.rstrip("\r\n")
        stripped = line.strip()

        if not buffer and stripped in _REPL_META:
            if stripped in {".exit", ".quit"}:
                return 0
            if stripped == ".help":
                sys.stderr.write(_REPL_HELP)
                continue
            if stripped == ".reset":
                session.reset()
                prompt("session reset\n")
                continue
            if stripped == ".vars":
                bindings = session.visible_bindings()
                if not bindings:
                    prompt("(no bindings)\n")
                else:
                    for name, value in bindings:
                        try:
                            rendered = _display_repl_value(value)
                        except RecursionError:
                            rendered = "<unrepresentable>"
                        prompt(f"{name} = {rendered}\n")
                continue

        # Comment-only or blank lines inside a packet are kept so line numbers
        # and multi-line constructs stay faithful; a blank line at top level is
        # a no-op.
        if not buffer and (stripped == "" or stripped.startswith("#")):
            continue

        buffer.append(line)
        source = "\n".join(buffer) + "\n"
        incomplete, error = _is_incomplete(source)
        if incomplete:
            continue
        buffer = []
        if error is not None:
            sys.stderr.write(format_diagnostic(error, "<repl>") + "\n")
            continue

        try:
            session.submit(parse(scan(source, "<repl>")))
        except LwtError as runtime_error:
            sys.stderr.write(format_diagnostic(runtime_error, "<repl>") + "\n")
        except RecursionError:
            sys.stderr.write("lwt: RuntimeError: host recursion limit reached\n")


def _display_repl_value(value: object) -> str:
    from .runtime import _display_value

    return _display_value(value)


def _run_schedule(argv: Sequence[str]) -> int:
    """Execute with deterministic scheduling, trace recording, and replay."""

    # S44 P0-2: these imports are only needed for the schedule subcommand,
    # which is a rare path; keep them out of plain `--check`/`--profile`/REPL.
    import hashlib

    from .concurrency import ScheduleTracer, source_digest

    source_path: str | None = None
    try:
        args = parse_schedule_cli_args(argv)
        source_path = args.source_path
        # Source texts are needed to bind the trace to exact program bytes.
        graph = load_module_graph(source_path, include_sources=True)
    except LwtError as error:
        sys.stderr.write(format_diagnostic(error, source_path) + "\n")
        return error.exit_code

    texts: dict[str, str] = {}
    for unit in graph.modules:
        key = str(unit.display_path or unit.canonical_path.name).replace("\\", "/")
        texts[key] = unit.source_text or ""
    entry_key = str(graph.entry.display_path or args.source_path).replace("\\", "/")
    if entry_key not in texts:
        texts[entry_key] = graph.entry.source_text or ""
    digest = source_digest(texts)

    replay_doc: dict[str, object] | None = None
    if args.replay_path:
        try:
            replay_doc = ScheduleTracer.load(args.replay_path)
        except ScheduleReplayMismatch as mismatch:
            sys.stderr.write(
                format_diagnostic(LwtError("CliError", str(mismatch), 4), args.replay_path)
                + "\n"
            )
            return 4

    policy = replay_doc["policy"] if replay_doc else args.policy
    decisions: list[dict[str, object]] = []
    out_tee = _TeeTextIO(sys.stdout)
    err_tee = _TeeTextIO(sys.stderr)
    exit_code = 0
    errorMessage: str | None = None
    try:
        execute(
            graph.entry.program,
            sys.stdin.buffer,
            out_tee,
            args.program_args,
            module_graph=graph,
            source_path=args.source_path,
            schedule_policy=policy,
            schedule_replay=args.replay_path,
            source_texts=texts,
            schedule_decisions=decisions,
        )
    except LwtError as error:
        exit_code = error.exit_code
        errorMessage = format_diagnostic(error, args.source_path)
    except ScheduleReplayMismatch as mismatch:
        exit_code = 4
        errorMessage = format_diagnostic(
            LwtError("CliError", str(mismatch), 4), args.replay_path or args.source_path
        )
    if errorMessage is not None:
        err_tee.write(errorMessage + "\n")
    stdout_bytes = out_tee.buffer.getvalue()
    stderr_bytes = err_tee.buffer.getvalue()

    if args.log_path and exit_code == 0:
        doc = {
            "schema": "lwt-schedule-trace/1",
            "schema_version": 1,
            "source": args.source_path,
            "source_sha256": digest,
            "program_args": list(args.program_args),
            "policy": policy,
            "expected_exit_code": exit_code,
            "expected_stdout_sha256": hashlib.sha256(stdout_bytes).hexdigest(),
            "expected_stderr_sha256": hashlib.sha256(stderr_bytes).hexdigest(),
            "decisions": decisions,
        }
        try:
            ScheduleTracer.write(args.log_path, doc)
        except OSError as error:
            sys.stderr.write(
                format_diagnostic(
                    LwtError("CliError", f"cannot write schedule trace: {error}", 4),
                    args.log_path,
                )
                + "\n"
            )
            return 4
    elif args.replay_path and replay_doc is not None and exit_code == 0:
        # Replay success requires byte-identical output and decision count.
        checks = (
            ("expected_exit_code", replay_doc.get("expected_exit_code"), exit_code),
            (
                "expected_stdout_sha256",
                replay_doc.get("expected_stdout_sha256"),
                hashlib.sha256(stdout_bytes).hexdigest(),
            ),
            (
                "expected_stderr_sha256",
                replay_doc.get("expected_stderr_sha256"),
                hashlib.sha256(stderr_bytes).hexdigest(),
            ),
            ("decisions", len(replay_doc.get("decisions", [])), len(decisions)),
        )
        for label, expected, actual in checks:
            if expected != actual:
                sys.stderr.write(
                    format_diagnostic(
                        LwtError(
                            "CliError",
                            f"replay mismatch in {label}: expected {expected!r}, got {actual!r}",
                            4,
                        ),
                        args.replay_path,
                    )
                    + "\n"
                )
                return 4
    return exit_code


def _help_text() -> str:
    """S45 WP2: static usage text for ``-h``/``--help`` (exit 0)."""

    from . import __version__

    return (
        f"LWT {__version__} -- tree-walk interpreter for the LWT language\n"
        "\n"
        "Usage:\n"
        "  python -m lwt SOURCE [-- PROGRAM_ARGS...]   run a program\n"
        "  python -m lwt --check [--format=json] SOURCE  static check only, no execution\n"
        "  python -m lwt --profile OUTPUT SOURCE [-- ARGS...]  collect an execution profile\n"
        "  python -m lwt --repl                       interactive REPL (stdin)\n"
        "  python -m lwt [--schedule=POLICY] [--schedule-log=FILE | --schedule-replay=FILE] SOURCE\n"
        "  python -m lwt -h | --help                  show this help\n"
        "  python -m lwt --version                    show the version\n"
        "\n"
        "Schedule policies: fifo (default) or random:SEED.\n"
        "Exit codes: 0 success; 2 static check errors; 3 runtime error; 4 CLI/file error.\n"
        "Language rules: docs/language-spec.md\n"
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Read, lex, parse, and execute one LWT source file."""

    _configure_standard_streams()
    arguments = list(sys.argv[1:] if argv is None else argv)
    # S45 WP2: help/version are early exits that never touch a source file.
    # Only a lone flag is intercepted, so a program path can never be shadowed.
    if len(arguments) == 1 and arguments[0] in ("-h", "--help"):
        sys.stdout.write(_help_text())
        return 0
    if len(arguments) == 1 and arguments[0] == "--version":
        from . import __version__

        sys.stdout.write(f"lwt {__version__}\n")
        return 0
    if arguments and arguments[0] == "--repl":
        if len(arguments) != 1:
            sys.stderr.write(
                format_diagnostic(
                    LwtError("CliError", "--repl takes no arguments", 4)
                )
                + "\n"
            )
            return 4
        return _run_repl(sys.stdin.buffer, sys.stdout)
    if arguments and arguments[0] == "--check":
        return _run_check(arguments)
    if arguments and arguments[0] == "--profile":
        return _run_profile(arguments)
    if any(arg.startswith("--schedule") for arg in arguments):
        return _run_schedule(arguments)
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
