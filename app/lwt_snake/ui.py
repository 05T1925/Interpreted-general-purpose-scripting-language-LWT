"""Tk renderer and event forwarding for the external LWT rule engine."""
from __future__ import annotations

from pathlib import Path
import queue
import tkinter as tk
from tkinter import ttk

from app.lwt_snake.bridge import GAME_SOURCE
from app.lwt_snake.protocol import GameSnapshot
from app.lwt_snake.session import EngineWorker, Reply
from app.ui_theme import COLORS, apply_theme


class LwtSnakeApp:
    def __init__(self, root: tk.Tk, *, source: Path = GAME_SOURCE, tick_ms: int = 140) -> None:
        self.root, self.source, self.tick_ms = root, source, tick_ms
        self.repository_root = Path(__file__).resolve().parents[2]
        self.snapshot: GameSnapshot | None = None
        self.replies: queue.Queue[Reply] = queue.Queue(maxsize=16)
        self.generation = 0
        self.request_id = 0
        self.busy = True
        self.failed = False
        self.closing = False
        self.tick_id: str | None = None
        self.poll_id: str | None = None
        self.focus_id: str | None = None
        root.title("LWT 驱动贪吃蛇")
        root.geometry("820x700")
        root.minsize(480, 440)
        apply_theme(root)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)
        header = ttk.Frame(root, padding=14)
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="LWT 驱动贪吃蛇", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="规则：game.lwt · Python：进程桥接与绘图", style="Subtitle.TLabel").pack(anchor="w")
        self.score_var = tk.StringVar(value="得分：0")
        ttk.Label(header, textvariable=self.score_var).pack(anchor="e")
        self.canvas = tk.Canvas(root, background=COLORS["surface_alt"], highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=14)
        self.canvas.bind("<Configure>", lambda event: self.draw())
        footer = ttk.Frame(root, padding=14)
        footer.grid(row=2, column=0, sticky="ew")
        self.start_button = ttk.Button(footer, text="开始", command=self.primary)
        self.start_button.grid(row=0, column=0)
        self.pause_button = ttk.Button(footer, text="暂停", command=self.pause)
        self.pause_button.grid(row=0, column=1, padx=6)
        self.reset_button = ttk.Button(footer, text="重新开始", command=self.reset)
        self.reset_button.grid(row=0, column=2)
        self.retry_button = ttk.Button(footer, text="重试引擎", command=self.retry)
        self.retry_button.grid(row=0, column=3, padx=6)
        self.status_var = tk.StringVar(value="正在启动 LWT 规则引擎…")
        ttk.Label(footer, textvariable=self.status_var, wraplength=430).grid(row=1, column=0, columnspan=4, sticky="w", pady=6)
        ttk.Label(footer, text="方向键 / WASD：转向　Space：开始/暂停/继续　R：复位\n失焦自动暂停；回到窗口后手动继续。", wraplength=430).grid(row=2, column=0, columnspan=4, sticky="w")
        self.key_tag = f"LwtSnakeKeys{id(self)}"
        root.bind_class(self.key_tag, "<KeyPress>", self.on_key)
        def install_key_tag(widget):
            widget.bindtags((self.key_tag, *widget.bindtags()))
            for child in widget.winfo_children():
                install_key_tag(child)
        install_key_tag(root)
        root.bind("<FocusOut>", self.on_focus_out, add="+")
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._start_worker()
        self.poll_id = root.after(10, self.poll)

    def _start_worker(self) -> None:
        self.generation += 1
        self.request_id = 0
        self.busy, self.failed = True, False
        self.worker = EngineWorker(self.repository_root, self.replies, self.generation, self.source)
        self.worker.start()
        self.sync_controls()

    def send(self, command: str, *args: object, replace: bool = False) -> None:
        if self.closing or self.failed or (self.busy and not replace):
            return
        self.cancel_tick()
        next_id = self.request_id + 1
        if self.worker.submit(next_id, command, *args, replace=replace):
            self.request_id = next_id
            self.busy = True
            self.status_var.set("等待 LWT 规则引擎响应…")
            self.sync_controls()

    def primary(self) -> None:
        if self.snapshot is None:
            return
        if self.snapshot.phase == "READY":
            self.send("START")
        elif self.snapshot.phase == "PAUSED":
            self.send("RESUME")
        elif self.snapshot.phase in {"GAME_OVER", "WON"}:
            self.reset()

    def pause(self) -> None:
        if self.snapshot and self.snapshot.phase == "RUNNING":
            self.send("PAUSE", replace=True)

    def reset(self) -> None:
        if self.failed:
            self.retry()
        else:
            self.send("RESET", replace=True)

    def retry(self) -> None:
        if not self.failed or not self.worker.finished.is_set():
            return
        self.snapshot = None
        self.status_var.set("正在重新启动 LWT 引擎…")
        self._start_worker()

    def on_key(self, event: tk.Event) -> str | None:
        key = str(event.keysym).lower()
        directions = {"up": "U", "w": "U", "right": "R", "d": "R", "down": "D", "s": "D", "left": "L", "a": "L"}
        if key in directions:
            if self.snapshot and self.snapshot.phase == "RUNNING":
                self.send("TURN", directions[key])
            return "break"
        if key == "space":
            if self.snapshot and self.snapshot.phase == "RUNNING":
                self.pause()
            else:
                self.primary()
            return "break"
        if key == "r":
            self.reset()
            return "break"
        return None

    def on_focus_out(self, event: tk.Event) -> None:
        if event.widget is self.root and not self.closing and self.focus_id is None:
            self.focus_id = self.root.after_idle(self.check_focus)

    def check_focus(self) -> None:
        self.focus_id = None
        if self.closing:
            return
        focused = self.root.focus_displayof()
        if focused is None or focused.winfo_toplevel() is not self.root:
            self.pause()

    def poll(self) -> None:
        self.poll_id = None
        if self.closing:
            return
        while True:
            try:
                reply = self.replies.get_nowait()
            except queue.Empty:
                break
            if reply.generation != self.generation or reply.request_id != self.request_id:
                continue
            self.busy = False
            if reply.error:
                self.failed = reply.fatal
                self.status_var.set("引擎错误：" + reply.error)
            elif reply.snapshot:
                self.snapshot = reply.snapshot
                self.status_var.set({"READY": "准备开始", "RUNNING": "游戏进行中", "PAUSED": "已暂停，按 Space 或继续", "GAME_OVER": "碰撞结束，按 R 复位", "WON": "棋盘填满，胜利！按 R 复位"}[reply.snapshot.phase])
                self.score_var.set(f"得分：{reply.snapshot.score}")
            self.sync_controls()
            self.draw()
            self.schedule_tick()
        self.poll_id = self.root.after(10, self.poll)

    def sync_controls(self) -> None:
        ready = self.snapshot is not None and not self.busy and not self.failed
        phase = self.snapshot.phase if self.snapshot else ""
        self.start_button.configure(text="继续" if phase == "PAUSED" else "开始", state="normal" if ready and phase != "RUNNING" else "disabled")
        self.pause_button.configure(state="normal" if ready and phase == "RUNNING" else "disabled")
        self.reset_button.configure(state="normal" if self.snapshot is not None and not self.failed else "disabled")
        self.retry_button.configure(state="normal" if self.failed else "disabled")

    def schedule_tick(self) -> None:
        if not self.closing and not self.failed and not self.busy and self.snapshot and self.snapshot.phase == "RUNNING" and self.tick_id is None:
            self.tick_id = self.root.after(self.tick_ms, self.tick)

    def cancel_tick(self) -> None:
        if self.tick_id is not None:
            self.root.after_cancel(self.tick_id)
            self.tick_id = None

    def tick(self) -> None:
        self.tick_id = None
        self.send("TICK")

    def draw(self) -> None:
        self.canvas.delete("all")
        state = self.snapshot
        if state is None:
            return
        width, height = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        cell = max(1, min(width // state.width, height // state.height))
        left, top = (width - cell * state.width) // 2, (height - cell * state.height) // 2
        self.canvas.create_rectangle(left, top, left + cell * state.width, top + cell * state.height, fill=COLORS["green_soft"])
        for index, (x, y) in enumerate(state.snake):
            color = COLORS["green_dark"] if index == 0 else COLORS["green"]
            self.canvas.create_rectangle(left+x*cell+1, top+y*cell+1, left+(x+1)*cell-1, top+(y+1)*cell-1, fill=color, outline=color)
        if state.food:
            x, y = state.food
            self.canvas.create_oval(left+x*cell+2, top+y*cell+2, left+(x+1)*cell-2, top+(y+1)*cell-2, fill=COLORS["food"], outline=COLORS["food"])

    def close(self) -> None:
        if self.closing:
            return
        self.closing = True
        self.cancel_tick()
        if self.focus_id:
            self.root.after_cancel(self.focus_id)
            self.focus_id = None
        if self.poll_id:
            self.root.after_cancel(self.poll_id)
            self.poll_id = None
        self.worker.stop()
        self.root.unbind_class(self.key_tag, "<KeyPress>")
        self.root.destroy()


def launch() -> None:
    root = tk.Tk()
    app = LwtSnakeApp(root)
    try:
        root.mainloop()
    finally:
        app.worker.stop()
        app.worker.join(timeout=6)
