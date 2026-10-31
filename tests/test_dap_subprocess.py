from __future__ import annotations

import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from lwt.dap_protocol import DapProtocolError, DapReader, encode_message


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class _DapClient:
    def __init__(self, cwd: Path) -> None:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join(
            [str(REPOSITORY_ROOT), environment.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep)
        self.process = subprocess.Popen(
            [sys.executable, "-m", "lwt.dap_server"],
            cwd=REPOSITORY_ROOT,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        assert self.process.stderr is not None
        self._next_request_seq = 1
        self._messages: queue.Queue[dict[str, object] | BaseException | None] = queue.Queue()
        self._pending: list[dict[str, object]] = []
        self._stderr = bytearray()
        self._reader = threading.Thread(target=self._read_messages, daemon=True)
        self._stderr_reader = threading.Thread(target=self._read_stderr, daemon=True)
        self._reader.start()
        self._stderr_reader.start()

    def _read_messages(self) -> None:
        assert self.process.stdout is not None
        reader = DapReader(self.process.stdout)
        try:
            while True:
                message = reader.read_message()
                if message is None:
                    self._messages.put(None)
                    return
                self._messages.put(message)
        except (DapProtocolError, OSError) as error:
            self._messages.put(error)

    def _read_stderr(self) -> None:
        assert self.process.stderr is not None
        while True:
            chunk = self.process.stderr.read(4096)
            if not chunk:
                return
            self._stderr.extend(chunk)

    @property
    def stderr(self) -> str:
        return self._stderr.decode("utf-8", errors="replace")

    def send_request(self, command: str, arguments: dict[str, object] | None = None) -> int:
        assert self.process.stdin is not None
        request_seq = self._next_request_seq
        self._next_request_seq += 1
        request: dict[str, object] = {
            "seq": request_seq,
            "type": "request",
            "command": command,
        }
        if arguments is not None:
            request["arguments"] = arguments
        self.process.stdin.write(encode_message(request))
        self.process.stdin.flush()
        return request_seq

    def request(self, command: str, arguments: dict[str, object] | None = None) -> dict[str, object]:
        return self.response(self.send_request(command, arguments))

    def response(self, request_seq: int) -> dict[str, object]:
        return self.wait_for(
            lambda message: message.get("type") == "response"
            and message.get("request_seq") == request_seq
        )

    def event(self, name: str) -> dict[str, object]:
        return self.wait_for(
            lambda message: message.get("type") == "event" and message.get("event") == name
        )

    def wait_for(self, predicate, timeout: float = 5.0) -> dict[str, object]:
        for index, message in enumerate(self._pending):
            if predicate(message):
                return self._pending.pop(index)
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError("timed out waiting for the expected DAP message")
            try:
                item = self._messages.get(timeout=remaining)
            except queue.Empty:
                raise AssertionError("timed out waiting for the expected DAP message") from None
            if item is None:
                raise AssertionError("DAP adapter closed stdout before the expected message")
            if isinstance(item, BaseException):
                raise AssertionError(f"DAP adapter wrote invalid protocol stdout: {item}")
            if predicate(item):
                return item
            self._pending.append(item)

    def close(self) -> None:
        if self.process.poll() is None:
            try:
                self.send_request("disconnect", {"terminateDebuggee": True})
            except (BrokenPipeError, OSError):
                pass
            try:
                self.process.stdin.close()  # type: ignore[union-attr]
            except OSError:
                pass
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        self._reader.join(timeout=1)
        self._stderr_reader.join(timeout=1)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            if stream is not None and not stream.closed:
                stream.close()


class DapSubprocessTests(unittest.TestCase):
    def _start_launch(self, client: _DapClient, launch: dict[str, object]) -> int:
        initialized = client.request("initialize", {"adapterID": "lwt"})
        self.assertTrue(initialized["success"])
        capabilities = initialized["body"]
        self.assertTrue(capabilities["supportsConfigurationDoneRequest"])
        self.assertTrue(capabilities["supportsTerminateRequest"])
        self.assertTrue(capabilities["supportsLoadedSourcesRequest"])
        self.assertNotIn("supportsSetVariable", capabilities)
        self.assertNotIn("supportsEvaluateForHovers", capabilities)
        launch_seq = client.send_request("launch", launch)
        event = client.event("initialized")
        self.assertEqual(event.get("event"), "initialized")
        return launch_seq

    def test_real_dap_pause_inspection_and_continue_with_module_paths_and_io(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt DAP 项目 with spaces ") as directory:
            root = Path(directory)
            source = root / "主程序 λ.lwt"
            module = root / "helper 模块.lwt"
            stdin_file = root / "program input 雪.txt"
            source.write_text(
                'import "helper 模块.lwt" as helper;\n'
                "record Box { items };\n"
                'let globalBox = Box{items: [1, "雪"]};\n'
                "let cycle = [];\n"
                "push(cycle, cycle);\n"
                'attempt { fail("recoverable"); } recover (problem) {\n'
                "    helper.inspect(globalBox, problem);\n"
                "}\n"
                "emit args()[0];\n"
                "emit input();\n",
                encoding="utf-8",
            )
            module.write_text(
                "fn inspect(box, problem) {\n"
                "    let value = [box.items, problem];\n"
                '    emit "helper-hit";\n'
                "}\n",
                encoding="utf-8",
            )
            stdin_file.write_text("input λ\n", encoding="utf-8")
            client = _DapClient(root)
            try:
                launch_seq = self._start_launch(
                    client,
                    {
                        "program": str(source),
                        "cwd": str(root),
                        "args": ["argument with spaces ☃"],
                        "stdinFile": str(stdin_file),
                    },
                )
                unsupported = client.request("evaluate", {"expression": "globalBox"})
                self.assertFalse(unsupported["success"])
                self.assertIn("unsupported DAP request", unsupported["message"])
                breakpoints = client.request(
                    "setBreakpoints",
                    {
                        "source": {"name": module.name, "path": str(module)},
                        "breakpoints": [{"line": 2}, {"line": 99}],
                    },
                )
                self.assertTrue(breakpoints["success"])
                requested = breakpoints["body"]["breakpoints"]
                self.assertEqual([item["verified"] for item in requested], [True, False])

                replaced = client.request(
                    "setBreakpoints",
                    {
                        "source": {"name": module.name, "path": str(module)},
                        "breakpoints": [{"line": 2}],
                    },
                )
                self.assertEqual(len(replaced["body"]["breakpoints"]), 1)
                config_seq = client.send_request("configurationDone", {})
                self.assertTrue(client.response(config_seq)["success"])
                self.assertTrue(client.response(launch_seq)["success"])

                stopped = client.event("stopped")
                self.assertEqual(stopped["body"]["reason"], "breakpoint")
                self.assertEqual(stopped["body"]["threadId"], 1)
                threads = client.request("threads")
                self.assertEqual(threads["body"]["threads"], [{"id": 1, "name": "LWT program"}])
                stack = client.request("stackTrace", {"threadId": 1})
                frames = stack["body"]["stackFrames"]
                self.assertEqual(len(frames), 2)
                self.assertIn("helper 模块.lwt", frames[0]["source"]["path"])
                self.assertEqual(frames[0]["line"], 2)
                self.assertIn("主程序 λ.lwt", frames[1]["source"]["path"])

                scopes = client.request("scopes", {"frameId": frames[0]["id"]})
                local_scope = next(
                    item for item in scopes["body"]["scopes"] if item["name"] == "Locals"
                )
                locals_response = client.request(
                    "variables", {"variablesReference": local_scope["variablesReference"]}
                )
                variables = {item["name"]: item for item in locals_response["body"]["variables"]}
                self.assertIn("helper.inspect", frames[0]["name"])
                self.assertEqual(variables["problem"]["type"], "Error")
                self.assertEqual(variables["problem"]["variablesReference"] > 0, True)
                error_fields = client.request(
                    "variables",
                    {"variablesReference": variables["problem"]["variablesReference"]},
                )["body"]["variables"]
                self.assertEqual(
                    [item["name"] for item in error_fields],
                    ["category", "message", "source", "line", "column"],
                )
                self.assertEqual(next(item for item in error_fields if item["name"] == "message")["value"], '"recoverable"')
                box_children = client.request(
                    "variables",
                    {"variablesReference": variables["box"]["variablesReference"]},
                )["body"]["variables"]
                self.assertEqual(box_children[0]["name"], "items")
                array_children = client.request(
                    "variables",
                    {"variablesReference": box_children[0]["variablesReference"]},
                )["body"]["variables"]
                self.assertEqual([item["name"] for item in array_children], ["[0]", "[1]"])
                entry_scopes = client.request("scopes", {"frameId": frames[1]["id"]})
                global_scope = next(
                    item for item in entry_scopes["body"]["scopes"] if item["name"] == "Globals"
                )
                globals_response = client.request(
                    "variables", {"variablesReference": global_scope["variablesReference"]}
                )
                self.assertIn(
                    "globalBox",
                    {item["name"] for item in globals_response["body"]["variables"]},
                )
                cycle_variable = next(
                    item for item in globals_response["body"]["variables"] if item["name"] == "cycle"
                )
                cycle_child = client.request(
                    "variables", {"variablesReference": cycle_variable["variablesReference"]}
                )["body"]["variables"][0]
                self.assertEqual(cycle_child["value"], "<cycle>")
                self.assertEqual(cycle_child["variablesReference"], 0)

                stale_reference = local_scope["variablesReference"]
                stale_frame_id = frames[0]["id"]
                continue_seq = client.send_request("continue", {"threadId": 1})
                self.assertTrue(client.response(continue_seq)["success"])
                self.assertTrue(client.event("continued")["body"]["allThreadsContinued"])
                stale_variables = client.request(
                    "variables", {"variablesReference": stale_reference}
                )
                self.assertEqual(stale_variables["body"]["variables"], [])
                stale_scopes = client.request("scopes", {"frameId": stale_frame_id})
                self.assertEqual(stale_scopes["body"]["scopes"], [])

                output_chunks: list[str] = []
                while True:
                    message = client.wait_for(
                        lambda candidate: candidate.get("type") == "event"
                        and candidate.get("event") in {"output", "exited", "terminated"}
                    )
                    if message.get("event") == "output":
                        output_chunks.append(message["body"]["output"])
                    elif message.get("event") == "exited":
                        self.assertEqual(message["body"]["exitCode"], 0)
                    elif message.get("event") == "terminated":
                        break
                self.assertEqual("".join(output_chunks), "helper-hit\nargument with spaces ☃\ninput λ\n")
                self.assertNotIn("Traceback", client.stderr)
                disconnect_seq = client.send_request("disconnect", {"terminateDebuggee": True})
                self.assertTrue(client.response(disconnect_seq)["success"])
                self.assertEqual(client.process.wait(timeout=3), 0)
            finally:
                client.close()

    def test_runtime_error_is_an_output_event_with_real_exit_code(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt dap runtime error ") as directory:
            root = Path(directory)
            source = root / "failure.lwt"
            source.write_text('emit "before";\nemit input();\nfail("boom");\n', encoding="utf-8")
            client = _DapClient(root)
            try:
                launch_seq = self._start_launch(client, {"program": str(source), "cwd": str(root)})
                config_seq = client.send_request("configurationDone", {})
                self.assertTrue(client.response(config_seq)["success"])
                self.assertTrue(client.response(launch_seq)["success"])
                chunks: list[str] = []
                exit_code = None
                terminated = False
                while not terminated:
                    message = client.wait_for(
                        lambda candidate: candidate.get("type") == "event"
                        and candidate.get("event") in {"output", "exited", "terminated"}
                    )
                    if message["event"] == "output":
                        chunks.append(message["body"]["output"])
                    elif message["event"] == "exited":
                        exit_code = message["body"]["exitCode"]
                    else:
                        terminated = True
                self.assertEqual(exit_code, 3)
                self.assertEqual(chunks[:2], ["before\n", "null\n"])
                self.assertTrue(chunks[2].endswith("RuntimeError: boom\n"), chunks[2])
                self.assertNotIn("Traceback", client.stderr)
                disconnect_seq = client.send_request("disconnect", {"terminateDebuggee": True})
                self.assertTrue(client.response(disconnect_seq)["success"])
                self.assertEqual(client.process.wait(timeout=3), 0)
            finally:
                client.close()

    def test_real_dap_step_in_next_and_step_out_use_standard_stop_events(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt dap stepping ") as directory:
            root = Path(directory)
            source = root / "steps.lwt"
            source.write_text(
                "fn inner(value) {\n"
                "  let local = value + 1;\n"
                "  return local;\n"
                "}\n"
                "fn outer(value) {\n"
                "  let result = inner(value);\n"
                "  return result;\n"
                "}\n"
                "let answer = outer(4);\n"
                "emit answer;\n",
                encoding="utf-8",
            )
            client = _DapClient(root)
            try:
                launch_seq = self._start_launch(
                    client, {"program": str(source), "cwd": str(root)}
                )
                breakpoints = client.request(
                    "setBreakpoints",
                    {
                        "source": {"name": source.name, "path": str(source)},
                        "breakpoints": [{"line": 9}],
                    },
                )
                self.assertTrue(breakpoints["body"]["breakpoints"][0]["verified"])
                config_seq = client.send_request("configurationDone", {})
                self.assertTrue(client.response(config_seq)["success"])
                self.assertTrue(client.response(launch_seq)["success"])
                self.assertEqual(client.event("stopped")["body"]["reason"], "breakpoint")

                step_in = client.send_request("stepIn", {"threadId": 1})
                self.assertTrue(client.response(step_in)["success"])
                self.assertEqual(client.event("continued")["event"], "continued")
                step_in_stop = client.event("stopped")
                self.assertEqual(step_in_stop["body"]["reason"], "step")
                stack = client.request("stackTrace", {"threadId": 1})["body"]["stackFrames"]
                self.assertEqual(stack[0]["name"], "outer")
                self.assertEqual(stack[0]["line"], 6)

                next_step = client.send_request("next", {"threadId": 1})
                self.assertTrue(client.response(next_step)["success"])
                self.assertEqual(client.event("continued")["event"], "continued")
                next_stop = client.event("stopped")
                self.assertEqual(next_stop["body"]["reason"], "step")
                stack = client.request("stackTrace", {"threadId": 1})["body"]["stackFrames"]
                self.assertEqual(stack[0]["name"], "outer")
                self.assertEqual(stack[0]["line"], 7)

                step_out = client.send_request("stepOut", {"threadId": 1})
                self.assertTrue(client.response(step_out)["success"])
                self.assertEqual(client.event("continued")["event"], "continued")
                step_out_stop = client.event("stopped")
                self.assertEqual(step_out_stop["body"]["reason"], "step")
                stack = client.request("stackTrace", {"threadId": 1})["body"]["stackFrames"]
                self.assertEqual(stack[0]["name"], "<entry>")
                self.assertEqual(stack[0]["line"], 10)

                continued = client.send_request("continue", {"threadId": 1})
                self.assertTrue(client.response(continued)["success"])
                self.assertEqual(client.event("continued")["event"], "continued")
                chunks: list[str] = []
                while True:
                    message = client.wait_for(
                        lambda candidate: candidate.get("type") == "event"
                        and candidate.get("event") in {"output", "exited", "terminated"}
                    )
                    if message["event"] == "output":
                        chunks.append(message["body"]["output"])
                    elif message["event"] == "exited":
                        self.assertEqual(message["body"]["exitCode"], 0)
                    else:
                        break
                self.assertEqual("".join(chunks), "5\n")
                disconnect_seq = client.send_request(
                    "disconnect", {"terminateDebuggee": True}
                )
                self.assertTrue(client.response(disconnect_seq)["success"])
                self.assertEqual(client.process.wait(timeout=3), 0)
            finally:
                client.close()

    def test_recursive_stack_and_block_shadowed_locals_are_inspectable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt dap recursion ") as directory:
            root = Path(directory)
            source = root / "recursive.lwt"
            source.write_text(
                "fn descend(value) {\n"
                "  when (value > 0) {\n"
                "    let value = value - 1;\n"
                "    descend(value);\n"
                "  }\n"
                "}\n"
                "descend(2);\n"
                'emit "done";\n',
                encoding="utf-8",
            )
            client = _DapClient(root)
            try:
                launch_seq = self._start_launch(
                    client, {"program": str(source), "cwd": str(root)}
                )
                breakpoints = client.request(
                    "setBreakpoints",
                    {
                        "source": {"name": source.name, "path": str(source)},
                        "breakpoints": [{"line": 4}],
                    },
                )
                self.assertTrue(breakpoints["body"]["breakpoints"][0]["verified"])
                config_seq = client.send_request("configurationDone", {})
                self.assertTrue(client.response(config_seq)["success"])
                self.assertTrue(client.response(launch_seq)["success"])
                client.event("stopped")

                continue_seq = client.send_request("continue", {"threadId": 1})
                self.assertTrue(client.response(continue_seq)["success"])
                client.event("continued")
                client.event("stopped")
                frames = client.request("stackTrace", {"threadId": 1})["body"]["stackFrames"]
                self.assertEqual(len(frames), 3)
                self.assertEqual([frame["name"] for frame in frames[:2]], ["descend", "descend"])

                def local_value(frame_id: int) -> str:
                    scopes = client.request("scopes", {"frameId": frame_id})["body"]["scopes"]
                    locals_scope = next(scope for scope in scopes if scope["name"] == "Locals")
                    variables = client.request(
                        "variables",
                        {"variablesReference": locals_scope["variablesReference"]},
                    )["body"]["variables"]
                    binding = next(item for item in variables if item["name"] == "value")
                    return binding["value"]

                self.assertEqual(local_value(frames[0]["id"]), "0")
                self.assertEqual(local_value(frames[1]["id"]), "1")

                continue_seq = client.send_request("continue", {"threadId": 1})
                self.assertTrue(client.response(continue_seq)["success"])
                client.event("continued")
                output = client.event("output")
                self.assertEqual(output["body"]["output"], "done\n")
                self.assertEqual(client.event("exited")["body"]["exitCode"], 0)
                client.event("terminated")
                disconnect_seq = client.send_request(
                    "disconnect", {"terminateDebuggee": True}
                )
                self.assertTrue(client.response(disconnect_seq)["success"])
                self.assertEqual(client.process.wait(timeout=3), 0)
            finally:
                client.close()

    def test_preflight_syntax_error_is_reported_with_exit_code_two(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt dap syntax error ") as directory:
            root = Path(directory)
            source = root / "invalid source.lwt"
            source.write_text("emit ;\n", encoding="utf-8")
            client = _DapClient(root)
            try:
                initialized = client.request("initialize", {"adapterID": "lwt"})
                self.assertTrue(initialized["success"])
                launch_seq = client.send_request(
                    "launch", {"program": str(source), "cwd": str(root)}
                )
                launch_response = client.response(launch_seq)
                self.assertFalse(launch_response["success"])
                self.assertIn("SyntaxError", launch_response["message"])
                output = client.event("output")
                self.assertEqual(output["body"]["category"], "stderr")
                self.assertIn("SyntaxError", output["body"]["output"])
                exited = client.event("exited")
                self.assertEqual(exited["body"]["exitCode"], 2)
                self.assertEqual(client.event("terminated")["event"], "terminated")
                self.assertEqual(client.process.wait(timeout=3), 0)
                self.assertEqual(client.stderr, "")
            finally:
                client.close()

    def test_missing_source_is_a_file_error_with_exit_code_four(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt dap missing source ") as directory:
            root = Path(directory)
            source = root / "missing.lwt"
            client = _DapClient(root)
            try:
                initialized = client.request("initialize", {"adapterID": "lwt"})
                self.assertTrue(initialized["success"])
                launch_seq = client.send_request(
                    "launch", {"program": str(source), "cwd": str(root)}
                )
                launch_response = client.response(launch_seq)
                self.assertFalse(launch_response["success"])
                self.assertIn("FileError", launch_response["message"])
                self.assertEqual(client.event("output")["body"]["category"], "stderr")
                self.assertEqual(client.event("exited")["body"]["exitCode"], 4)
                self.assertEqual(client.event("terminated")["event"], "terminated")
                self.assertEqual(client.process.wait(timeout=3), 0)
                self.assertEqual(client.stderr, "")
            finally:
                client.close()

    def test_large_program_output_is_chunked_into_valid_dap_frames(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt dap large output ") as directory:
            root = Path(directory)
            source = root / "large output.lwt"
            expected = "x" * (512 * 1024 + 37)
            source.write_text(f'emit "{expected}";\n', encoding="utf-8")
            client = _DapClient(root)
            try:
                launch_seq = self._start_launch(
                    client, {"program": str(source), "cwd": str(root)}
                )
                config_seq = client.send_request("configurationDone", {})
                self.assertTrue(client.response(config_seq)["success"])
                self.assertTrue(client.response(launch_seq)["success"])
                chunks: list[str] = []
                while True:
                    message = client.wait_for(
                        lambda candidate: candidate.get("type") == "event"
                        and candidate.get("event") in {"output", "terminated"}
                    )
                    if message["event"] == "terminated":
                        break
                    chunk = message["body"]["output"]
                    self.assertLessEqual(len(chunk.encode("utf-8")), 512 * 1024)
                    chunks.append(chunk)
                self.assertGreater(len(chunks), 1)
                self.assertEqual("".join(chunks), expected + "\n")
                disconnect_seq = client.send_request(
                    "disconnect", {"terminateDebuggee": True}
                )
                self.assertTrue(client.response(disconnect_seq)["success"])
                self.assertEqual(client.process.wait(timeout=3), 0)
            finally:
                client.close()

    def test_terminate_during_unbounded_loop_uses_runtime_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt dap loop cancel ") as directory:
            root = Path(directory)
            source = root / "loop.lwt"
            source.write_text("let i = 0;\nwhile (true) { i = i + 1; }\n", encoding="utf-8")
            client = _DapClient(root)
            try:
                launch_seq = self._start_launch(client, {"program": str(source), "cwd": str(root)})
                config_seq = client.send_request("configurationDone", {})
                self.assertTrue(client.response(config_seq)["success"])
                self.assertTrue(client.response(launch_seq)["success"])
                terminate_seq = client.send_request("terminate", {})
                self.assertTrue(client.response(terminate_seq)["success"])
                exit_event = client.event("exited")
                self.assertEqual(exit_event["body"]["exitCode"], 1)
                ended = client.event("terminated")
                self.assertEqual(ended["event"], "terminated")
                disconnect_seq = client.send_request("disconnect", {"terminateDebuggee": True})
                self.assertTrue(client.response(disconnect_seq)["success"])
                self.assertEqual(client.process.wait(timeout=3), 0)
                self.assertNotIn("Traceback", client.stderr)
            finally:
                client.close()

    def test_malformed_protocol_is_reported_only_on_stderr_and_exits(self) -> None:
        process = subprocess.Popen(
            [sys.executable, "-m", "lwt.dap_server"],
            cwd=REPOSITORY_ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        assert process.stdin is not None
        assert process.stdout is not None
        assert process.stderr is not None
        process.stdin.write(b"Content-Length: nope\r\n\r\n")
        process.stdin.close()
        stdout = process.stdout.read()
        stderr = process.stderr.read()
        process.wait(timeout=3)
        process.stdout.close()
        process.stderr.close()
        self.assertEqual(process.returncode, 1)
        self.assertEqual(stdout, b"")
        self.assertIn(b"protocol error", stderr)
        self.assertNotIn(b"Traceback", stderr)


if __name__ == "__main__":
    unittest.main()
