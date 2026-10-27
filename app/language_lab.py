"""Desktop entry point for the read-only LWT language teaching lab."""

from __future__ import annotations

import tkinter as tk
import sys

from app.language_lab_ui import LanguageLabApp


def launch() -> None:
    try:
        root = tk.Tk()
    except tk.TclError as error:
        raise RuntimeError(f"无法创建 Tkinter 语义实验室窗口：{error}") from error
    LanguageLabApp(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        launch()
    except RuntimeError as error:
        print(f"LWT 语义实验室不可用：{error}", file=sys.stderr)
