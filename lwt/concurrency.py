"""Deterministic, replayable cooperative concurrency for LWT 0.2 (S43).

This module owns the scheduler, task/channel state, the self-contained PRNG,
and schedule-trace reading/writing. The tree-walk runtime only *wires* to it;
there are no hooks in the hot statement/expression path (invariant I2).

Design (spec section 11): a single token lets exactly one task run LWT code.
The main task (id 0) runs on the calling thread; spawned tasks run on host
threads. Each task has a sticky ``threading.Event`` token: the owner hands the
token to the chosen task by ``set``-ing its event and clearing its own, then
waits on its own event. Sticky Events are not subject to the lost-wakeup hazard
that a bare ``Condition.notify_all`` handoff showed in the WP0 probe.

Invariants (I1-I7) are documented in ``docs/language-spec.md`` section 11.4 and
asserted by ``tests/test_concurrency.py``.
"""

from __future__ import annotations

from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
import hashlib
import json
import os
import tempfile
import threading
from typing import Any, Callable

from .errors import LwtError, SourceLocation

SCHEMA = "lwt-schedule-trace/1"
SCHEMA_VERSION = 1

# Per-thread current task id. The runtime context is shared across task
# threads, so the active task must be thread-local (never a shared field).
_context = threading.local()


def current_task_id() -> int:
    return getattr(_context, "task_id", 0)


def set_current_task_id(task_id: int) -> None:
    _context.task_id = task_id


# ---------------------------------------------------------------------------
# Self-contained PRNG (spec 11.4); no `random`, no platform-dependent state.
# ---------------------------------------------------------------------------
class SplitMix64:
    MASK = (1 << 64) - 1
    GAMMA = 0x9E3779B97F4A7C15

    def __init__(self, seed: int) -> None:
        self.state = seed & self.MASK

    def next_u64(self) -> int:
        self.state = (self.state + self.GAMMA) & self.MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & self.MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & self.MASK
        return z ^ (z >> 31)

    def below(self, n: int) -> int:
        return self.next_u64() % n


def source_digest(entries: dict[str, str]) -> str:
    """Normalized digest over entry + all module sources, path-sorted."""

    digest = hashlib.sha256()
    for path in sorted(entries):
        digest.update(path.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(entries[path].encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ScheduleReplayMismatch(Exception):
    """A replay trace field is inconsistent (mapped to CliError/4 by cli)."""


class DeadlockDetected(Exception):
    """Internal signal that the scheduler found no runnable task."""


# ---------------------------------------------------------------------------
# Opaque value state.
# ---------------------------------------------------------------------------
@dataclass
class ChannelState:
    channel_id: int
    items: deque[object] = field(default_factory=deque)
    closed: bool = False
    waiting: deque[int] = field(default_factory=deque)

    def send(self, value: object) -> None:
        self.items.append(value)

    def close(self) -> None:
        self.closed = True

    def receive(self) -> tuple[bool, object]:
        if self.items:
            return False, self.items.popleft()
        if self.closed:
            return False, None
        return True, None


@dataclass
class TaskState:
    task_id: int
    status: str = "ready"  # ready | blocked | io_pending | done
    token: threading.Event = field(default_factory=threading.Event)
    injected: object = None
    result: object = None
    error: BaseException | None = None
    last_block_location: SourceLocation | None = None
    joiners: set[int] = field(default_factory=set)
    joined: bool = False  # an explicit join already consumed result/error


# ---------------------------------------------------------------------------
# Schedule trace recording / replay / validation.
# ---------------------------------------------------------------------------
@dataclass
class ScheduleTracer:
    source: str
    source_sha256: str
    program_args: tuple[str, ...]
    policy: str
    replay: dict[str, Any] | None = None
    decisions: list[dict[str, Any]] = field(default_factory=list)

    def validate_bindings(self) -> None:
        trace = self.replay
        if trace is None:
            return
        expected = {
            "schema": SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "source": self.source,
            "source_sha256": self.source_sha256,
            "policy": self.policy,
        }
        for key, value in expected.items():
            if trace.get(key) != value:
                raise ScheduleReplayMismatch(f"trace binding mismatch: {key}")
        if list(trace.get("program_args", [])) != list(self.program_args):
            raise ScheduleReplayMismatch("trace binding mismatch: program_args")
        if not isinstance(trace.get("decisions"), list):
            raise ScheduleReplayMismatch("trace binding mismatch: decisions")

    def replay_choice(self, index: int, ready: list[int]) -> int:
        trace = self.replay
        assert trace is not None
        records: list[Any] = trace["decisions"]
        if index >= len(records):
            raise ScheduleReplayMismatch(f"decision {index}: trace too short")
        record = records[index]
        if record.get("index") != index:
            raise ScheduleReplayMismatch(
                f"decision {index}: expected index {index}, got {record.get('index')!r}"
            )
        chosen = record.get("chosen")
        if chosen not in ready:
            raise ScheduleReplayMismatch(
                f"decision {index}: chosen {chosen!r} not in ready {ready}"
            )
        return int(chosen)

    def record(self, index: int, ready: list[int], chosen: int) -> None:
        self.decisions.append({"index": index, "ready": list(ready), "chosen": chosen})

    def document(self, *, exit_code: int, stdout: bytes, stderr: bytes) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "source": self.source,
            "source_sha256": self.source_sha256,
            "program_args": list(self.program_args),
            "policy": self.policy,
            "expected_exit_code": exit_code,
            "expected_stdout_sha256": _sha256_bytes(stdout),
            "expected_stderr_sha256": _sha256_bytes(stderr),
            "decisions": list(self.decisions),
        }

    @staticmethod
    def load(path: str) -> dict[str, Any]:
        try:
            with open(path, "r", encoding="utf-8", newline="") as handle:
                data = json.load(handle)
        except (OSError, ValueError) as error:
            raise ScheduleReplayMismatch(f"cannot read schedule trace: {error}") from None
        if not isinstance(data, dict) or data.get("schema") != SCHEMA:
            raise ScheduleReplayMismatch("unsupported schedule trace schema")
        return data

    @staticmethod
    def write(path: str, document: dict[str, Any]) -> None:
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        text = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", dir=parent,
            prefix=os.path.basename(path) + ".", suffix=".tmp", delete=False,
        ) as handle:
            temporary = handle.name
            handle.write(text)
        os.replace(temporary, path)


