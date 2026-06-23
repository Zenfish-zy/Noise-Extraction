use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct AppConfig {
    pub mode: ProcessMode,
    pub denoise: DenoiseConfig,
    pub detect: DetectConfig,
    pub gain: GainConfig,
    pub export: ExportConfig,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ProcessMode {
    FullDenoise,
    FullAmplify,
    Highlight,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct DenoiseConfig {
    pub enabled: bool,
    pub noise_sample_seconds: f64,
    pub prop_decrease: f64,
    pub stationary: bool,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct DetectConfig {
    pub frame_ms: f64,
    pub hop_ms: f64,
    pub sensitivity: Sensitivity,
    pub min_event_seconds: f64,
    pub merge_gap_seconds: f64,
    pub pad_seconds: f64,
    pub min_peak_dbfs: f64,
}

impl Default for DetectConfig {
    fn default() -> Self {
        Self {
            frame_ms: 30.0,
            hop_ms: 10.0,
            sensitivity: Sensitivity::Medium,
            min_event_seconds: 0.08,
            merge_gap_seconds: 0.8,
            pad_seconds: 0.6,
            min_peak_dbfs: -45.0,
        }
    }
}

impl DetectConfig {
    pub fn margin_db(&self) -> f64 {
        match self.sensitivity {
            Sensitivity::High => 6.0,
            Sensitivity::Medium => 10.0,
            Sensitivity::Low => 15.0,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct GainConfig {
    pub enabled: bool,
    pub mode: GainMode,
    pub target_peak_dbfs: f64,
    pub max_gain_db: f64,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct ExportConfig {
    pub gap_seconds: f64,
    pub insert_beep: bool,
    pub beep_hz: f64,
    pub beep_seconds: f64,
    pub out_samplerate: Option<u32>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Sensitivity {
    Low,
    Medium,
    High,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum GainMode {
    Off,
    Global,
    PerEvent,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct NoiseEvent {
    pub start: f64,
    pub end: f64,
    pub peak_dbfs: f64,
    pub rms_dbfs: f64,
    pub low_ratio: f64,
    pub high_ratio: f64,
    pub kind: EventKind,
    pub suspect_self: bool,
    pub keep: bool,
    pub manual: bool,
}

impl NoiseEvent {
    pub fn duration(&self) -> f64 {
        self.end - self.start
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct AnalyzeResult {
    pub samplerate: u32,
    pub duration_seconds: f64,
    pub events: Vec<NoiseEvent>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct WaveformBin {
    pub min: f32,
    pub max: f32,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct WaveformResult {
    pub samplerate: u32,
    pub duration_seconds: f64,
    pub bins: Vec<WaveformBin>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct AudioPreviewResult {
    pub wav_path: String,
    pub samplerate: u32,
    pub duration_seconds: f64,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct ExportResult {
    pub wav_path: String,
    pub csv_path: Option<String>,
    pub kept_events: usize,
    pub duration_seconds: f64,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct ErrorResult {
    pub code: String,
    pub message: String,
    pub details: Option<String>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EventKind {
    Rumble,
    Thud,
    Drag,
    Transient,
    Other,
}
