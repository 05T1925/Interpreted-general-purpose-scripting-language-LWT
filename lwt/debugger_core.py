"""Read-only source debugger controller for LWT runtime hooks."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shlex
from threading import Condition
from typing import Callable, TextIO

from .ast_nodes import (
    AttemptStatement,
    Block,
    EachStatement,
    EmitStatement,
    ExpressionStatement,
    FunctionDeclaration,
    LetStatement,
    Program,
    ReturnStatement,
    Statement,
    WhenStatement,
    WhileStatement,
    BreakStatement,
    ContinueStatement,
)
from .errors import SourceLocation
from .modules import ModuleGraph, ModuleUnit
from .runtime import Environment, _RuntimeContext, _format_value


_EXECUTABLE_STATEMENT_TYPES = (
    AttemptStatement,
    BreakStatement,
    ContinueStatement,
    EachStatement,
    EmitStatement,
    ExpressionStatement,
    LetStatement,
    ReturnStatement,
    WhenStatement,
    WhileStatement,
)
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_MAX_DISPLAY_CHARS = 240
_MAX_LIST_LINES = 40
_HELP = """LWT source debugger commands:
  help                         show this help
  continue | c                 resume until a breakpoint or program end
  step | s                     execute this statement, stop at the next statement
  next | n                     step over user functions in the current frame
  finish | out                 run until the current function returns
  break | b PATH:LINE          add an exact-line source breakpoint
  delete ID                    delete a breakpoint
  breakpoints                  list verified and unmapped breakpoints
  where | stack                show LWT frames, current first
  locals                       show visible locals in the current frame
  globals                      show this module's global bindings
  print | p IDENTIFIER         read one existing binding; no expressions
  list [COUNT]                 show finite source context around this stop
  quit | q                     cancel this debug session

