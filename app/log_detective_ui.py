"""Tkinter front end for the LWT Log Detective game."""

from __future__ import annotations

from dataclasses import dataclass
import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Callable

from app.log_detective_core import (
    DEFAULT_LOG,
    QUESTIONS,
    AnalysisResult,
    GameSession,
    analyze_question,
    full_report,
)
from app.log_report_view import (
    LogReport,
    WorkbenchQuery,
    WorkbenchSession,
    analyze_workbench,
)
from app.log_workbench_ui import WorkbenchPanel
from app.ui_theme import COLORS, apply_theme, system_font


@dataclass(frozen=True)
class _WorkerResult:
    action: str
    value: object | None = None
    error: Exception | None = None
    revision: int | None = None


class GuiUnavailableError(RuntimeError):
    """The current machine cannot create a Tk desktop window."""


class LogDetectiveApp:
    """Owns all Tk widgets; subprocess work runs outside the Tk event thread."""

    def __init__(
        self,
        root: tk.Tk,
        *,
        log_path: str | Path = DEFAULT_LOG,
        question_runner: Callable[..., AnalysisResult] = analyze_question,
        report_runner: Callable[..., str] = full_report,
        workbench_runner: Callable[[WorkbenchQuery], LogReport] | None = None,
    ) -> None:
        self.root = root
        self.log_path = Path(log_path).resolve()
        self.question_runner = question_runner
        self.report_runner = report_runner
        self.workbench_runner = workbench_runner or analyze_workbench
        self.session = GameSession()
        self.workbench_state = WorkbenchSession()
        self.results: dict[int, AnalysisResult] = {}
        self.messages: queue.Queue[_WorkerResult] = queue.Queue()
        self.busy = False
        self._busy_action: str | None = None
        self._closing = False
        self._poll_id: str | None = None

        root.title("LWT 日志侦探")
        root.geometry("1080x750")
        root.minsize(640, 500)
        apply_theme(root)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        outer = ttk.Frame(root, padding=(22, 18))
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)

        ttk.Label(outer, text="LWT 日志侦探", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.description_label = ttk.Label(
            outer,
            text="根据 LWT 日志分析器的真实结果回答问题。每题统计由 app/log_report.lwt 计算。",
            style="Subtitle.TLabel",
            wraplength=760,
        )
        self.description_label.grid(row=1, column=0, sticky="w", pady=(5, 14))

        file_row = ttk.Frame(outer, padding=12, style="Card.TFrame")
        file_row.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        file_row.columnconfigure(1, weight=1)
        ttk.Label(file_row, text="当前日志", style="CardHeading.TLabel").grid(
            row=0, column=0, sticky="nw", padx=(0, 10)
        )
        self.path_var = tk.StringVar(value=str(self.log_path))
        self.path_label = ttk.Label(
            file_row,
            textvariable=self.path_var,
            style="Card.TLabel",
            anchor="w",
            justify="left",
            wraplength=520,
        )
        self.path_label.grid(
            row=0, column=1, sticky="ew", padx=(0, 10)
        )
        self.choose_button = ttk.Button(file_row, text="选择日志文件…", command=self.choose_file)
        self.choose_button.grid(row=0, column=2, sticky="e")

        self.notebook = ttk.Notebook(outer)
        self.notebook.grid(row=3, column=0, sticky="nsew")
        self.workbench = WorkbenchPanel(
            self.notebook,
            on_query=self.query_workbench,
            on_change=self._invalidate_workbench,
            on_report=self.show_workbench_report,
        )
        self.notebook.add(self.workbench, text="分析工作台")
        self.challenge_tab = ttk.Frame(self.notebook, padding=(10, 8))
        self.challenge_tab.columnconfigure(0, weight=1)
        self.challenge_tab.rowconfigure(0, weight=1)
        self.notebook.add(self.challenge_tab, text="五题挑战")

        self.content = ttk.Frame(self.challenge_tab, padding=20, style="Card.TFrame")
        self.content.grid(row=0, column=0, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(4, weight=1)
        self.progress_var = tk.StringVar(value=f"第 0/{self.session.question_count} 题　得分：0")
        ttk.Label(self.content, textvariable=self.progress_var, style="CardHeading.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.question_var = tk.StringVar(value="准备好后开始游戏。")
        self.question_label = ttk.Label(
            self.content,
            textvariable=self.question_var,
            style="Question.TLabel",
            wraplength=700,
            justify="left",
        )
        self.question_label.grid(row=1, column=0, sticky="nw", pady=(22, 12))
        self.feedback_var = tk.StringVar(value="")
        self.feedback_label = ttk.Label(
            self.content,
            textvariable=self.feedback_var,
            style="Muted.TLabel",
            wraplength=700,
            justify="left",
        )
        self.feedback_label.grid(row=2, column=0, sticky="nw")

        answer_row = ttk.Frame(self.content)
        answer_row.grid(row=3, column=0, sticky="ew", pady=(15, 4))
        ttk.Label(answer_row, text="匹配记录数：").grid(row=0, column=0, sticky="w")
        self.answer_var = tk.StringVar()
        self.answer_entry = ttk.Entry(answer_row, textvariable=self.answer_var, width=18)
        self.answer_entry.grid(row=0, column=1, sticky="w", padx=(5, 10))
        self.submit_button = ttk.Button(
            answer_row, text="提交答案", style="Primary.TButton", command=self.submit_answer
        )
        self.submit_button.grid(row=0, column=2, sticky="w")
        self.answer_entry.bind("<Return>", self._submit_on_enter)

        actions = ttk.Frame(self.challenge_tab)
        actions.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.start_button = ttk.Button(
            actions, text="开始游戏", style="Primary.TButton", command=self.start_game
        )
        self.start_button.pack(side="left")
        self.next_button = ttk.Button(actions, text="下一题", command=self.next_question, state="disabled")
        self.next_button.pack(side="left", padx=(8, 0))
        self.report_button = ttk.Button(actions, text="查看完整 LWT 报告", command=self.show_full_report)
        self.report_button.pack(side="left", padx=(8, 0))
        self.status_var = tk.StringVar(value="就绪")
        self.status_label = ttk.Label(actions, textvariable=self.status_var, style="Status.TLabel")
        self.status_label.pack(side="right")

        root.bind("<Configure>", self._on_resize, add="+")
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed, add="+")
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._poll_id = self.root.after(60, self._drain_messages)
        self._render_state()

    def _on_resize(self, event: tk.Event[tk.Misc]) -> None:
        if event.widget is not self.root:
            return
        available = max(280, int(event.width) - 96)
        self.description_label.configure(wraplength=available)
        self.question_label.configure(wraplength=available)
        self.feedback_label.configure(wraplength=available)
        self.path_label.configure(wraplength=max(220, int(event.width) - 350))

    def _set_feedback(self, message: str, tone: str = "muted") -> None:
        styles = {"muted": "Muted.TLabel", "success": "Success.TLabel", "error": "Error.TLabel"}
        self.feedback_var.set(message)
        self.feedback_label.configure(style=styles[tone])

    def _set_status(self, message: str, *, error: bool = False) -> None:
        self.status_var.set(message)
        self.status_label.configure(style="StatusError.TLabel" if error else "Status.TLabel")

    def _submit_on_enter(self, _event: tk.Event[tk.Misc]) -> str:
        self.submit_answer()
        return "break"

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.choose_button.configure(state=state)
        self.start_button.configure(state=state)
        self.report_button.configure(state=state)
        self.workbench.set_busy(busy)
        if busy:
            self.submit_button.configure(state="disabled")
            self.next_button.configure(state="disabled")
        self._set_status("正在运行 LWT 分析器…" if busy else "就绪")

    def _run_worker(
        self, action: str, callback: Callable[[], object], revision: int | None = None
    ) -> None:
        if self.busy:
            return
        self._busy_action = action
        self._set_busy(True)

        def work() -> None:
            try:
                self.messages.put(_WorkerResult(action, value=callback(), revision=revision))
            except Exception as error:  # show errors safely on Tk's own thread
                self.messages.put(_WorkerResult(action, error=error, revision=revision))

        threading.Thread(target=work, name=f"lwt-{action}", daemon=True).start()

    def _drain_messages(self) -> None:
        if self._closing:
            return
        try:
            while True:
                result = self.messages.get_nowait()
                self._busy_action = None
                self._set_busy(False)
                if result.action == "analysis":
                    accepted = self.workbench_state.complete(
                        result.revision if result.revision is not None else -1,
                        result.value if isinstance(result.value, LogReport) else None,
                        str(result.error) if result.error is not None else None,
                    )
                    if accepted:
                        if result.error is not None:
                            self.workbench.show_error(str(result.error))
                        elif isinstance(result.value, LogReport):
                            query = self.workbench_state.query
                            if query is not None:
                                self.workbench.show_report(query, result.value)
                    self._render_state()
                    continue
                if result.error is not None:
                    if result.action == "question":
                        self._set_feedback(
                            f"本题查询失败。{result.error} 请重新开始或选择其他日志。", "error"
                        )
                    self._set_status("查询失败；可重新开始或选择日志", error=True)
                    messagebox.showerror("LWT 分析失败", str(result.error), parent=self.root)
                    self._render_state()
                    continue
                if result.action == "question":
                    index, analysis = result.value  # type: ignore[misc]
                    self.results[index] = analysis
                    self._set_feedback(
                        "本题统计已由 LWT CLI 生成，请输入 Matched records 数值。"
                    )
                    self._set_status("查询完成 · 请提交答案")
                    self._render_state()
                    self.answer_entry.focus_set()
                elif result.action == "report":
                    self._open_report(str(result.value))
                    self._set_status("完整报告已打开")
                    self._render_state()
        except queue.Empty:
            pass
        if not self._closing:
            try:
                self._poll_id = self.root.after(60, self._drain_messages)
            except tk.TclError:
                self._closing = True

    def _render_state(self) -> None:
        self.progress_var.set(
            f"第 {min(self.session.round_number, self.session.question_count) if self.session.started else 0}/"
            f"{self.session.question_count} 题　得分：{self.session.score}"
        )
        if self.session.finished:
            self.question_var.set("挑战完成！")
            self._set_feedback(
                f"最终得分：{self.session.score}/{self.session.question_count}", "success"
            )
            self.answer_entry.configure(state="disabled")
            self.submit_button.configure(state="disabled")
            self.next_button.configure(text="下一题", state="disabled")
            self.start_button.configure(text="重新开始")
            return
        if not self.session.started:
            self.question_var.set("准备好后开始游戏。")
            self._set_feedback("回答五道基于真实日志查询的问题；完整报告可随时核对分析器输出。")
            self.answer_entry.configure(state="normal")
            self.answer_var.set("")
            self.submit_button.configure(state="disabled")
            self.next_button.configure(state="disabled")
            self.start_button.configure(text="开始游戏")
            return

        index = self.session.index
        self.question_var.set(f"问题：{self.session.current_question.condition} 的匹配记录数是多少？")
        self.answer_entry.configure(state="normal")
        can_submit = not self.busy and not self.session.answered and index in self.results
        self.submit_button.configure(state="normal" if can_submit else "disabled")
        self.next_button.configure(
            text="查看最终结果" if index + 1 == self.session.question_count else "下一题",
            state="normal" if self.session.answered and not self.busy else "disabled",
        )
        self.start_button.configure(text="重新开始")

    def _load_current_question(self) -> None:
        index = self.session.index
        question = self.session.current_question
        self._set_feedback("正在查询所选日志…")
        self.answer_var.set("")
        self._render_state()
        self._run_worker(
            "question",
            lambda: (index, self.question_runner(self.log_path, question)),
        )

    def start_game(self) -> None:
        self.session.start()
        self.results.clear()
        self._load_current_question()

    def submit_answer(self) -> None:
        if self.busy or not self.session.started or self.session.answered:
            return
        raw = self.answer_var.get().strip()
        if not raw or not raw.isascii() or not raw.isdecimal():
            messagebox.showwarning("输入无效", "请输入非负十进制整数。", parent=self.root)
            self.answer_entry.focus_set()
            return
        try:
            answer = int(raw)
        except ValueError:
            messagebox.showwarning(
                "输入过大", "当前 Python 无法转换这么长的整数，请输入较短的非负整数。", parent=self.root
            )
            self.answer_entry.focus_set()
            return
        analysis = self.results.get(self.session.index)
        if analysis is None:
            messagebox.showwarning("尚未就绪", "本题的 LWT 查询尚未完成。", parent=self.root)
            return
        correct = self.session.submit(answer, analysis.matched_records)
        if correct:
            self._set_feedback(f"回答正确！匹配记录数为 {analysis.matched_records}。", "success")
        else:
            self._set_feedback(
                f"回答错误。正确答案是 {analysis.matched_records}。该数值来自 LWT 分析报告。",
                "error",
            )
        self._render_state()

    def next_question(self) -> None:
        if self.busy:
            return
        has_next = self.session.advance()
        if has_next:
            self._load_current_question()
        else:
            self._render_state()

    def choose_file(self) -> None:
        if self.busy:
            return
        filename = filedialog.askopenfilename(
            parent=self.root,
            title="选择日志文件",
            filetypes=(("日志和文本", "*.log *.txt"), ("所有文件", "*.*")),
        )
        if not filename:
            return
        self.log_path = Path(filename).resolve()
        self.path_var.set(str(self.log_path))
        self._invalidate_workbench()
        self.session = GameSession()
        self.results.clear()
        self._set_feedback("已选择新日志。开始游戏后将由 LWT 分析该文件。", "success")
        self._render_state()

    def show_full_report(self) -> None:
        self._run_worker("report", lambda: self.report_runner(self.log_path))

    def _invalidate_workbench(self) -> None:
        self.workbench_state.invalidate()
        self.workbench.clear("条件已改变，请重新运行 LWT 查询。")
        self.workbench.status_var.set("等待新查询")
        self.workbench.status_label.configure(style="Status.TLabel")

    def _on_tab_changed(self, _event: tk.Event[tk.Misc]) -> None:
        if self._busy_action == "analysis" and self.notebook.select() != str(self.workbench):
            self._invalidate_workbench()

    def query_workbench(self) -> None:
        if self.busy:
            return
        try:
            query = WorkbenchQuery.from_fields(
                self.log_path,
                self.workbench.level_var.get(),
                self.workbench.keyword_var.get(),
                self.workbench.top_var.get(),
            )
        except Exception as error:
            self._invalidate_workbench()
            self.workbench.show_error(str(error))
            return
        revision = self.workbench_state.begin(query)
        self.workbench.show_running(query)
        self._run_worker("analysis", lambda: self.workbench_runner(query), revision)

    def show_workbench_report(self) -> None:
        if self.workbench_state.report is not None and not self.busy:
            self._open_report(self.workbench_state.report.raw)

    def _open_report(self, report: str) -> None:
        window = tk.Toplevel(self.root)
        window.title("LWT 完整分析报告")
        window.geometry("800x580")
        window.minsize(460, 300)
        frame = ttk.Frame(window, padding=10)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text="以下内容为 `python -m lwt` 的完整标准输出：",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(0, 8))
        text = ScrolledText(
            frame,
            wrap="none",
            font=system_font(self.root, 10),
            background=COLORS["surface"],
            foreground=COLORS["text"],
            insertbackground=COLORS["green_dark"],
        )
        text.pack(fill="both", expand=True)
        text.insert("1.0", report)
        text.configure(state="disabled")

    def _on_close(self) -> None:
        self._closing = True
        self.workbench_state.invalidate()
        if self._poll_id is not None:
            try:
                self.root.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None
        self.root.destroy()


def launch() -> None:
    try:
        root = tk.Tk()
    except tk.TclError as error:
        raise GuiUnavailableError(f"无法创建 Tkinter 桌面窗口：{error}") from error
    LogDetectiveApp(root)
    root.mainloop()
