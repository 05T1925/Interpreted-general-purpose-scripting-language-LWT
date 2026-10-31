from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from lwt.lsp_protocol import (
    InvalidMessage,
    JsonParseError,
    ProtocolError,
    encode_message,
    read_message,
)


def frame(body: bytes, headers: bytes = b"") -> bytes:
    return headers + f"Content-Length: {len(body)}\r\n\r\n".encode() + body


class ChunkedStream:
    def __init__(self, data: bytes, chunk_size: int = 1) -> None:
        self.data = data
        self.offset = 0
        self.chunk_size = chunk_size

    def read(self, size: int = -1) -> bytes:
        if self.offset >= len(self.data):
            return b""
        if size < 0:
            size = len(self.data)
        end = min(self.offset + size, self.offset + self.chunk_size, len(self.data))
        chunk = self.data[self.offset:end]
        self.offset = end
        return chunk


class LspProtocolTests(unittest.TestCase):
    def test_unicode_body_length_is_utf8_byte_count(self) -> None:
        message = {"jsonrpc": "2.0", "method": "test", "params": {"text": "雪😀"}}
        encoded = encode_message(message)
        header, body = encoded.split(b"\r\n\r\n", 1)
        self.assertEqual(int(header.split(b":", 1)[1]), len(body))
        self.assertEqual(read_message(io.BytesIO(encoded)), message)

    def test_contiguous_messages(self) -> None:
        first = {"jsonrpc": "2.0", "id": 1, "result": None}
        second = {"jsonrpc": "2.0", "method": "initialized"}
        stream = io.BytesIO(encode_message(first) + encode_message(second))
        self.assertEqual(read_message(stream), first)
        self.assertEqual(read_message(stream), second)
        self.assertIsNone(read_message(stream))

    def test_fragmented_header_and_body(self) -> None:
        message = {"jsonrpc": "2.0", "method": "notify", "params": {"s": "🧪"}}
        self.assertEqual(read_message(ChunkedStream(encode_message(message))), message)

    def test_optional_utf8_content_type(self) -> None:
        body = b'{"jsonrpc":"2.0","method":"x"}'
        data = b"Content-Type: application/vscode-jsonrpc; charset=utf-8\r\n" + frame(body)
        self.assertEqual(read_message(io.BytesIO(data)), {"jsonrpc": "2.0", "method": "x"})

    def test_missing_content_length(self) -> None:
        with self.assertRaises(ProtocolError):
            read_message(io.BytesIO(b"X-Test: yes\r\n\r\n{}"))

    def test_duplicate_content_length(self) -> None:
        with self.assertRaises(ProtocolError):
            read_message(io.BytesIO(b"Content-Length: 2\r\nContent-Length: 2\r\n\r\n{}"))

    def test_invalid_content_length_forms(self) -> None:
        for value in (b"-1", b"abc", b"+2", b"", "٢".encode()):
            with self.subTest(value=value), self.assertRaises(ProtocolError):
                read_message(io.BytesIO(b"Content-Length: " + value + b"\r\n\r\n"))

    def test_non_utf8_content_type_rejected(self) -> None:
        body = b"{}"
        data = b"Content-Type: application/vscode-jsonrpc; charset=utf-16\r\n" + frame(body)
        with self.assertRaises(ProtocolError):
            read_message(io.BytesIO(data))

    def test_non_ascii_header_rejected(self) -> None:
        with self.assertRaises(ProtocolError):
            read_message(io.BytesIO(b"X-" + bytes([255]) + b": x\r\nContent-Length: 2\r\n\r\n{}"))

    def test_truncated_header(self) -> None:
        with self.assertRaises(ProtocolError):
            read_message(io.BytesIO(b"Content-Length: 2\r\n"))

    def test_truncated_body(self) -> None:
        with self.assertRaises(ProtocolError):
            read_message(io.BytesIO(b"Content-Length: 3\r\n\r\n{}"))

    def test_message_limit(self) -> None:
        with patch("lwt.lsp_protocol.MAX_MESSAGE_BYTES", 3):
            with self.assertRaises(ProtocolError):
                read_message(io.BytesIO(b"Content-Length: 4\r\n\r\n{}xx"))

    def test_invalid_json_and_duplicate_key(self) -> None:
        for body in (b"{", b'{"jsonrpc":"2.0","jsonrpc":"2.0"}'):
            with self.subTest(body=body), self.assertRaises(JsonParseError):
                read_message(io.BytesIO(frame(body)))

    def test_invalid_utf8_json_body(self) -> None:
        with self.assertRaises(JsonParseError):
            read_message(io.BytesIO(frame(b"\xff")))

    def test_json_top_level_must_be_object(self) -> None:
        with self.assertRaises(InvalidMessage):
            read_message(io.BytesIO(frame(json.dumps([1]).encode())))


if __name__ == "__main__":
    unittest.main()
