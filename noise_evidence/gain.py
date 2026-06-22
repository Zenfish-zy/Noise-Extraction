"""不失真响度放大。

核心原理（向用户的承诺）:
  纯线性缩放——每个采样点乘以同一系数 k。波形形状逐点不变，
  频率/音色/音调完全保留，只是"更响"。只要缩放后峰值不超过
  target_peak（<0 dBFS），数学上就不会削波，因此绝不失真。
  这与"音量开大"在物理上等价，但提前烘焙进音频里，
  手机外放也不必开到最大。

两种模式:
  global    —— 整段乘同一系数，保留各事件之间的相对强弱（最忠实）。
  per_event —— 每个事件各自归一到目标响度，让微弱的噪音也清晰可闻
               （便于取证：弱噪音不再"听不见"），但会拉平段间强弱差异。
"""

from __future__ import annotations

import numpy as np

from .config import GainConfig
from .detect import NoiseEvent


def _db_to_lin(db: float) -> float:
    return float(10.0 ** (db / 20.0))


def _peak(data: np.ndarray) -> float:
    return float(np.max(np.abs(data))) if data.size else 0.0


def _gain_for(
    seg_peak: float, target_lin: float, max_gain_lin: float
) -> float:
    """求把 seg_peak 抬到 target 的系数，并夹在 max_gain 以内。"""
    if seg_peak <= 1e-9:
        return 1.0  # 纯静音，放大无意义且会放大数值噪声
    g = target_lin / seg_peak
    return min(g, max_gain_lin)


def apply_global_gain(
    data: np.ndarray, cfg: GainConfig
) -> tuple[np.ndarray, float]:
    """整段统一放大。返回 (放大后波形, 实际增益dB)。"""
    target_lin = _db_to_lin(cfg.target_peak_dbfs)
    max_gain_lin = _db_to_lin(cfg.max_gain_db)
    g = _gain_for(_peak(data), target_lin, max_gain_lin)
    out = (data.astype(np.float32) * g).astype(np.float32)
    return out, 20.0 * np.log10(g + 1e-12)


def amplify_segment(
    seg: np.ndarray, cfg: GainConfig
) -> np.ndarray:
    """把单个事件片段归一到目标响度（per_event 模式用）。"""
    if not cfg.enabled or cfg.mode == "off" or seg.size == 0:
        return seg.astype(np.float32)
    target_lin = _db_to_lin(cfg.target_peak_dbfs)
    max_gain_lin = _db_to_lin(cfg.max_gain_db)
    g = _gain_for(_peak(seg), target_lin, max_gain_lin)
    return (seg.astype(np.float32) * g).astype(np.float32)


def apply_gain(
    data: np.ndarray, cfg: GainConfig
) -> np.ndarray:
    """供"整段试听"用的放大入口（global / off）。

    per_event 模式无法对整段统一处理（每段系数不同），整段试听时
    退化为 global，保证试听响度与导出大致一致；逐段精确放大在导出时完成。
    """
    if not cfg.enabled or cfg.mode == "off" or data.size == 0:
        return data.astype(np.float32)
    out, _ = apply_global_gain(data, cfg)
    return out


def amplify_events_inplace(
    data: np.ndarray, sr: int, events: list[NoiseEvent], cfg: GainConfig
) -> np.ndarray:
    """返回整段的一个副本，其中每个保留事件区间按 per_event 放大。

    仅用于"整段预览逐段放大效果"；真正导出时在 build_highlight 内逐段放大。
    """
    if not cfg.enabled or cfg.mode != "per_event":
        return apply_gain(data, cfg)
    out = data.astype(np.float32).copy()
    for ev in events:
        if not ev.keep:
            continue
        i0, i1 = int(ev.start * sr), int(ev.end * sr)
        out[i0:i1] = amplify_segment(out[i0:i1], cfg)
    return out
