"""资源路径解析：兼容开发环境与 PyInstaller 打包环境。

PyInstaller 打包后，数据文件被解到 sys._MEIPASS（onefile）或
exe 同级的 _internal（onedir）。这里统一查找 assets 目录。
"""

from __future__ import annotations

import sys
from pathlib import Path


def asset_path(name: str) -> Path:
    """返回 assets/<name> 的绝对路径，开发与打包环境均可用。"""
    # PyInstaller 运行时把根目录放在 sys._MEIPASS
    base = getattr(sys, "_MEIPASS", None)
    candidates = []
    if base:
        candidates.append(Path(base) / "noise_evidence" / "assets" / name)
        candidates.append(Path(base) / "assets" / name)
    # 开发环境：本文件同级的 assets
    candidates.append(Path(__file__).resolve().parent / "assets" / name)
    for c in candidates:
        if c.exists():
            return c
    # 兜底返回最可能的开发路径（即便不存在，调用方可自行处理）
    return Path(__file__).resolve().parent / "assets" / name


def icon_path() -> str:
    """应用图标 .ico 的字符串路径。"""
    return str(asset_path("icon.ico"))
