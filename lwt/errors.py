"""Shared error and source-location types for the LWT command line tools."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """A one-based source position measured in Unicode code points."""

    line: int
    column: int


class LwtError(Exception):
    """An expected LWT/CLI error that can be rendered without a traceback."""

    def __init__(
        self,
        category: str,
        message: str,
        exit_code: int,
        location: SourceLocation | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.message = message
        self.exit_code = exit_code
        self.location = location


def _single_line(value: str) -> str:
    """Escape line breaks so one diagnostic always occupies one output line."""

    return value.replace("\r", "\\r").replace("\n", "\\n")


def format_diagnostic(error: LwtError, source_path: str | None = None) -> str:
    """Format a user-facing diagnostic, without its terminating LF."""

    category = _single_line(error.category)
    message = _single_line(error.message)
    if error.location is None or source_path is None:
        return f"lwt: {category}: {message}"

    path = _single_line(source_path)
    return (
        f"{path}:{error.location.line}:{error.location.column}: "
        f"{category}: {message}"
    )
