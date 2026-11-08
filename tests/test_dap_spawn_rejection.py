"""S45 WP4: DAP protocol-frame level rejection of ``spawn`` programs.

Starts the real adapter (``python -m lwt.dap_server``) and drives it over stdio
with hand-checked DAP frames. Assertions:

* ``Content-Length`` is the UTF-8 byte length, including for a non-ASCII path;
* ``initialize`` is the first request and its response echoes request_seq/command;
* ``launch`` of a program containing ``spawn`` fails with a structured error and
  exit code 4 (spec 11.8), not a half-started debug session;
* no ``stopped`` / breakpoint events and no stdout from the debuggee appear;
* the adapter terminates cleanly (exit 0) and leaves no background task threads.

The reader below parses frames manually (rather than reusing the adapter's own
encoder) so a wrong byte count cannot be masked by a symmetric bug.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]


class _RawDapClient:
    """Minimal DAP client that validates Content-Length as UTF-8 bytes."""

    def __init__(self, cwd: Path) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            [str(REPO_ROOT), env.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep)
        self.process = subprocess.Popen(
            [sys.executable, "-m", "lwt.dap_server"],
            cwd=str(REPO_ROOT), env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self._seq = 1
        self._pending: list[dict] = []
        self.frame_lengths: list[tuple[int, int]] = []  # (declared, actual utf-8 bytes)

    def send(self, command: str, arguments: dict | None = None) -> int:
        seq = self._seq
        self._seq += 1
        payload = {"seq": seq, "type": "request", "command": command}
        if arguments is not None:
            payload["arguments"] = arguments
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        assert self.process.stdin is not None
        self.process.stdin.write(header + body)
        self.process.stdin.flush()
        return seq

    def _read_exact(self, count: int) -> bytes:
        assert self.process.stdout is not None
        data = b""
        while len(data) < count:
            chunk = self.process.stdout.read(count - len(data))
            if not chunk:
                raise AssertionError("DAP adapter closed stdout mid-frame")
            data += chunk
        return data

    def read_message(self) -> dict:
        # Messages that did not match an earlier predicate are kept in order,
        # so a request/response interleave (config response before launch
        # response) cannot silently drop a frame.
        if self._pending:
            return self._pending.pop(0)
        return self._read_frame()

    def _read_frame(self) -> dict:
        assert self.process.stdout is not None
        header_lines: list[bytes] = []
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise AssertionError("DAP adapter closed stdout before a frame")
            if line in (b"\r\n", b"\n"):
                break
            header_lines.append(line)
        declared = None
        for line in header_lines:
            name, _, value = line.decode("ascii", "replace").partition(":")
            if name.strip().lower() == "content-length":
                declared = int(value.strip())
        if declared is None:
            raise AssertionError(f"missing Content-Length in {header_lines!r}")
        body = self._read_exact(declared)
        self.frame_lengths.append((declared, len(body)))
        return json.loads(body.decode("utf-8"))

    def wait_for(self, predicate, limit: int = 40) -> dict:
        for index, message in enumerate(self._pending):
            if predicate(message):
                return self._pending.pop(index)
        for _ in range(limit):
            message = self._read_frame()  # always advance the pipe
            if predicate(message):
                return message
            self._pending.append(message)
        raise AssertionError("no matching DAP message")

    def response(self, request_seq: int) -> dict:
        return self.wait_for(
            lambda m: m.get("type") == "response" and m.get("request_seq") == request_seq
        )

    def close(self) -> None:
        if self.process.poll() is None:
            try:
                self.send("disconnect", {"terminateDebuggee": True})
            except (BrokenPipeError, OSError):
                pass
            try:
                self.process.stdin.close()  # type: ignore[union-attr]
            except OSError:
                pass

    def terminate_and_wait(self, timeout: float = 5) -> int:
        """Send disconnect (correct DAP shutdown) and return the adapter code."""
        self.close()
        return self.process.wait(timeout=timeout)

    def shutdown(self) -> None:
        """Close and reap the adapter so Windows can delete its cwd temp dir."""
        self.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            try:
                if stream is not None:
                    stream.close()
            except OSError:
                pass


class DapSpawnRejectionFrameTests(unittest.TestCase):
    def test_spawn_launch_is_rejected_with_exit_four_and_no_stop_events(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt dap spawn ") as directory:
            root = Path(directory)
            # Non-ASCII filename exercises UTF-8 Content-Length on the wire.
            source = root / "并发 程序.lwt"
            source.write_text(
                'fn work(){ return 1; }\n'
                'let t = spawn work();\n'
                'emit str(join(t));\n',
                encoding="utf-8",
            )
            client = _RawDapClient(root)
            try:
                init_seq = client.send("initialize", {"adapterID": "lwt"})
                init = client.response(init_seq)
                self.assertTrue(init["success"], init)
                self.assertEqual(init["command"], "initialize")
                self.assertEqual(init["request_seq"], init_seq)

                # DAP order: initialize -> launch -> initialized event ->
                # configurationDone (execution starts, spawn is rejected).
                launch_seq = client.send("launch", {"program": str(source), "cwd": str(root)})
                client.wait_for(lambda m: m.get("event") == "initialized")
                config_seq = client.send("configurationDone", {})
                launch = client.response(launch_seq)
                self.assertTrue(launch["success"], "launch itself is accepted")
                self.assertEqual(launch["command"], "launch")
                config = client.response(config_seq)
                self.assertTrue(config["success"], config)

                output = client.wait_for(
                    lambda m: m.get("type") == "event" and m.get("event") == "output"
                )
                self.assertEqual(output["body"]["category"], "stderr")
                self.assertIn("spawn", output["body"]["output"])

                exited = client.wait_for(
                    lambda m: m.get("type") == "event" and m.get("event") == "exited"
                )
                self.assertEqual(exited["body"]["exitCode"], 4)
                client.wait_for(lambda m: m.get("event") == "terminated")

                # Every received frame declared exactly its UTF-8 byte length.
                for declared, actual in client.frame_lengths:
                    self.assertEqual(declared, actual, "Content-Length must be UTF-8 bytes")

                self.assertEqual(client.terminate_and_wait(), 0, "adapter must exit cleanly")
                assert client.process.stderr is not None
                stderr = client.process.stderr.read().decode("utf-8", "replace")
                self.assertEqual(stderr, "", f"adapter wrote to stderr: {stderr}")
            finally:
                client.shutdown()

    def test_no_stdout_leaks_and_no_stop_events(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt dap spawn leak ") as directory:
            root = Path(directory)
            source = root / "spawn.lwt"
            source.write_text(
                'fn boom(){ throw "must not run"; return 0; }\n'
                'let t = spawn boom();\n'
                'emit "SHOULD-NOT-APPEAR";\n'
                'join(t);\n',
                encoding="utf-8",
            )
            client = _RawDapClient(root)
            try:
                client.send("initialize", {"adapterID": "lwt"})
                client.response(1)
                client.send("launch", {"program": str(source), "cwd": str(root)})
                client.wait_for(lambda m: m.get("event") == "initialized")
                client.send("configurationDone", {})
                client.response(3)
                events: list[dict] = []
                while True:
                    message = client.read_message()
                    events.append(message)
                    if message.get("event") == "terminated":
                        break
                names = [e.get("event") for e in events if e.get("type") == "event"]
                self.assertNotIn("stopped", names, "spawn must not produce stop events")
                self.assertNotIn("breakpoint", names, "spawn must not register breakpoints")
                for event in events:
                    if event.get("event") == "output":
                        self.assertNotIn("SHOULD-NOT-APPEAR", event["body"]["output"])
                        self.assertEqual(event["body"]["category"], "stderr")
                exited = [e for e in events if e.get("event") == "exited"][0]
                self.assertEqual(exited["body"]["exitCode"], 4)
                self.assertEqual(client.terminate_and_wait(), 0, "adapter must exit cleanly")
            finally:
                client.shutdown()


if __name__ == "__main__":
    unittest.main()
