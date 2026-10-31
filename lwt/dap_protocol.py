"""Small, strict Debug Adapter Protocol stdio framing codec."""

from __future__ import annotations

import json
from typing import BinaryIO, Mapping


MAX_CONTENT_LENGTH = 8 * 1024 * 1024
MAX_HEADER_LENGTH = 16 * 1024


class DapProtocolError(ValueError):
    """A malformed or incomplete DAP frame."""


def encode_message(message: Mapping[str, object]) -> bytes:
    """Encode one DAP object using a UTF-8 byte-counted Content-Length."""

    try:
        payload = json.dumps(
            message,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8", errors="strict")
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise DapProtocolError(f"cannot encode DAP message: {error}") from None
    if len(payload) > MAX_CONTENT_LENGTH:
        raise DapProtocolError("DAP message exceeds the content length limit")
    return f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii") + payload


class DapReader:
    """Incrementally read DAP frames from a binary stream."""

    def __init__(
        self,
        stream: BinaryIO,
        *,
        max_content_length: int = MAX_CONTENT_LENGTH,
        max_header_length: int = MAX_HEADER_LENGTH,
    ) -> None:
        self.stream = stream
        self.max_content_length = max_content_length
        self.max_header_length = max_header_length

    def read_message(self) -> dict[str, object] | None:
        header = self._read_header()
        if header is None:
            return None
        content_length = self._parse_header(header, self.max_content_length)
        payload = self._read_exact(content_length)
        try:
            decoded = payload.decode("utf-8", errors="strict")
            message = json.loads(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise DapProtocolError("DAP message body is not valid UTF-8 JSON") from None
        if not isinstance(message, dict):
            raise DapProtocolError("DAP message body must be a JSON object")
        return message

    def _read_header(self) -> bytes | None:
        result = bytearray()
        while True:
            chunk = self.stream.read(1)
            if chunk == b"":
                if not result:
                    return None
                raise DapProtocolError("unexpected EOF inside DAP header")
            result.extend(chunk)
            if len(result) > self.max_header_length:
                raise DapProtocolError("DAP header exceeds the length limit")
            if result.endswith(b"\r\n\r\n"):
                return bytes(result[:-4])

    @staticmethod
    def _parse_header(header: bytes, max_content_length: int = MAX_CONTENT_LENGTH) -> int:
        try:
            lines = header.decode("ascii", errors="strict").split("\r\n")
        except UnicodeDecodeError:
            raise DapProtocolError("DAP header must contain ASCII characters") from None
        if not lines or any(not line for line in lines):
            raise DapProtocolError("DAP header contains an empty line")
        values: dict[str, str] = {}
        for line in lines:
            name, separator, value = line.partition(":")
            if not separator or not name or not value.startswith(" "):
                raise DapProtocolError("malformed DAP header")
            key = name.lower()
            if key not in {"content-length", "content-type"}:
                raise DapProtocolError(f"unsupported DAP header {name!r}")
            if key in values:
                raise DapProtocolError(f"duplicate DAP header {name!r}")
            values[key] = value[1:].strip()
        raw_length = values.get("content-length")
        if raw_length is None:
            raise DapProtocolError("DAP header is missing Content-Length")
        if not raw_length.isascii() or not raw_length.isdecimal():
            raise DapProtocolError("Content-Length must be a non-negative decimal integer")
        content_length = 0
        for digit in raw_length:
            content_length = content_length * 10 + ord(digit) - ord("0")
            if content_length > max_content_length:
                raise DapProtocolError("DAP message exceeds the content length limit")
        return content_length

    def _read_exact(self, length: int) -> bytes:
        result = bytearray()
        while len(result) < length:
            chunk = self.stream.read(length - len(result))
            if not chunk:
                raise DapProtocolError("unexpected EOF inside DAP message body")
            result.extend(chunk)
        return bytes(result)
