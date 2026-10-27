"""Desktop entry point for the read-only LWT language teaching lab."""

from __future__ import annotations

import sys


class TkLaunchError(RuntimeError):
    """An expected failure while importing or initializing the Tk desktop UI."""


def launch() -> None:
    try:
        import tkinter as tk
    except ImportError as error:
        raise TkLaunchError("当前 Python 无法导入 Tkinter，语义实验室需要可用的 Tk 支持。") from error
    root = None
    try:
        from app.language_lab_ui import LanguageLabApp

        root = tk.Tk()
        LanguageLabApp(root)
        root.mainloop()
    except tk.TclError as error:
        if root is not None:
            try:
                root.destroy()
            except tk.TclError:
                pass
        raise TkLaunchError(f"无法创建 Tkinter 语义实验室窗口：{error}") from error


def main() -> int:
    try:
        launch()
    except TkLaunchError as error:
        print(f"LWT 语义实验室不可用：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
