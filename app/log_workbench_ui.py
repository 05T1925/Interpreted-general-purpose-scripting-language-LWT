"""Tk widgets for displaying reports computed by the LWT CLI."""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk
from typing import Callable

from app.log_detective_core import build_lwt_command
from app.log_report_view import CountRow, LogReport, WorkbenchQuery
from app.ui_theme import COLORS, system_font


class _BarChart(ttk.Frame):
    """A scrollable rendering of already-computed LWT count rows."""

    def __init__(
        self, parent: tk.Misc, *, on_select: Callable[[str], None] | None = None
    ) -> None:
        super().__init__(parent)
        self.rows: tuple[CountRow, ...] = ()
        self.on_select = on_select
        self.canvas = tk.Canvas(
            self, height=124, background=COLORS["surface"], highlightthickness=0
        )
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas.bind("<Configure>", lambda _event: self._draw())
        if on_select is not None:
            self.canvas.bind("<Button-1>", self._clicked)

    def set_rows(self, rows: tuple[CountRow, ...]) -> None:
        self.rows = rows
        self.canvas.configure(height=min(190, max(58, len(rows) * 34)))
        self._draw()

    def _clicked(self, event: tk.Event[tk.Misc]) -> None:
        index = int(self.canvas.canvasy(event.y)) // 34
        if self.on_select is not None and 0 <= index < len(self.rows):
            self.on_select(self.rows[index].name)

    def _draw(self) -> None:
        self.canvas.delete("all")
        width = max(300, self.canvas.winfo_width())
        self.canvas.configure(scrollregion=(0, 0, width, max(58, len(self.rows) * 34)))
        if not self.rows:
            self.canvas.create_text(
                12, 26, anchor="w", text="没有可显示的统计项", fill=COLORS["muted"]
            )
            return
        peak = max(row.count for row in self.rows)
        bar_left = min(150, max(100, width // 4))
        bar_space = max(65, width - bar_left - 74)
        for index, row in enumerate(self.rows):
            y = index * 34 + 17
            label = row.name if row.name else "（空字段）"
            self.canvas.create_text(
                10, y, anchor="w", text=label, fill=COLORS["text"],
                font=system_font(self.canvas, 10),
            )
            bar_width = max(2, round(bar_space * row.count / peak)) if peak else 2
            self.canvas.create_rectangle(
                bar_left, y - 9, bar_left + bar_width, y + 9,
                fill=COLORS["green"], outline="",
            )
            self.canvas.create_text(
                bar_left + bar_space + 12, y, anchor="w",
                text=str(row.count), fill=COLORS["text"],
                font=system_font(self.canvas, 10, "bold"),
            )


class WorkbenchPanel(ttk.Frame):
    """Input and report display. Parent owns subprocess scheduling and state."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        on_query: Callable[[], None],
        on_change: Callable[[], None],
        on_report: Callable[[], None],
    ) -> None:
        super().__init__(parent, padding=(10, 8))
        self.on_change = on_change
        self.level_var = tk.StringVar()
        self.keyword_var = tk.StringVar()
        self.top_var = tk.StringVar(value="5")
        self.source_var = tk.StringVar(value="数据由 LWT 程序计算 · Python 负责调用、校验与展示")
        self.condition_var = tk.StringVar(value="设置条件后点击“运行 LWT 查询”。")
        self.status_var = tk.StringVar(value="尚未查询")
        self.metrics = [tk.StringVar(value="—") for _ in range(4)]
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        filters = ttk.Frame(self, padding=12, style="Card.TFrame")
        filters.grid(row=0, column=0, sticky="ew")
        for index in (1, 3):
            filters.columnconfigure(index, weight=1)
        ttk.Label(filters, text="Level", style="Card.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 6)
        )
        self.level_entry = ttk.Entry(filters, textvariable=self.level_var, width=12)
        self.level_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        ttk.Label(filters, text="Keyword", style="Card.TLabel").grid(
            row=0, column=2, sticky="w", padx=(0, 6)
        )
        self.keyword_entry = ttk.Entry(filters, textvariable=self.keyword_var, width=16)
        self.keyword_entry.grid(row=0, column=3, sticky="ew", padx=(0, 10))
        ttk.Label(filters, text="Top", style="Card.TLabel").grid(
            row=0, column=4, sticky="w", padx=(0, 6)
        )
        self.top_entry = ttk.Entry(filters, textvariable=self.top_var, width=6)
        self.top_entry.grid(row=0, column=5, sticky="w")
        ttk.Label(
            filters, text="空 Level / Keyword 表示不过滤；Top=0 隐藏模块排行。",
            style="Muted.TLabel",
        ).grid(row=1, column=0, columnspan=6, sticky="w", pady=(8, 0))

        controls = ttk.Frame(self, padding=(0, 9))
        controls.grid(row=1, column=0, sticky="ew")
        self.query_button = ttk.Button(
            controls, text="运行 LWT 查询", style="Primary.TButton", command=on_query
        )
        self.query_button.pack(side="left")
        self.report_button = ttk.Button(
            controls, text="查看此次原始报告", command=on_report, state="disabled"
        )
        self.report_button.pack(side="left", padx=(8, 0))
        self.status_label = ttk.Label(
            controls, textvariable=self.status_var, style="Status.TLabel"
        )
        self.status_label.pack(side="right")

        body = ttk.Frame(self)
        body.grid(row=2, column=0, sticky="nsew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        self.scroll = tk.Canvas(
            body, background=COLORS["page"], highlightthickness=0
        )
        self.scroll.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.scroll.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.scroll.configure(yscrollcommand=scrollbar.set)
        self.inner = ttk.Frame(self.scroll, padding=(0, 4))
        self.inner.columnconfigure(0, weight=1)
        self.inner.bind(
            "<Configure>",
            lambda _event: self.scroll.configure(scrollregion=self.scroll.bbox("all")),
        )
        inner_id = self.scroll.create_window((0, 0), window=self.inner, anchor="nw")
        self.scroll.bind(
            "<Configure>",
            lambda event: self.scroll.itemconfigure(inner_id, width=event.width),
        )
        ttk.Label(
            self.inner, textvariable=self.source_var, style="Subtitle.TLabel"
        ).grid(row=0, column=0, sticky="w")
        self.condition_label = ttk.Label(
            self.inner, textvariable=self.condition_var, style="Subtitle.TLabel",
            wraplength=560, justify="left",
        )
        self.condition_label.grid(row=1, column=0, sticky="ew", pady=(4, 10))
        self.argv_label = ttk.Label(
            self.inner, text="", style="Subtitle.TLabel", wraplength=560,
            justify="left",
        )
        self.argv_label.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        summary = ttk.Frame(self.inner, padding=12, style="Card.TFrame")
        summary.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        for index, title in enumerate(("总行数", "有效记录", "坏行", "匹配记录")):
            summary.columnconfigure(index, weight=1)
            ttk.Label(summary, text=title, style="Muted.TLabel").grid(
                row=0, column=index, sticky="w"
            )
            ttk.Label(
                summary, textvariable=self.metrics[index], style="CardHeading.TLabel"
            ).grid(row=1, column=index, sticky="w", pady=(3, 0))

        levels_card = ttk.Frame(self.inner, padding=12, style="Card.TFrame")
        levels_card.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        levels_card.columnconfigure(0, weight=1)
        ttk.Label(
            levels_card, text="级别统计 · 点击某一行可填入 Level",
            style="CardHeading.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.level_chart = _BarChart(levels_card, on_select=self._select_level)
        self.level_chart.grid(row=1, column=0, sticky="ew")

        modules_card = ttk.Frame(self.inner, padding=12, style="Card.TFrame")
        modules_card.grid(row=5, column=0, sticky="ew", pady=(0, 10))
        modules_card.columnconfigure(0, weight=1)
        ttk.Label(
            modules_card, text="模块排行 · 由 LWT 的 Top 参数截断，模块不能筛选",
            style="CardHeading.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.module_chart = _BarChart(modules_card)
        self.module_chart.grid(row=1, column=0, sticky="ew")

        examples_card = ttk.Frame(self.inner, padding=12, style="Card.TFrame")
        examples_card.grid(row=6, column=0, sticky="ew")
        examples_card.columnconfigure(0, weight=1)
        ttk.Label(
            examples_card, text="前 3 条匹配示例（LWT 原样输出）",
            style="CardHeading.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.examples_var = tk.StringVar(value="查询后显示匹配示例。")
        self.examples_label = ttk.Label(
            examples_card, textvariable=self.examples_var,
            style="Card.TLabel", justify="left", wraplength=560,
        )
        self.examples_label.grid(row=1, column=0, sticky="ew")

        for variable in (self.level_var, self.keyword_var, self.top_var):
            variable.trace_add("write", self._changed)
        self.bind("<Configure>", self._resize, add="+")

    def _changed(self, *_args: object) -> None:
        self.on_change()

    def _select_level(self, level: str) -> None:
        self.level_var.set(level)
        self.level_entry.focus_set()

    def _resize(self, event: tk.Event[tk.Misc]) -> None:
        if event.widget is self:
            wrap = max(280, int(event.width) - 55)
            for label in (self.condition_label, self.argv_label, self.examples_label):
                label.configure(wraplength=wrap)

    def set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.query_button.configure(state=state)
        self.level_entry.configure(state=state)
        self.keyword_entry.configure(state=state)
        self.top_entry.configure(state=state)
        if busy:
            self.report_button.configure(state="disabled")

    def clear(self, message: str = "设置条件后点击“运行 LWT 查询”。") -> None:
        self.condition_var.set(message)
        self.argv_label.configure(text="")
        self.metrics[0].set("—")
        self.metrics[1].set("—")
        self.metrics[2].set("—")
        self.metrics[3].set("—")
        self.level_chart.set_rows(())
        self.module_chart.set_rows(())
        self.examples_var.set("查询后显示匹配示例。")
        self.report_button.configure(state="disabled")

    def show_running(self, query: WorkbenchQuery) -> None:
        self.clear("正在运行 LWT 程序；查询结果会与本次条件绑定。")
        self.status_var.set("查询中…")
        self.status_label.configure(style="Status.TLabel")
        self.show_query(query)

    def show_query(self, query: WorkbenchQuery) -> None:
        self.condition_var.set(
            f"文件：{query.log_path}　Level：{query.level or '全部'}　"
            f"Keyword：{query.keyword or '全部'}　Top：{query.top}"
        )
        argv = build_lwt_command(query.log_path, query.filter_args)
        self.argv_label.configure(
            text="实际 CLI argv（每项独立参数）："
            + json.dumps(argv, ensure_ascii=False)
        )

    def show_error(self, message: str) -> None:
        self.clear(f"查询失败：{message} 修改条件或文件后可重试。")
        self.status_var.set("失败 · 可重试")
        self.status_label.configure(style="StatusError.TLabel")

    def show_report(self, query: WorkbenchQuery, report: LogReport) -> None:
        self.show_query(query)
        self.status_var.set("LWT 查询完成")
        self.status_label.configure(style="StatusSuccess.TLabel")
        for var, value in zip(
            self.metrics,
            (report.total_lines, report.valid_records,
             report.malformed_lines, report.matched_records),
        ):
            var.set(str(value))
        self.level_chart.set_rows(report.level_counts)
        self.module_chart.set_rows(report.top_modules)
        if report.matched_records == 0:
            self.examples_var.set("没有匹配记录。可调整 Level 或 Keyword 后重新查询。")
        else:
            self.examples_var.set("\n".join(report.matching_examples))
        self.report_button.configure(state="normal")
