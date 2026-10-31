"""Long-lived subprocess bridge to the LWT Snake rule engine."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
from typing import BinaryIO, Callable

from app.lwt_snake.protocol import (
    MAX_CELLS,
    MAX_HEIGHT,
    MAX_SEQUENCE,
    MAX_WIDTH,
    CommandRejected,
    GameSnapshot,
    ProtocolError,
    format_request,
    parse_response,
)


GAME_SOURCE = Path(__file__).with_name("game.lwt")
DEFAULT_WIDTH = 24
DEFAULT_HEIGHT = 18
DEFAULT_SEED = 1
DEFAULT_TIMEOUT = 2.0
STDERR_TAIL_BYTES = 8192
_EOF = object()


class BridgeFailure(ProtocolError):
    """The LWT interpreter could not start, respond, or finish cleanly."""


@dataclass(frozen=True)
class _ReaderFault:
    message: str


ProcessFactory = Callable[..., subprocess.Popen[bytes]]


class LwtSnakeBridge:
    """Owns one LWT process and permits one request/response at a time."""

    def __init__(
        self,
        *,
        repository_root: Path,
        source_path: Path = GAME_SOURCE,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        seed: int = DEFAULT_SEED,
        timeout: float = DEFAULT_TIMEOUT,
        python_executable: str = sys.executable,
        process_factory: ProcessFactory = subprocess.Popen,
    ) -> None:
        self.repository_root = repository_root.resolve()
        candidate = source_path if source_path.is_absolute() else self.repository_root / source_path
        self.source_path = candidate.resolve()
        self.width = width
        self.height = height
        self.seed = seed
        self.timeout = timeout
        self.python_executable = python_executable
        self._process_factory = process_factory
        self._process: subprocess.Popen[bytes] | None = None
        self._stdout_events: queue.Queue[bytes | _ReaderFault | object] = queue.Queue(maxsize=4)
        self._stderr_lock = threading.Lock()
        self._stderr_tail = bytearray()
        self._reader_stop = threading.Event()
        self._stdout_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._request_lock = threading.Lock()
        self._next_sequence = 1
        self._started = False
        self._closed = False
        self._broken = False

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process is not None else None

    @property
    def returncode(self) -> int | None:
        return self._process.poll() if self._process is not None else None

    @property
    def command(self) -> tuple[str, ...]:
        return (
            self.python_executable,
            "-u",
            "-m",
            "lwt",
            str(self.source_path),
        )

    def start(self) -> GameSnapshot:
        if self._started or self._closed:
            raise BridgeFailure("LWT Snake bridge can only be started once")
        if not 4 <= self.width <= MAX_WIDTH or not 1 <= self.height <= MAX_HEIGHT:
            raise BridgeFailure("board dimensions are outside the protocol limits")
        if self.width * self.height > MAX_CELLS:
            raise BridgeFailure("board area exceeds the protocol limit")
        if not 1 <= self.seed <= 2_147_483_646:
            raise BridgeFailure("seed must be between 1 and 2147483646")
        if self.timeout <= 0:
            raise BridgeFailure("response timeout must be positive")
        if not self.source_path.is_file():
            raise BridgeFailure(f"LWT game source does not exist: {self.source_path}")

        options: dict[str, object] = {
            "args": list(self.command),
            "cwd": str(self.repository_root),
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "shell": False,
            "bufsize": -1,
        }
        if os.name == "nt":
            options["creationflags"] = (
                getattr(subprocess, "CREATE_NO_WINDOW", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            )
        try:
            self._process = self._process_factory(**options)  # type: ignore[arg-type]
        except (OSError, ValueError) as error:
            self._closed = True
            raise BridgeFailure(f"could not start the LWT interpreter: {error}") from error
        if self._process.stdin is None or self._process.stdout is None or self._process.stderr is None:
            self._terminate_process()
            self._closed = True
            raise BridgeFailure("LWT interpreter pipes could not be created")

        self._stdout_thread = threading.Thread(
            target=self._read_stdout,
            args=(self._process.stdout,),
            name="lwt-snake-stdout",
            daemon=True,
        )
        self._stderr_thread = threading.Thread(
            target=self._read_stderr,
            args=(self._process.stderr,),
            name="lwt-snake-stderr",
            daemon=True,
        )
        self._stdout_thread.start()
        self._stderr_thread.start()
        self._started = True
        try:
            return self.request("INIT", self.width, self.height, self.seed)
        except BaseException:
            self._abort_process()
            self.close()
            raise

    def request(self, command: str, *arguments: object) -> GameSnapshot:
        """Send one supported command and wait for exactly its response frame."""

        with self._request_lock:
            if not self._started or self._closed or self._broken or self._process is None:
                raise BridgeFailure("LWT Snake bridge is not running")
            if self._process.poll() is not None:
                raise self._process_failure("interpreter exited before the request")
            if self._next_sequence > MAX_SEQUENCE:
                raise BridgeFailure("request sequence limit reached; restart the LWT session")
            fields = self._command_fields(command, arguments)
            sequence = self._next_sequence
            self._reject_pending_output(sequence)
            frame = format_request(sequence, command, fields)
            try:
                assert self._process.stdin is not None
                self._process.stdin.write(frame)
                self._process.stdin.flush()
            except (BrokenPipeError, OSError, ValueError) as error:
                self._abort_process()
                raise self._process_failure(f"could not write request {sequence:06d}: {error}") from error
            self._next_sequence += 1

            try:
                event = self._stdout_events.get(timeout=self.timeout)
            except queue.Empty as error:
                self._abort_process()
                raise self._process_failure(
                    f"timed out after {self.timeout:.3g}s waiting for request {sequence:06d}"
                ) from error
            if event is _EOF:
                self._abort_process()
                raise self._process_failure(f"interpreter reached EOF during request {sequence:06d}")
            if isinstance(event, _ReaderFault):
                self._abort_process()
                raise self._process_failure(event.message)
            if not isinstance(event, bytes):
                self._abort_process()
                raise self._process_failure("stdout reader returned an invalid event")

            try:
                snapshot = parse_response(
                    event,
                    expected_sequence=sequence,
                    width=self.width,
                    height=self.height,
                )
            except CommandRejected:
                self._reject_extra_after_response(command)
                raise
            except ProtocolError as error:
                self._abort_process()
                raise self._process_failure(f"invalid response for request {sequence:06d}: {error}") from error

            self._reject_extra_after_response(command)
            return snapshot

    @staticmethod
    def _command_fields(command: str, arguments: tuple[object, ...]) -> tuple[str, str, str]:
        if command == "INIT":
            if len(arguments) != 3:
                raise ProtocolError("INIT requires width, height, and seed")
            width, height, seed = arguments
            if not all(isinstance(value, int) and not isinstance(value, bool) for value in arguments):
                raise ProtocolError("INIT fields must be integers")
            return str(width), str(height), f"{seed:010d}"
        if command == "TURN":
            if len(arguments) != 1 or arguments[0] not in {"U", "R", "D", "L"}:
                raise ProtocolError("TURN requires exactly one U/R/D/L direction")
            return str(arguments[0]), "-", "-"
        if command in {"START", "TICK", "PAUSE", "RESUME", "RESET", "QUIT"}:
            if arguments:
                raise ProtocolError(f"{command} does not accept argument values")
            return "-", "-", "-"
        raise ProtocolError(f"unsupported LWT Snake command: {command!r}")

    def _read_stdout(self, stream: BinaryIO) -> None:
        while not self._reader_stop.is_set():
            try:
                line = stream.readline(4098)
            except (OSError, ValueError) as error:
                self._publish_stdout(_ReaderFault(f"stdout read failed: {error}"))
                return
            if line == b"":
                self._publish_stdout(_EOF)
                return
            if not line.endswith(b"\n"):
                self._publish_stdout(_ReaderFault("stdout frame is overlong or missing its LF terminator"))
                return
            frame = line[:-1]
            if len(frame) > 4096:
                self._publish_stdout(_ReaderFault("stdout frame exceeds the 4096-byte limit"))
                return
            self._publish_stdout(frame)

    def _publish_stdout(self, item: bytes | _ReaderFault | object) -> None:
        while not self._reader_stop.is_set():
            try:
                self._stdout_events.put(item, timeout=0.1)
                return
            except queue.Full:
                continue

    def _read_stderr(self, stream: BinaryIO) -> None:
        while not self._reader_stop.is_set():
            try:
                chunk = stream.read(2048)
            except (OSError, ValueError):
                return
            if not chunk:
                return
            with self._stderr_lock:
                self._stderr_tail.extend(chunk)
                excess = len(self._stderr_tail) - STDERR_TAIL_BYTES
                if excess > 0:
                    del self._stderr_tail[:excess]

    def _stderr_text(self) -> str:
        with self._stderr_lock:
            content = bytes(self._stderr_tail)
        return content.decode("utf-8", "replace").strip()

    def _process_failure(self, message: str) -> BridgeFailure:
        returncode = self._process.poll() if self._process is not None else None
        if returncode is not None and self._stderr_thread is not None:
            self._stderr_thread.join(timeout=0.2)
        detail = f"{message} (exit code {returncode})" if returncode is not None else message
        diagnostic = self._stderr_text()
        if diagnostic:
            detail += f"; stderr: {diagnostic}"
        return BridgeFailure(detail)

    def _reject_pending_output(self, sequence: int) -> None:
        try:
            event = self._stdout_events.get_nowait()
        except queue.Empty:
            return
        self._abort_process()
        if isinstance(event, bytes):
            detail = event[:160].decode("ascii", "backslashreplace")
            raise self._process_failure(f"unexpected extra stdout frame before request {sequence:06d}: {detail!r}")
        if isinstance(event, _ReaderFault):
            raise self._process_failure(event.message)
        raise self._process_failure("interpreter closed stdout before the next request")

    def _reject_extra_after_response(self, command: str) -> None:
        try:
            event = self._stdout_events.get_nowait()
        except queue.Empty:
            return
        if event is _EOF and command == "QUIT":
            return
        self._abort_process()
        if isinstance(event, bytes):
            detail = event[:160].decode("ascii", "backslashreplace")
            raise self._process_failure(f"interpreter emitted an extra stdout frame: {detail!r}")
        if isinstance(event, _ReaderFault):
            raise self._process_failure(event.message)
        raise self._process_failure("interpreter closed stdout before a non-QUIT response")

    def _abort_process(self) -> None:
        self._broken = True
        self._terminate_process()

    def _terminate_process(self) -> None:
        process = self._process
        if process is None or process.poll() is not None:
            return
        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    shell=False,
                    timeout=2.0,
                    check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
        if process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=0.5)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                except OSError:
                    pass
        try:
            process.wait(timeout=1.0)
        except (OSError, subprocess.TimeoutExpired):
            pass

    def close(self) -> None:
        if self._closed:
            return
        pending_error: BaseException | None = None
        process = self._process
        if process is not None and process.poll() is None and self._started and not self._broken:
            try:
                self.request("QUIT")
                process.wait(timeout=self.timeout)
                if process.returncode != 0:
                    raise self._process_failure("interpreter exited unsuccessfully after QUIT")
                self._check_only_eof_after_exit()
            except BaseException as error:
                pending_error = error
                self._terminate_process()
        else:
            self._terminate_process()

        self._reader_stop.set()
        if process is not None:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass
        for thread in (self._stdout_thread, self._stderr_thread):
            if thread is not None:
                thread.join(timeout=1.0)
        self._closed = True
        if pending_error is not None:
            raise pending_error

    def _check_only_eof_after_exit(self) -> None:
        if self._stdout_thread is not None:
            self._stdout_thread.join(timeout=1.0)
        while True:
            try:
                event = self._stdout_events.get_nowait()
            except queue.Empty:
                return
            if event is _EOF:
                continue
            if isinstance(event, bytes):
                self._abort_process()
                detail = event[:160].decode("ascii", "backslashreplace")
                raise self._process_failure(f"extra stdout after QUIT response: {detail!r}")
            if isinstance(event, _ReaderFault):
                raise self._process_failure(event.message)

    def __enter__(self) -> LwtSnakeBridge:
        self.start()
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        try:
            self.close()
        except BridgeFailure:
            if exc_type is None:
                raise