# ---------------------------------------------------------------------------
# The scheduler.
# ---------------------------------------------------------------------------
class Scheduler:
    """Single-token deterministic scheduler over host threads.

    ``switch`` is called only from the five scheduling points. It records a
    decision, chooses the next owner from the sorted ready set, transfers the
    sticky Event token, and blocks until this task is owner again.
    """

    def __init__(
        self,
        *,
        policy: str,
        tracer: ScheduleTracer,
        max_workers: int = 8,
    ) -> None:
        self.policy = policy
        self.tracer = tracer
        self.cond = threading.Condition(threading.Lock())
        self.tasks: dict[int, TaskState] = {0: TaskState(task_id=0, status="blocked")}
        self.channels: dict[int, ChannelState] = {}
        self.owner = 0
        self.next_task_id = 1
        self.next_channel_id = 1
        self.prng = SplitMix64(int(policy.split(":", 1)[1])) if policy.startswith("random:") else None
        self.shutdown = False
        self.deadlock = False
        self.deadlock_location: SourceLocation | None = None
        self.replay_error: ScheduleReplayMismatch | None = None
        self._pending_io: dict[int, tuple[Future[Any], Callable[[Future[Any]], object]]] = {}
        self._queue: deque[int] = deque()  # true FIFO ready queue (spec 11.4)
        self._threads: list[threading.Thread] = []
        self._task_pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="lwt-task")
        self._io_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="lwt-io")
        # The main task starts owning the token; its event is set.
        self.tasks[0].token.set()

    # -- handle allocation -------------------------------------------------
    def register_task(self, task_id: int, *, at_tail: bool = True) -> None:
        """Make an existing task ready, enqueued at the tail (or head for main)."""

        if at_tail:
            self._queue.append(task_id)
        else:
            self._queue.appendleft(task_id)

    def new_task_id(self) -> int:
        with self.cond:
            task_id = self.next_task_id
            self.next_task_id += 1
            self.tasks[task_id] = TaskState(task_id=task_id)
            return task_id

    def new_channel_id(self) -> int:
        with self.cond:
            channel_id = self.next_channel_id
            self.next_channel_id += 1
            self.channels[channel_id] = ChannelState(channel_id)
            return channel_id

    def channel(self, channel_id: int) -> ChannelState:
        return self.channels[channel_id]

    def wake_receiver(self, channel_id: int, value: object) -> None:
        """Hand a sent value to a task blocked in receive (id-ordered FIFO)."""

        with self.cond:
            channel = self.channels[channel_id]
            if not channel.waiting:
                return
            receiver = channel.waiting.popleft()
            state = self.tasks[receiver]
            state.injected = value
            if state.status == "blocked":
                state.status = "ready"
                self._queue.append(receiver)

    # -- choice (I5: pure) -------------------------------------------------
    def _choose(self) -> int:
        """Choose the next owner from the FIFO queue.

        fifo takes the head; random:SEED chooses a uniform index over a sorted
        snapshot of the queue. The recorded ``ready`` is always the sorted set
        (a stable, order-independent view); replay therefore matches whichever
        policy produced the trace. Selection reads no time/thread id.
        """

        snapshot = sorted(self._queue)
        index = len(self.tracer.decisions)
        if self.tracer.replay is not None:
            chosen = self.tracer.replay_choice(index, snapshot)
        elif self.prng is None:
            chosen = self._queue[0]
        else:
            ordered = sorted(self._queue)
            chosen = ordered[self.prng.below(len(ordered))]
        self.tracer.record(index, snapshot, chosen)
        self._queue.remove(chosen)
        return chosen

    def _ready_ids(self) -> list[int]:
        return list(self._queue)

    def _attach_io(
        self,
        task_id: int,
        future: Future[Any],
        continuation: Callable[[Future[Any]], object],
    ) -> None:
        """Attach a done-callback so a completed I/O batch requeues its tasks.

        The callback runs on the I/O worker but mutates scheduler state only
        under ``cond`` (I3). It wakes a pending switch from ``cond.wait``.
        """

        self._pending_io[task_id] = (future, continuation)

        def on_done(done: Future[Any]) -> None:
            with self.cond:
                if task_id not in self._pending_io:
                    return
                del self._pending_io[task_id]
                state = self.tasks[task_id]
                try:
                    state.injected = continuation(done)
                except BaseException as error:  # re-raised in the owning task
                    state.injected = error
                if state.status == "io_pending":
                    state.status = "ready"
                    self._queue.append(task_id)
                self.cond.notify_all()

        future.add_done_callback(on_done)

    def _all_children_done(self) -> bool:
        return all(
            state.status == "done" for tid, state in self.tasks.items() if tid != 0
        )

    def switch(
        self,
        current: int,
        *,
        release: str,
        block_on: int | None = None,
        io: tuple[Future[Any], Callable[[Future[Any]], object]] | None = None,
        location: SourceLocation | None = None,
    ) -> object:
        """Release the token and block until this task owns it again.

        ``release``: ``ready`` (yield / spawn handoff), ``blocked`` (join /
        receive), ``io_pending`` (read_text), ``done`` (task finished).
        Returns the value injected by the task that wakes us.
        """

        with self.cond:
            state = self.tasks[current]
            if location is not None:
                state.last_block_location = location
            if release == "ready":
                state.status = "ready"
                self._queue.append(current)
            elif release == "blocked":
                state.status = "blocked"
                if block_on is not None:
                    self.tasks[block_on].joiners.add(current)
            elif release == "io_pending":
                state.status = "io_pending"
                if io is not None:
                    future, continuation = io
                    self._attach_io(current, future, continuation)
            elif release == "done":
                state.status = "done"
                # Waking joiners must be order-independent: requeue in id order.
                woken = sorted(
                    joiner for joiner in state.joiners
                    if self.tasks[joiner].status == "blocked"
                )
                for joiner in woken:
                    self.tasks[joiner].status = "ready"
                    self._queue.append(joiner)
                state.joiners.clear()
                if self.tasks[0].status == "blocked" and self._all_children_done():
                    self.tasks[0].status = "ready"
            else:
                raise AssertionError(f"unknown release kind: {release!r}")

            # I/O batch barrier (spec 11.8): when no task is runnable but some
            # are waiting on I/O, wait for the batch to complete. The done
            # callbacks requeue finished tasks under ``cond`` and notify us.
            while not self._queue and self._pending_io and not self.shutdown:
                self.cond.wait(timeout=0.25)

            if not self._queue:
                unfinished = any(
                    state.status != "done"
                    for tid, state in self.tasks.items()
                    if tid != 0
                )
                unfinished = unfinished or self.tasks[0].status == "blocked"
                if unfinished and not self.shutdown:
                    self.deadlock = True
                    self.shutdown = True
                    self.deadlock_location = state.last_block_location
                    for task in self.tasks.values():
                        task.token.set()
                    self.cond.notify_all()
                    raise DeadlockDetected()
                # A replay failure already woke everyone; fall through to hand
                # the token back so the waiting task can re-raise it.
                chosen = 0
            else:
                try:
                    chosen = self._choose()
                except ScheduleReplayMismatch as error:
                    # Fatal: wake every task thread before propagating, else a
                    # peer waiting on its token would hang the process.
                    self.replay_error = error
                    self.shutdown = True
                    for task in self.tasks.values():
                        task.token.set()
                    self.cond.notify_all()
                    raise

            self.owner = chosen
            self.tasks[current].token.clear()
            self.tasks[chosen].token.set()
            self.cond.notify_all()

        # Wait for the token to come back (sticky Event: no lost wakeups).
        result = state_result_wait(self.cond, self, current)
        return result

    def wait_io_batch(self) -> None:
        """Block until every io_pending future in the current batch is done."""

        with self.cond:
            futures = [
                future for future, _cont in self._pending_io.values()
                if not future.done()
            ]
        for future in futures:
            try:
                future.result()
            except BaseException:
                pass

    @property
    def io_pool(self) -> ThreadPoolExecutor:
        return self._io_pool

    @property
    def task_pool(self) -> ThreadPoolExecutor:
        return self._task_pool

    def submit_task(self, task_id: int, runner: Callable[[int], None]) -> None:
        """Run ``runner`` on a host thread; it waits for the token first."""

        def wrapped() -> None:
            state = self.tasks[task_id]
            while True:
                if self.shutdown:
                    return
                if state.token.wait(timeout=0.25):
                    state.token.clear()
                    break
            try:
                runner(task_id)
            except SystemExit:
                raise
            except KeyboardInterrupt:
                raise
            except BaseException as error:  # converted to LwtError by runner
                state.error = error
                state.status = "done"

        future = self._task_pool.submit(wrapped)
        self._threads.append(future)

    def task_state(self, task_id: int) -> TaskState:
        return self.tasks[task_id]

    def join_target(self, current: int, target: int) -> bool:
        """True if target is done (and its result/error was injected)."""

        with self.cond:
            return self.tasks[target].status == "done"

    def mark_main_blocked(self, location: SourceLocation | None) -> None:
        with self.cond:
            self.tasks[0].status = "blocked"
            if location is not None:
                self.tasks[0].last_block_location = location

    def mark_main_ready(self) -> None:
        with self.cond:
            self.tasks[0].status = "ready"

    def stop(self) -> None:
        with self.cond:
            self.shutdown = True
            for state in self.tasks.values():
                state.token.set()
            self.cond.notify_all()

    def fail_replay(self, error: ScheduleReplayMismatch) -> None:
        """A replay mismatch is fatal: wake every waiter so no thread hangs."""

        with self.cond:
            self.replay_error = error
            self.shutdown = True
            for state in self.tasks.values():
                state.token.set()
            self.cond.notify_all()

    def close(self) -> None:
        self._task_pool.shutdown(wait=True, cancel_futures=True)
        self._io_pool.shutdown(wait=True, cancel_futures=True)


def state_result_wait(
    cond: threading.Condition, scheduler: Scheduler, task_id: int
) -> object:
    """Wait on this task's sticky token, then return its injected value."""

    state = scheduler.tasks[task_id]
    while True:
        if state.token.wait(timeout=0.25):
            state.token.clear()
            if scheduler.replay_error is not None:
                raise scheduler.replay_error
            return state.injected
        if scheduler.shutdown:
            if scheduler.replay_error is not None:
                raise scheduler.replay_error
            raise DeadlockDetected()
