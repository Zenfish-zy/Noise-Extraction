# Data Contracts

The next-generation implementation uses JSON contracts to compare Python reference behavior, Rust core behavior, and Tauri frontend integration.

## AppConfig

```json
{
  "mode": "highlight",
  "denoise": {
    "enabled": true,
    "noise_sample_seconds": 1.0,
    "prop_decrease": 0.9,
    "stationary": true
  },
  "detect": {
    "frame_ms": 30.0,
    "hop_ms": 10.0,
    "sensitivity": "medium",
    "min_event_seconds": 0.08,
    "merge_gap_seconds": 0.8,
    "pad_seconds": 0.6,
    "min_peak_dbfs": -45.0
  },
  "gain": {
    "enabled": true,
    "mode": "per_event",
    "target_peak_dbfs": -1.0,
    "max_gain_db": 36.0
  },
  "export": {
    "gap_seconds": 0.5,
    "insert_beep": true,
    "beep_hz": 880.0,
    "beep_seconds": 0.12,
    "out_samplerate": null
  }
}
```

## NoiseEvent

```json
{
  "start": 0.9,
  "end": 1.6,
  "peak_dbfs": -3.1,
  "rms_dbfs": -8.2,
  "low_ratio": 0.62,
  "high_ratio": 0.04,
  "kind": "rumble",
  "suspect_self": false,
  "keep": true,
  "manual": false
}
```

## AnalyzeResult

```json
{
  "samplerate": 48000,
  "duration_seconds": 123.45,
  "events": []
}
```

## ExportResult

```json
{
  "wav_path": "C:\\\\Users\\\\name\\\\Desktop\\\\noise_highlight.wav",
  "csv_path": "C:\\\\Users\\\\name\\\\Desktop\\\\noise_report.csv",
  "kept_events": 3,
  "duration_seconds": 18.42
}
```

## Audio Input

Current next-generation support:

- `noise-cli analyze-audio --input <audio> --config <json>` reads local audio files.
- Tauri command `analyze_audio(input_path, detect)` reads local audio files selected by the frontend dialog.
- Supported input families are currently handled through Symphonia: `m4a/mp4/aac`, `mp3`, `wav`, `flac`, `ogg/oga`.
- Audio is decoded to mono `f32`; multichannel files are averaged per frame.
- `noise-cli export-audio --input <audio> --output <wav> --config <json> [--csv <report.csv>]` writes a WAV export and, in highlight mode, an optional CSV report.
- Tauri command `manual_event(input_path, start, end)` analyzes a user-selected span from the original audio and returns a full `NoiseEvent` with `manual: true`.
- Tauri command `export_audio(input_path, wav_path, csv_path, config, events)` writes full-mode WAV or highlight-mode WAV + CSV.
- In `highlight` mode, `events` is the user-reviewed event list from the frontend. Deleted events are absent, `keep: false` events are excluded from the WAV highlight, and manual events are included when `keep: true`.
- In full modes, `events` is ignored and only WAV is exported.

Current limitations:

- Exotic codecs outside Symphonia's enabled decoders may still need the Python reference app or a future ffmpeg fallback.
- Noise reduction is not yet implemented in the Rust backend.

## ErrorResult

```json
{
  "code": "decode_failed",
  "message": "ffmpeg decode failed",
  "details": "stderr or library error"
}
```

## Enum Values

### mode

- `full_denoise`
- `full_amplify`
- `highlight`

### sensitivity

- `low`
- `medium`
- `high`

### gain.mode

- `off`
- `global`
- `per_event`

### event.kind

- `rumble`
- `thud`
- `drag`
- `transient`
- `other`

## Compatibility Rules

- Times are seconds as `f64`/number.
- Audio samples are mono `f32` internally.
- JSON field names use `snake_case`.
- Unknown fields should be ignored by readers.
- Missing required fields should produce a structured error.
