"""Strict parsing and formatting for the LWT Snake line protocol."""

from __future__ import annotations

from dataclasses import dataclass


PROTOCOL_VERSION = "LWS1"
MAX_REQUEST_BYTES = 128
MAX_RESPONSE_BYTES = 4096
MAX_WIDTH = 24
MAX_HEIGHT = 18
MAX_CELLS = 432
MAX_SEQUENCE = 999_999
VALID_PHASES = {"READY", "RUNNING", "PAUSED", "GAME_OVER", "WON"}
VALID_DIRECTIONS = {"U", "R", "D", "L"}
VALID_ERROR_CODES = {
    "BAD_FIELD_COUNT",
    "BAD_VERSION",
    "BAD_SEQUENCE",
    "FRAME_TOO_LONG",
    "BAD_COMMAND",
    "BAD_ARGUMENT",
    "BAD_STATE",
    "NOT_INITIALIZED",
    "BAD_TURN",
}


class ProtocolError(RuntimeError):
    """The LWT child violated the agreed protocol or exited unexpectedly."""


class CommandRejected(ProtocolError):
    """The LWT server rejected a well-framed command without changing state."""

    def __init__(self, sequence: int, code: str) -> None:
        self.sequence = sequence
        self.code = code
        super().__init__(f"LWT Snake command {sequence:06d} rejected: {code}")


@dataclass(frozen=True)
class GameSnapshot:
    sequence: int
    phase: str
    score: int
    direction: str
    food: tuple[int, int] | None
    snake: tuple[tuple[int, int], ...]
    width: int
    height: int


def _ascii_decimal(text: str, *, canonical: bool = True) -> int:
    if not text or any(character < "0" or character > "9" for character in text):
        raise ProtocolError("protocol field must be an ASCII decimal integer")
    value = int(text)
    if canonical and str(value) != text:
        raise ProtocolError("protocol integer uses non-canonical leading zeroes")
    return value


def _sequence_field(text: str, expected: int) -> int:
    if len(text) != 6 or any(character < "0" or character > "9" for character in text):
        raise ProtocolError("protocol sequence must contain six ASCII digits")
    value = int(text)
    if value != expected:
        raise ProtocolError(f"response sequence {value:06d} does not match request {expected:06d}")
    return value


def format_request(sequence: int, command: str, args: tuple[str, str, str]) -> bytes:
    if not 1 <= sequence <= MAX_SEQUENCE:
        raise ProtocolError("request sequence limit reached; restart the LWT session")
    if len(args) != 3:
        raise ProtocolError("internal request must have exactly three argument fields")
    fields = (PROTOCOL_VERSION, f"{sequence:06d}", command, *args)
    for field in fields:
        try:
            encoded = field.encode("ascii", "strict")
        except UnicodeEncodeError as error:
            raise ProtocolError("request fields must be ASCII") from error
        if b"|" in encoded or b"\r" in encoded or b"\n" in encoded:
            raise ProtocolError("request fields cannot contain frame delimiters")
    line = "|".join(fields).encode("ascii")
    if len(line) > MAX_REQUEST_BYTES:
        raise ProtocolError("request exceeds the 128-byte frame limit")
    return line + b"\n"


def parse_response(
    line: bytes,
    *,
    expected_sequence: int,
    width: int,
    height: int,
) -> GameSnapshot:
    """Parse one response frame (without LF), rejecting inconsistent snapshots."""

    if not line or len(line) > MAX_RESPONSE_BYTES:
        raise ProtocolError("response frame is empty or exceeds the 4096-byte limit")
    if b"\n" in line or b"\r" in line:
        raise ProtocolError("response frame contains an embedded line ending")
    try:
        text = line.decode("ascii", "strict")
    except UnicodeDecodeError as error:
        raise ProtocolError("response frame is not ASCII/UTF-8 protocol text") from error
    fields = text.split("|")
    if len(fields) == 4 and fields[0] == PROTOCOL_VERSION and fields[1] == "ERR":
        sequence = _sequence_field(fields[2], expected_sequence)
        if fields[3] not in VALID_ERROR_CODES:
            raise ProtocolError(f"unknown LWT Snake error code: {fields[3]!r}")
        raise CommandRejected(sequence, fields[3])
    if len(fields) != 10:
        raise ProtocolError(f"state response has {len(fields)} fields; expected exactly 10")
    if fields[0] != PROTOCOL_VERSION or fields[2] != "STATE":
        raise ProtocolError("response version or frame kind is invalid")
    sequence = _sequence_field(fields[1], expected_sequence)
    phase = fields[3]
    if phase not in VALID_PHASES:
        raise ProtocolError(f"unknown game phase: {phase!r}")
    score = _ascii_decimal(fields[4])
    if score % 10:
        raise ProtocolError("score must be a non-negative multiple of 10")
    direction = fields[5]
    if direction not in VALID_DIRECTIONS:
        raise ProtocolError(f"unknown direction: {direction!r}")

    if fields[6] == "-" and fields[7] == "-":
        food = None
    elif fields[6] == "-" or fields[7] == "-":
        raise ProtocolError("food coordinates must both be integers or both be '-'")
    else:
        food = (_ascii_decimal(fields[6]), _ascii_decimal(fields[7]))
        if not (0 <= food[0] < width and 0 <= food[1] < height):
            raise ProtocolError("food coordinate is outside the configured board")

    body_length = _ascii_decimal(fields[8])
    if not 3 <= body_length <= min(width * height, MAX_CELLS):
        raise ProtocolError("snake length is outside the configured board limits")
    raw_parts = fields[9].split(";")
    if len(raw_parts) != body_length:
        raise ProtocolError("BODY_LEN does not match the number of body coordinates")
    snake: list[tuple[int, int]] = []
    for raw_part in raw_parts:
        coordinates = raw_part.split(",")
        if len(coordinates) != 2:
            raise ProtocolError("snake coordinate must have exactly two fields")
        point = (_ascii_decimal(coordinates[0]), _ascii_decimal(coordinates[1]))
        if not (0 <= point[0] < width and 0 <= point[1] < height):
            raise ProtocolError("snake coordinate is outside the configured board")
        if point in snake:
            raise ProtocolError("snake body contains duplicate coordinates")
        if snake:
            previous = snake[-1]
            if abs(point[0] - previous[0]) + abs(point[1] - previous[1]) != 1:
                raise ProtocolError("adjacent snake segments are not orthogonally connected")
        snake.append(point)
    if food is not None and food in snake:
        raise ProtocolError("food overlaps the snake")
    if (phase == "WON") != (food is None):
        raise ProtocolError("only WON state may have no food")
    return GameSnapshot(sequence, phase, score, direction, food, tuple(snake), width, height)
