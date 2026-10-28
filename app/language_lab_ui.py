"""Tkinter presentation for bundled, CLI-executed LWT teaching examples."""

from __future__ import annotations

from dataclasses import dataclass
import json
import queue
import threading
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from typing import Callable

from app.language_lab_core import (
    EXAMPLES,
    LabResult,
    LabSession,
    LanguageLabError,
    describe_outcome,
    load_source,
    run_example,
)
from app.ui_theme import COLORS, apply_theme, system_font


@dataclass(frozen=True)
class _LabMessage:
    revision: int
    result: LabResult | None = None
    error: str | None = None


class LanguageLabApp:
    """Own Tk controls; execute LWT CLI calls in a worker thread."""

    def __init__(
        self,
        root: tk.Tk,
        *,
        example_runner: Callable[[str], LabResult] | None = None,
    ) -> None:
        self.root = root
        self.example_runner = example_runner or run_example
        self.session = LabSession()
        self.session.select(EXAMPLES[0].id)
        self.messages: queue.Queue[_LabMessage] = queue.Queue()
        self.busy = False
        self.closing = False
        self.source_error: str | None = None
        self.poll_id: str | None = None
        self.examples_by_title = {example.title: example for example in EXAMPLES}
        self.prediction_buttons: list[ttk.Radiobutton] = []

        root.title("LWT 语义实验室（Python 教学前端）")
        root.geometry("1120x760")
        root.minsize(880, 580)
        apply_theme(root)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        outer = ttk.Frame(root, padding=(18, 14))
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(4, weight=1)

        ttk.Label(outer, text="LWT 语义实验室", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            outer,
            text=(
                "Python 制作的只读教学前端；每个示例都通过公开 LWT CLI 执行。"
                "日志分析器仍是课程 Agent 编写的完整 LWT 应用。"
            ),
            style="Subtitle.TLabel",
            wraplength=1000,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(4, 10))

        controls = ttk.Frame(outer, padding=10, style="Card.TFrame")
        controls.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        controls.columnconfigure(1, weight=1)
        ttk.Label(controls, text="选择主题", style="Card.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        self.example_var = tk.StringVar(value=EXAMPLES[0].title)
        self.example_picker = ttk.Combobox(
            controls,
            textvariable=self.example_var,
            values=tuple(example.title for example in EXAMPLES),
            state="readonly",
        )
        self.example_picker.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self.reset_button = ttk.Button(
            controls,
            text="重新预测",
            command=self.reset_lesson,
        )
        self.reset_button.grid(row=0, column=2, sticky="e")
        self.status_var = tk.StringVar(value="先观察提示，再运行 LWT 程序。")
        self.status_label = ttk.Label(
            controls, textvariable=self.status_var, style="Status.TLabel"
        )
        self.status_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.example_picker.bind("<<ComboboxSelected>>", self._selection_changed)

        prompt_card = ttk.Frame(outer, padding=10, style="Card.TFrame")
        prompt_card.grid(row=3, column=0, sticky="new", pady=(0, 10))
        prompt_card.columnconfigure(1, weight=1)
        ttk.Label(prompt_card, text="规范对应", style="CardHeading.TLabel").grid(
            row=0, column=0, sticky="nw", padx=(0, 10)
        )
        self.spec_var = tk.StringVar()
        ttk.Label(
            prompt_card,
            textvariable=self.spec_var,
            style="Card.TLabel",
            wraplength=900,
            justify="left",
        ).grid(row=0, column=1, sticky="ew")
        ttk.Label(prompt_card, text="观察点", style="CardHeading.TLabel").grid(
            row=1, column=0, sticky="nw", padx=(0, 10), pady=(5, 0)
        )
        self.observation_var = tk.StringVar()
        ttk.Label(
            prompt_card,
            textvariable=self.observation_var,
            style="Card.TLabel",
            wraplength=900,
            justify="left",
        ).grid(row=1, column=1, sticky="ew", pady=(5, 0))

        ttk.Separator(prompt_card).grid(row=2, column=0, columnspan=2, sticky="ew", pady=8)
        ttk.Label(prompt_card, text="先预测", style="CardHeading.TLabel").grid(
            row=3, column=0, sticky="nw", padx=(0, 10)
        )
        self.question_var = tk.StringVar()
        ttk.Label(
            prompt_card,
            textvariable=self.question_var,
            style="Card.TLabel",
            wraplength=900,
            justify="left",
        ).grid(row=3, column=1, sticky="ew")
        self.prediction_var = tk.StringVar(value="")
        self.options_frame = ttk.Frame(prompt_card, style="Card.TFrame")
        self.options_frame.grid(row=4, column=1, sticky="ew", pady=(4, 2))
        self.submit_button = ttk.Button(
            prompt_card,
            text="提交预测",
            command=self.submit_prediction,
        )
        self.submit_button.grid(row=5, column=1, sticky="w", pady=(4, 0))
        self.submit_button.bind("<Return>", self._submit_on_return)
        self.run_button = ttk.Button(
            prompt_card,
            text="运行 LWT 示例",
            style="Primary.TButton",
            command=self.run_selected,
        )
        self.run_button.grid(row=5, column=1, sticky="w", padx=(92, 0), pady=(4, 0))
        self.run_button.bind("<Return>", self._run_on_return)
        self.prediction_feedback_var = tk.StringVar(value="")
        self.prediction_feedback_label = ttk.Label(
            prompt_card,
            textvariable=self.prediction_feedback_var,
            style="CardHeading.TLabel",
            wraplength=900,
            justify="left",
        )
        self.prediction_feedback_label.grid(row=6, column=1, sticky="ew", pady=(4, 0))
        self.explanation_var = tk.StringVar(value="")
        ttk.Label(
            prompt_card,
            textvariable=self.explanation_var,
            style="Card.TLabel",
            wraplength=900,
            justify="left",
        ).grid(row=7, column=1, sticky="ew", pady=(3, 0))

        panes = ttk.Panedwindow(outer, orient="horizontal")
        panes.grid(row=4, column=0, sticky="nsew")
        source_frame = ttk.Frame(panes, padding=(0, 0, 7, 0))
        output_frame = ttk.Frame(panes, padding=(7, 0, 0, 0))
        panes.add(source_frame, weight=1)
        panes.add(output_frame, weight=1)
        source_frame.rowconfigure(1, weight=1)
        source_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(1, weight=1)
        output_frame.columnconfigure(0, weight=1)
        ttk.Label(source_frame, text="完整 LWT 源码（只读）", style="CardHeading.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 5)
        )
        self.source_text = self._text_area(source_frame, wrap="none")
        self.source_text.grid(row=1, column=0, sticky="nsew")

        ttk.Label(output_frame, text="本次公开 CLI 执行", style="CardHeading.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 5)
        )
        output_frame.rowconfigure(2, weight=1)
        self.details_text = self._text_area(output_frame, wrap="word", height=5)
        self.details_text.grid(row=1, column=0, sticky="ew", pady=(0, 7))

        result_panes = ttk.Panedwindow(output_frame, orient="vertical")
        result_panes.grid(row=2, column=0, sticky="nsew")
        stdout_frame = ttk.Frame(result_panes)
        stderr_frame = ttk.Frame(result_panes)
        stdout_frame.rowconfigure(1, weight=1)
        stderr_frame.rowconfigure(1, weight=1)
        stdout_frame.columnconfigure(0, weight=1)
        stderr_frame.columnconfigure(0, weight=1)
        result_panes.add(stdout_frame, weight=1)
        result_panes.add(stderr_frame, weight=1)
        ttk.Label(stdout_frame, text="stdout", style="Muted.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(stderr_frame, text="stderr", style="Muted.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.stdout_text = self._text_area(stdout_frame, wrap="none")
        self.stderr_text = self._text_area(stderr_frame, wrap="word")
        self.stdout_text.grid(row=1, column=0, sticky="nsew")
        self.stderr_text.grid(row=1, column=0, sticky="nsew")

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._show_selected_source()
        self._refresh_quiz_controls()
        self.poll_id = self.root.after(60, self._drain_messages)

    def _text_area(self, parent: tk.Misc, *, wrap: str, height: int = 10) -> ScrolledText:
        return ScrolledText(
            parent,
            wrap=wrap,
            height=height,
            font=system_font(self.root, 10),
            background=COLORS["surface"],
            foreground=COLORS["text"],
            insertbackground=COLORS["green_dark"],
        )

    @staticmethod
    def _set_text(widget: ScrolledText, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def _selected_example_id(self) -> str | None:
        example = self.examples_by_title.get(self.example_var.get())
        return example.id if example is not None else None

    def _selection_changed(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        example_id = self._selected_example_id()
        self.session.select(example_id)
        self._show_selected_source()
        self._refresh_quiz_controls()

    def _show_selected_source(self) -> None:
        example_id = self._selected_example_id()
        self.source_error = None
        self._set_text(self.source_text, "")
        self._set_text(self.details_text, "")
        self._set_text(self.stdout_text, "")
        self._set_text(self.stderr_text, "")
        self.prediction_var.set("")
        self.prediction_feedback_var.set("")
        self.explanation_var.set("")
        for button in self.prediction_buttons:
            button.destroy()
        self.prediction_buttons.clear()
        if example_id is None:
            self.spec_var.set("")
            self.observation_var.set("")
            self.question_var.set("")
            self._set_status("请从固定示例清单中选择主题。", error=True)
            return
        example = next(item for item in EXAMPLES if item.id == example_id)
        self.spec_var.set(example.spec_reference)
        self.observation_var.set(example.observation)
        self.question_var.set(example.prediction.prompt)
        for row, option in enumerate(example.prediction.options):
            button = ttk.Radiobutton(
                self.options_frame,
                text=option,
                value=option,
                variable=self.prediction_var,
                command=lambda value=option: self._choose_prediction(value),
            )
            button.grid(row=row, column=0, sticky="w", pady=1)
            self.prediction_buttons.append(button)
        try:
            _, source = load_source(example_id)
        except LanguageLabError as error:
            self.source_error = str(error)
            self._set_status(self.source_error, error=True)
            return
        self._set_text(self.source_text, source)
        self._refresh_quiz_controls()

    def _set_status(self, message: str, *, error: bool = False) -> None:
        self.status_var.set(message)
        self.status_label.configure(style="StatusError.TLabel" if error else "Status.TLabel")

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        self._refresh_quiz_controls()

    def _submit_on_return(self, _event: tk.Event[tk.Misc]) -> str:
        self.submit_prediction()
        return "break"

    def _run_on_return(self, _event: tk.Event[tk.Misc]) -> str:
        self.run_selected()
        return "break"

    def _choose_prediction(self, option: str) -> None:
        try:
            self.session.choose_prediction(option)
        except LanguageLabError as error:
            self._set_status(str(error), error=True)
            return
        self._refresh_quiz_controls()

    def submit_prediction(self) -> None:
        if self.closing or self.busy:
            return
        try:
            self.session.submit_prediction()
        except LanguageLabError as error:
            self._set_status(str(error), error=True)
            return
        self.prediction_feedback_var.set("预测已记录；运行 LWT 示例后揭晓答案与解释。")
        self.explanation_var.set("")
        self._refresh_quiz_controls()

    def reset_lesson(self) -> None:
        if self.closing or self.busy:
            return
        try:
            self.session.reset_lesson()
        except LanguageLabError as error:
            self._set_status(str(error), error=True)
            return
        self._show_selected_source()
        self._refresh_quiz_controls()

    def _refresh_quiz_controls(self) -> None:
        if self.closing:
            return
        submitted = self.session.prediction_submitted
        has_result = self.session.result is not None or self.session.error is not None
        self.example_picker.configure(state="disabled" if self.busy else "readonly")
        for button in self.prediction_buttons:
            button.configure(state="disabled" if self.busy or submitted else "normal")
        self.submit_button.configure(
            state=(
                "normal"
                if not self.busy and not submitted and self.session.prediction_choice is not None
                else "disabled"
            )
        )
        self.run_button.configure(
            state="normal" if not self.busy and submitted and not has_result else "disabled"
        )
        self.reset_button.configure(state="disabled" if self.busy else "normal")

        if self.busy:
            self._set_status("运行中：正在等待 LWT CLI。")
        elif self.source_error is not None:
            self._set_status(self.source_error, error=True)
        elif self.session.error is not None:
            self._set_status("运行失败：重置本例并重新预测后可重试。", error=True)
        elif self.session.result is not None:
            self._set_status("运行完成；请分别查看预测反馈和 CLI 契约核对。")
        elif submitted:
            self._set_status("已答：预测已提交，运行后揭晓。")
        elif self.session.prediction_choice is not None:
            self._set_status("未答完：已选一个选项，请提交预测。")
        else:
            self._set_status("未答：选择预测并提交后，才能运行 LWT 示例。")

    def run_selected(self) -> None:
        if self.closing or self.busy:
            return
        example_id = self._selected_example_id()
        if example_id is None:
            self._set_status("请先选择一个语义示例。", error=True)
            return
        try:
            revision = self.session.begin()
        except LanguageLabError as error:
            self._set_status(str(error), error=True)
            return
        self._set_busy(True)
        self._set_text(self.details_text, "")
        self._set_text(self.stdout_text, "")
        self._set_text(self.stderr_text, "")

        def work() -> None:
            try:
                self.messages.put(
                    _LabMessage(revision, result=self.example_runner(example_id))
                )
            except LanguageLabError as error:
                self.messages.put(_LabMessage(revision, error=str(error)))
            except Exception as error:
                self.messages.put(_LabMessage(revision, error=f"语义示例运行失败：{error}"))

        threading.Thread(target=work, name="lwt-language-lab", daemon=True).start()

    def _render_result(self, result: LabResult) -> None:
        example = result.example
        argv = json.dumps(list(result.command), ensure_ascii=False)
        arguments = json.dumps(list(example.program_args), ensure_ascii=False)
        stdin = json.dumps(result.stdin_text, ensure_ascii=False)
        outcome = describe_outcome(result)
        choice = self.session.prediction_choice or "未选择"
        prediction_correct = self.session.prediction_correct is True
        prediction_mark = "预测正确" if prediction_correct else "预测不正确"
        details = (
            f"命令 argv：{argv}\n"
            f"工作目录：{result.working_directory}\n"
            f"-- 后程序参数：{arguments}\n"
            f"stdin：{stdin}\n"
            f"退出码：{result.returncode}\n"
            f"CLI 结果：{outcome}"
        )
        self._set_text(self.details_text, details)
        self._set_text(self.stdout_text, result.stdout)
        self._set_text(self.stderr_text, result.stderr)
        self.prediction_feedback_var.set(
            f"你的预测：{choice}。{prediction_mark}；固定教学答案：{example.prediction.correct_option}。"
        )
        self.explanation_var.set(example.prediction.explanation)
        self._set_status(
            f"LWT CLI {outcome} · exit {result.returncode}；{prediction_mark}",
            error=not result.expectation_met,
        )

    def _drain_messages(self) -> None:
        if self.closing:
            return
        try:
            while True:
                message = self.messages.get_nowait()
                accepted = self.session.complete(
                    message.revision, message.result, message.error
                )
                if not accepted:
                    continue
                self._set_busy(False)
                if message.error is not None:
                    self._set_text(self.details_text, "CLI 未产生结果；已保留重试入口。")
                    self._set_text(self.stderr_text, message.error)
                    example = next(
                        item for item in EXAMPLES if item.id == self.session.selected_id
                    )
                    choice = self.session.prediction_choice or "未选择"
                    correct = self.session.prediction_correct is True
                    self.prediction_feedback_var.set(
                        f"你的预测：{choice}。"
                        f"{'预测正确' if correct else '预测不正确'}；"
                        f"固定教学答案：{example.prediction.correct_option}。"
                    )
                    self.explanation_var.set(example.prediction.explanation)
                    self._set_status(f"{message.error}；重置本例后可重试。", error=True)
                elif message.result is not None:
                    self._render_result(message.result)
        except queue.Empty:
            pass
        if not self.closing:
            try:
                self.poll_id = self.root.after(60, self._drain_messages)
            except tk.TclError:
                self.closing = True

    def close(self) -> None:
        if self.closing:
            return
        self.closing = True
        self.session.close()
        if self.poll_id is not None:
            try:
                self.root.after_cancel(self.poll_id)
            except tk.TclError:
                pass
            self.poll_id = None
        self.root.destroy()
