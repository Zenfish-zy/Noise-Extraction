# Next Architecture

下一代版本目标：保留当前 Python 版作为稳定参考实现，同时在 `next/` 下建设更易扩展、更好看的桌面应用。

## Decision

采用 `Tauri + React/TypeScript + Rust core`。

理由：

- UI 使用 Web 技术实现，视觉自由度高，适合做放松、低压、易理解的工具界面。
- Tauri 后端使用 Rust，适合逐步承接音频解码、检测、导出等重计算逻辑。
- 当前本机已经具备 Node/pnpm 和 Rust/Cargo 环境，可以直接推进。
- 当前 Python/PySide6 版本已经可运行，应作为 reference implementation，而不是立刻删除。

## Non-Goals

- 不在第一阶段重写全部功能。
- 不在第一阶段删除 `noise_evidence/`。
- 不在第一阶段追求检测算法完全重写。
- 不把本地录音、导出结果、打包产物纳入版本库。

## Repository Layout

```text
Noise-Extraction/
├─ noise_evidence/              # Python stable/reference app
├─ tests/                       # Python reference behavior tests
├─ docs/
│  ├─ architecture-next.md
│  └─ migration-plan.md
├─ next/
│  ├─ README.md
│  ├─ desktop/                  # Future Tauri desktop app
│  ├─ crates/
│  │  ├─ noise-types/           # Shared config/event/report types
│  │  ├─ noise-core/            # Audio processing core
│  │  ├─ noise-io/              # Audio loading/decoding boundary
│  │  └─ noise-cli/             # CLI bridge and golden-test runner
│  └─ fixtures/                 # Synthetic and sanitized test fixtures
└─ README.md
```

## Module Boundaries

### Python Reference

Current responsibilities:

- Working desktop UI.
- Baseline event detection behavior.
- Baseline export behavior.
- Regression oracle for Rust core.

### React Frontend

Future responsibilities:

- Workflow navigation.
- Calm visual layout.
- Waveform/timeline interaction.
- Event review table.
- Settings panels.
- Export progress and result summary.

Frontend must not contain audio-processing logic.

### Tauri Backend

Future responsibilities:

- File dialogs and local file access.
- Calling Rust core.
- Long-running task orchestration.
- Progress events to frontend.
- Error normalization.

### Rust Core

Future responsibilities:

- Event detection and merge logic.
- Manual event construction.

### Rust IO

Current responsibilities:

- Common local audio decode to mono `f32`.
- Supported input families: `m4a/mp4/aac`, `mp3`, `wav`, `flac`, `ogg/oga`.
- Stereo/multichannel downmix.
- Mono 16-bit WAV writing.
- UTF-8-BOM CSV report writing.
- Sampling-rate and duration reporting.

Future responsibilities:

- Optional ffmpeg fallback for codecs outside Symphonia's enabled decoders.

### Rust Processing Pipeline

Future responsibilities:

- Optional noise reduction.
- Preprocess/analyze/export orchestration.

Rust processing modules must be usable without the GUI through `noise-cli`.

## Data Contracts

Initial contract should be JSON-first:

```json
{
  "mode": "highlight",
  "denoise": { "enabled": true },
  "detect": {
    "sensitivity": "medium",
    "min_peak_dbfs": -45.0,
    "merge_gap_seconds": 0.8,
    "pad_seconds": 0.6
  },
  "export": {
    "gap_seconds": 0.5,
    "insert_beep": true
  },
  "gain": {
    "enabled": true,
    "mode": "per_event"
  }
}
```

Events:

```json
{
  "start": 1.2,
  "end": 2.1,
  "peak_dbfs": -8.4,
  "rms_dbfs": -18.2,
  "low_ratio": 0.66,
  "high_ratio": 0.08,
  "kind": "rumble",
  "suspect_self": false,
  "keep": true,
  "manual": false
}
```

## UI Direction

The app should feel quiet and task-focused:

- Warm off-white background.
- Low-saturation green/gray accent colors.
- Large waveform/timeline as the central object.
- Clear workflow steps, but no tutorial-like text on the main surface.
- Side panel for current selection and settings.
- Export result shown as a compact completion sheet.

Primary screens:

1. Import and mode selection.
2. Preprocess progress.
3. Detection and review.
4. Manual edit.
5. Export summary.

## Risk Register

| Risk | Mitigation |
|---|---|
| Rust audio decode differs from Python/ffmpeg | Keep Python fixtures and golden tests. Add ffmpeg fallback if needed. |
| Tauri UI scope grows too fast | Build static prototype first, then wire commands. |
| Detection output changes unexpectedly | Compare event count, starts/ends, and exported CSV against fixtures. |
| Windows packaging edge cases | Keep current PyInstaller app until Tauri build is verified. |
| User recordings leak into Git | Keep `.gitignore` strict and use sanitized fixtures only. |
