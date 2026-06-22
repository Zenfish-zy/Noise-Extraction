"""楼上噪音取证助手 — 程序入口（瘦封装）。

两种启动方式，最终都走同一个 noise_evidence.app.main：
  uv run noise-evidence      # 安装后的命令行入口
  uv run python main.py      # 直接跑脚本
"""

from __future__ import annotations

from noise_evidence.app import main

if __name__ == "__main__":
    main()
