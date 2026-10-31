"""Bounded worker messages; this module has no Tk dependency or game rules."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import queue
import threading

from app.lwt_snake.bridge import GAME_SOURCE, LwtSnakeBridge
from app.lwt_snake.protocol import CommandRejected, GameSnapshot
from app.lwt_snake.replay import Recorder, Replay, Verified, load, reconstruct, save


@dataclass(frozen=True)
class Reply:
    generation: int
    request_id: int
    snapshot: GameSnapshot | None = None
    error: str | None = None
    fatal: bool = False
    record: Replay | None = None
    verified: Verified | None = None
    progress: tuple[int, int] | None = None


class EngineWorker(threading.Thread):
    def __init__(self, root: Path, replies: queue.Queue[Reply], generation: int,
                 source: Path = GAME_SOURCE, *, replay: Replay | None = None,
                 replay_path: Path | None = None, prefix: int | None = None) -> None:
        super().__init__(name="lwt-snake-worker", daemon=False)
        self.bridge = LwtSnakeBridge(repository_root=root, source_path=source)
        self.replies = replies
        self.generation = generation
        self.commands: queue.Queue[tuple[int, str, tuple[object, ...]]] = queue.Queue(maxsize=1)
        self.stopping = threading.Event()
        self.finished = threading.Event()
        self.source = source
        self.replay = replay
        self.replay_path = replay_path
        self.prefix = prefix
        self.recorder = None

    def submit(self, request_id: int, command: str, *args: object, replace: bool = False) -> bool:
        if self.stopping.is_set() or self.finished.is_set():
            return False
        if replace:
            try:
                self.commands.get_nowait()
            except queue.Empty:
                pass
        try:
            self.commands.put_nowait((request_id, command, args))
            return True
        except queue.Full:
            return False

    def stop(self) -> None:
        self.stopping.set()

    def _post(self, reply: Reply) -> None:
        if self.stopping.is_set():
            return
        try:
            self.replies.put_nowait(reply)
        except queue.Full:
            # Only stale UI snapshots can accumulate: retain the newest event.
            try:
                self.replies.get_nowait()
            except queue.Empty:
                pass
            self.replies.put_nowait(reply)

    def run(self) -> None:
        request_id = 0
        try:
            replay = load(self.replay_path) if self.replay_path else self.replay
            if replay is not None:
                result = reconstruct(replay, prefix=self.prefix, keep=self.prefix is not None,
                                     cancel=self.stopping, progress=lambda n,total: self._post(Reply(self.generation, 0, progress=(n,total))),
                                     on_bridge=lambda bridge: setattr(self, 'bridge', bridge))
                if self.prefix is None:
                    self._post(Reply(self.generation, 0, verified=result))
                    return
                self.bridge, self.recorder = result.bridge, result.recorder
                self._post(Reply(self.generation, 0, result.states[-1]))
            else:
                self.recorder = Recorder(source=self.source)
                self.bridge.on_transaction = self.recorder.append
                self._post(Reply(self.generation, 0, self.bridge.start()))
            while not self.stopping.is_set():
                try:
                    request_id, command, args = self.commands.get(timeout=0.05)
                except queue.Empty:
                    continue
                try:
                    if command == 'SAVE':
                        record = self.recorder.snapshot()
                        save(Path(args[0]), record)
                        self._post(Reply(self.generation, request_id, record=record))
                        continue
                    state = self.bridge.request(command, *args)
                    self._post(Reply(self.generation, request_id, state))
                except CommandRejected as error:
                    self._post(Reply(self.generation, request_id, error=str(error)))
                except (OSError, ValueError) as error:
                    self._post(Reply(self.generation, request_id, error=str(error)))
        except Exception as error:
            if self.recorder: self.recorder.interrupt(error)
            self._post(Reply(self.generation, request_id, error=str(error), fatal=True))
        finally:
            try:
                self.bridge.close()
            except Exception as error:
                self._post(Reply(self.generation, request_id, error=str(error), fatal=True))
            self.finished.set()
