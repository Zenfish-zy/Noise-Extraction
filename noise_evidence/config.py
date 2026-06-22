"""全局可调参数。集中放置，避免魔法数字散落各处（DRY）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ProcessMode(str, Enum):
    """录音处理模式：决定整条流水线如何分叉。

    - FULL_DENOISE   整段·只滤底噪：输出完整一整段，不检测、不切片。
    - FULL_AMPLIFY   整段·滤底噪+放大：完整一整段并整体放大。
    - HIGHLIGHT      智能切片合集：检测事件→切片→拼成密集噪音合集（默认）。
    """

    FULL_DENOISE = "full_denoise"
    FULL_AMPLIFY = "full_amplify"
    HIGHLIGHT = "highlight"

    @property
    def is_full(self) -> bool:
        """是否为「整段」模式（不切片）。"""
        return self in (ProcessMode.FULL_DENOISE, ProcessMode.FULL_AMPLIFY)


@dataclass
class DenoiseConfig:
    """底噪滤除参数。"""

    enabled: bool = True
    # 噪声样本：自动从整段里找最安静的窗口（秒）
    noise_sample_seconds: float = 1.0
    # noisereduce 的削减强度 0~1，越大滤得越狠（也越可能伤及噪音事件本身）
    prop_decrease: float = 0.9
    # 平稳噪声假设：环境底噪通常是平稳的
    stationary: bool = True


@dataclass
class DetectConfig:
    """事件检测参数。"""

    # 分析帧
    frame_ms: float = 30.0
    hop_ms: float = 10.0
    # 灵敏度档位: "high"(多框) / "medium" / "low"(少误报)
    sensitivity: str = "medium"
    # 阈值 = 噪声基准 + margin_db；不同灵敏度对应不同 margin
    margin_db: dict[str, float] = field(
        default_factory=lambda: {"high": 6.0, "medium": 10.0, "low": 15.0}
    )
    # 事件最短时长，短于此忽略（秒）
    min_event_seconds: float = 0.08
    # 相邻事件间隔小于此则合并为一段（秒）。
    # 默认 0.8s 更贴近"连续几下楼板声=一次持续噪音事件"的复核习惯。
    merge_gap_seconds: float = 0.8
    # 事件前后各留出的padding（秒），给噪音"始末感"：
    # 听得出它怎么起、怎么落，而不是突然冒出又突然消失。
    pad_seconds: float = 0.6
    # 绝对最小峰值门限（dBFS）：峰值低于此的事件视为太弱(疑似误检)直接丢弃。
    # 比"噪声基准+margin"更硬，专治"框出来却听不见"的片段。
    min_peak_dbfs: float = -45.0

    def margin(self) -> float:
        return self.margin_db.get(self.sensitivity, 10.0)


@dataclass
class ClassifyConfig:
    """事件分类 / 疑似混入判定的频谱阈值。"""

    # 低频上限（Hz）：楼板传导的脚步/闷响能量集中在低频
    low_freq_hz: float = 300.0
    # 高频下限（Hz）：近场尖锐声/手碰设备含大量高频
    high_freq_hz: float = 4000.0
    # 低频能量占比高于此 → 判为低频闷响（脚步/跺脚/掉落）
    low_ratio_thresh: float = 0.55
    # 高频能量占比高于此 + 高幅度 → 疑似录制混入（近场）
    high_ratio_suspect: float = 0.35
    # 峰值接近满刻度（dBFS）视为近场过响，疑似碰到设备
    clip_dbfs_suspect: float = -3.0


@dataclass
class GainConfig:
    """响度放大（不失真）参数。

    原理: 纯线性缩放波形。只要缩放后峰值不超过 target_peak_dbfs(<0)，
    数学上就不会削波，因此不失真——只是"声音更大"，不改变波形形状。
    """

    enabled: bool = True
    # 放大模式:
    #   "off"      不放大
    #   "global"   全局归一化：整段乘同一系数，保留各事件相对强弱
    #   "per_event" 逐段归一化：每个保留事件各自归一到目标，使弱噪音也听得清
    mode: str = "per_event"
    # 目标峰值（dBFS），留 1dB 余量防止重采样/播放器轻微过冲
    target_peak_dbfs: float = -1.0
    # 单段最大允许增益（dB）：防止把极安静的段放大到全是底噪/喷麦
    max_gain_db: float = 36.0


@dataclass
class ExportConfig:
    """导出参数。"""

    # 段间静音间隔（秒）——可在界面调节，让合集疏密随心
    gap_seconds: float = 0.5
    # 段间是否插入分隔提示音（短促 beep），标明这是剪辑过的合集
    insert_beep: bool = True
    beep_hz: float = 880.0
    beep_seconds: float = 0.12
    # 导出采样率（None=保持原始）
    out_samplerate: int | None = None


@dataclass
class AppConfig:
    # 处理模式：默认「智能切片合集」，保持与历史行为一致
    mode: ProcessMode = ProcessMode.HIGHLIGHT
    denoise: DenoiseConfig = field(default_factory=DenoiseConfig)
    detect: DetectConfig = field(default_factory=DetectConfig)
    classify: ClassifyConfig = field(default_factory=ClassifyConfig)
    gain: GainConfig = field(default_factory=GainConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
