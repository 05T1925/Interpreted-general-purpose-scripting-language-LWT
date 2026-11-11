"""Protocol-level tests for the minimal MCP server (stdio JSON-RPC 2.0).

These tests speak the wire format to a real subprocess; they do not import the
handler functions, so framing, ordering and error shapes are covered too.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELLO = ROOT / "examples" / "guide" / "hello.lwt"
BAD_CALL = ROOT / "tests" / "cases" / "concurrency" / "check-spawn-undefined.lwt"


def _session(requests: list[dict]) -> list[dict]:
    payload = "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in requests)
    completed = subprocess.run(
        [sys.executable, "-m", "lwt.mcp_server"],
        input=payload.encode("utf-8"),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=ROOT, timeout=180, check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"mcp server exited {completed.returncode}: {completed.stderr.decode('utf-8', 'replace')}"
        )
    return [json.loads(line) for line in completed.stdout.decode("utf-8").splitlines() if line.strip()]


def _call(name: str, arguments: dict, request_id: int = 2) -> dict:
    return {
        "jsonrpc": "2.0", "id": request_id, "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }


class McpHandshakeTests(unittest.TestCase):
    def test_initialize_returns_protocol_and_tool_capability(self) -> None:
        (response,) = _session([{
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "test", "version": "0"}},
        }])
        result = response["result"]
        self.assertEqual(result["protocolVersion"], "2024-11-05")
        self.assertIn("tools", result["capabilities"])
        self.assertEqual(result["serverInfo"]["name"], "lwt")

    def test_tools_list_exposes_exactly_three_tools(self) -> None:
        (response,) = _session([{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}])
        tools = response["result"]["tools"]
        self.assertEqual([tool["name"] for tool in tools],
                         ["lwt_check", "lwt_run", "lwt_profile"])
        for tool in tools:
            self.assertEqual(tool["inputSchema"]["type"], "object")
            self.assertIn("path", tool["inputSchema"]["required"])


class McpToolCallTests(unittest.TestCase):
    def test_run_executes_a_real_program(self) -> None:
        (response,) = _session([_call("lwt_run", {"path": str(HELLO)})])
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(payload["exit_code"], 0)
        self.assertIn("hello, LWT", payload["stdout"])
        self.assertFalse(response["result"]["isError"])

    def test_check_reports_a_static_diagnostic(self) -> None:
        (response,) = _session([_call("lwt_check", {"path": str(BAD_CALL)})])
        result = response["result"]
        self.assertTrue(result["isError"], "a static diagnostic must set isError")
        document = json.loads(result["content"][0]["text"])
        self.assertFalse(document["ok"])
        self.assertEqual(document["diagnostics"][0]["code"], "E-SPAWN-001")

    def test_profile_returns_a_summary(self) -> None:
        (response,) = _session([_call("lwt_profile", {"path": str(HELLO)})])
        summary = json.loads(response["result"]["content"][0]["text"])
        self.assertGreaterEqual(summary["schema_version"], 1)
        self.assertGreater(summary["events"], 0)
        self.assertEqual(summary["exit_code"], 0)

    def test_unknown_tool_is_a_jsonrpc_error(self) -> None:
        (response,) = _session([_call("lwt_nope", {"path": str(HELLO)})])
        self.assertEqual(response["error"]["code"], -32602)
        self.assertIn("unknown tool", response["error"]["message"])

    def test_unknown_method_is_a_jsonrpc_error(self) -> None:
        (response,) = _session([{"jsonrpc": "2.0", "id": 9, "method": "tools/nope"}])
        self.assertEqual(response["error"]["code"], -32601)

    def test_missing_file_is_reported_as_a_tool_error(self) -> None:
        (response,) = _session([_call("lwt_run", {"path": "does/not/exist.lwt"})])
        self.assertEqual(response["error"]["code"], -32602)
        self.assertIn("file not found", response["error"]["message"])


if __name__ == "__main__":
    unittest.main()
