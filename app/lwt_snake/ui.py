"""Tk renderer and event forwarding for the external LWT rule engine."""
from __future__ import annotations

from pathlib import Path
import queue
import time
import tkinter as tk
from tkinter import ttk, filedialog

from app.lwt_snake.bridge import GAME_SOURCE
from app.lwt_snake.protocol import GameSnapshot
from app.lwt_snake.session import EngineWorker, Reply
from app.ui_theme import COLORS, apply_theme
from app.lwt_snake.clock import GameClock, focus_is_external
from app.lwt_snake.replay import save


def _install_key_tag(widget, key_tag):
    # Module-level recursion avoids a local recursive closure retaining the app.
    widget.bindtags((key_tag, *widget.bindtags()))
    for child in widget.winfo_children():
        _install_key_tag(child, key_tag)


class LwtSnakeApp:
    def __init__(self, root: tk.Tk, *, source: Path = GAME_SOURCE, tick_ms: int = 140) -> None:
        self.root, self.source, self.tick_ms = root, source, tick_ms
        self.clock = GameClock(tick_ms / 1000)
        self.last_command = 'INIT'
        self.mode = 'live'
        self.verified = None
        self.replay_index = 0
        self.play_id = None
        self.next_worker = None
        self.pending_save = None
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
        replay_controls = ttk.Frame(footer)
        replay_controls.grid(row=3, column=0, columnspan=4, sticky='ew', pady=4)
        self.save_button = ttk.Button(replay_controls, text='保存本局', command=self.save_game)
        self.load_button = ttk.Button(replay_controls, text='载入记录', command=self.load_game)
        self.cancel_button = ttk.Button(replay_controls, text='取消验证', command=self.cancel_verify)
        self.live_button = ttk.Button(replay_controls, text='返回实时', command=self.return_live)
        self.previous_button = ttk.Button(replay_controls, text='上一条', command=lambda: self.show_replay(self.replay_index-1))
        self.next_button = ttk.Button(replay_controls, text='下一条', command=lambda: self.show_replay(self.replay_index+1))
        self.play_button = ttk.Button(replay_controls, text='播放/暂停', command=self.toggle_play)
        self.take_button = ttk.Button(replay_controls, text='从此接管', command=self.take_over)
        for i, button in enumerate((self.save_button,self.load_button,self.cancel_button,self.live_button,self.previous_button,self.next_button,self.play_button,self.take_button)):
            button.grid(row=i//4, column=i%4, sticky='ew')
        self.speed = ttk.Combobox(replay_controls, state='readonly', values=('慢','中','快'), width=4)
        self.speed.set('中'); self.speed.grid(row=2,column=0)
        self.position_var = tk.StringVar(value='实时对局')
        ttk.Label(replay_controls, textvariable=self.position_var, wraplength=330).grid(row=2,column=1,columnspan=3,sticky='w')
        self.key_tag = f"LwtSnakeKeys{id(self)}"
        root.bind_class(self.key_tag, "<KeyPress>", self.on_key)
        _install_key_tag(root, self.key_tag)
        root.bind("<FocusOut>", self.on_focus_out, add="+")
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._start_worker()
        self.poll_id = root.after(10, self.poll)

    def _start_worker(self, **options) -> None:
        self.generation += 1
        self.request_id = 0
        self.busy, self.failed = True, False
        self.worker = EngineWorker(self.repository_root, self.replies, self.generation, self.source, **options)
        self.worker.start()
        self.sync_controls()

    def send(self, command: str, *args: object, replace: bool = False) -> None:
        if self.mode != 'live' or self.closing or self.failed or (self.busy and not replace):
            return
        if command == 'TURN' and self.clock.due(time.monotonic()):
            command, args = 'TICK', ()
        if command in {'PAUSE', 'RESET'}:
            self.clock.stop()
            self.cancel_tick()
        next_id = self.request_id + 1
        if self.worker.submit(next_id, command, *args, replace=replace):
            self.request_id = next_id
            self.last_command = command
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
        if self.mode != 'live':
            return None
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
        if self.mode == 'live' and focus_is_external(self.root, focused):
            self.pause()

    def poll(self) -> None:
        self.poll_id = None
        if self.closing:
            return
        if self.next_worker is not None and self.worker.finished.is_set():
            options = self.next_worker
            self.next_worker = None
            self._start_worker(**options)
        while True:
            try:
                reply = self.replies.get_nowait()
            except queue.Empty:
                break
            if reply.generation != self.generation or reply.request_id != self.request_id:
                continue
            if reply.progress:
                self.status_var.set(f'真实 LWT 验证 {reply.progress[0]}/{reply.progress[1]}')
                continue
            self.busy = False
            if reply.verified:
                self.verified = reply.verified
                self.mode = 'replay'
                self.show_replay(0)
            if reply.record:
                self.status_var.set(f'已保存完整前缀：{len(reply.record.transactions)} 条' + (('；'+reply.record.interruption) if reply.record.interruption else ''))
            if reply.error:
                self.failed = reply.fatal
                self.status_var.set("引擎错误：" + reply.error)
            elif reply.snapshot:
                if self.mode == 'handoff': self.mode = 'live'
                self.snapshot = reply.snapshot
                if self.mode == 'live':
                    branched = self.worker.recorder is not None and self.worker.recorder.origin is not None
                    self.position_var.set('实时对局 · 接管分支' if branched else '实时对局')
                if reply.snapshot.phase != 'RUNNING':
                    self.clock.stop()
                    self.cancel_tick()
                elif self.last_command == 'TICK':
                    self.clock.completed(time.monotonic())
                else:
                    self.clock.start(time.monotonic())
                self.status_var.set({"READY": "准备开始", "RUNNING": "游戏进行中", "PAUSED": "已暂停，按 Space 或继续", "GAME_OVER": "碰撞结束，按 R 复位", "WON": "棋盘填满，胜利！按 R 复位"}[reply.snapshot.phase])
                self.score_var.set(f"得分：{reply.snapshot.score}")
            self.sync_controls()
            if self.failed:
                self.clock.stop()
                self.cancel_tick()
            self.draw()
            self.schedule_tick()
        if self.mode in {'loading','handoff'} and not self.busy:
            if self.failed:
                self.mode = 'idle'; self.position_var.set('未验证')
        if self.mode in {'loading','handoff'} and self.worker.stopping.is_set() and self.worker.finished.is_set() and self.next_worker is None:
            self.mode = 'idle'; self.busy = False
            self.position_var.set('已取消 · 未验证')
            self.status_var.set('已取消验证/重建')
        if self.pending_save is not None and not self.busy and self.mode == 'live':
            if not self.failed or self.worker.finished.is_set():
                path, self.pending_save = self.pending_save, None
                if self.failed: self.save_interrupted(path)
                else: self.send('SAVE', path)
        self.sync_controls()
        if self.mode == 'live' and not self.failed and self.worker.recorder is not None and self.worker.recorder.reason:
            self.status_var.set(self.worker.recorder.reason)
        self.poll_id = self.root.after(10, self.poll)

    def sync_controls(self) -> None:
        ready = self.mode == 'live' and self.snapshot is not None and not self.busy and not self.failed
        phase = self.snapshot.phase if self.snapshot else ""
        self.start_button.configure(text="继续" if phase == "PAUSED" else "开始", state="normal" if ready and phase != "RUNNING" else "disabled")
        self.pause_button.configure(state="normal" if ready and phase == "RUNNING" else "disabled")
        self.reset_button.configure(state="normal" if self.mode == 'live' and self.snapshot is not None and not self.failed else "disabled")
        self.retry_button.configure(state="normal" if self.mode == 'live' and self.failed else "disabled")
        replay = self.mode == 'replay' and self.verified is not None
        for button in (self.previous_button,self.next_button,self.play_button): button.configure(state='normal' if replay else 'disabled')
        self.take_button.configure(state='normal' if replay and self.snapshot.phase not in {'GAME_OVER','WON'} else 'disabled')
        self.save_button.configure(state='normal' if self.mode == 'live' and self.worker.recorder is not None else 'disabled')
        self.cancel_button.configure(state='normal' if self.mode in {'loading','handoff'} else 'disabled')

    def schedule_tick(self) -> None:
        if self.mode == 'live' and not self.closing and not self.failed and not self.busy and self.snapshot and self.snapshot.phase == "RUNNING" and self.tick_id is None:
            self.clock.start(time.monotonic())
            delay = max(0, int((self.clock.deadline - time.monotonic()) * 1000))
            self.tick_id = self.root.after(delay, self.tick)

    def cancel_tick(self) -> None:
        if self.tick_id is not None:
            self.root.after_cancel(self.tick_id)
            self.tick_id = None

    def tick(self) -> None:
        self.tick_id = None
        if self.clock.due(time.monotonic()):
            self.send("TICK")
        else:
            self.schedule_tick()

    def save_game(self) -> None:
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension='.json', filetypes=[('对局 JSON','*.json')], confirmoverwrite=True)
        if not path or self.closing: return
        if self.failed and self.worker.finished.is_set():
            self.save_interrupted(Path(path))
        else:
            self.pending_save = Path(path)

    def save_interrupted(self, path):
        try:
            record = self.worker.recorder.snapshot(); save(Path(path), record)
            self.status_var.set(f'已保存中断前缀：{len(record.transactions)} 条')
        except (OSError, ValueError) as error: self.status_var.set('保存失败：'+str(error))

    def load_game(self) -> None:
        path = filedialog.askopenfilename(parent=self.root, filetypes=[('对局 JSON','*.json')])
        if path: self.load_path(Path(path))

    def load_path(self, path: Path) -> None:
        self.transition('loading', replay_path=path)

    def transition(self, mode, **options):
        self.clock.stop(); self.cancel_tick(); self.stop_play()
        self.pending_save = None
        self.mode = mode; self.busy = True; self.failed = False
        self.position_var.set({'loading':'验证中','handoff':'接管重建中','live':'返回实时中'}[mode])
        self.generation += 1  # Invalidate messages before waiting for the old owner.
        self.worker.stop()
        self.next_worker = options
        self.status_var.set('正在回收旧引擎并启动真实 LWT 验证…')
        self.sync_controls()

    def cancel_verify(self):
        self.next_worker = None
        self.worker.stop()
        self.generation += 1
        self.status_var.set('正在取消并回收进程…')

    def return_live(self):
        self.transition('live')

    def show_replay(self, index):
        if self.mode != 'replay' or self.verified is None: return
        self.replay_index = max(0,min(index,len(self.verified.states)-1))
        self.snapshot = self.verified.states[self.replay_index]
        tx = self.verified.replay.transactions[self.replay_index]
        self.position_var.set(f'已验证 {self.replay_index+1}/{len(self.verified.states)} · {tx.request.split("|")[2]}' + (' · 拒绝' if '|ERR|' in tx.response else ''))
        self.score_var.set(f'得分：{self.snapshot.score}')
        self.status_var.set('复盘：按事务前进；转向/暂停不一定移动')
        self.draw(); self.sync_controls()

    def stop_play(self):
        if self.play_id is not None:
            self.root.after_cancel(self.play_id); self.play_id = None

    def toggle_play(self):
        if self.play_id is not None: self.stop_play()
        elif self.mode == 'replay': self.play_next()

    def play_next(self):
        self.play_id = None
        if self.mode != 'replay' or self.replay_index >= len(self.verified.states)-1: return
        self.show_replay(self.replay_index+1)
        self.play_id = self.root.after({'慢':1000,'中':500,'快':150}[self.speed.get()],self.play_next)

    def take_over(self):
        if self.mode == 'replay' and self.snapshot.phase not in {'GAME_OVER','WON'}:
            self.transition('handoff', replay=self.verified.replay, prefix=self.replay_index+1)

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
        self.next_worker = None
        self.stop_play()
        self.clock.stop()
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
