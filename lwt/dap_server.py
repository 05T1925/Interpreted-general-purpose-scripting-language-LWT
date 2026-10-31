"""A single-threaded LWT Debug Adapter Protocol server over stdio."""

from __future__ import annotations

from dataclasses import dataclass
import io
import json
import os
from pathlib import Path
import queue
import sys
import threading
from typing import BinaryIO, TextIO

from .dap_protocol import DapProtocolError, DapReader, encode_message
from .debugger_core import DebugAbort, DebugFrame, DebuggerController
from .errors import LwtError, format_diagnostic
from .modules import ModuleGraph, load_module_graph
from .runtime import _ErrorValue, _RecordValue, _format_value, execute


THREAD_ID = 1
_REFERENCE_BASE = 1000


@dataclass(frozen=True, slots=True)
class _Launch:
    program: str
    cwd: str
    arguments: tuple[str, ...]
    program_stdin: bytes
    graph: ModuleGraph


@dataclass(frozen=True, slots=True)
class _VariableReference:
    generation: int
    value: object
    ancestors: frozenset[int]


class _DapTextOutput:
    """Text stream facade which queues output events without touching stdout."""

    def __init__(self, enqueue) -> None:
        self._enqueue = enqueue

    def write(self, text: str) -> int:
        if text:
            self._enqueue("stdout", text)
        return len(text)

    def flush(self) -> None:
        return None


class _UnbufferedFdReader:
    """Read protocol bytes without holding TextIOWrapper shutdown locks."""

    def __init__(self, descriptor: int) -> None:
        self.descriptor = descriptor

    def read(self, length: int = -1) -> bytes:
        return os.read(self.descriptor, length if length >= 0 else 4096)


