"""Bounded stdio framing and JSON-RPC helpers for the LWT language server."""

from __future__ import annotations

import json
from typing import BinaryIO


MAX_HEADER_BYTES = 16 * 1024
MAX_MESSAGE_BYTES = 8 * 1024 * 1024


class ProtocolError(Exception):
    """A framing error that makes it unsafe to continue reading the stream."""


class JsonParseError(Exception):
    """A framed body that is not one strict JSON-RPC object."""


class InvalidMessage(Exception):
    """Valid JSON with a top-level shape that cannot be a JSON-RPC message."""


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise ValueError("non-finite JSON number")


def read_message(stream: BinaryIO) -> dict[str, object] | None:
    """Read one Content-Length frame, returning None only at clean EOF."""
    header = bytearray()
    while not header.endswith(b"\r\n\r\n"):
        chunk = stream.read(1)
        if not chunk:
            if not header:
                return None
            raise ProtocolError("truncated LSP header")
        header.extend(chunk)
        if len(header) > MAX_HEADER_BYTES:
            raise ProtocolError("LSP header exceeds size limit")

    try:
        header_text = bytes(header[:-4]).decode("ascii", errors="strict")
    except UnicodeDecodeError as error:
        raise ProtocolError("LSP headers must be ASCII") from error

    content_lengths: list[str] = []
    content_types: list[str] = []
    for line in header_text.split("\r\n"):
        if not line or ":" not in line:
            raise ProtocolError("malformed LSP header")
        name, value = line.split(":", 1)
        value = value.strip()
        if name.lower() == "content-length":
            content_lengths.append(value)
        elif name.lower() == "content-type":
            content_types.append(value)
    if len(content_lengths) != 1:
        raise ProtocolError("exactly one Content-Length header is required")
    raw_length = content_lengths[0]
    if not raw_length.isascii() or not raw_length.isdecimal():
        raise ProtocolError("invalid Content-Length")
    content_length = int(raw_length)
    if content_length > MAX_MESSAGE_BYTES:
        raise ProtocolError("LSP message exceeds size limit")
    if len(content_types) > 1:
        raise ProtocolError("duplicate Content-Type header")
    if content_types:
        media_type = content_types[0].lower().replace(" ", "")
        if media_type not in {
            "application/vscode-jsonrpc;charset=utf-8",
            "application/vscode-jsonrpc; charset=utf-8".replace(" ", ""),
        }:
            raise ProtocolError("Content-Type must specify UTF-8")

    body = bytearray()
    while len(body) < content_length:
        chunk = stream.read(content_length - len(body))
        if not chunk:
            raise ProtocolError("truncated LSP body")
        body.extend(chunk)
    try:
        text = bytes(body).decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise JsonParseError("invalid JSON-RPC body") from error
    if not isinstance(value, dict):
        raise InvalidMessage("JSON-RPC message must be an object")
    return value


def encode_message(message: dict[str, object]) -> bytes:
    """Encode one compact UTF-8 JSON-RPC object with byte-accurate framing."""
    payload = json.dumps(
        message, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8", errors="strict")
    return f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii") + payload


def response(request_id: object, result: object) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def error_response(
    request_id: object, code: int, message: str
) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }
