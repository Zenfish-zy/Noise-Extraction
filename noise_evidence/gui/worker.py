"""后台处理线程。

解耦为两个独立步骤（符合昴君要求的工作流）:
  1. PreprocessWorker —— 导入即运行：解码 +（可选）滤底噪，得到"可试听的整段"。
  2. DetectWorker     —— 手动触发：在预处理后的整段上检测噪音事件。

拆开的好处:
  - 「整段模式」只需第 1 步，根本不必检测、不必切片。
  - 检测参数（灵敏度/合并间隔/前后缓冲/门限）调好后点按钮才跑，所见即所得。
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QThread, Signal

from ..audio_io import load_audio
from ..config import AppConfig
from ..denoise import reduce_noise
from ..detect import detect_events


class PreprocessWorker(QThread):
    """解码并（可选）滤除底噪。导入文件后即运行。

    信号:
      progress(int, str)            — (百分比, 阶段文本)
      finished_ok(object, int)      — (预处理后整段 np.ndarray, 采样率)
      failed(str)                   — 出错信息
    """

    progress = Signal(int, str)
    finished_ok = Signal(object, int)
    failed = Signal(str)

    def __init__(self, path, cfg: AppConfig) -> None:
        super().__init__()
        self._path = path
        self._cfg = cfg

    def run(self) -> None:  # noqa: D401 - QThread 入口
        try:
            self.progress.emit(15, "正在解码音频…")
            data, sr = load_audio(self._path)

            work = data
            if self._cfg.denoise.enabled:
                self.progress.emit(55, "正在滤除底噪…")
                work = reduce_noise(data, sr, self._cfg.denoise)

            self.progress.emit(100, "预处理完成")
            self.finished_ok.emit(work.astype(np.float32), sr)
        except Exception as exc:  # noqa: BLE001 - 兜底回传给界面
            self.failed.emit(str(exc))


class DetectWorker(QThread):
    """在预处理后的整段上检测噪音事件。由「检测事件」按钮手动触发。

    信号:
      progress(int, str)     — (百分比, 阶段文本)
      finished_ok(object)    — 事件列表 list[NoiseEvent]
      failed(str)            — 出错信息
    """

    progress = Signal(int, str)
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, data: np.ndarray, sr: int, cfg: AppConfig) -> None:
        super().__init__()
        self._data = data
        self._sr = sr
        self._cfg = cfg

    def run(self) -> None:  # noqa: D401 - QThread 入口
        try:
            self.progress.emit(30, "正在检测噪音事件…")
            events = detect_events(
                self._data, self._sr, self._cfg.detect, self._cfg.classify
            )
            self.progress.emit(100, f"完成：检测到 {len(events)} 个事件")
            self.finished_ok.emit(events)
        except Exception as exc:  # noqa: BLE001 - 兜底回传给界面
            self.failed.emit(str(exc))
