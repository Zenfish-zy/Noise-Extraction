#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ProcessMode {
    FullDenoise,
    FullAmplify,
    Highlight,
}

#[derive(Clone, Debug, PartialEq)]
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

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Sensitivity {
    Low,
    Medium,
    High,
}

#[derive(Clone, Debug, PartialEq)]
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

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum EventKind {
    Rumble,
    Thud,
    Drag,
    Transient,
    Other,
}
