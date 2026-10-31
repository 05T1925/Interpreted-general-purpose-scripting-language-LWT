from __future__ import annotations

import json
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lwt.lsp_protocol import encode_message
from lwt.lsp_documents import codepoint_to_utf16_character
from lwt.lsp_server import LspServer


REPOSITORY = Path(__file__).resolve().parents[1]


def frames(raw: bytes) -> list[dict[str, object]]:
    messages: list[dict[str, object]] = []
    offset = 0
    while offset < len(raw):
        separator = raw.find(b"\r\n\r\n", offset)
        if separator < 0:
            raise AssertionError("stdout contains bytes outside LSP framing")
        header = raw[offset:separator].decode("ascii")
        lengths = [line.split(":", 1)[1].strip() for line in header.split("\r\n") if line.lower().startswith("content-length:")]
        if len(lengths) != 1:
            raise AssertionError("response must have exactly one Content-Length")
        length = int(lengths[0])
        body_start = separator + 4
        body_end = body_start + length
        if body_end > len(raw):
            raise AssertionError("truncated response body")
        body = raw[body_start:body_end]
        if len(body) != length:
            raise AssertionError("Content-Length is not a UTF-8 byte count")
        messages.append(json.loads(body.decode("utf-8")))
        offset = body_end
    return messages


