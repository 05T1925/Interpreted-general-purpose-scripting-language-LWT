"""A minimal MCP server for LWT (JSON-RPC 2.0 over stdio).

Course chapter 4.3 describes MCP as the standard way to expose a tool to an
agent: ``initialize`` for the handshake, ``tools/list`` for capability discovery
and ``tools/call`` for invocation. MCP's stdio transport uses **newline
delimited JSON**, not LSP's ``Content-Length`` framing, so ``lwt/lsp_protocol.py``
is not reused here.

The three tools are thin wrappers around the public CLI (``python -m lwt``), so
the agent sees exactly what a human sees: exit code, stdout and stderr.

Run it with::

    python -m lwt.mcp_server

It is a separate entry point and does not change any existing CLI behaviour.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Callable

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "lwt"
SERVER_VERSION = "0.3.0"

TOOLS: tuple[dict[str, Any], ...] = (
    {
        "name": "lwt_check",
        "description": (
            "Statically check an LWT source file without executing it. Returns the "
            "same JSON document as 'python -m lwt --check --format=json'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to a .lwt file"},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "lwt_run",
        "description": (
            "Run an LWT program and return its stdout, stderr and exit code. "
            "Exit codes: 0 ok, 2 syntax/static, 3 runtime, 4 CLI/file."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to a .lwt file"},
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Program arguments placed after '--'",
                },
                "stdin": {"type": "string", "description": "Text piped to stdin"},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "lwt_profile",
        "description": (
            "Profile an LWT program and return a summary of the profile document "
            "(schema version, event count, coverage keys, exit code)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to a .lwt file"},
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Program arguments placed after '--'",
                },
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
)


class ToolError(Exception):
    """Raised when a tool call is malformed (JSON-RPC -32602)."""


def _require_path(arguments: dict[str, Any]) -> str:
    path = arguments.get("path")
    if not isinstance(path, str) or not path:
        raise ToolError("'path' must be a non-empty string")
    if not Path(path).exists():
        raise ToolError(f"file not found: {path}")
    return path


def _program_args(arguments: dict[str, Any]) -> list[str]:
    args = arguments.get("args", [])
    if not isinstance(args, list) or any(not isinstance(item, str) for item in args):
        raise ToolError("'args' must be an array of strings")
    return list(args)


def _base_command() -> list[str]:
    # ``python -m lwt`` keeps the agent on the same public surface a human uses.
    return [sys.executable, "-m", "lwt"]


def _text_result(text: str, *, is_error: bool) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def call_lwt_check(arguments: dict[str, Any]) -> dict[str, Any]:
    path = _require_path(arguments)
    completed = subprocess.run(
        _base_command() + ["--check", "--format=json", path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, check=False,
    )
    document = completed.stdout.decode("utf-8", "replace").strip()
    return _text_result(document or completed.stderr.decode("utf-8", "replace").strip(),
                        is_error=completed.returncode != 0)


def call_lwt_run(arguments: dict[str, Any]) -> dict[str, Any]:
    path = _require_path(arguments)
    command = _base_command() + [path]
    extra = _program_args(arguments)
    if extra:
        command += ["--"] + extra
    stdin_text = arguments.get("stdin", "")
    if not isinstance(stdin_text, str):
        raise ToolError("'stdin' must be a string")
    completed = subprocess.run(
        command, input=stdin_text.encode("utf-8"),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, check=False,
    )
    payload = {
        "exit_code": completed.returncode,
        "stdout": completed.stdout.decode("utf-8", "replace"),
        "stderr": completed.stderr.decode("utf-8", "replace"),
        "command": command,
    }
    return _text_result(json.dumps(payload, ensure_ascii=False),
                        is_error=completed.returncode != 0)


def call_lwt_profile(arguments: dict[str, Any]) -> dict[str, Any]:
    path = _require_path(arguments)
    extra = _program_args(arguments)
    with tempfile.TemporaryDirectory(prefix="lwt-mcp-profile-") as temporary:
        target = Path(temporary) / "profile.json"
        command = _base_command() + ["--profile", str(target), path]
        if extra:
            command += ["--"] + extra
        completed = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=120, check=False,
        )
        if not target.exists():
            return _text_result(
                "profile was not produced; exit="
                f"{completed.returncode}; stderr={completed.stderr.decode('utf-8', 'replace')}",
                is_error=True,
            )
        document = json.loads(target.read_text(encoding="utf-8"))
        summary = {
            "exit_code": completed.returncode,
            "schema_version": document.get("schema_version"),
            "events": len(document.get("events", [])),
            "coverage_keys": sorted(document.get("coverage", {}))[:12],
            "modules": len(document.get("modules", [])),
        }
    return _text_result(json.dumps(summary, ensure_ascii=False),
                        is_error=completed.returncode != 0)


TOOL_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "lwt_check": call_lwt_check,
    "lwt_run": call_lwt_run,
    "lwt_profile": call_lwt_profile,
}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    """Return a JSON-RPC response, or None for notifications."""

    method = request.get("method")
    request_id = request.get("id")
    is_notification = "id" not in request

    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }
        return None if is_notification else {"jsonrpc": "2.0", "id": request_id, "result": result}

    if method in ("notifications/initialized", "notifications/cancelled"):
        return None

    if method == "tools/list":
        result = {"tools": [dict(tool) for tool in TOOLS]}
        return None if is_notification else {"jsonrpc": "2.0", "id": request_id, "result": result}

    if method == "tools/call":
        params = request.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        handler = TOOL_HANDLERS.get(name)
        if handler is None:
            return _error(request_id, -32602, f"unknown tool: {name!r}")
        try:
            result = handler(arguments)
        except ToolError as error:
            return _error(request_id, -32602, str(error))
        except subprocess.TimeoutExpired:
            return _error(request_id, -32603, f"tool {name} timed out")
        return None if is_notification else {"jsonrpc": "2.0", "id": request_id, "result": result}

    return _error(request_id, -32601, f"method not found: {method!r}")


def serve(stdin: Any = None, stdout: Any = None) -> None:
    """Read newline-delimited JSON-RPC from stdin and answer on stdout."""

    source = stdin or sys.stdin
    sink = stdout or sys.stdout
    for line in source:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as error:
            response = _error(None, -32700, f"parse error: {error}")
        else:
            response = handle_request(request)
        if response is not None:
            sink.write(json.dumps(response, ensure_ascii=False) + "\n")
            sink.flush()


def main() -> int:
    serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
