"""Launch the optional standalone Tkinter Snake game."""

from __future__ import annotations

from pathlib import Path
import sys


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    try:
        import tkinter
    except ModuleNotFoundError as error:
        if error.name in {"tkinter", "_tkinter"}:
            print(
                "无法启动贪吃蛇图形界面：当前 Python 未安装 Tkinter。"
                "请使用带 Tk 支持的 Python，或运行无头规则测试。",
                file=sys.stderr,
            )
            return 4
        raise

    try:
        from app.snake_game_ui import launch

        launch()
    except tkinter.TclError as error:
        print(f"无法启动贪吃蛇图形界面：{error}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
