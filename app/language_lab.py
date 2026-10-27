"""Desktop entry point for the read-only LWT language teaching lab."""

from __future__ import annotations

import sys


def launch() -> None:
    try:
        import tkinter as tk
    except ImportError as error:
        raise RuntimeError("当前 Python 无法导入 Tkinter，语义实验室需要可用的 Tk 支持。") from error
    try:
        from app.language_lab_ui import LanguageLabApp

        root = tk.Tk()
        LanguageLabApp(root)
        root.mainloop()
    except tk.TclError as error:
        raise RuntimeError(f"无法创建 Tkinter 语义实验室窗口：{error}") from error


if __name__ == "__main__":
    try:
        launch()
    except RuntimeError as error:
        print(f"LWT 语义实验室不可用：{error}", file=sys.stderr)
