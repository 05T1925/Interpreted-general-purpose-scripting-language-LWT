from __future__ import annotations

import io
import unittest

from lwt.dap_protocol import DapProtocolError, DapReader, encode_message


class _FragmentedReader:
    def __init__(self, payload: bytes, fragment_size: int = 2) -> None:
        self.payload = payload
        self.fragment_size = fragment_size
        self.offset = 0

    def read(self, length: int = -1) -> bytes:
        if self.offset >= len(self.payload):
            return b""
        requested = len(self.payload) - self.offset if length < 0 else length
        count = min(requested, self.fragment_size)
        result = self.payload[self.offset : self.offset + count]
        self.offset += len(result)
        return result


class DapProtocolCodecTests(unittest.TestCase):
    def test_content_length_counts_utf8_bytes_and_round_trips_unicode(self) -> None:
        message = {"seq": 9, "type": "event", "event": "output", "body": {"output": "雪 λ"}}
        frame = encode_message(message)
        header, payload = frame.split(b"\r\n\r\n", 1)
        declared = int(header.split(b":", 1)[1])
        self.assertEqual(declared, len(payload))
        self.assertGreater(declared, len(payload.decode("utf-8")))
        self.assertEqual(DapReader(io.BytesIO(frame)).read_message(), message)

    def test_fragmented_and_concatenated_frames_are_read_separately(self) -> None:
        first = {"seq": 1, "type": "request", "command": "initialize"}
        second = {"seq": 2, "type": "event", "event": "initialized", "body": {}}
        stream = _FragmentedReader(encode_message(first) + encode_message(second), 1)
        reader = DapReader(stream)
        self.assertEqual(reader.read_message(), first)
        self.assertEqual(reader.read_message(), second)
        self.assertIsNone(reader.read_message())

    def test_accepts_optional_content_type_header(self) -> None:
        payload = b'{"seq":1,"type":"response"}'
        frame = (
            f"Content-Length: {len(payload)}\r\nContent-Type: application/vscode-jsonrpc; charset=utf-8\r\n\r\n".encode("ascii")
            + payload
        )
        self.assertEqual(DapReader(io.BytesIO(frame)).read_message()["type"], "response")

    def test_rejects_malformed_and_duplicate_headers(self) -> None:
        payload = b"{}"
        bad_headers = [
            b"content length: 2\r\n\r\n",
            b"Content-Length: 2\r\nContent-Length: 2\r\n\r\n",
            b"Content-Length: -1\r\n\r\n",
            b"Content-Length: 1.5\r\n\r\n",
            b"X-Test: value\r\nContent-Length: 2\r\n\r\n",
            b"\r\n\r\n",
        ]
        for header in bad_headers:
            with self.subTest(header=header):
                with self.assertRaises(DapProtocolError):
                    DapReader(io.BytesIO(header + payload)).read_message()

    def test_rejects_invalid_json_utf8_and_non_object_bodies(self) -> None:
        for payload in (b"{", b"\xff", b"[]", b"null"):
            frame = f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii") + payload
            with self.subTest(payload=payload):
                with self.assertRaises(DapProtocolError):
                    DapReader(io.BytesIO(frame)).read_message()

    def test_rejects_oversized_header_and_content_before_reading_body(self) -> None:
        header = b"Content-Length: 9\r\n\r\n"
        with self.assertRaisesRegex(DapProtocolError, "content length limit"):
            DapReader(io.BytesIO(header), max_content_length=8).read_message()
        huge_length = b"Content-Length: " + b"9" * 5000 + b"\r\n\r\n"
        with self.assertRaisesRegex(DapProtocolError, "content length limit"):
            DapReader(io.BytesIO(huge_length)).read_message()
        with self.assertRaisesRegex(DapProtocolError, "header exceeds"):
            DapReader(
                io.BytesIO(b"X" * 32), max_header_length=16
            ).read_message()

    def test_reports_eof_inside_header_and_body(self) -> None:
        with self.assertRaisesRegex(DapProtocolError, "EOF inside DAP header"):
            DapReader(io.BytesIO(b"Content-Length: 2\r\n")).read_message()
        with self.assertRaisesRegex(DapProtocolError, "EOF inside DAP message body"):
            DapReader(io.BytesIO(b"Content-Length: 5\r\n\r\n{}")).read_message()


if __name__ == "__main__":
    unittest.main()
