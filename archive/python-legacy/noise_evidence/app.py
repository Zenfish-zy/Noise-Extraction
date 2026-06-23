"""楼上噪音取证助手 — 应用入口（包内）。

放在包内是为了让安装后的命令行入口 `noise-evidence` 能稳定找到它，
不依赖项目根目录是否在 sys.path 上。

运行方式:
  uv run noise-evidence      # 命令行入口
  uv run python main.py      # 直接跑根目录脚本
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .gui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("楼上噪音取证助手")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
