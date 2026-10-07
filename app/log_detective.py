"""Launch the optional Tkinter LWT Log Detective desktop game."""

from __future__ import annotations

from pathlib import Path
import sys


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    try:
        from app.log_detective_ui import GuiUnavailableError, launch
    except ModuleNotFoundError as error:
        if error.name in {"tkinter", "_tkinter"}:
            print(
                "无法启动图形界面：当前 Python 未安装 Tkinter。请安装带 Tk 支持的 Python，"
                "或继续使用命令行日志分析器。",
                file=sys.stderr,
            )
            return 4
        raise
    try:
        launch()
    except GuiUnavailableError as error:
        print(f"无法启动图形界面：{error}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
