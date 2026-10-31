"""Launch with python -m app.lwt_snake."""
import sys


def main() -> int:
    try:
        import tkinter as tk
        from app.lwt_snake.ui import launch
    except ImportError as error:
        print(f"无法启动 LWT 驱动贪吃蛇：Tkinter 不可用：{error}", file=sys.stderr)
        return 4
    try:
        launch()
    except tk.TclError as error:
        print(f"无法启动 LWT 驱动贪吃蛇：{error}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
