"""Tkinter Canvas user interface for the standalone Snake game."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from app.snake_game_core import Direction, GameStatus, SnakeGame, TickResult


TICK_MILLISECONDS = 140


class SnakeGameApp:
    """Owns the Tk event loop and draws the headless Snake state."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.game = SnakeGame()
        self._after_id: str | None = None

        root.title("LWT 贪吃蛇")
        root.geometry("760x650")
        root.minsize(480, 440)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        heading = ttk.Frame(root, padding=(14, 12, 14, 6))
        heading.grid(row=0, column=0, sticky="ew")
        heading.columnconfigure(0, weight=1)
        ttk.Label(heading, text="贪吃蛇", font=("Microsoft YaHei UI", 20, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        self.score_var = tk.StringVar(value="得分：0")
        ttk.Label(heading, textvariable=self.score_var, font=("Microsoft YaHei UI", 13)).grid(
            row=0, column=1, sticky="e"
        )

        self.canvas = tk.Canvas(root, background="#f4f7f2", highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=14, pady=6)
        self.canvas.bind("<Configure>", lambda _event: self._draw())

        footer = ttk.Frame(root, padding=(14, 6, 14, 12))
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(1, weight=1)
        controls = ttk.Frame(footer)
        controls.grid(row=0, column=0, sticky="w")
        self.start_button = ttk.Button(controls, text="开始游戏", command=self._start_or_resume)
        self.start_button.pack(side="left")
        self.pause_button = ttk.Button(
            controls, text="暂停", command=self._toggle_pause, state="disabled"
        )
        self.pause_button.pack(side="left", padx=(7, 0))
        ttk.Button(controls, text="重新开始", command=self._restart).pack(side="left", padx=(7, 0))

        help_text = "方向键 / WASD：移动　Space：开始/暂停/继续　R：重新开始\n窗口失焦会自动暂停；回到窗口后按 Space 或“继续”。"
        ttk.Label(footer, text=help_text, justify="right", wraplength=420).grid(
            row=0, column=1, sticky="e", padx=(12, 0)
        )
        self.status_var = tk.StringVar(value="准备开始")
        ttk.Label(footer, textvariable=self.status_var).grid(row=1, column=0, columnspan=2, sticky="w", pady=(7, 0))

        root.bind_all("<KeyPress>", self._on_key, add="+")
        root.bind_all("<FocusOut>", self._on_focus_out, add="+")
        root.protocol("WM_DELETE_WINDOW", self._close)
        self._draw()
        self._sync_controls()

    def _start_or_resume(self) -> None:
        if self.game.status is GameStatus.READY:
            self.game.start()
        elif self.game.status is GameStatus.PAUSED:
            self.game.resume()
        elif self.game.status in {GameStatus.GAME_OVER, GameStatus.WON}:
            self.game.restart()
        self._sync_controls()
        self._schedule_tick()

    def _toggle_pause(self) -> None:
        if self.game.status is GameStatus.READY:
            self._start_or_resume()
            return
        if self.game.status is GameStatus.RUNNING:
            self.game.pause()
            self._cancel_tick()
        elif self.game.status is GameStatus.PAUSED:
            self.game.resume()
            self._schedule_tick()
        self._sync_controls()
        self._draw()

    def _restart(self) -> None:
        self._cancel_tick()
        self.game.restart()
        self._sync_controls()
        self._draw()

    def _on_key(self, event: tk.Event[tk.Misc]) -> str | None:
        key = str(event.keysym).lower()
        directions = {
            "up": Direction.UP,
            "w": Direction.UP,
            "right": Direction.RIGHT,
            "d": Direction.RIGHT,
            "down": Direction.DOWN,
            "s": Direction.DOWN,
            "left": Direction.LEFT,
            "a": Direction.LEFT,
        }
        if key in directions:
            self.game.set_direction(directions[key])
            return "break"
        if key == "space":
            self._toggle_pause()
            return "break"
        if key == "r":
            self._restart()
            return "break"
        return None

    def _on_focus_out(self, _event: tk.Event[tk.Misc]) -> None:
        # Defer until focus transitions within this window have settled.
        try:
            self.root.after_idle(self._pause_if_focus_left)
        except tk.TclError:
            return

    def _pause_if_focus_left(self) -> None:
        try:
            focused = self.root.focus_displayof()
            if focused is None or focused.winfo_toplevel() is not self.root:
                if self.game.on_focus_lost():
                    self._cancel_tick()
                    self._sync_controls()
                    self._draw()
        except tk.TclError:
            return

    def _schedule_tick(self) -> None:
        if self.game.status is GameStatus.RUNNING and self._after_id is None:
            self._after_id = self.root.after(TICK_MILLISECONDS, self._on_tick)

    def _cancel_tick(self) -> None:
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _on_tick(self) -> None:
        self._after_id = None
        result = self.game.step()
        if result in {TickResult.WALL_COLLISION, TickResult.SELF_COLLISION}:
            self.status_var.set("游戏结束！按 R 重新开始。")
        elif result is TickResult.WON:
            self.status_var.set("棋盘已填满，你赢了！按 R 再玩一次。")
        self._sync_controls()
        self._draw()
        self._schedule_tick()

    def _sync_controls(self) -> None:
        labels = {
            GameStatus.READY: ("准备开始", "开始游戏", "normal", "disabled"),
            GameStatus.RUNNING: ("游戏进行中", "进行中", "disabled", "normal"),
            GameStatus.PAUSED: ("游戏已暂停", "继续", "normal", "disabled"),
            GameStatus.GAME_OVER: ("游戏结束", "再来一局", "normal", "disabled"),
            GameStatus.WON: ("胜利！", "再来一局", "normal", "disabled"),
        }
        status, start_text, start_state, pause_state = labels[self.game.status]
        self.status_var.set(status)
        self.start_button.configure(text=start_text, state=start_state)
        self.pause_button.configure(
            text="暂停" if self.game.status is GameStatus.RUNNING else "继续",
            state=pause_state,
        )
        self.score_var.set(f"得分：{self.game.score}")

    def _draw(self) -> None:
        self.canvas.delete("all")
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        cell = max(1, min(width // self.game.width, height // self.game.height))
        board_width = cell * self.game.width
        board_height = cell * self.game.height
        left = (width - board_width) // 2
        top = (height - board_height) // 2
        right = left + board_width
        bottom = top + board_height
        self.canvas.create_rectangle(left, top, right, bottom, fill="#e7eee3", outline="#82927e", width=2)
        for x in range(1, self.game.width):
            px = left + x * cell
            self.canvas.create_line(px, top, px, bottom, fill="#d8e1d3")
        for y in range(1, self.game.height):
            py = top + y * cell
            self.canvas.create_line(left, py, right, py, fill="#d8e1d3")
        if self.game.food is not None:
            self._draw_cell(self.game.food, left, top, cell, inset=max(2, cell // 5), color="#d84a45", oval=True)
        for index, point in reversed(list(enumerate(self.game.snake))):
            color = "#1d7758" if index else "#11543e"
            self._draw_cell(point, left, top, cell, inset=max(1, cell // 12), color=color)
        if self.game.status in {GameStatus.READY, GameStatus.PAUSED, GameStatus.GAME_OVER, GameStatus.WON}:
            overlays = {
                GameStatus.READY: "按 Space 或“开始游戏”开始",
                GameStatus.PAUSED: "已暂停　按 Space 或“继续”",
                GameStatus.GAME_OVER: "撞到了！按 R 重新开始",
                GameStatus.WON: "棋盘填满！你赢了",
            }
            center_x = left + board_width / 2
            center_y = top + board_height / 2
            self.canvas.create_rectangle(
                center_x - 180, center_y - 23, center_x + 180, center_y + 23,
                fill="#ffffff", outline="#82927e", stipple="gray50",
            )
            self.canvas.create_text(
                center_x, center_y, text=overlays[self.game.status],
                fill="#183b2e", font=("Microsoft YaHei UI", 13, "bold"),
            )

    def _draw_cell(
        self,
        point: tuple[int, int],
        left: int,
        top: int,
        cell: int,
        *,
        inset: int,
        color: str,
        oval: bool = False,
    ) -> None:
        x, y = point
        box = (left + x * cell + inset, top + y * cell + inset,
               left + (x + 1) * cell - inset, top + (y + 1) * cell - inset)
        drawer = self.canvas.create_oval if oval else self.canvas.create_rectangle
        drawer(*box, fill=color, outline=color)

    def _close(self) -> None:
        self._cancel_tick()
        try:
            self.root.destroy()
        except tk.TclError:
            pass


def launch() -> None:
    root = tk.Tk()
    SnakeGameApp(root)
    root.mainloop()
