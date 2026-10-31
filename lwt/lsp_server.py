"""A deliberately small, static-only LWT Language Server over stdio."""

from __future__ import annotations

import sys
from typing import BinaryIO

from .language_service import LanguageService
from .lsp_documents import path_from_file_uri
from .lsp_protocol import (
    InvalidMessage,
    JsonParseError,
    ProtocolError,
    encode_message,
    error_response,
    read_message,
    response,
)


SERVER_INFO = {"name": "lwt-language-server", "version": "0.1"}
CAPABILITIES = {
    "positionEncoding": "utf-16",
    "textDocumentSync": {"openClose": True, "change": 1},
    "hoverProvider": True,
    "definitionProvider": True,
    "documentSymbolProvider": True,
}


class LspServer:
    def __init__(self, input_stream: BinaryIO, output_stream: BinaryIO, error_stream=None) -> None:
        self.input = input_stream
        self.output = output_stream
        self.error_stream = error_stream or sys.stderr
        self.service = LanguageService()
        self.initialized = False
        self.client_initialized = False
        self.shutdown = False
        self.exit_requested = False
        self.exit_code = 1

    def run(self) -> int:
        while not self.exit_requested:
            try:
                message = read_message(self.input)
            except JsonParseError:
                self._send(error_response(None, -32700, "Parse error"))
                continue
            except InvalidMessage:
                self._send(error_response(None, -32600, "Invalid Request"))
                continue
            except ProtocolError:
                self._log("invalid or truncated LSP framing")
                self._send(error_response(None, -32600, "Invalid Request"))
                return 1
            if message is None:
                self.exit_code = 0 if self.shutdown else 1
                return self.exit_code
            try:
                self._dispatch(message)
            except (BrokenPipeError, OSError):
                self._log("LSP stdio closed")
                return 1
        return self.exit_code

    def _dispatch(self, message: dict[str, object]) -> None:
        request_id = message.get("id")
        is_request = "id" in message
        if message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
            if is_request:
                self._send(error_response(_safe_id(request_id), -32600, "Invalid Request"))
            return
        if is_request and not _valid_id(request_id):
            self._send(error_response(None, -32600, "Invalid Request"))
            return
        method = message["method"]
        params = message.get("params", {})
        if not isinstance(params, dict):
            if is_request:
                self._send(error_response(request_id, -32602, "Invalid params"))
            return

        if method == "exit":
            if is_request:
                self._send(error_response(request_id, -32600, "Invalid Request"))
                return
            self.exit_requested = True
            self.exit_code = 0 if self.shutdown else 1
            return

        if self.shutdown:
            if is_request:
                self._send(error_response(request_id, -32600, "Invalid Request"))
            return

        if method == "initialize":
            if not is_request:
                return
            if self.initialized:
                self._send(error_response(request_id, -32600, "Invalid Request"))
                return
            self.initialized = True
            self._send(response(request_id, {"serverInfo": SERVER_INFO, "capabilities": CAPABILITIES}))
            return

        if method == "initialized":
            if self.initialized and not is_request:
                self.client_initialized = True
            return

        if method == "shutdown":
            if not is_request:
                return
            if not self._ready(request_id):
                return
            self.shutdown = True
            self._send(response(request_id, None))
            return

        if not self._ready(request_id if is_request else None):
            return

        try:
            if method in {
                "textDocument/didOpen",
                "textDocument/didChange",
                "textDocument/didClose",
            }:
                if is_request:
                    self._send(error_response(request_id, -32600, "Invalid Request"))
                    return
                self._document_notification(method, params)
                return
            if method == "textDocument/documentSymbol":
                uri = _document_uri(params)
                result = self.service.symbols(uri)
            elif method == "textDocument/hover":
                uri = _document_uri(params)
                line, character = _position(params)
                result = self.service.hover(uri, line, character)
            elif method == "textDocument/definition":
                uri = _document_uri(params)
                line, character = _position(params)
                result = self.service.definition(uri, line, character)
            else:
                if is_request:
                    self._send(error_response(request_id, -32601, "Method not found"))
                return
            if is_request:
                self._send(response(request_id, result))
        except ValueError:
            if is_request:
                self._send(error_response(request_id, -32602, "Invalid params"))
        except Exception:
            # Never send Python exception text, paths, or traceback to the client.
            self._log("language service request failed")
            if is_request:
                self._send(error_response(request_id, -32603, "Internal error"))

    def _ready(self, request_id: object | None) -> bool:
        if self.initialized and self.client_initialized:
            return True
        if request_id is not None:
            self._send(error_response(request_id, -32002, "Server not initialized"))
        return False

    def _document_notification(self, method: str, params: dict[str, object]) -> None:
        text_document = params.get("textDocument")
        if not isinstance(text_document, dict):
            self._log("ignored malformed document notification")
            return
        uri = text_document.get("uri")
        if not isinstance(uri, str):
            self._log("ignored malformed document URI")
            return

        if method == "textDocument/didOpen":
            language_id = text_document.get("languageId")
            version = text_document.get("version")
            text = text_document.get("text")
            if not isinstance(language_id, str) or not _valid_version(version) or not isinstance(text, str):
                self._log("ignored malformed didOpen payload")
                return
            try:
                document = self.service.open_document(uri, language_id, version, text)
            except ValueError as error:
                self._publish_one(uri, [_protocol_diagnostic(str(error))])
                return
            diagnostics = self.service.analyze_open_documents()
            self._publish(diagnostics)
            return

        if method == "textDocument/didChange":
            version = text_document.get("version")
            changes = params.get("contentChanges")
            if not _valid_version(version) or not isinstance(changes, list) or len(changes) != 1:
                self._log("ignored didChange without one full-text change")
                return
            change = changes[0]
            if not isinstance(change, dict) or "range" in change or "rangeLength" in change or not isinstance(change.get("text"), str):
                self._log("ignored ranged or malformed didChange")
                return
            try:
                self.service.change_document(uri, version, change["text"])
            except ValueError:
                # Stale versions and unknown documents cannot replace current overlays.
                self._log("ignored stale or unknown didChange")
                return
            self._publish(self.service.analyze_open_documents())
            return

        closed = self.service.close_document(uri)
        if closed is None:
            return
        self._publish_one(closed.uri, [])
        self._publish(self.service.analyze_open_documents())

    def _publish(self, diagnostics: dict[str, list[dict[str, object]]]) -> None:
        for uri in sorted(diagnostics):
            self._publish_one(uri, diagnostics[uri])

    def _publish_one(self, uri: str, diagnostics: list[dict[str, object]]) -> None:
        self._send({"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics", "params": {"uri": uri, "diagnostics": diagnostics}})

    def _send(self, message: dict[str, object]) -> None:
        try:
            self.output.write(encode_message(message))
            self.output.flush()
        except OSError:
            self.exit_requested = True
            self.exit_code = 1

    def _log(self, message: str) -> None:
        try:
            self.error_stream.write(message + "\n")
            self.error_stream.flush()
        except Exception:
            pass


def _safe_id(value: object) -> object:
    return value if _valid_id(value) else None


def _valid_id(value: object) -> bool:
    return value is None or (isinstance(value, str)) or (isinstance(value, int) and not isinstance(value, bool))


def _valid_version(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _document_uri(params: dict[str, object]) -> str:
    text_document = params.get("textDocument")
    if not isinstance(text_document, dict) or not isinstance(text_document.get("uri"), str):
        raise ValueError("invalid textDocument")
    uri = text_document["uri"]
    # Validate local file URI without reading from disk.
    path_from_file_uri(uri)
    return uri


def _position(params: dict[str, object]) -> tuple[int, int]:
    position = params.get("position")
    if not isinstance(position, dict):
        raise ValueError("invalid position")
    line = position.get("line")
    character = position.get("character")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (line, character)):
        raise ValueError("invalid position")
    return line, character


def _protocol_diagnostic(message: str) -> dict[str, object]:
    return {
        "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}},
        "severity": 1,
        "code": "SRC001",
        "source": "lwt",
        "message": message,
    }


def main() -> int:
    return LspServer(sys.stdin.buffer, sys.stdout.buffer, sys.stderr).run()


if __name__ == "__main__":
    raise SystemExit(main())
