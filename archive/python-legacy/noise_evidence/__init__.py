"""Noise Evidence — 楼上噪音取证分析工具。

模块职责（遵循单一职责原则）:
    config   — 全局可调参数
    audio_io — 多格式音频解码 / WAV 写出
    denoise  — 底噪频谱门控
    detect   — 噪音事件检测与分类
    export   — 噪音提取拼接 + CSV 证据报告
    app      — PySide6 桌面界面
"""

__version__ = "0.1.0"
