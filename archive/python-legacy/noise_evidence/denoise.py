"""底噪滤除：自动取最安静窗口作噪声样本，做频谱门控。

环境底噪（空调、电流、远处车流）通常是平稳的，可用一段"只有底噪、
没有事件"的样本估计其频谱，再从全段中扣除。这里自动挑选 RMS 最低的
窗口作样本，无需用户手动指定。
"""

from __future__ import annotations

import numpy as np

from .config import DenoiseConfig


def _quietest_window(data: np.ndarray, sr: int, win_sec: float) -> np.ndarray:
    """返回整段中能量最低的 win_sec 窗口（最可能是纯底噪）。"""
    win = max(1, int(win_sec * sr))
    if len(data) <= win:
        return data
    # 用滑动 RMS 找最安静处；步长取窗口的 1/4 兼顾速度与精度
    step = max(1, win // 4)
    best_start, best_energy = 0, np.inf
    sq = data.astype(np.float64) ** 2
    for start in range(0, len(data) - win, step):
        energy = float(sq[start : start + win].mean())
        if energy < best_energy:
            best_energy, best_start = energy, start
    return data[best_start : best_start + win]


def reduce_noise(
    data: np.ndarray, sr: int, cfg: DenoiseConfig
) -> np.ndarray:
    """对整段做底噪滤除，返回同长度 float32 波形。"""
    if not cfg.enabled or data.size == 0:
        return data

    # 延迟导入：noisereduce 较重，仅在需要时加载
    import noisereduce as nr

    noise_clip = _quietest_window(data, sr, cfg.noise_sample_seconds)
    reduced = nr.reduce_noise(
        y=data,
        sr=sr,
        y_noise=noise_clip,
        stationary=cfg.stationary,
        prop_decrease=cfg.prop_decrease,
    )
    return reduced.astype(np.float32, copy=False)
