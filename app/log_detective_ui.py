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


@dataclass(frozen=True)
class _WorkerResult:
    action: str
    value: object | None = None
    error: Exception | None = None


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
    ) -> None:
        self.root = root
        self.log_path = Path(log_path).resolve()
        self.question_runner = question_runner
        self.report_runner = report_runner
        self.session = GameSession()
        self.results: dict[int, AnalysisResult] = {}
        self.messages: queue.Queue[_WorkerResult] = queue.Queue()
        self.busy = False

        root.title("LWT 日志侦探")
        root.geometry("860x620")
        root.minsize(700, 500)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        outer = ttk.Frame(root, padding=18)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)

        ttk.Label(outer, text="LWT 日志侦探", font=("Microsoft YaHei UI", 20, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            outer,
            text="根据 LWT 日志分析器的真实结果回答问题。每题统计由 app/log_report.lwt 计算。",
            wraplength=790,
        ).grid(row=1, column=0, sticky="w", pady=(5, 14))

        file_row = ttk.Frame(outer)
        file_row.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        file_row.columnconfigure(1, weight=1)
        ttk.Label(file_row, text="当前日志：").grid(row=0, column=0, sticky="w")
        self.path_var = tk.StringVar(value=str(self.log_path))
        ttk.Label(file_row, textvariable=self.path_var, anchor="w").grid(
            row=0, column=1, sticky="ew", padx=(4, 10)
        )
        self.choose_button = ttk.Button(file_row, text="选择日志文件…", command=self.choose_file)
        self.choose_button.grid(row=0, column=2, sticky="e")

        self.content = ttk.Frame(outer, padding=18, relief="groove")
        self.content.grid(row=3, column=0, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(2, weight=1)
        self.progress_var = tk.StringVar(value=f"第 0/{self.session.question_count} 题　得分：0")
        ttk.Label(self.content, textvariable=self.progress_var, font=("Microsoft YaHei UI", 11)).grid(
            row=0, column=0, sticky="w"
        )
        self.question_var = tk.StringVar(value="准备好后开始游戏。")
        self.question_label = ttk.Label(
            self.content,
            textvariable=self.question_var,
            font=("Microsoft YaHei UI", 16),
            wraplength=740,
            justify="left",
        )
        self.question_label.grid(row=1, column=0, sticky="nw", pady=(26, 12))
        self.feedback_var = tk.StringVar(value="")
        self.feedback_label = ttk.Label(
            self.content, textvariable=self.feedback_var, font=("Microsoft YaHei UI", 12), wraplength=740
        )
        self.feedback_label.grid(row=2, column=0, sticky="nw")

        answer_row = ttk.Frame(self.content)
        answer_row.grid(row=3, column=0, sticky="ew", pady=(15, 4))
        ttk.Label(answer_row, text="匹配记录数：").grid(row=0, column=0, sticky="w")
        self.answer_var = tk.StringVar()
        self.answer_entry = ttk.Entry(answer_row, textvariable=self.answer_var, width=18)
        self.answer_entry.grid(row=0, column=1, sticky="w", padx=(5, 10))
        self.submit_button = ttk.Button(answer_row, text="提交答案", command=self.submit_answer)
        self.submit_button.grid(row=0, column=2, sticky="w")
        self.answer_entry.bind("<Return>", lambda _event: self.submit_answer())

        actions = ttk.Frame(outer)
        actions.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        self.start_button = ttk.Button(actions, text="开始游戏", command=self.start_game)
        self.start_button.pack(side="left")
        self.next_button = ttk.Button(actions, text="下一题", command=self.next_question, state="disabled")
        self.next_button.pack(side="left", padx=(8, 0))
        self.report_button = ttk.Button(actions, text="查看完整 LWT 报告", command=self.show_full_report)
        self.report_button.pack(side="left", padx=(8, 0))
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(actions, textvariable=self.status_var).pack(side="right")

        self.root.after(60, self._drain_messages)
        self._render_state()

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.choose_button.configure(state=state)
        self.start_button.configure(state=state)
        self.report_button.configure(state=state)
        if busy:
            self.submit_button.configure(state="disabled")
            self.next_button.configure(state="disabled")
        self.status_var.set("正在运行 LWT 分析器…" if busy else "就绪")

    def _run_worker(self, action: str, callback: Callable[[], object]) -> None:
        if self.busy:
            return
        self._set_busy(True)

        def work() -> None:
            try:
                self.messages.put(_WorkerResult(action, value=callback()))
            except Exception as error:  # show errors safely on Tk's own thread
                self.messages.put(_WorkerResult(action, error=error))

        threading.Thread(target=work, name=f"lwt-{action}", daemon=True).start()

    def _drain_messages(self) -> None:
        try:
            while True:
                result = self.messages.get_nowait()
                self._set_busy(False)
                if result.error is not None:
                    if result.action == "question":
                        self.feedback_var.set(
                            f"本题查询失败。{result.error} 请重新开始或选择其他日志。"
                        )
                    messagebox.showerror("LWT 分析失败", str(result.error), parent=self.root)
                    self._render_state()
                    continue
                if result.action == "question":
                    index, analysis = result.value  # type: ignore[misc]
                    self.results[index] = analysis
                    self.feedback_var.set("本题统计已由 LWT CLI 生成，请输入 Matched records 数值。")
                    self._render_state()
                    self.answer_entry.focus_set()
                elif result.action == "report":
                    self._open_report(str(result.value))
                    self._render_state()
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(60, self._drain_messages)

    def _render_state(self) -> None:
        self.progress_var.set(
            f"第 {min(self.session.round_number, self.session.question_count) if self.session.started else 0}/"
            f"{self.session.question_count} 题　得分：{self.session.score}"
        )
        if self.session.finished:
            self.question_var.set("挑战完成！")
            self.feedback_var.set(f"最终得分：{self.session.score}/{self.session.question_count}")
            self.answer_entry.configure(state="disabled")
            self.submit_button.configure(state="disabled")
            self.next_button.configure(text="下一题", state="disabled")
            self.start_button.configure(text="重新开始")
            return
        if not self.session.started:
            self.question_var.set("准备好后开始游戏。")
            self.feedback_var.set("回答五道基于真实日志查询的问题，查看完整报告可随时核对分析器输出。")
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
        self.feedback_var.set("正在查询所选日志…")
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
            self.feedback_var.set(f"回答正确！匹配记录数为 {analysis.matched_records}。")
        else:
            self.feedback_var.set(
                f"回答错误。正确答案是 {analysis.matched_records}。该数值来自 LWT 分析报告。"
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
        filename = filedialog.askopenfilename(
            parent=self.root,
            title="选择日志文件",
            filetypes=(("日志和文本", "*.log *.txt"), ("所有文件", "*.*")),
        )
        if not filename:
            return
        self.log_path = Path(filename).resolve()
        self.path_var.set(str(self.log_path))
        self.session = GameSession()
        self.results.clear()
        self.feedback_var.set("已选择新日志。开始游戏后将由 LWT 分析该文件。")
        self._render_state()

    def show_full_report(self) -> None:
        self._run_worker("report", lambda: self.report_runner(self.log_path))

    def _open_report(self, report: str) -> None:
        window = tk.Toplevel(self.root)
        window.title("LWT 完整分析报告")
        window.geometry("780x560")
        window.minsize(500, 350)
        frame = ttk.Frame(window, padding=10)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="以下内容为 `python -m lwt` 的完整标准输出：").pack(anchor="w", pady=(0, 8))
        text = ScrolledText(frame, wrap="none", font=("Consolas", 10))
        text.pack(fill="both", expand=True)
        text.insert("1.0", report)
        text.configure(state="disabled")


def launch() -> None:
    try:
        root = tk.Tk()
    except tk.TclError as error:
        raise GuiUnavailableError(f"无法创建 Tkinter 桌面窗口：{error}") from error
    LogDetectiveApp(root)
    root.mainloop()