class DapServer:
    """Own the DAP writer and coordinate protocol and LWT execution threads."""

    def __init__(
        self,
        input_stream: BinaryIO | None = None,
        output_stream: BinaryIO | None = None,
        diagnostic_stream: TextIO | None = None,
    ) -> None:
        self.input_stream = (
            input_stream
            if input_stream is not None
            else _UnbufferedFdReader(sys.stdin.fileno())
        )
        self.output_stream = output_stream or sys.stdout.buffer
        self.diagnostic_stream = diagnostic_stream or sys.stderr
        self._incoming: queue.Queue[object] = queue.Queue()
        self._events: queue.Queue[dict[str, object]] = queue.Queue()
        self._reader_thread: threading.Thread | None = None
        self._execution_thread: threading.Thread | None = None
        self._execution_finished = threading.Event()
        self._server_seq = 1
        self._initialized = False
        self._launch: _Launch | None = None
        self._pending_launch_request: dict[str, object] | None = None
        self._controller: DebuggerController | None = None
        self._worker_exit_code: int | None = None
        self._reference_counter = _REFERENCE_BASE
        self._references: dict[int, _VariableReference] = {}
        self._pause_generation = 0
        self._dap_frame_counter = 0
        self._dap_frame_ids: dict[int, int] = {}
        self._dap_frames: dict[int, tuple[int, int]] = {}
        self._terminated_sent = False
        self._shutdown_after_execution = False
        self._peer_closed = False
        self._protocol_failed = False

    def run(self) -> int:
        self._reader_thread = threading.Thread(
            target=self._read_loop, name="lwt-dap-reader", daemon=True
        )
        self._reader_thread.start()
        while True:
            try:
                item = self._incoming.get(timeout=0.05)
            except queue.Empty:
                item = None
            if item is _EOF:
                self._peer_closed = True
                self._request_stop()
                self._shutdown_after_execution = True
            elif isinstance(item, _ProtocolFailure):
                self._protocol_failed = True
                self.diagnostic_stream.write(f"lwt-dap: protocol error: {item.message}\n")
                self._request_stop()
                self._shutdown_after_execution = True
            elif isinstance(item, dict):
                self._handle_message(item)
            self._drain_events()
            if self._shutdown_after_execution and (
                self._execution_thread is None or self._execution_finished.is_set()
            ):
                self._drain_events()
                if not self._peer_closed and not self._protocol_failed:
                    self._send_terminated()
                break
        return 1 if self._protocol_failed else 0

    def _read_loop(self) -> None:
        reader = DapReader(self.input_stream)
        try:
            while True:
                message = reader.read_message()
                if message is None:
                    self._incoming.put(_EOF)
                    return
                self._incoming.put(message)
        except (DapProtocolError, OSError) as error:
            self._incoming.put(_ProtocolFailure(str(error)))
        except Exception as error:
            self._incoming.put(
                _ProtocolFailure(f"cannot read DAP message ({type(error).__name__})")
            )

    def _handle_message(self, message: dict[str, object]) -> None:
        if message.get("type") != "request":
            self.diagnostic_stream.write("lwt-dap: ignored non-request DAP message\n")
            return
        request_seq = message.get("seq")
        command = message.get("command")
        if type(request_seq) is not int or not isinstance(command, str):
            self.diagnostic_stream.write("lwt-dap: ignored malformed DAP request\n")
            return
        body = message.get("arguments", {})
        if not isinstance(body, dict):
            self._error_response(message, "request arguments must be a JSON object")
            return
        handler = getattr(self, f"_request_{command}", None)
        if handler is None:
            self._error_response(message, f"unsupported DAP request: {command}")
            return
        try:
            handler(message, body)
        except (LwtError, OSError, ValueError, TypeError) as error:
            self._error_response(message, str(error))
        except Exception as error:
            self.diagnostic_stream.write(
                f"lwt-dap: internal request failure ({command}): {type(error).__name__}\n"
            )
            self._error_response(message, "internal debug adapter failure")

    def _request_initialize(
        self, request: dict[str, object], _arguments: dict[str, object]
    ) -> None:
        if self._initialized:
            raise ValueError("initialize may be sent only once")
        self._initialized = True
        self._respond(
            request,
            {
                "supportsConfigurationDoneRequest": True,
                "supportsTerminateRequest": True,
                "supportsLoadedSourcesRequest": True,
            },
        )

    def _request_launch(
        self, request: dict[str, object], arguments: dict[str, object]
    ) -> None:
        if not self._initialized:
            raise ValueError("initialize must be completed before launch")
        if self._launch is not None or self._pending_launch_request is not None:
            raise ValueError("only one launch is supported per DAP session")
        try:
            launch = self._prepare_launch(arguments)
        except LwtError as error:
            diagnostic = format_diagnostic(error)
            self._event("output", {"category": "stderr", "output": diagnostic + "\n"})
            self._error_response(request, diagnostic)
            self._event("exited", {"exitCode": error.exit_code})
            self._send_terminated()
            self._execution_finished.set()
            self._shutdown_after_execution = True
            return
        self._launch = launch
        self._controller = DebuggerController(
            launch.graph,
            launch.program,
            io.StringIO(),
            self.diagnostic_stream,
            scripted=True,
            pause_handler=self._on_pause,
        )
        self._pending_launch_request = request
        self._event("initialized", {})

    def _prepare_launch(self, arguments: dict[str, object]) -> _Launch:
        program = arguments.get("program")
        if not isinstance(program, str) or not program:
            raise LwtError("CliError", "launch requires a program path", 4)
        cwd_value = arguments.get("cwd")
        if cwd_value is not None and (not isinstance(cwd_value, str) or not cwd_value):
            raise LwtError("CliError", "launch cwd must be a non-empty path", 4)
        try:
            cwd = Path(cwd_value or os.getcwd()).resolve()
        except (OSError, ValueError, RuntimeError):
            raise LwtError("CliError", "launch working directory is invalid", 4) from None
        if not cwd.is_dir():
            raise LwtError("FileError", "working directory is not a directory", 4)
        try:
            source = Path(program)
            if not source.is_absolute():
                source = cwd / source
            source = source.resolve()
        except (OSError, ValueError, RuntimeError):
            raise LwtError("CliError", "launch source path is invalid", 4) from None
        raw_arguments = arguments.get("args", [])
        if not isinstance(raw_arguments, list) or any(
            not isinstance(value, str) for value in raw_arguments
        ):
            raise LwtError("CliError", "launch args must be an array of strings", 4)
        stdin_file = arguments.get("stdinFile", "")
        if not isinstance(stdin_file, str):
            raise LwtError("CliError", "stdinFile must be a string", 4)
        program_stdin = b""
        if stdin_file:
            input_path = Path(stdin_file)
            if not input_path.is_absolute():
                input_path = cwd / input_path
            try:
                program_stdin = input_path.read_bytes()
            except (OSError, ValueError):
                raise LwtError("FileError", "cannot read program stdin file", 4) from None
        try:
            graph = load_module_graph(str(source), include_sources=True)
        except LwtError:
            raise
        except (OSError, ValueError, RuntimeError):
            raise LwtError("FileError", "cannot read source file", 4) from None
        return _Launch(str(source), str(cwd), tuple(raw_arguments), program_stdin, graph)

    def _request_setBreakpoints(
        self, request: dict[str, object], arguments: dict[str, object]
    ) -> None:
        controller = self._require_controller()
        source = arguments.get("source")
        if not isinstance(source, dict) or not isinstance(source.get("path"), str):
            raise ValueError("setBreakpoints requires source.path")
        raw_breakpoints = arguments.get("breakpoints")
        if raw_breakpoints is None:
            raw_breakpoints = [
                {"line": line} for line in arguments.get("lines", [])
            ]
        if not isinstance(raw_breakpoints, list):
            raise ValueError("breakpoints must be an array")
        lines: list[int] = []
        for breakpoint in raw_breakpoints:
            if not isinstance(breakpoint, dict) or type(breakpoint.get("line")) is not int:
                raise ValueError("each source breakpoint requires an integer line")
            lines.append(breakpoint["line"])
        source_path = source["path"]
        mapped = controller.set_breakpoints(source_path, lines)
        self._respond(
            request,
            {
                "breakpoints": [
                    {
                        "id": item.breakpoint_id,
                        "verified": item.status == "verified",
                        "message": item.detail,
                        "source": self._source_for_path(source_path),
                        "line": item.line,
                    }
                    for item in mapped
                ]
            },
        )

    def _request_configurationDone(
        self, request: dict[str, object], _arguments: dict[str, object]
    ) -> None:
        if self._pending_launch_request is None or self._launch is None:
            raise ValueError("launch must be configured before configurationDone")
        self._respond(request, {})
        self._respond(self._pending_launch_request, {})
        self._pending_launch_request = None
        assert self._controller is not None
        self._controller.start()
        self._execution_finished.clear()
        self._execution_thread = threading.Thread(
            target=self._execute_program,
            name="lwt-dap-program",
            daemon=True,
        )
        self._execution_thread.start()

    def _request_threads(
        self, request: dict[str, object], _arguments: dict[str, object]
    ) -> None:
        if self._execution_finished.is_set() or self._launch is None:
            threads: list[dict[str, object]] = []
        else:
            threads = [{"id": THREAD_ID, "name": "LWT program"}]
        self._respond(request, {"threads": threads})

    def _request_stackTrace(
        self, request: dict[str, object], arguments: dict[str, object]
    ) -> None:
        controller = self._require_controller()
        self._validate_thread(arguments)
        start = arguments.get("startFrame", 0)
        levels = arguments.get("levels", 0)
        if type(start) is not int or start < 0 or type(levels) is not int or levels < 0:
            raise ValueError("stackTrace startFrame and levels must be non-negative integers")
        frames = controller.frames()
        selected = frames[start:] if levels == 0 else frames[start : start + levels]
        result: list[dict[str, object]] = []
        for frame in selected:
            source_path, line, column = controller.frame_position(frame)
            canonical = (
                frame.module_unit.canonical_path
                if frame.module_unit is not None
                else Path(source_path)
            )
            dap_frame_id = self._dap_frame_ids.get(frame.frame_id)
            if dap_frame_id is None:
                self._dap_frame_counter += 1
                dap_frame_id = self._dap_frame_counter
                self._dap_frame_ids[frame.frame_id] = dap_frame_id
                self._dap_frames[dap_frame_id] = (
                    self._pause_generation,
                    frame.frame_id,
                )
            result.append(
                {
                    "id": dap_frame_id,
                    "name": frame.qualified_name,
                    "source": self._source_for_path(str(canonical)),
                    "line": line,
                    "column": column,
                }
            )
        body: dict[str, object] = {"stackFrames": result}
        if controller.is_paused:
            body["totalFrames"] = len(frames)
        self._respond(request, body)

    def _request_scopes(
        self, request: dict[str, object], arguments: dict[str, object]
    ) -> None:
        controller = self._require_controller()
        dap_frame_id = arguments.get("frameId")
        if type(dap_frame_id) is not int:
            raise ValueError("scopes requires an integer frameId")
        saved_frame = self._dap_frames.get(dap_frame_id)
        frame = None
        if saved_frame is not None and saved_frame[0] == self._pause_generation:
            frame = controller.frame(saved_frame[1])
        if frame is None:
            self._respond(request, {"scopes": []})
            return
        locals_map = controller.locals_for_frame(frame)
        globals_map = controller.globals_for_frame(frame)
        scopes = [
            {
                "name": "Locals",
                "presentationHint": "locals",
                "variablesReference": self._new_reference(locals_map),
                "namedVariables": len(locals_map),
                "expensive": False,
            },
            {
                "name": "Globals",
                "presentationHint": "globals",
                "variablesReference": self._new_reference(globals_map),
                "namedVariables": len(globals_map),
                "expensive": False,
            },
        ]
        self._respond(request, {"scopes": scopes})

    def _request_variables(
        self, request: dict[str, object], arguments: dict[str, object]
    ) -> None:
        reference = arguments.get("variablesReference")
        if type(reference) is not int or reference <= 0:
            raise ValueError("variables requires a positive variablesReference")
        saved = self._references.get(reference)
        if saved is None or saved.generation != self._pause_generation:
            self._respond(request, {"variables": []})
            return
        filter_value = arguments.get("filter")
        if filter_value not in (None, "indexed", "named"):
            raise ValueError("variables filter must be indexed or named")
        start = arguments.get("start", 0)
        count = arguments.get("count", 0)
        if type(start) is not int or start < 0 or type(count) is not int or count < 0:
            raise ValueError("variables start and count must be non-negative integers")
        entries = self._child_entries(saved.value)
        if filter_value == "indexed":
            entries = [(name, value) for name, value in entries if name.startswith("[")]
        elif filter_value == "named":
            entries = [(name, value) for name, value in entries if not name.startswith("[")]
        selected = entries[start:] if count == 0 else entries[start : start + count]
        variables = [
            self._variable(name, value, saved.ancestors)
            for name, value in selected
        ]
        self._respond(request, {"variables": variables})

    def _request_continue(
        self, request: dict[str, object], arguments: dict[str, object]
    ) -> None:
        self._resume(request, arguments, "continue")

    def _request_next(
        self, request: dict[str, object], arguments: dict[str, object]
    ) -> None:
        self._resume(request, arguments, "next")

    def _request_stepIn(
        self, request: dict[str, object], arguments: dict[str, object]
    ) -> None:
        self._resume(request, arguments, "stepIn")

    def _request_stepOut(
        self, request: dict[str, object], arguments: dict[str, object]
    ) -> None:
        self._resume(request, arguments, "stepOut")

    def _resume(
        self,
        request: dict[str, object],
        arguments: dict[str, object],
        action: str,
    ) -> None:
        controller = self._require_controller()
        self._validate_thread(arguments)
        controller.resume(action)
        self._references.clear()
        self._pause_generation += 1
        self._dap_frame_ids.clear()
        self._dap_frames.clear()
        self._respond(request, {"allThreadsContinued": True} if action == "continue" else {})
        self._event(
            "continued", {"threadId": THREAD_ID, "allThreadsContinued": True}
        )

    def _request_loadedSources(
        self, request: dict[str, object], _arguments: dict[str, object]
    ) -> None:
        launch = self._launch
        sources: list[dict[str, object]] = []
        if launch is not None:
            sources = [
                self._source_for_path(str(unit.canonical_path))
                for unit in launch.graph.modules
            ]
        self._respond(request, {"sources": sources})

    def _request_terminate(
        self, request: dict[str, object], _arguments: dict[str, object]
    ) -> None:
        self._respond(request, {})
        self._request_stop()
        if self._execution_thread is None:
            self._execution_finished.set()
            self._send_terminated()

    def _request_disconnect(
        self, request: dict[str, object], _arguments: dict[str, object]
    ) -> None:
        self._respond(request, {})
        self._request_stop()
        self._shutdown_after_execution = True
        if self._execution_thread is None:
            self._execution_finished.set()

    def _request_stop(self) -> None:
        if self._controller is not None:
            self._controller.cancel()

    def _execute_program(self) -> None:
        launch = self._launch
        controller = self._controller
        exit_code = 1
        if launch is not None and controller is not None:
            try:
                os.chdir(launch.cwd)
                execute(
                    launch.graph.entry.program,
                    io.BytesIO(launch.program_stdin),
                    _DapTextOutput(self._queue_output),
                    launch.arguments,
                    module_graph=launch.graph,
                    source_path=launch.program,
                    debug_hook=controller,
                )
                exit_code = 0
            except DebugAbort:
                exit_code = 1
            except LwtError as error:
                self._queue_output(
                    "stderr", format_diagnostic(error, launch.program) + "\n"
                )
                exit_code = error.exit_code
            except Exception as error:
                self.diagnostic_stream.write(
                    f"lwt-dap: internal execution failure ({type(error).__name__})\n"
                )
                self._queue_output("stderr", "lwt: DebugError: internal execution failure\n")
                exit_code = 1
        self._worker_exit_code = exit_code
        self._execution_finished.set()
        if not self._peer_closed and not self._protocol_failed:
            self._events.put({"event": "exited", "body": {"exitCode": exit_code}})
            self._events.put({"event": "terminated", "body": {}})
            self._terminated_sent = True

    def _on_pause(self, reason: str, frame: DebugFrame, statement) -> None:
        self._references.clear()
        self._pause_generation += 1
        self._dap_frame_ids.clear()
        self._dap_frames.clear()
        if reason.startswith("breakpoint"):
            dap_reason = "breakpoint"
        elif reason in {"step", "next", "finish"}:
            dap_reason = "step"
        else:
            dap_reason = "pause"
        self._events.put(
            {
                "event": "stopped",
                "body": {
                    "reason": dap_reason,
                    "description": reason,
                    "threadId": THREAD_ID,
                    "allThreadsStopped": True,
                    "preserveFocusHint": False,
                },
            }
        )

    def _queue_output(self, category: str, text: str) -> None:
        if not text:
            return
        chunk: list[str] = []
        byte_count = 0
        for character in text:
            encoded_size = len(character.encode("utf-8"))
            if byte_count and byte_count + encoded_size > 512 * 1024:
                self._events.put(
                    {"event": "output", "body": {"category": category, "output": "".join(chunk)}}
                )
                chunk.clear()
                byte_count = 0
            chunk.append(character)
            byte_count += encoded_size
        if chunk:
            self._events.put(
                {"event": "output", "body": {"category": category, "output": "".join(chunk)}}
            )

    def _child_entries(self, value: object) -> list[tuple[str, object]]:
        if isinstance(value, dict):
            return [(str(name), child) for name, child in sorted(value.items())]
        if type(value) is list:
            return [(f"[{index}]", child) for index, child in enumerate(value)]
        if isinstance(value, _RecordValue):
            return [(name, value.fields[name]) for name in value.field_names]
        if isinstance(value, _ErrorValue):
            return [
                ("category", value.category),
                ("message", value.message),
                ("source", value.source),
                ("line", value.line),
                ("column", value.column),
            ]
        return []

    def _variable(
        self, name: str, value: object, ancestors: frozenset[int]
    ) -> dict[str, object]:
        value_type = self._value_type(value)
        if self._is_composite(value):
            identity = id(value)
            if identity in ancestors:
                return {
                    "name": name,
                    "value": "<cycle>",
                    "type": value_type,
                    "variablesReference": 0,
                }
            reference = self._new_reference(value, ancestors | {identity})
        else:
            reference = 0
        return {
            "name": name,
            "value": self._display_value(value),
            "type": value_type,
            "variablesReference": reference,
        }

    def _new_reference(
        self, value: object, ancestors: frozenset[int] = frozenset()
    ) -> int:
        self._reference_counter += 1
        reference = self._reference_counter
        self._references[reference] = _VariableReference(
            self._pause_generation, value, ancestors
        )
        return reference

    @staticmethod
    def _is_composite(value: object) -> bool:
        return type(value) in {dict, list} or isinstance(
            value, (_RecordValue, _ErrorValue)
        )

    @staticmethod
    def _value_type(value: object) -> str:
        if type(value) is bool:
            return "boolean"
        if type(value) is int:
            return "integer"
        if type(value) is str:
            return "string"
        if value is None:
            return "null"
        if type(value) is list:
            return "array"
        if isinstance(value, _RecordValue):
            return value.type_name
        if isinstance(value, _ErrorValue):
            return "Error"
        return type(value).__name__

    def _display_value(self, value: object) -> str:
        if isinstance(value, dict):
            return "{" + ", ".join(
                f"{name}: {self._display_value(child)}"
                for name, child in sorted(value.items())
            ) + "}"
        try:
            return _format_value(value, set(), nested=True)
        except RecursionError:
            return "<value too deeply nested>"

    @staticmethod
    def _source_for_path(path_text: str) -> dict[str, object]:
        path = Path(path_text).resolve()
        return {"name": path.name, "path": str(path), "sourceReference": 0}

    def _require_controller(self) -> DebuggerController:
        if self._controller is None:
            raise ValueError("launch must be configured before this request")
        return self._controller

    @staticmethod
    def _validate_thread(arguments: dict[str, object]) -> None:
        thread_id = arguments.get("threadId")
        if type(thread_id) is not int or thread_id != THREAD_ID:
            raise ValueError("threadId must identify the single LWT program thread")

    def _respond(
        self,
        request: dict[str, object],
        body: dict[str, object],
        *,
        success: bool = True,
        message: str | None = None,
    ) -> None:
        self._send(
            {
                "type": "response",
                "request_seq": request["seq"],
                "command": request["command"],
                "success": success,
                "body": body,
                **({"message": message} if message else {}),
            }
        )

    def _error_response(self, request: dict[str, object], message: str) -> None:
        if type(request.get("seq")) is not int or not isinstance(
            request.get("command"), str
        ):
            return
        self._respond(
            request,
            {"error": {"id": 1000, "format": message, "showUser": True}},
            success=False,
            message=message,
        )

    def _event(self, event: str, body: dict[str, object]) -> None:
        self._send({"type": "event", "event": event, "body": body})

    def _send(self, message: dict[str, object]) -> None:
        payload = {"seq": self._server_seq, **message}
        self._server_seq += 1
        try:
            self.output_stream.write(encode_message(payload))
            self.output_stream.flush()
        except (BrokenPipeError, OSError) as error:
            self.diagnostic_stream.write(f"lwt-dap: cannot write protocol frame: {error}\n")
            self._peer_closed = True
            self._request_stop()
            self._shutdown_after_execution = True

    def _drain_events(self) -> None:
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                return
            name = event.get("event")
            body = event.get("body")
            if isinstance(name, str) and isinstance(body, dict):
                if name == "terminated":
                    self._terminated_sent = True
                self._event(name, body)

    def _send_terminated(self) -> None:
        if not self._terminated_sent:
            self._event("terminated", {})
            self._terminated_sent = True


_EOF = object()


@dataclass(frozen=True, slots=True)
class _ProtocolFailure:
    message: str


def main() -> int:
    try:
        return DapServer().run()
    except KeyboardInterrupt:
        sys.stderr.write("lwt-dap: adapter interrupted\n")
        return 1
    except Exception as error:
        sys.stderr.write(f"lwt-dap: adapter failed ({type(error).__name__})\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