Quote PATH:LINE when the path contains spaces. Relative paths use the process
working directory. Breakpoints match exact source lines; no nearest-line
relocation is performed."""


class DebugAbort(Exception):
    """A deliberate, user-visible cancellation of a debug session."""

    lwt_debugger_control = True


@dataclass(slots=True)
class DebugFrame:
    frame_id: int
    module_unit: ModuleUnit
    qualified_name: str
    declaration: FunctionDeclaration | None
    environment: Environment
    global_environment: Environment
    current_environment: Environment
    current_statement: Statement | None = None
    caller_module: ModuleUnit | None = None
    call_location: SourceLocation | None = None


@dataclass(slots=True)
class Breakpoint:
    breakpoint_id: int
    requested_path: str
    line: int
    canonical_key: str | None
    status: str
    detail: str
    statement: Statement | None = None
    display_path: str | None = None


@dataclass(frozen=True, slots=True)
class StepPlan:
    kind: str
    frame_id: int


class DebuggerController:
    """Runtime hook implementing source breakpoints and statement stepping."""

    def __init__(
        self,
        graph: ModuleGraph,
        entry_path: str,
        commands: TextIO,
        stderr: TextIO,
        *,
        scripted: bool,
        pause_handler: Callable[[str, DebugFrame, Statement], None] | None = None,
    ) -> None:
        self.graph = graph
        self.entry_path = entry_path
        self.commands = commands
        self.stderr = stderr
        self.scripted = scripted
        self._units_by_path = {
            self._path_key(unit.canonical_path): unit for unit in graph.modules
        }
        self._statements_by_path = {
            self._path_key(unit.canonical_path): self._index_unit(unit.program)
            for unit in graph.modules
        }
        self._breakpoints: list[Breakpoint] = []
        self._next_breakpoint_id = 1
        self._next_frame_id = 1
        self._frames: list[DebugFrame] = []
        self._step_plan: StepPlan | None = None
        self._running = False
        self._has_stopped = False
        self._is_paused = False
        self._cancelled = False
        self._pause_handler = pause_handler
        self._pause_condition = Condition()
        self._resume_requested = False

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def start(self) -> None:
        """Let the next statement run unless a configured breakpoint matches."""

        self._running = True

    def resume(self, action: str) -> None:
        """Resume with a DAP-style execution action, without CLI text commands."""

        if not self._is_paused or not self._frames:
            raise ValueError("the LWT program is not paused")
        frame = self._frames[-1]
        if action == "continue":
            self._step_plan = None
        elif action == "stepIn":
            self._step_plan = StepPlan("step", frame.frame_id)
        elif action == "next":
            self._step_plan = StepPlan("next", frame.frame_id)
        elif action == "stepOut":
            if frame.declaration is None:
                raise ValueError("stepOut is unavailable in the entry frame")
            self._step_plan = StepPlan("finish", frame.frame_id)
        else:
            raise ValueError(f"unsupported execution action {action!r}")
        self._running = True
        self._is_paused = False
        if self._pause_handler is not None:
            with self._pause_condition:
                self._resume_requested = True
                self._pause_condition.notify_all()

    def cancel(self) -> None:
        """Request safe cancellation at the next LWT statement boundary."""

        self._cancelled = True
        self._is_paused = False
        with self._pause_condition:
            self._resume_requested = True
            self._pause_condition.notify_all()

    def set_breakpoints(self, source_path: str, lines: list[int]) -> list[Breakpoint]:
        """Replace all breakpoints for one source, retaining exact-line mapping."""

        key = self._path_key(source_path)
        self._breakpoints = [
            breakpoint
            for breakpoint in self._breakpoints
            if breakpoint.canonical_key != key
        ]
        unit = self._units_by_path.get(key)
        result: list[Breakpoint] = []
        for line in lines:
            statements = self._statements_by_path.get(key, {}).get(line, ())
            statement = statements[0] if unit is not None and statements else None
            if unit is None:
                status = "unmapped"
                detail = "source is not in the loaded module graph"
                display = None
            elif statement is None:
                status = "unmapped"
                detail = "line has no executable statement"
                display = self._display_path(unit)
            else:
                status = "verified"
                detail = "first executable statement on the exact line"
                display = self._display_path(unit)
            breakpoint = Breakpoint(
                self._next_breakpoint_id,
                source_path,
                line,
                key,
                status,
                detail,
                statement,
                display,
            )
            self._next_breakpoint_id += 1
            self._breakpoints.append(breakpoint)
            result.append(breakpoint)
        return result

    def frames(self) -> tuple[DebugFrame, ...]:
        """Return the current LWT frames, newest first, while paused."""

        if not self._is_paused:
            return ()
        return tuple(reversed(self._frames))

    def frame(self, frame_id: int) -> DebugFrame | None:
        if not self._is_paused:
            return None
        return next((frame for frame in self._frames if frame.frame_id == frame_id), None)

    def frame_position(self, frame: DebugFrame) -> tuple[str, int, int]:
        return self._frame_position(frame)

    def locals_for_frame(self, frame: DebugFrame) -> dict[str, object]:
        return self._local_bindings(frame)

    @staticmethod
    def globals_for_frame(frame: DebugFrame) -> dict[str, object]:
        return frame.global_environment.values

    def display_value(self, value: object) -> str:
        return self._display_value(value)

    @staticmethod
    def _path_key(path: str | Path) -> str:
        try:
            return os.path.normcase(str(Path(path).resolve()))
        except (OSError, ValueError, RuntimeError):
            return os.path.normcase(os.path.abspath(os.fspath(path)))

    @staticmethod
    def _index_unit(program: Program) -> dict[int, tuple[Statement, ...]]:
        ordered: list[Statement] = []

        def visit(statement: Statement) -> None:
            if isinstance(statement, Block):
                for child in statement.statements:
                    visit(child)
                return
            if isinstance(statement, _EXECUTABLE_STATEMENT_TYPES):
                ordered.append(statement)
            if isinstance(statement, WhenStatement):
                visit(statement.then_branch)
                if statement.otherwise_branch is not None:
                    visit(statement.otherwise_branch)
            elif isinstance(statement, (WhileStatement, EachStatement)):
                visit(statement.body)
            elif isinstance(statement, AttemptStatement):
                visit(statement.body)
                visit(statement.recover_body)

        for item in program.items:
            if isinstance(item, FunctionDeclaration):
                visit(item.body)
            elif isinstance(item, _EXECUTABLE_STATEMENT_TYPES + (Block,)):
                visit(item)

        by_line: dict[int, list[tuple[int, Statement]]] = {}
        for order, statement in enumerate(ordered):
            by_line.setdefault(statement.location.line, []).append((order, statement))
        return {
            line: tuple(
                statement
                for _, statement in sorted(
                    statements,
                    key=lambda entry: (entry[1].location.column, entry[0]),
                )
            )
            for line, statements in by_line.items()
        }

    def program_start(self, runtime: _RuntimeContext) -> None:
        unit = runtime.module_unit
        if unit is None:
            raise RuntimeError("debugger runtime has no source module")
        root = runtime.global_environment
        self._frames = [
            DebugFrame(
                0,
                unit,
                "<entry>",
                None,
                root,
                root,
                root,
            )
        ]

    def enter_function(
        self,
        declaration: FunctionDeclaration,
        activation: Environment,
        runtime: _RuntimeContext,
        caller_runtime: _RuntimeContext,
        call_location: SourceLocation,
        qualified_name: str,
    ) -> None:
        unit = runtime.module_unit
        caller_unit = caller_runtime.module_unit
        if unit is None:
            raise RuntimeError("debugger function frame has no source module")
        self._frames.append(
            DebugFrame(
                self._next_frame_id,
                unit,
                qualified_name,
                declaration,
                activation,
                activation.global_scope(),
                activation,
                caller_module=caller_unit,
                call_location=call_location,
            )
        )
        self._next_frame_id += 1

    def leave_function(self) -> None:
        if len(self._frames) > 1:
            self._frames.pop()

    def before_statement(
        self, statement: Statement, environment: Environment, runtime: _RuntimeContext
    ) -> None:
        if self._cancelled:
            raise DebugAbort("debug session terminated")
        if isinstance(statement, Block):
            return
        if not self._frames:
            self.program_start(runtime)
        frame = self._frames[-1]
        frame.current_environment = environment
        frame.current_statement = statement

        matching = [
            breakpoint.breakpoint_id
            for breakpoint in self._breakpoints
            if breakpoint.status == "verified"
            and breakpoint.statement is statement
        ]
        if matching:
            self._step_plan = None
            self._pause(f"breakpoint {','.join(map(str, matching))}", statement, frame)
            return

        reason = self._step_stop_reason()
        if reason is not None:
            self._step_plan = None
            self._pause(reason, statement, frame)
            return

        if not self._running:
            reason = "entry" if not self._has_stopped else "paused"
            self._pause(reason, statement, frame)

    def _step_stop_reason(self) -> str | None:
        plan = self._step_plan
        if plan is None:
            return None
        active_ids = {frame.frame_id for frame in self._frames}
        if plan.kind == "step":
            return "step"
        if plan.kind == "next":
            if plan.frame_id not in active_ids:
                return "next"
            if self._frames[-1].frame_id == plan.frame_id:
                return "next"
            return None
        if plan.kind == "finish" and plan.frame_id not in active_ids:
            return "finish"
        return None

    def _pause(self, reason: str, statement: Statement, frame: DebugFrame) -> None:
        self._running = False
        self._has_stopped = True
        self._is_paused = True
        if self._pause_handler is not None:
            with self._pause_condition:
                self._resume_requested = False
            self._pause_handler(reason, frame, statement)
            with self._pause_condition:
                while not self._resume_requested and not self._cancelled:
                    self._pause_condition.wait()
            if self._cancelled:
                raise DebugAbort("debug session terminated")
            return
        path = self._display_path(frame.module_unit)
        location = statement.location
        self._write(
            f"Stopped ({reason}) at {path}:{location.line}:{location.column}"
        )
        self._write_source_line(frame.module_unit, location.line)
        while True:
            if not self.scripted:
                self.stderr.write("lwt-debug> ")
                self.stderr.flush()
            line = self.commands.readline()
            if line == "":
                raise DebugAbort("command input ended while the program was paused")
            command = line.rstrip("\r\n")
            if command.strip() == "":
                self._write("DebugError: empty command")
                continue
            try:
                tokens = self._split_command(command)
            except ValueError:
                self._write("DebugError: invalid command quoting")
                continue
            if not tokens:
                self._write("DebugError: empty command")
                continue
            if self._dispatch(tokens, frame, statement):
                return

    @staticmethod
    def _split_command(command: str) -> list[str]:
        lexer = shlex.shlex(command, posix=True)
        lexer.whitespace_split = True
        lexer.commenters = ""
        lexer.escape = ""
        return list(lexer)

    def _dispatch(
        self, tokens: list[str], frame: DebugFrame, statement: Statement
    ) -> bool:
        command, *arguments = tokens
        if command == "help":
            if arguments:
                self._write("DebugError: help takes no arguments")
                return False
            self._write(_HELP)
            return False
        if command in {"continue", "c"}:
            if arguments:
                self._write("DebugError: continue takes no arguments")
                return False
            self.resume("continue")
            return True
        if command in {"step", "s", "next", "n"}:
            if arguments:
                self._write(f"DebugError: {command} takes no arguments")
                return False
            action = "stepIn" if command in {"step", "s"} else "next"
            self.resume(action)
            return True
        if command in {"finish", "out"}:
            if arguments:
                self._write(f"DebugError: {command} takes no arguments")
                return False
            if frame.declaration is None:
                self._write("DebugError: finish is unavailable in the entry frame")
                return False
            self.resume("stepOut")
            return True
        if command in {"break", "b"}:
            if len(arguments) != 1:
                self._write("DebugError: usage: break PATH:LINE")
                return False
            self._add_breakpoint(arguments[0])
            return False
        if command == "delete":
            if len(arguments) != 1 or not arguments[0].isdecimal():
                self._write("DebugError: usage: delete ID")
                return False
            self._delete_breakpoint(int(arguments[0]))
            return False
        if command == "breakpoints":
            if arguments:
                self._write("DebugError: breakpoints takes no arguments")
                return False
            self._show_breakpoints()
            return False
        if command in {"where", "stack"}:
            if arguments:
                self._write(f"DebugError: {command} takes no arguments")
                return False
            self._show_stack()
            return False
        if command == "locals":
            if arguments:
                self._write("DebugError: locals takes no arguments")
                return False
            self._show_bindings("Locals", self._local_bindings(frame))
            return False
        if command == "globals":
            if arguments:
                self._write("DebugError: globals takes no arguments")
                return False
            self._show_bindings("Globals", frame.global_environment.values)
            return False
        if command in {"print", "p"}:
            if len(arguments) != 1 or _IDENTIFIER.fullmatch(arguments[0]) is None:
                self._write("DebugError: usage: print IDENTIFIER")
                return False
            self._print_binding(arguments[0], frame)
            return False
        if command == "list":
            if len(arguments) > 1 or (
                arguments and not arguments[0].isdecimal()
            ):
                self._write("DebugError: usage: list [COUNT]")
                return False
            count = int(arguments[0]) if arguments else 5
            if count < 1 or count > _MAX_LIST_LINES:
                self._write(f"DebugError: list count must be between 1 and {_MAX_LIST_LINES}")
                return False
            self._list_source(frame, statement, count)
            return False
        if command in {"quit", "q"}:
            if arguments:
                self._write(f"DebugError: {command} takes no arguments")
                return False
            raise DebugAbort("session cancelled by user")
        self._write(f"DebugError: unknown command {command!r}")
        return False

    def _add_breakpoint(self, specification: str) -> None:
        path_text, separator, line_text = specification.rpartition(":")
        if not separator or not path_text or not line_text.isdecimal():
            self._write("DebugError: breakpoint must use PATH:LINE with a positive line")
            return
        line = int(line_text)
        if line < 1:
            self._write("DebugError: breakpoint line must be positive")
            return
        path = Path(path_text)
        try:
            canonical = path.resolve()
        except (OSError, ValueError, RuntimeError):
            canonical = Path(os.path.abspath(path_text))
        key = self._path_key(canonical)
        unit = self._units_by_path.get(key)
        statements = self._statements_by_path.get(key, {}).get(line, ())
        statement = statements[0] if unit is not None and statements else None
        if unit is None:
            status, detail, display = "unmapped", "source is not in the loaded module graph", None
        elif statement is None:
            status, detail, display = "unmapped", "line has no executable statement", self._display_path(unit)
        else:
            status, detail, display = "verified", "first executable statement on the exact line", self._display_path(unit)
        breakpoint = Breakpoint(
            self._next_breakpoint_id,
            path_text,
            line,
            key,
            status,
            detail,
            statement,
            display,
        )
        self._breakpoints.append(breakpoint)
        self._next_breakpoint_id += 1
        self._write(
            f"Breakpoint {breakpoint.breakpoint_id} {status}: "
            f"{display or path_text}:{line} ({detail})"
        )

    def _delete_breakpoint(self, breakpoint_id: int) -> None:
        for index, breakpoint in enumerate(self._breakpoints):
            if breakpoint.breakpoint_id == breakpoint_id:
                del self._breakpoints[index]
                self._write(f"Deleted breakpoint {breakpoint_id}")
                return
        self._write(f"DebugError: no breakpoint with id {breakpoint_id}")

    def _show_breakpoints(self) -> None:
        if not self._breakpoints:
            self._write("Breakpoints: <none>")
            return
        self._write("Breakpoints:")
        for breakpoint in self._breakpoints:
            path = breakpoint.display_path or breakpoint.requested_path
            self._write(
                f"  {breakpoint.breakpoint_id} {breakpoint.status} "
                f"{path}:{breakpoint.line} ({breakpoint.detail})"
            )

    def _show_stack(self) -> None:
        self._write("LWT stack (current frame first):")
        for index in range(len(self._frames) - 1, -1, -1):
            frame = self._frames[index]
            path, line, column = self._frame_position(frame)
            label = (
                "<entry>"
                if frame.declaration is None
                else f"fn {frame.qualified_name}"
            )
            self._write(f"  #{len(self._frames) - 1 - index} {label} at {path}:{line}:{column}")

    def _frame_position(self, frame: DebugFrame) -> tuple[str, int, int]:
        statement = frame.current_statement
        if statement is not None:
            location = statement.location
            return self._display_path(frame.module_unit), location.line, location.column
        if frame.call_location is not None:
            location = frame.call_location
            caller = frame.caller_module or frame.module_unit
            return self._display_path(caller), location.line, location.column
        return self._display_path(frame.module_unit), 1, 1

    @staticmethod
    def _local_bindings(frame: DebugFrame) -> dict[str, object]:
        visible: dict[str, object] = {}
        environment: Environment | None = frame.current_environment
        while environment is not None and environment is not frame.global_environment:
            for name, value in environment.values.items():
                visible.setdefault(name, value)
            environment = environment.parent
        return visible

    def _show_bindings(self, title: str, values: dict[str, object]) -> None:
        self._write(f"{title}:")
        if not values:
            self._write("  <empty>")
            return
        for name in sorted(values):
            self._write(f"  {name} = {self._display_value(values[name])}")

    def _print_binding(self, name: str, frame: DebugFrame) -> None:
        environment = frame.current_environment.resolve(name)
        if environment is None:
            self._write(f"DebugError: variable {name!r} is not visible here")
            return
        self._write(f"{name} = {self._display_value(environment.values[name])}")

    @staticmethod
    def _display_value(value: object) -> str:
        try:
            rendered = _format_value(value, set(), nested=True)
        except RecursionError:
            rendered = "<value too deeply nested>"
        if len(rendered) > _MAX_DISPLAY_CHARS:
            rendered = rendered[:_MAX_DISPLAY_CHARS] + "… [truncated]"
        return rendered

    def _list_source(
        self, frame: DebugFrame, statement: Statement, count: int
    ) -> None:
        self._write_source_line(frame.module_unit, statement.location.line, count=count)

    def _write_source_line(
        self,
        unit: ModuleUnit,
        line: int,
        *,
        count: int = 1,
    ) -> None:
        source = unit.source_text
        if source is None:
            self._write("  <source text unavailable>")
            return
        lines = re.split(r"\r\n|\n|\r", source)
        half = (count - 1) // 2
        start = max(1, line - half)
        end = min(len(lines), start + count - 1)
        start = max(1, end - count + 1)
        width = len(str(end))
        for number in range(start, end + 1):
            prefix = "=>" if number == line else "  "
            self._write(f"{prefix} {number:>{width}} | {lines[number - 1]}")

    def _display_path(self, unit: ModuleUnit) -> str:
        if unit is self.graph.entry:
            return self.entry_path
        return unit.display_path or str(unit.canonical_path)

    def _write(self, text: str) -> None:
        self.stderr.write(text + "\n")
