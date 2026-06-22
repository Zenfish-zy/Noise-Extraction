"""导出：精选噪音合集音频 + CSV 证据报告。

诚实原则（取证可信度）:
  - 原始录音永远不动，只另存噪音提取。
  - 合集段间默认插入短促 beep + 静音，明确告知"这是剪辑过的合集"，
    并在 CSV 里保留每段的原始起止时间戳，让证据经得起追问。
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from .audio_io import save_wav
from .config import ExportConfig, GainConfig
from .detect import NoiseEvent
from .gain import amplify_segment, apply_global_gain


def _format_hms(seconds: float) -> str:
    """秒 → HH:MM:SS.mmm，便于在报告里对照原始录音。"""
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _beep(sr: int, cfg: ExportConfig) -> np.ndarray:
    """生成短促分隔提示音（带淡入淡出，避免爆音）。"""
    n = max(1, int(cfg.beep_seconds * sr))
    t = np.arange(n) / sr
    tone = 0.2 * np.sin(2.0 * np.pi * cfg.beep_hz * t).astype(np.float32)
    fade = max(1, n // 10)
    env = np.ones(n, dtype=np.float32)
    env[:fade] = np.linspace(0.0, 1.0, fade)
    env[-fade:] = np.linspace(1.0, 0.0, fade)
    return tone * env


def build_highlight(
    data: np.ndarray, sr: int, events: list[NoiseEvent],
    cfg: ExportConfig, gcfg: GainConfig | None = None,
) -> tuple[np.ndarray, list[tuple[NoiseEvent, float]]]:
    """把选中(keep=True)的事件拼成一段密集合集。

    gcfg 给定时按其放大:
      per_event —— 每段拼接前各自归一；global —— 拼接后整体归一。
    返回 (合集波形, [(事件, 该事件在合集中的起始秒)])，
    后者用于在报告里标注"合集内位置 ↔ 原始位置"的对照。
    """
    kept = [e for e in events if e.keep]
    if not kept:
        return np.zeros(0, dtype=np.float32), []

    gap = np.zeros(int(cfg.gap_seconds * sr), dtype=np.float32)
    sep = _beep(sr, cfg) if cfg.insert_beep else np.zeros(0, dtype=np.float32)

    per_event = bool(gcfg and gcfg.enabled and gcfg.mode == "per_event")

    pieces: list[np.ndarray] = []
    mapping: list[tuple[NoiseEvent, float]] = []
    cursor = 0  # 当前合集样本位置
    for idx, ev in enumerate(kept):
        i0, i1 = int(ev.start * sr), int(ev.end * sr)
        seg = data[i0:i1]
        if per_event:
            seg = amplify_segment(seg, gcfg)
        if idx > 0:
            pieces.append(gap)
            cursor += gap.size
            if sep.size:
                pieces.append(sep)
                cursor += sep.size
                pieces.append(gap)
                cursor += gap.size
        mapping.append((ev, cursor / sr))
        pieces.append(seg)
        cursor += seg.size

    highlight = np.concatenate(pieces).astype(np.float32)
    # 全局模式：整段统一放大（保留各事件相对强弱）
    if gcfg and gcfg.enabled and gcfg.mode == "global":
        highlight, _ = apply_global_gain(highlight, gcfg)
    return highlight, mapping


def _resample_if_needed(
    data: np.ndarray, sr: int, out_sr: int
) -> np.ndarray:
    """按需做简单线性重采样（导出场景对音质要求不苛刻）。"""
    if out_sr == sr or data.size == 0:
        return data
    n_out = int(data.size * out_sr / sr)
    x_old = np.linspace(0.0, 1.0, data.size, endpoint=False)
    x_new = np.linspace(0.0, 1.0, n_out, endpoint=False)
    return np.interp(x_new, x_old, data).astype(np.float32)


def export_full_wav(
    data: np.ndarray, sr: int, out_path: str | Path,
    cfg: ExportConfig, gcfg: GainConfig | None = None,
) -> None:
    """整段模式：导出完整的一整段 WAV（不切片、不拼合集）。

    gcfg 给定且启用时，对整段统一放大（global / per_event 均退化为整段统一，
    因为整段没有"逐事件"概念）。
    """
    if data.size == 0:
        raise ValueError("没有可导出的音频。")
    out = data.astype(np.float32)
    if gcfg and gcfg.enabled and gcfg.mode != "off":
        out, _ = apply_global_gain(out, gcfg)
    out_sr = cfg.out_samplerate or sr
    out = _resample_if_needed(out, sr, out_sr)
    save_wav(out_path, out, out_sr)


def export_highlight_wav(
    data: np.ndarray, sr: int, events: list[NoiseEvent],
    out_path: str | Path, cfg: ExportConfig, gcfg: GainConfig | None = None,
) -> int:
    """导出噪音提取 WAV，返回拼入的事件数。"""
    highlight, _ = build_highlight(data, sr, events, cfg, gcfg)
    if highlight.size == 0:
        raise ValueError("没有选中的事件，无法导出合集。请至少保留一个事件。")
    out_sr = cfg.out_samplerate or sr
    highlight = _resample_if_needed(highlight, sr, out_sr)
    save_wav(out_path, highlight, out_sr)
    return sum(1 for e in events if e.keep)


def export_report_csv(
    events: list[NoiseEvent], out_path: str | Path,
) -> None:
    """导出 CSV 证据报告（UTF-8-BOM，Excel 直接可读）。

    保留每段相对原始录音的起止时间戳，让"密集合集"可追溯回原始位置，
    经得起对方质疑。
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "序号", "保留", "来源", "类型", "疑似录制混入",
            "原始起始", "原始结束", "时长(秒)",
            "峰值(dBFS)", "平均(dBFS)", "低频占比", "高频占比",
        ])
        for i, ev in enumerate(events, 1):
            w.writerow([
                i,
                "是" if ev.keep else "否",
                "手动" if ev.manual else "自动",
                ev.label,
                "是" if ev.suspect_self else "",
                _format_hms(ev.start),
                _format_hms(ev.end),
                f"{ev.duration:.2f}",
                f"{ev.peak_dbfs:.1f}",
                f"{ev.rms_dbfs:.1f}",
                f"{ev.low_ratio:.2f}",
                f"{ev.high_ratio:.2f}",
            ])


def summarize(events: list[NoiseEvent]) -> dict:
    """汇总统计，供界面右侧面板展示。"""
    from collections import Counter

    kept = [e for e in events if e.keep]
    return {
        "total": len(events),
        "kept": len(kept),
        "suspect": sum(1 for e in events if e.suspect_self),
        "manual": sum(1 for e in events if e.manual),
        "kept_duration": sum(e.duration for e in kept),
        "by_kind": dict(Counter(e.kind for e in events)),
    }
