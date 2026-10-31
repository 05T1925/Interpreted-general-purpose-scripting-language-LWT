from __future__ import annotations

import io
from pathlib import Path
import queue
import tempfile
import threading
import unittest

from lwt.debugger_core import DebugAbort, DebugFrame, DebuggerController
from lwt.modules import load_module_graph
from lwt.runtime import execute


class _PauseQueue:
    def __init__(self) -> None:
        self.pauses: queue.Queue[tuple[str, DebugFrame, object]] = queue.Queue()

    def __call__(self, reason: str, frame: DebugFrame, statement: object) -> None:
        self.pauses.put((reason, frame, statement))


class DebuggerEngineTests(unittest.TestCase):
    def _make_controller(self, root: Path, source: Path, pause_queue: _PauseQueue):
        graph = load_module_graph(str(source), include_sources=True)
        controller = DebuggerController(
            graph,
            str(source),
            io.StringIO(),
            io.StringIO(),
            scripted=True,
            pause_handler=pause_queue,
        )
        return graph, controller

    @staticmethod
    def _start(graph, controller, output: io.TextIOBase):
        failures: list[BaseException] = []

        def run_program() -> None:
            try:
                execute(
                    graph.entry.program,
                    io.BytesIO(),
                    output,
                    module_graph=graph,
                    source_path=str(graph.entry.canonical_path),
                    debug_hook=controller,
                )
            except DebugAbort:
                return
            except BaseException as error:
                failures.append(error)

        controller.start()
        thread = threading.Thread(target=run_program, name="lwt-engine-test")
        thread.start()
        return thread, failures

    def _ensure_thread_stopped(
        self, controller: DebuggerController, thread: threading.Thread
    ) -> None:
        if thread.is_alive():
            controller.cancel()
            thread.join(timeout=2)
        self.assertFalse(thread.is_alive(), "debug execution thread leaked")

    def test_breakpoints_are_exact_per_source_and_replaced_as_a_batch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt dap engine ") as directory:
            root = Path(directory)
            source = root / "main λ.lwt"
            module = root / "worker lib.lwt"
            source.write_text('import "worker lib.lwt" as worker;\nlet value = 1;\nworker.work();\nemit value;\n', encoding="utf-8")
            module.write_text("fn work() {\n  emit 2;\n}\n", encoding="utf-8")
            pauses = _PauseQueue()
            graph, controller = self._make_controller(root, source, pauses)

            first = controller.set_breakpoints(str(source), [1, 99])
            self.assertEqual([item.status for item in first], ["unmapped", "unmapped"])
            replaced = controller.set_breakpoints(str(source), [2])
            self.assertEqual([item.status for item in replaced], ["verified"])
            module_breakpoint = controller.set_breakpoints(str(module), [2])
            self.assertEqual(module_breakpoint[0].status, "verified")
            cleared = controller.set_breakpoints(str(source), [])
            self.assertEqual(cleared, [])

            thread, failures = self._start(graph, controller, io.StringIO())
            self.addCleanup(self._ensure_thread_stopped, controller, thread)
            reason, frame, statement = pauses.pauses.get(timeout=2)
            self.assertEqual(reason, "breakpoint 4")
            self.assertEqual(frame.module_unit.canonical_path, module.resolve())
            self.assertEqual(statement.location.line, 2)
            controller.resume("continue")
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(failures, [])

    def test_step_in_and_step_out_keep_lwt_call_stack_and_scope(self) -> None:
        source_text = (
            "fn target(value) {\n"
            "  let local = value + 1;\n"
            "  return local;\n"
            "}\n"
            "let global = 4;\n"
            "let result = target(global);\n"
            "emit result;\n"
        )
        with tempfile.TemporaryDirectory(prefix="lwt dap step ") as directory:
            root = Path(directory)
            source = root / "main.lwt"
            source.write_text(source_text, encoding="utf-8")
            pauses = _PauseQueue()
            graph, controller = self._make_controller(root, source, pauses)
            breakpoint = controller.set_breakpoints(str(source), [6])[0]
            self.assertEqual(breakpoint.status, "verified")
            thread, failures = self._start(graph, controller, io.StringIO())
            self.addCleanup(self._ensure_thread_stopped, controller, thread)

            reason, entry_frame, _ = pauses.pauses.get(timeout=2)
            self.assertEqual(reason, "breakpoint 1")
            self.assertEqual(entry_frame.qualified_name, "<entry>")
            controller.resume("stepIn")

            reason, function_frame, statement = pauses.pauses.get(timeout=2)
            self.assertEqual(reason, "step")
            self.assertEqual(function_frame.qualified_name, "target")
            self.assertEqual(statement.location.line, 2)
            self.assertEqual([item.qualified_name for item in controller.frames()], ["target", "<entry>"])
            self.assertEqual(controller.locals_for_frame(function_frame)["value"], 4)
            controller.resume("stepOut")

            reason, caller_frame, statement = pauses.pauses.get(timeout=2)
            self.assertEqual(reason, "finish")
            self.assertEqual(caller_frame.qualified_name, "<entry>")
            self.assertEqual(statement.location.line, 7)
            controller.resume("continue")
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(failures, [])

    def test_next_steps_over_function_and_stops_in_caller(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt dap next ") as directory:
            root = Path(directory)
            source = root / "main.lwt"
            source.write_text(
                "fn f() {\n  emit 2;\n}\nlet before = 1;\nf();\nemit before;\n",
                encoding="utf-8",
            )
            pauses = _PauseQueue()
            graph, controller = self._make_controller(root, source, pauses)
            controller.set_breakpoints(str(source), [5])
            thread, failures = self._start(graph, controller, io.StringIO())
            self.addCleanup(self._ensure_thread_stopped, controller, thread)
            pauses.pauses.get(timeout=2)
            controller.resume("next")
            reason, frame, statement = pauses.pauses.get(timeout=2)
            self.assertEqual(reason, "next")
            self.assertEqual(frame.qualified_name, "<entry>")
            self.assertEqual(statement.location.line, 6)
            self.assertTrue(controller.is_paused)
            controller.resume("continue")
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(failures, [])

    def test_cancel_during_unbounded_loop_stops_at_next_statement_hook(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt dap terminate ") as directory:
            root = Path(directory)
            source = root / "loop.lwt"
            source.write_text("let i = 0;\nwhile (true) {\n  emit i;\n  i = i + 1;\n}\n", encoding="utf-8")
            pauses = _PauseQueue()
            graph, controller = self._make_controller(root, source, pauses)
            output = _CancelOnFirstWrite(controller)
            thread, failures = self._start(graph, controller, output)
            self.addCleanup(self._ensure_thread_stopped, controller, thread)
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive(), "unbounded loop did not honor cancellation")
            self.assertEqual(output.getvalue(), "0\n")
            self.assertEqual(failures, [])

    def test_cancel_wakes_program_paused_at_breakpoint(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lwt dap paused cancel ") as directory:
            root = Path(directory)
            source = root / "main.lwt"
            source.write_text("emit 1;\nemit 2;\n", encoding="utf-8")
            pauses = _PauseQueue()
            graph, controller = self._make_controller(root, source, pauses)
            controller.set_breakpoints(str(source), [1])
            thread, failures = self._start(graph, controller, io.StringIO())
            self.addCleanup(self._ensure_thread_stopped, controller, thread)
            pauses.pauses.get(timeout=2)
            controller.cancel()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(failures, [])


class _CancelOnFirstWrite(io.StringIO):
    def __init__(self, controller: DebuggerController) -> None:
        super().__init__()
        self.controller = controller
        self.cancelled = False

    def write(self, text: str) -> int:
        result = super().write(text)
        if not self.cancelled:
            self.cancelled = True
            self.controller.cancel()
        return result


if __name__ == "__main__":
    unittest.main()
