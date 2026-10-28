"""Real Tk widget/event-loop integration coverage for the shipped GUI apps."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
import json
import threading
import time
import tempfile
import unittest
from unittest.mock import patch

try:
    import tkinter as tk
except ModuleNotFoundError as error:
    tk = None
    TK_IMPORT_ERROR = str(error)
else:
    TK_IMPORT_ERROR = None

if tk is not None:
    from app.language_lab_core import EXAMPLES, load_source, run_example
    from app.language_lab_ui import LanguageLabApp
    from app.log_detective_core import DEFAULT_LOG
    from app.log_detective_ui import LogDetectiveApp
    from app.snake_game_core import Direction, GameStatus
    from app.snake_game_ui import SnakeGameApp


def _destroy_root(root: tk.Tk) -> None:
    try:
        if root.winfo_exists():
            root.destroy()
    except tk.TclError:
        pass


def _invoke_window_close(root: tk.Tk) -> None:
    """Invoke the command registered for a real WM_DELETE_WINDOW protocol."""

    command = root.tk.call("wm", "protocol", root._w, "WM_DELETE_WINDOW")
    if command:
        root.tk.call(command)


def _walk_widgets(widget: tk.Misc):
    for child in widget.winfo_children():
        yield child
        yield from _walk_widgets(child)


class TkIntegrationCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._tk_unavailable_reason = None
        if tk is None:
            cls._tk_unavailable_reason = f"Tkinter unavailable: {TK_IMPORT_ERROR}"
            return
        try:
            probe = tk.Tk()
            probe.withdraw()
            probe.update_idletasks()
            probe.destroy()
        except tk.TclError as error:
            cls._tk_unavailable_reason = f"Tk display unavailable: {error}"

    def setUp(self) -> None:
        if self._tk_unavailable_reason:
            self.skipTest(self._tk_unavailable_reason)

    def make_root(self) -> tk.Tk:
        root = tk.Tk()
        root.withdraw()
        root.update_idletasks()
        self.addCleanup(_destroy_root, root)
        return root

    def pump_until(
        self,
        root: tk.Tk,
        predicate,
        *,
        timeout: float = 12.0,
        description: str = "Tk callback",
    ) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            root.update()
            if predicate():
                root.update_idletasks()
                return
            threading.Event().wait(0.002)
        self.fail(f"timed out waiting for {description}")


class LanguageLabTkIntegrationTests(TkIntegrationCase):
    def make_app(self, root: tk.Tk, **kwargs) -> LanguageLabApp:
        app = LanguageLabApp(root, **kwargs)
        self.addCleanup(lambda: app.close() if not app.closing else None)
        return app

    def select_example(self, app: LanguageLabApp, root: tk.Tk, example_id: str) -> None:
        index = next(i for i, example in enumerate(EXAMPLES) if example.id == example_id)
        app.example_picker.current(index)
        app.example_picker.event_generate("<<ComboboxSelected>>", when="now")
        root.update()

    def run_example_from_controls(
        self,
        app: LanguageLabApp,
        root: tk.Tk,
        example_id: str,
        *,
        choice: str | None = None,
    ) -> None:
        self.select_example(app, root, example_id)
        example = next(item for item in EXAMPLES if item.id == example_id)
        selected = choice or example.prediction.correct_option
        radio = next(button for button in app.prediction_buttons if button.cget("text") == selected)
        radio.invoke()
        app.submit_button.invoke()
        self.assertTrue(app.session.prediction_submitted)
        self.assertEqual(str(app.run_button.cget("state")), "normal")
        app.run_button.invoke()
        self.assertTrue(app.busy)
        self.assertEqual(str(app.run_button.cget("state")), "disabled")
        self.pump_until(
            root,
            lambda: not app.busy and (app.session.result is not None or app.session.error is not None),
            description=f"{example_id} CLI result",
        )

    def test_real_combobox_events_switch_all_topics_and_keep_source_read_only(self) -> None:
        root = self.make_root()
        app = self.make_app(root)
        root.update()

        self.assertEqual(tuple(app.example_picker.cget("values")), tuple(item.title for item in EXAMPLES))
        self.assertEqual(app.source_text.cget("state"), "disabled")
        for example in EXAMPLES:
            with self.subTest(topic=example.id):
                self.select_example(app, root, example.id)
                selected, source = load_source(example.id)
                self.assertEqual(app.session.selected_id, example.id)
                self.assertEqual(app.example_var.get(), selected.title)
                self.assertEqual(app.question_var.get(), selected.prediction.prompt)
                self.assertEqual(app.spec_var.get(), selected.spec_reference)
                self.assertEqual(app.source_text.get("1.0", "end-1c"), source)
                self.assertEqual(app.source_text.cget("state"), "disabled")
                before = app.source_text.get("1.0", "end-1c")
                app.source_text.insert("end", "must stay read-only")
                self.assertEqual(app.source_text.get("1.0", "end-1c"), before)

        self.select_example(app, root, "control-flow")
        self.assertEqual(str(app.run_button.cget("state")), "disabled")
        app.run_button.invoke()
        self.assertIsNone(app.session.pending)
        self.assertIsNone(app.session.result)
        self.assertIn("未答", app.status_var.get())

    def test_real_buttons_run_success_stdin_and_expected_runtime_error_cli_cases(self) -> None:
        root = self.make_root()
        app = self.make_app(root)
        root.update()

        functions = next(item for item in EXAMPLES if item.id == "functions")
        wrong = next(option for option in functions.prediction.options if option != functions.prediction.correct_option)
        self.run_example_from_controls(app, root, "functions", choice=wrong)
        result = app.session.result
        self.assertIsNotNone(result)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "120\n")
        self.assertEqual(result.stderr, "")
        self.assertIn("预测不正确", app.prediction_feedback_var.get())
        self.assertIn("CLI 结果：成功，符合 stdout 与退出码预期", app.details_text.get("1.0", "end-1c"))
        self.assertIn("120\n", app.stdout_text.get("1.0", "end-1c"))

        app.reset_button.invoke()
        self.run_example_from_controls(app, root, "stdin")
        stdin_result = app.session.result
        self.assertEqual(stdin_result.stdin_text, "LWT 输入演示\n")
        self.assertEqual(stdin_result.returncode, 0)
        self.assertEqual(stdin_result.stdout, "Enter one line:\nLWT 输入演示\n")

        app.reset_button.invoke()
        self.run_example_from_controls(app, root, "runtime-error")
        error_result = app.session.result
        self.assertEqual(error_result.returncode, 3)
        self.assertIn(":2:8: RuntimeError:", error_result.stderr)
        self.assertIn("按预期报告 RuntimeError", app.details_text.get("1.0", "end-1c"))
        self.assertEqual(app.stderr_text.get("1.0", "end-1c"), error_result.stderr)
        self.assertNotIn("Traceback", error_result.stderr)

    def test_busy_controls_are_locked_and_window_close_rejects_late_worker_result(self) -> None:
        root = self.make_root()
        started = threading.Event()
        release = threading.Event()
        finished = threading.Event()

        def release_worker() -> None:
            release.set()
            finished.wait(8)

        self.addCleanup(release_worker)

        def blocked_runner(example_id: str):
            started.set()
            if not release.wait(8):
                raise TimeoutError("test did not release the controlled runner")
            try:
                return run_example(example_id)
            finally:
                finished.set()

        app = self.make_app(root, example_runner=blocked_runner)
        root.update()
        self.select_example(app, root, "functions")
        example = next(item for item in EXAMPLES if item.id == "functions")
        next(button for button in app.prediction_buttons if button.cget("text") == example.prediction.correct_option).invoke()
        app.submit_button.invoke()
        app.run_button.invoke()
        self.pump_until(root, started.is_set, description="controlled language-lab worker start")
        self.assertEqual(str(app.example_picker.cget("state")), "disabled")
        self.assertEqual(str(app.reset_button.cget("state")), "disabled")
        self.assertEqual(str(app.run_button.cget("state")), "disabled")
        app.reset_button.invoke()
        self.assertEqual(app.session.selected_id, "functions")

        _invoke_window_close(root)
        self.assertTrue(app.closing)
        release.set()
        self.assertTrue(finished.wait(8), "worker did not stop after test release")
        self.assertTrue(app.closing)


class LogDetectiveTkIntegrationTests(TkIntegrationCase):
    def make_app(self, root: tk.Tk, **kwargs) -> LogDetectiveApp:
        app = LogDetectiveApp(root, **kwargs)
        self.addCleanup(lambda: app._on_close() if not app._closing else None)
        return app

    def query_and_wait(self, app: LogDetectiveApp, root: tk.Tk) -> None:
        app.workbench.query_button.invoke()
        self.assertTrue(app.busy)
        self.assertEqual(str(app.workbench.query_button.cget("state")), "disabled")
        self.pump_until(
            root,
            lambda: not app.busy
            and (app.workbench_state.report is not None or app.workbench_state.error is not None),
            description="workbench query completion",
        )

    def choose_log(self, app: LogDetectiveApp, path: Path) -> None:
        with patch("app.log_detective_ui.filedialog.askopenfilename", autospec=True, return_value=str(path)):
            app.choose_button.invoke()

    def test_default_and_combined_queries_use_real_lwt_cli_and_same_request_report(self) -> None:
        root = self.make_root()
        app = self.make_app(root, log_path=DEFAULT_LOG)
        root.update()

        self.query_and_wait(app, root)
        report = app.workbench_state.report
        self.assertEqual(tuple(var.get() for var in app.workbench.metrics), ("7", "6", "1", "6"))
        self.assertEqual(report.matched_records, 6)
        self.assertIn("LWT log report", report.raw)
        self.assertIn(json.dumps(str(DEFAULT_LOG.resolve()), ensure_ascii=False), app.workbench.argv_label.cget("text"))

        app.workbench.level_entry.insert(0, "WARN")
        app.workbench.keyword_entry.insert(0, "retry")
        app.workbench.top_entry.delete(0, "end")
        app.workbench.top_entry.insert(0, "2")
        self.query_and_wait(app, root)
        query = app.workbench_state.query
        report = app.workbench_state.report
        self.assertEqual((query.level, query.keyword, query.top), ("WARN", "retry", "2"))
        self.assertEqual(tuple(var.get() for var in app.workbench.metrics), ("7", "6", "1", "1"))
        self.assertEqual([(item.name, item.count) for item in report.level_counts], [("WARN", 1)])
        self.assertEqual([(item.name, item.count) for item in report.top_modules], [("cache", 1)])
        self.assertEqual(report.matching_examples, ("2026-10-07T10:00:03Z|WARN|cache|retry scheduled",))
        self.assertIn('"--level", "WARN", "--keyword", "retry", "--top", "2"', app.workbench.argv_label.cget("text"))
        self.assertEqual(app.workbench.examples_var.get(), report.matching_examples[0])

        app.workbench.report_button.invoke()
        windows = [child for child in root.winfo_children() if isinstance(child, tk.Toplevel)]
        self.assertEqual(len(windows), 1)
        report_widgets = [widget for widget in _walk_widgets(windows[0]) if isinstance(widget, tk.Text)]
        self.assertEqual(len(report_widgets), 1)
        self.assertEqual(report_widgets[0].get("1.0", "end-1c"), report.raw)

    def test_actual_file_picker_path_zero_match_failure_and_recovery(self) -> None:
        root = self.make_root()
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "日志 with spaces.log"
            log_path.write_text("t|WARN|cache|retry now\n", encoding="utf-8")
            missing = Path(temp_dir) / "缺失 日志.log"
            app = self.make_app(root, log_path=DEFAULT_LOG)
            root.update()

            self.choose_log(app, log_path)
            self.assertEqual(app.log_path, log_path.resolve())
            app.workbench.level_entry.insert(0, "WARN")
            app.workbench.keyword_entry.insert(0, "retry")
            app.workbench.top_entry.delete(0, "end")
            app.workbench.top_entry.insert(0, "2")
            self.query_and_wait(app, root)
            self.assertEqual(app.workbench_state.report.matched_records, 1)
            self.assertIn(json.dumps(str(log_path.resolve()), ensure_ascii=False), app.workbench.argv_label.cget("text"))

            app.workbench.keyword_entry.delete(0, "end")
            app.workbench.keyword_entry.insert(0, "absent")
            self.query_and_wait(app, root)
            self.assertEqual(app.workbench_state.report.matched_records, 0)
            self.assertIn("没有匹配记录", app.workbench.examples_var.get())

            self.choose_log(app, missing)
            self.assertEqual(app.log_path, missing.resolve())
            self.query_and_wait(app, root)
            self.assertIsNone(app.workbench_state.report)
            self.assertIsNotNone(app.workbench_state.error)
            self.assertIn("失败", app.workbench.status_var.get())
            self.assertEqual(str(app.workbench.query_button.cget("state")), "normal")

            self.choose_log(app, DEFAULT_LOG)
            app.workbench.level_entry.delete(0, "end")
            app.workbench.keyword_entry.delete(0, "end")
            self.query_and_wait(app, root)
            self.assertEqual(app.workbench_state.report.matched_records, 6)

    def test_pending_query_busy_lock_invalidation_and_close_do_not_apply_stale_result(self) -> None:
        root = self.make_root()
        started = threading.Event()
        release = threading.Event()
        finished = threading.Event()

        def release_worker() -> None:
            release.set()
            finished.wait(8)

        self.addCleanup(release_worker)

        def gated_runner(query):
            started.set()
            if not release.wait(8):
                raise TimeoutError("test did not release the controlled workbench runner")
            try:
                from app.log_report_view import analyze_workbench
                return analyze_workbench(query)
            finally:
                finished.set()

        app = self.make_app(root, log_path=DEFAULT_LOG, workbench_runner=gated_runner)
        root.update()
        app.workbench.level_entry.insert(0, "WARN")
        app.workbench.keyword_entry.insert(0, "retry")
        app.workbench.query_button.invoke()
        self.pump_until(root, started.is_set, description="controlled workbench worker start")
        self.assertEqual(str(app.workbench.level_entry.cget("state")), "disabled")
        self.assertEqual(str(app.workbench.query_button.cget("state")), "disabled")
        app.workbench.query_button.invoke()
        self.assertIsNotNone(app.workbench_state.pending)

        # Exercise the real variable trace while the Entry widget is locked.
        # This models a condition revision arriving before the worker result is drained.
        app.workbench.keyword_var.set("changed while pending")
        self.assertIsNone(app.workbench_state.query)
        self.assertEqual(app.workbench.metrics[3].get(), "—")
        release.set()
        self.pump_until(root, lambda: not app.busy, description="stale workbench result drain")
        self.assertIsNone(app.workbench_state.report)
        self.assertIsNone(app.workbench_state.error)
        self.assertIn("条件已改变", app.workbench.condition_var.get())
        self.assertTrue(finished.wait(2))

        app.workbench.query_button.invoke()
        self.pump_until(root, lambda: not app.busy, description="recovered workbench request")
        self.assertIsNotNone(app.workbench_state.report)

        # A second controlled request proves destruction cancels the UI poll safely.
        started.clear()
        release.clear()
        finished.clear()
        app.workbench.keyword_var.set("retry")
        app.workbench.query_button.invoke()
        self.pump_until(root, started.is_set, description="close-path workbench worker start")
        _invoke_window_close(root)
        self.assertTrue(app._closing)
        release.set()
        self.assertTrue(finished.wait(8), "workbench worker did not stop after test release")
        self.assertTrue(app._closing)

    def test_five_question_game_uses_real_widgets_enter_and_real_cli_queries(self) -> None:
        root = self.make_root()
        app = self.make_app(root, log_path=DEFAULT_LOG)
        root.update()
        app.notebook.select(app.challenge_tab)
        root.update()
        app.start_button.invoke()

        for index in range(len(app.session.questions)):
            self.pump_until(
                root,
                lambda i=index: not app.busy and i in app.results,
                description=f"challenge question {index + 1} LWT query",
            )
            self.assertEqual(app.session.index, index)
            matched = app.results[index].matched_records
            answer = matched if index % 2 else matched + 1
            app.answer_entry.delete(0, "end")
            app.answer_entry.insert(0, str(answer))
            if index == 0:
                root.deiconify()
                root.update()
                app.answer_entry.focus_set()
                app.answer_entry.focus_force()
                root.update()
                app.answer_entry.event_generate("<Return>", when="now")
                root.update()
            else:
                app.submit_button.invoke()
            self.assertTrue(app.session.answered)
            self.assertEqual(app.session.score, sum(1 for answered in range(index + 1) if answered % 2 == 1))
            self.assertIn("回答正确" if index % 2 else "回答错误", app.feedback_var.get())
            app.next_button.invoke()

        self.assertTrue(app.session.finished)
        self.assertIn("挑战完成", app.question_var.get())
        self.assertEqual(app.start_button.cget("text"), "重新开始")
        self.assertIn("最终得分：2/5", app.feedback_var.get())
        app.start_button.invoke()
        self.pump_until(root, lambda: not app.busy and 0 in app.results, description="challenge restart query")
        self.assertFalse(app.session.finished)
        self.assertEqual(app.session.index, 0)
        self.assertEqual(app.session.score, 0)


class ManualTimer:
    def __init__(self) -> None:
        self._next_id = 0
        self.pending: OrderedDict[str, object] = OrderedDict()

    def after(self, delay: int, callback):
        self._next_id += 1
        timer_id = f"manual-{self._next_id}"
        self.pending[timer_id] = (delay, callback)
        return timer_id

    def after_cancel(self, timer_id: str) -> None:
        self.pending.pop(timer_id, None)

    def fire(self) -> None:
        timer_id, (_delay, callback) = self.pending.popitem(last=False)
        callback()


class SnakeTkIntegrationTests(TkIntegrationCase):
    def make_snake(self):
        root = self.make_root()
        timer = ManualTimer()
        app = SnakeGameApp(root, after=timer.after, after_cancel=timer.after_cancel)
        self.addCleanup(app._close)
        root.update()
        return root, app, timer

    def test_real_buttons_keys_and_manual_ticks_keep_controls_and_canvas_in_sync(self) -> None:
        root, app, timer = self.make_snake()
        self.assertEqual(app.game.status, GameStatus.READY)
        self.assertEqual(len(timer.pending), 0)
        app.start_button.invoke()
        self.assertEqual(app.game.status, GameStatus.RUNNING)
        self.assertEqual(str(app.start_button.cget("state")), "disabled")
        self.assertEqual(len(timer.pending), 1)

        old_head = app.game.snake[0]
        root.deiconify()
        root.update()
        # The app uses bind_all so direction keys must still work when a
        # control, rather than the Canvas, owns keyboard focus.
        app.pause_button.focus_force()
        root.update()
        app.pause_button.event_generate("<KeyPress>", keysym="w", when="now")
        root.update()
        self.assertEqual(app.game.direction, Direction.UP)
        app.pause_button.event_generate("<KeyPress>", keysym="s", when="now")
        root.update()
        self.assertEqual(app.game.direction, Direction.UP)
        app.pause_button.event_generate("<KeyPress>", keysym="d", when="now")
        root.update()
        self.assertEqual(app.game.direction, Direction.RIGHT)
        app.pause_button.event_generate("<KeyPress>", keysym="a", when="now")
        root.update()
        self.assertEqual(app.game.direction, Direction.RIGHT)
        app.pause_button.event_generate("<KeyPress>", keysym="Up", when="now")
        root.update()
        self.assertEqual(app.game.direction, Direction.UP)
        app.pause_button.event_generate("<KeyPress>", keysym="Down", when="now")
        root.update()
        self.assertEqual(app.game.direction, Direction.UP)
        timer.fire()
        self.assertEqual(app.game.snake[0], (old_head[0], old_head[1] - 1))
        self.assertEqual(len(timer.pending), 1)
        self.assertGreater(len(app.canvas.find_all()), 0)

        app.pause_button.invoke()
        self.assertEqual(app.game.status, GameStatus.PAUSED)
        self.assertEqual(len(timer.pending), 0)
        app.canvas.event_generate("<KeyPress>", keysym="space", when="now")
        root.update()
        self.assertEqual(app.game.status, GameStatus.RUNNING)
        self.assertEqual(len(timer.pending), 1)

        app.canvas.event_generate("<KeyPress>", keysym="r", when="now")
        root.update()
        self.assertEqual(app.game.status, GameStatus.READY)
        self.assertEqual(app.game.score, 0)
        self.assertEqual(len(timer.pending), 0)

    def test_focus_out_pause_terminal_collision_replay_and_close_cancel_ticks(self) -> None:
        root, app, timer = self.make_snake()
        app.start_button.invoke()
        self.assertEqual(len(timer.pending), 1)
        root.deiconify()
        root.update()
        app.canvas.focus_force()
        root.update()
        with patch.object(root, "focus_displayof", return_value=None, autospec=True):
            app.canvas.event_generate("<FocusOut>", when="now")
            root.update()
        self.assertEqual(app.game.status, GameStatus.PAUSED)
        self.assertEqual(len(timer.pending), 0)
        app.canvas.event_generate("<FocusIn>", when="now")
        root.update()
        self.assertEqual(app.game.status, GameStatus.PAUSED)
        app.start_button.invoke()
        self.assertEqual(app.game.status, GameStatus.RUNNING)
        self.assertEqual(len(timer.pending), 1)

        app.canvas.event_generate("<KeyPress>", keysym="r", when="now")
        root.update()
        self.assertEqual(app.game.status, GameStatus.READY)
        app.canvas.event_generate("<KeyPress>", keysym="r", when="now")
        root.update()
        self.assertEqual(app.game.status, GameStatus.READY)
        app._cancel_tick()
        y = app.game.height // 2
        app.game.snake = [(app.game.width - 1, y), (app.game.width - 2, y), (app.game.width - 3, y)]
        app.game.direction = Direction.RIGHT
        app.game.food = (0, 0)
        app._sync_controls()
        app.start_button.invoke()
        self.assertEqual(len(timer.pending), 1)
        timer.fire()
        self.assertEqual(app.game.status, GameStatus.GAME_OVER)
        self.assertIn("游戏结束", app.status_var.get())
        self.assertEqual(app.start_button.cget("text"), "再来一局")
        self.assertEqual(len(timer.pending), 0)
        app.start_button.invoke()
        self.assertEqual(app.game.status, GameStatus.RUNNING)
        self.assertEqual(app.game.score, 0)
        self.assertEqual(len(app.game.snake), 3)
        self.assertEqual(len(timer.pending), 1)

        _invoke_window_close(root)
        self.assertEqual(len(timer.pending), 0)
        self.assertEqual(len(timer.pending), 0)

    def test_narrow_and_large_geometry_keep_canvas_and_primary_controls_bounded(self) -> None:
        root, app, _timer = self.make_snake()
        root.deiconify()
        for geometry in ("480x440", "1100x820"):
            with self.subTest(geometry=geometry):
                root.geometry(geometry)
                root.update()
                width, height = root.winfo_width(), root.winfo_height()
                canvas_width, canvas_height = app.canvas.winfo_width(), app.canvas.winfo_height()
                self.assertGreaterEqual(width, 480)
                self.assertGreaterEqual(height, 440)
                self.assertGreater(canvas_width, 0)
                self.assertGreater(canvas_height, 0)
                for control in (app.start_button, app.pause_button, app.help_label):
                    self.assertGreater(control.winfo_width(), 0)
                    self.assertGreater(control.winfo_height(), 0)
                for item_id in app.canvas.find_all():
                    coords = app.canvas.coords(item_id)
                    self.assertTrue(coords)
                    for x, y in zip(coords[::2], coords[1::2]):
                        self.assertTrue(0 <= x <= canvas_width)
                        self.assertTrue(0 <= y <= canvas_height)


if __name__ == "__main__":
    unittest.main()
