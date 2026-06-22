"""多格式音频解码与 WAV 写出。

- wav/flac/ogg 等 → 直接用 soundfile 读取
- m4a/mp3/aac/mp4 等 → 用 imageio-ffmpeg 自带的 ffmpeg 解码为原始 PCM，
  再喂给 numpy，全程不依赖系统安装的 ffmpeg、不落临时文件。
统一返回单声道 float32 波形 + 采样率。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import soundfile as sf

# soundfile(libsndfile) 原生支持的容器，直接读
_SOUNDFILE_EXTS = {".wav", ".flac", ".ogg", ".oga", ".aiff", ".aif", ".w64"}


def _to_mono(data: np.ndarray) -> np.ndarray:
    """多声道取平均降为单声道，返回 float32。"""
    if data.ndim == 2:
        data = data.mean(axis=1)
    return data.astype(np.float32, copy=False)


def _load_via_soundfile(path: Path) -> tuple[np.ndarray, int]:
    data, sr = sf.read(str(path), dtype="float32", always_2d=False)
    return _to_mono(data), int(sr)


def _probe_samplerate(path: Path) -> int:
    """用 ffmpeg 探测采样率；失败则回退 44100。"""
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    proc = subprocess.run(
        [exe, "-i", str(path), "-hide_banner"],
        capture_output=True,
        text=True,
    )
    # ffmpeg 把流信息写到 stderr，形如 "... 48000 Hz ..."
    for token in proc.stderr.replace(",", " ").split():
        if token.isdigit():
            val = int(token)
            if 8000 <= val <= 192000:
                # 紧邻 "Hz" 的数字才是采样率，做一次邻近校验
                idx = proc.stderr.find(token)
                if "Hz" in proc.stderr[idx : idx + 12]:
                    return val
    return 44100


def _load_via_ffmpeg(path: Path) -> tuple[np.ndarray, int]:
    """解码任意 ffmpeg 支持的格式为单声道 float32 PCM。"""
    sr = _probe_samplerate(path)
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        exe,
        "-i", str(path),
        "-f", "f32le",      # 32-bit float little-endian 裸 PCM
        "-acodec", "pcm_f32le",
        "-ac", "1",          # 单声道
        "-ar", str(sr),
        "-hide_banner",
        "-loglevel", "error",
        "pipe:1",
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg 解码失败: {path.name}\n{proc.stderr.decode(errors='ignore')}"
        )
    data = np.frombuffer(proc.stdout, dtype=np.float32)
    return data.copy(), sr


def load_audio(path: str | Path) -> tuple[np.ndarray, int]:
    """加载音频，统一返回 (单声道 float32 波形, 采样率)。"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"找不到音频文件: {path}")
    if path.suffix.lower() in _SOUNDFILE_EXTS:
        return _load_via_soundfile(path)
    return _load_via_ffmpeg(path)


def save_wav(path: str | Path, data: np.ndarray, samplerate: int) -> None:
    """写出 16-bit PCM WAV（通用、体积适中、各处可播放）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # 防削波：超出 [-1,1] 时整体归一
    peak = float(np.max(np.abs(data))) if data.size else 0.0
    if peak > 1.0:
        data = data / peak
    sf.write(str(path), data.astype(np.float32), samplerate, subtype="PCM_16")
