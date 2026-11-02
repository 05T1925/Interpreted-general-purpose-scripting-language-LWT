"""Read-only Tk viewer for verified LWT same-observation, one-tick experiments."""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, ttk

from app.lwt_snake.replay import ROOT

CATALOG = ROOT / 'app/lwt_snake/strategies/strategy-catalog.json'
DEMOS = (ROOT / 'reports/s40-demo', ROOT / 'reports/s40-divergence')


class CounterfactualWindow:
    def __init__(self, root, *, runner=None):
        self.root = root
        self.root.title('LWT 策略反事实实验台 · 同一观察轨迹')
        self.root.minsize(700, 480)
        self.runner = runner or self._run
        self.generation = 0
        self.closed = False
        self.busy = False
        self.cancel = threading.Event()
        self.loaded_witness = None
        self.results = queue.Queue()
        self.choice = tk.IntVar(value=1)
        self.status = tk.StringVar(value='选择固定演示并验真；分支只推进一步。')
        top = ttk.Frame(root, padding=12)
        top.pack(fill='x')
        ttk.Label(top, text='Python 展示前端；策略和游戏规则均由真实 LWT CLI 运行。').pack(anchor='w')
        ttk.Label(top, text='同一已验观察轨迹上的响应，不是候选策略自然对局的同序号一步。').pack(anchor='w')
        self.select = ttk.Combobox(top, state='readonly', values=('第 1 步：同向不同原因', '第 2 步：方向分歧', '本地 S41 见证'))
        self.select.current(1)
        self.select.pack(side='left', padx=(0, 8))
        self.select.bind('<<ComboboxSelected>>', self._changed)
        self.prev = ttk.Button(top, text='上一步', command=lambda: self._choose(0))
        self.prev.pack(side='left')
        self.next = ttk.Button(top, text='下一步', command=lambda: self._choose(1))
        self.next.pack(side='left')
        self.load_button = ttk.Button(top, text='加载见证目录', command=self.load_witness)
        self.load_button.pack(side='left', padx=8)
        self.verify_button = ttk.Button(top, text='重新验真', command=self.verify)
        self.verify_button.pack(side='left', padx=8)
        ttk.Label(root, textvariable=self.status, padding=(12, 4)).pack(anchor='w')
        self.text = tk.Text(root, wrap='word', state='disabled', height=20)
        self.text.pack(fill='both', expand=True, padx=12, pady=8)
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.verify()

    def _choose(self, index):
        self.select.current(index)
        self._changed()

    def load_witness(self):
        selected = filedialog.askdirectory(title='选择 S41 见证目录')
        if not selected:
            return
        self.loaded_witness = Path(selected)
        self.select.current(2)
        self._changed()

    def _current_folder(self):
        return self.loaded_witness if self.select.current() == 2 else DEMOS[self.select.current()]

    def _changed(self, _event=None):
        self.generation += 1
        if self.busy:
            self.cancel.set()
        self._set_text('条件已改变；旧结果已清除。请重新验真。')
        self.status.set('等待验真')
        self.verify_button.configure(state='normal' if not self.busy else 'disabled')

    def _set_text(self, value):
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', value)
        self.text.configure(state='disabled')

    @staticmethod
    def _run(folder, cancel):
        if (folder / 'witness.json').is_file():
            command = [sys.executable, '-m', 'app.lwt_snake.witness', '--verify', str(folder), '--catalog', str(CATALOG)]
            result = CounterfactualWindow._execute(command, cancel)
            if result[1] != 0:
                return result
            if not json.loads((folder / 'witness.json').read_text(encoding='utf-8'))['found']:
                return result
            followup = [sys.executable, '-m', 'app.lwt_snake.counterfactual', '--explain', str(folder / 'analysis'), '--catalog', str(CATALOG)]
            second = CounterfactualWindow._execute(followup, cancel)
            return command, second[1], result[2] + '\n' + second[2], result[3] + second[3]
        command = [sys.executable, '-m', 'app.lwt_snake.counterfactual', '--explain', str(folder), '--catalog', str(CATALOG)]
        return CounterfactualWindow._execute(command, cancel)

    @staticmethod
    def _execute(command, cancel):
        options = {'cwd': ROOT, 'shell': False, 'stdout': subprocess.PIPE, 'stderr': subprocess.PIPE}
        if os.name == 'nt':
            options['creationflags'] = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0) | getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        else:
            options['start_new_session'] = True
        process = subprocess.Popen(command, **options)
        try:
            deadline = time.monotonic() + 90
            while process.poll() is None:
                if cancel.is_set() or time.monotonic() >= deadline:
                    if os.name == 'nt':
                        subprocess.run(['taskkill', '/T', '/F', '/PID', str(process.pid)],
                                       capture_output=True, timeout=5, shell=False)
                    else:
                        os.killpg(process.pid, 15)
                    process.wait(timeout=5)
                    raise RuntimeError('已取消或超时，子进程树已回收')
                cancel.wait(0.05)
            stdout, stderr = process.communicate(timeout=5)
            return command, process.returncode, stdout.decode('utf-8', 'replace'), stderr.decode('utf-8', 'replace')
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)

    def verify(self):
        if self.closed or self.busy:
            return
        self.busy = True
        self.cancel = threading.Event()
        stop = self.cancel
        self.generation += 1
        number = self.generation
        folder = self._current_folder()
        self.verify_button.configure(state='disabled')
        self.status.set('真实 LWT 游戏与策略进程验真中…')
        self._set_text('验证完整原局和候选一步分支，请稍候。')

        def worker():
            try:
                value = self.runner(folder, stop)
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                value = ([], 3, '', f'启动失败或超时：{error}')
            self.results.put((number, folder, value))

        threading.Thread(target=worker, name='lwt-counterfactual-ui', daemon=True).start()
        self.root.after(50, self._poll)

    def _poll(self):
        if self.closed:
            return
        try:
            number, folder, (command, code, stdout, stderr) = self.results.get_nowait()
        except queue.Empty:
            self.root.after(50, self._poll)
            return
        self.busy = False
        self.verify_button.configure(state='normal')
        if number != self.generation or folder != self._current_folder():
            self.status.set('旧请求已丢弃；可重新验真当前步骤。')
            return
        if code != 0:
            self.status.set(f'验真失败，退出码 {code}；可重试。')
            self._set_text(stderr[:2000])
            return
        if (folder / 'witness.json').is_file():
            witness = json.loads((folder / 'witness.json').read_text(encoding='utf-8'))
            if not witness['found']:
                self.status.set('有界搜索验真通过：未发现方向分歧。')
                self._set_text('原始命令：\n' + subprocess.list2cmdline(command) + '\n\n' + stdout + '\n不能据此断言策略等价。')
                return
        analysis_folder = folder / 'analysis' if (folder / 'witness.json').is_file() else folder
        data = json.loads((analysis_folder / 'analysis.json').read_text(encoding='utf-8'))
        witness_text = ''
        if analysis_folder != folder:
            witness = json.loads((folder / 'witness.json').read_text(encoding='utf-8'))
            witness_text = f"搜索：seed 升序、咨询步升序、挑战者 ID 升序；扫描 {witness['scanned']}/{witness['max_observations']}，命中 {witness['case']} 第 {witness['step']} 步。\n"
        self.status.set(f"双层原局与一步分支均已重新验真 · {data['case']} · 第 {data['step']} 步")
        evidence = ['原始命令：', subprocess.list2cmdline(command), '',
                    witness_text,
                    '候选策略响应及一步结果：', stdout, '',
                    '原始 LWA1 请求：', data['candidates'][0]['request'], '',
                    '证据文件：', str(analysis_folder / 'analysis.json')]
        self._set_text('\n'.join(evidence))

    def close(self):
        self.closed = True
        self.generation += 1
        self.cancel.set()
        self.root.destroy()


def main():
    try:
        root = tk.Tk()
    except tk.TclError as error:
        print(f'Tk unavailable: {error}', file=sys.stderr)
        return 3
    CounterfactualWindow(root)
    root.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
