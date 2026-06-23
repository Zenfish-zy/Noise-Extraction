"""噪音事件检测与分类。

流程:
  1. 分帧算 RMS → dB 曲线
  2. 以"噪声基准 + margin"为阈值，找出高于阈值的帧
  3. 合并相邻事件、过滤过短事件、前后加 padding
  4. 对每个事件做频谱分析 → 分类(低频闷响/瞬态/拖拽/其他)
  5. 标记疑似"录制时混入"的事件(近场宽频高幅)，交用户复核

诚实声明: 第 5 步只是"声学线索辅助判断"，无法 100% 确定声音来源，
最终保留/排除由用户试听后决定。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config import ClassifyConfig, DetectConfig

# 事件类型中文标签
TYPE_LABELS = {
    "rumble": "低频闷响(脚步/跺脚)",
    "thud": "重击/掉落",
    "drag": "拖拽/摩擦",
    "transient": "尖锐瞬态",
    "other": "其他",
}


@dataclass
class NoiseEvent:
    """一个噪音事件。时间均以秒为单位（相对录音起点）。"""

    start: float
    end: float
    peak_dbfs: float          # 峰值响度
    rms_dbfs: float           # 平均响度
    low_ratio: float          # 低频能量占比
    high_ratio: float         # 高频能量占比
    kind: str = "other"       # 分类 key
    suspect_self: bool = False  # 疑似录制混入
    keep: bool = True         # 用户是否保留（默认保留）
    manual: bool = False      # 是否为用户手动框选添加（区别于自动检测）

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def label(self) -> str:
        return TYPE_LABELS.get(self.kind, self.kind)


def _frame_rms_db(data: np.ndarray, frame: int, hop: int) -> np.ndarray:
    """逐帧 RMS 转 dBFS。返回每帧 dB 值数组。"""
    n = 1 + max(0, (len(data) - frame) // hop)
    out = np.empty(n, dtype=np.float32)
    eps = 1e-10
    for i in range(n):
        seg = data[i * hop : i * hop + frame]
        rms = np.sqrt(np.mean(seg.astype(np.float64) ** 2) + eps)
        out[i] = 20.0 * np.log10(rms + eps)
    return out


def _noise_floor_db(db: np.ndarray) -> float:
    """以较低分位数估计噪声基准（避开偶发事件抬高均值）。"""
    return float(np.percentile(db, 20))


def _merge_and_filter(
    frames_hot: np.ndarray, hop_sec: float, cfg: DetectConfig
) -> list[tuple[float, float]]:
    """把"高于阈值的帧"连成时间段，合并近邻、过滤过短。"""
    spans: list[tuple[float, float]] = []
    in_event = False
    start_idx = 0
    for i, hot in enumerate(frames_hot):
        if hot and not in_event:
            in_event, start_idx = True, i
        elif not hot and in_event:
            in_event = False
            spans.append((start_idx * hop_sec, i * hop_sec))
    if in_event:
        spans.append((start_idx * hop_sec, len(frames_hot) * hop_sec))

    # 合并间隔小于 merge_gap 的相邻段
    merged: list[list[float]] = []
    for s, e in spans:
        if merged and s - merged[-1][1] <= cfg.merge_gap_seconds:
            merged[-1][1] = e
        else:
            merged.append([s, e])

    # 过滤过短事件
    return [
        (s, e) for s, e in merged if (e - s) >= cfg.min_event_seconds
    ]


def _band_ratios(
    seg: np.ndarray, sr: int, ccfg: ClassifyConfig
) -> tuple[float, float]:
    """返回 (低频能量占比, 高频能量占比)。"""
    if seg.size < 16:
        return 0.0, 0.0
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    power = spec ** 2
    total = float(power.sum()) + 1e-12
    freqs = np.fft.rfftfreq(len(seg), d=1.0 / sr)
    low = float(power[freqs <= ccfg.low_freq_hz].sum())
    high = float(power[freqs >= ccfg.high_freq_hz].sum())
    return low / total, high / total


def _classify(
    low_ratio: float, high_ratio: float, duration: float, peak_dbfs: float,
    ccfg: ClassifyConfig,
) -> tuple[str, bool]:
    """返回 (类型key, 是否疑似录制混入)。"""
    # 疑似混入：近场声音常是宽频 + 高频丰富 + 接近过响
    suspect = high_ratio >= ccfg.high_ratio_suspect and peak_dbfs >= ccfg.clip_dbfs_suspect

    if low_ratio >= ccfg.low_ratio_thresh:
        # 低频主导：短促=重击/掉落，较长=脚步连续/跺脚闷响
        kind = "thud" if duration < 0.4 else "rumble"
    elif high_ratio >= ccfg.high_ratio_suspect:
        kind = "transient"
    elif duration >= 0.5:
        kind = "drag"  # 持续、中频为主 → 拖拽摩擦
    else:
        kind = "other"
    return kind, suspect


def _make_event(
    data: np.ndarray, sr: int, start: float, end: float, ccfg: ClassifyConfig
) -> NoiseEvent | None:
    """对 [start, end] 时间区间做响度/频谱分析，构造一个 NoiseEvent。

    被自动检测与人工框选共用（DRY）。区间为空时返回 None。
    """
    i0, i1 = int(start * sr), int(end * sr)
    seg = data[i0:i1]
    if seg.size == 0:
        return None
    peak = float(np.max(np.abs(seg)))
    peak_db = 20.0 * np.log10(peak + 1e-10)
    rms = float(np.sqrt(np.mean(seg.astype(np.float64) ** 2)))
    rms_db = 20.0 * np.log10(rms + 1e-10)
    low_r, high_r = _band_ratios(seg, sr, ccfg)
    kind, suspect = _classify(low_r, high_r, end - start, peak_db, ccfg)
    return NoiseEvent(
        start=start, end=end,
        peak_dbfs=peak_db, rms_dbfs=rms_db,
        low_ratio=low_r, high_ratio=high_r,
        kind=kind, suspect_self=suspect,
    )


def make_manual_event(
    data: np.ndarray, sr: int, start: float, end: float, ccfg: ClassifyConfig
) -> NoiseEvent | None:
    """人工框选构造事件：分析所选区间，标记为手动添加。

    手动事件不受峰值门限过滤——用户既然亲手框了，就尊重其判断。
    """
    total_sec = len(data) / sr
    lo, hi = sorted((start, end))
    lo = max(0.0, min(total_sec, lo))
    hi = max(0.0, min(total_sec, hi))
    ev = _make_event(data, sr, lo, hi, ccfg)
    if ev is not None:
        ev.manual = True
    return ev


def detect_events(
    data: np.ndarray, sr: int, cfg: DetectConfig, ccfg: ClassifyConfig
) -> list[NoiseEvent]:
    """检测并分类噪音事件。"""
    if data.size == 0:
        return []

    frame = max(1, int(cfg.frame_ms * sr / 1000))
    hop = max(1, int(cfg.hop_ms * sr / 1000))
    hop_sec = hop / sr

    db = _frame_rms_db(data, frame, hop)
    floor = _noise_floor_db(db)
    threshold = floor + cfg.margin()
    frames_hot = db > threshold

    spans = _merge_and_filter(frames_hot, hop_sec, cfg)

    events: list[NoiseEvent] = []
    total_sec = len(data) / sr
    for s, e in spans:
        # 加 padding 并裁剪到边界
        s_pad = max(0.0, s - cfg.pad_seconds)
        e_pad = min(total_sec, e + cfg.pad_seconds)
        ev = _make_event(data, sr, s_pad, e_pad, ccfg)
        if ev is None:
            continue
        # 硬门限：峰值太弱的片段（听不见、疑似误检）直接丢弃
        if ev.peak_dbfs < cfg.min_peak_dbfs:
            continue
        events.append(ev)
    return events