def run_server(messages: list[dict[str, object]], *, timeout: float = 10.0):
    process = subprocess.Popen(
        [sys.executable, "-m", "lwt.lsp_server"],
        cwd=REPOSITORY,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    payload = b"".join(encode_message(message) for message in messages)
    try:
        stdout, stderr = process.communicate(payload, timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate(timeout=2)
        raise AssertionError(f"language server timed out; stderr={stderr!r}; stdout={stdout!r}")
    return process.returncode, stdout, stderr, frames(stdout)


class LspServerSubprocessTests(unittest.TestCase):
    def test_real_stdio_lifecycle_features_diagnostics_and_overlay(self) -> None:
        with tempfile.TemporaryDirectory(prefix="LWT LSP 中文 ") as directory:
            source_path = Path(directory) / "hello space.lwt"
            uri = source_path.as_uri()
            expected_definition_uri = source_path.resolve(strict=False).as_uri()
            text = 'let mark = "😀";\nfn greet(name) { return name; }\nlet out = greet(mark);\nemit input();\n'
            changed = text + "missing();\n"
            messages = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "method": "initialized", "params": {}},
                {"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {"textDocument": {"uri": uri, "languageId": "lwt", "version": 1, "text": text}}},
                {"jsonrpc": "2.0", "method": "textDocument/didChange", "params": {"textDocument": {"uri": uri, "version": 2}, "contentChanges": [{"range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}}, "text": changed}]}},
                {"jsonrpc": "2.0", "method": "textDocument/didChange", "params": {"textDocument": {"uri": uri, "version": 1}, "contentChanges": [{"text": changed}]}},
                {"jsonrpc": "2.0", "id": 2, "method": "textDocument/documentSymbol", "params": {"textDocument": {"uri": uri}}},
                {"jsonrpc": "2.0", "id": 3, "method": "textDocument/hover", "params": {"textDocument": {"uri": uri}, "position": {"line": 2, "character": codepoint_to_utf16_character(text.splitlines()[2], text.splitlines()[2].index("greet"))}}},
                {"jsonrpc": "2.0", "id": 4, "method": "textDocument/definition", "params": {"textDocument": {"uri": uri}, "position": {"line": 2, "character": codepoint_to_utf16_character(text.splitlines()[2], text.splitlines()[2].index("greet"))}}},
                {"jsonrpc": "2.0", "method": "textDocument/didChange", "params": {"textDocument": {"uri": uri, "version": 2}, "contentChanges": [{"text": changed}]}},
                {"jsonrpc": "2.0", "method": "textDocument/didChange", "params": {"textDocument": {"uri": uri, "version": 3}, "contentChanges": [{"text": text}]}},
                {"jsonrpc": "2.0", "method": "textDocument/didClose", "params": {"textDocument": {"uri": uri}}},
                {"jsonrpc": "2.0", "id": 5, "method": "shutdown", "params": {}},
                {"jsonrpc": "2.0", "id": 6, "method": "textDocument/documentSymbol", "params": {"textDocument": {"uri": uri}}},
                {"jsonrpc": "2.0", "method": "exit"},
            ]
            code, stdout, stderr, result = run_server(messages)

        self.assertEqual(code, 0)
        self.assertNotIn(b"Traceback", stderr)
        self.assertNotIn(b"Traceback", stdout)
        self.assertTrue(all(item.get("jsonrpc") == "2.0" for item in result))
        self.assertEqual([item.get("id") for item in result if "id" in item], [1, 2, 3, 4, 5, 6])
        initialize = result[0]["result"]
        self.assertEqual(initialize["serverInfo"], {"name": "lwt-language-server", "version": "0.1"})
        capabilities = initialize["capabilities"]
        self.assertEqual(capabilities["positionEncoding"], "utf-16")
        self.assertEqual(capabilities["textDocumentSync"], {"openClose": True, "change": 1})
        self.assertNotIn("completionProvider", capabilities)
        notifications = [item for item in result if item.get("method") == "textDocument/publishDiagnostics"]
        self.assertEqual(len(notifications), 4)
        self.assertEqual(notifications[0]["params"]["diagnostics"], [])
        self.assertEqual(notifications[1]["params"]["diagnostics"][0]["code"], "STC010")
        self.assertEqual(notifications[2]["params"]["diagnostics"], [])
        self.assertEqual(notifications[3]["params"]["diagnostics"], [])
        responses = {item["id"]: item for item in result if "id" in item}
        symbols = responses[2]["result"]
        self.assertEqual([item["name"] for item in symbols], ["mark", "greet", "out"])
        self.assertEqual(responses[3]["result"]["contents"]["value"], "fn greet(name)")
        definition = responses[4]["result"]
        self.assertEqual(definition["uri"], expected_definition_uri)
        self.assertEqual(definition["range"]["start"], {"line": 1, "character": 3})
        self.assertIsNone(responses[5]["result"])
        self.assertEqual(responses[6]["error"]["code"], -32600)

    def test_errors_before_initialize_method_not_found_and_unexpected_exit(self) -> None:
        messages = [
            {"jsonrpc": "2.0", "id": 7, "method": "textDocument/hover", "params": {}},
            {"jsonrpc": "2.0", "id": 8, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "initialized"},
            {"jsonrpc": "2.0", "id": 9, "method": "workspace/executeCommand", "params": {}},
            {"jsonrpc": "2.0", "method": "exit"},
        ]
        code, _stdout, stderr, result = run_server(messages)
        self.assertEqual(code, 1)
        self.assertNotIn(b"Traceback", stderr)
        errors = [item["error"] for item in result if "error" in item]
        self.assertEqual([item["code"] for item in errors], [-32002, -32601])

    def test_unknown_notification_is_ignored_and_eof_has_fixed_failure_status(self) -> None:
        process = subprocess.Popen(
            [sys.executable, "-m", "lwt.lsp_server"], cwd=REPOSITORY,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
        )
        payload = encode_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        payload += encode_message({"jsonrpc": "2.0", "method": "initialized"})
        payload += encode_message({"jsonrpc": "2.0", "method": "custom/unknownNotification"})
        stdout, stderr = process.communicate(payload, timeout=5)
        self.assertEqual(process.returncode, 1)
        self.assertEqual(len(frames(stdout)), 1)
        self.assertNotIn(b"Traceback", stderr)

    def test_parse_and_invalid_params_error_codes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "x.lwt"
            uri = source.as_uri()
            payload = b"Content-Length: 1\r\n\r\n{"  # valid frame, malformed JSON
            payload += encode_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
            payload += encode_message({"jsonrpc": "2.0", "method": "initialized"})
            payload += encode_message({"jsonrpc": "2.0", "id": 2, "method": "textDocument/hover", "params": {"textDocument": {"uri": uri}, "position": {"line": "zero", "character": 0}}})
            payload += encode_message({"jsonrpc": "2.0", "id": 3, "method": "shutdown", "params": {}})
            payload += encode_message({"jsonrpc": "2.0", "method": "exit"})
            process = subprocess.Popen(
                [sys.executable, "-m", "lwt.lsp_server"], cwd=REPOSITORY,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
            )
            stdout, stderr = process.communicate(payload, timeout=8)
        result = frames(stdout)
        errors = [item["error"]["code"] for item in result if "error" in item]
        self.assertEqual(process.returncode, 0)
        self.assertEqual(errors, [-32700, -32602])
        self.assertNotIn(b"Traceback", stderr)

    def test_internal_error_is_sanitized(self) -> None:
        class FailingService:
            def hover(self, *_args):
                raise RuntimeError("private path C:\\secret\\source.lwt")

        payload = b"".join(
            encode_message(item)
            for item in [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "method": "initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "textDocument/hover", "params": {"textDocument": {"uri": "file:///C:/x.lwt"}, "position": {"line": 0, "character": 0}}},
            ]
        )
        output = io.BytesIO()
        errors = io.StringIO()
        server = LspServer(io.BytesIO(payload), output, errors)
        server.service = FailingService()
        server.run()
        result = frames(output.getvalue())
        self.assertEqual(result[-1]["error"]["code"], -32603)
        self.assertEqual(result[-1]["error"]["message"], "Internal error")
        self.assertNotIn("private path", output.getvalue().decode("utf-8"))
        self.assertNotIn("Traceback", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
