"""Lightweight scheduling support shared by the runtime, CLI and scheduler.

This module deliberately depends only on ``threading`` (a small stdlib module).
It holds the internal scheduling exceptions and the thread-local current-task
id so that ``lwt.runtime`` and ``lwt.cli`` can be imported *without* pulling in
the heavy scheduler stack (``concurrent.futures``, ``hashlib``, ``json``,
``tempfile``) for programs that never use ``spawn`` (S44 P0-1).

``lwt.concurrency`` re-exports these names, so existing imports from that
module keep working and the exception class identity stays single: a
``DeadlockDetected`` raised by the scheduler is the same class object that the
runtime catches.
"""

from __future__ import annotations

import threading

__all__ = (
    "DeadlockDetected",
    "ScheduleReplayMismatch",
    "current_task_id",
    "set_current_task_id",
)


class ScheduleReplayMismatch(Exception):
    """A replay trace field is inconsistent (mapped to CliError/4 by cli)."""


class DeadlockDetected(Exception):
    """Internal signal that the scheduler found no runnable task."""


# Per-thread current task id. The runtime context is shared across task
# threads, so the active task must be thread-local (never a shared field).
_context = threading.local()


def current_task_id() -> int:
    return getattr(_context, "task_id", 0)


def set_current_task_id(task_id: int) -> None:
    _context.task_id = task_id
