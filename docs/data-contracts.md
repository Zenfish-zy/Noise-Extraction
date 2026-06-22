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
