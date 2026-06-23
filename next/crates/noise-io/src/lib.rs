use std::fmt;
use std::fs;
use std::io::Write;
use std::path::Path;

use noise_types::{EventKind, NoiseEvent};

#[derive(Clone, Debug, PartialEq)]
pub struct DecodedAudio {
    pub samples: Vec<f32>,
    pub samplerate: u32,
    pub duration_seconds: f64,
}

#[derive(Debug)]
pub enum AudioIoError {
    Open {
        path: String,
        source: hound::Error,
    },
    CreateDir {
        path: String,
        source: std::io::Error,
    },
    Create {
        path: String,
        source: hound::Error,
    },
    CreateFile {
        path: String,
        source: std::io::Error,
    },
    Decode(hound::Error),
    Write(hound::Error),
    Csv(csv::Error),
    Flush(std::io::Error),
    InvalidFormat(String),
}

impl fmt::Display for AudioIoError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            AudioIoError::Open { path, source } => {
                write!(f, "failed to open WAV '{}': {source}", path)
            }
            AudioIoError::CreateDir { path, source } => {
                write!(f, "failed to create parent directory '{}': {source}", path)
            }
            AudioIoError::Create { path, source } => {
                write!(f, "failed to create WAV '{}': {source}", path)
            }
            AudioIoError::CreateFile { path, source } => {
                write!(f, "failed to create file '{}': {source}", path)
            }
            AudioIoError::Decode(source) => write!(f, "failed to decode WAV samples: {source}"),
            AudioIoError::Write(source) => write!(f, "failed to write audio samples: {source}"),
            AudioIoError::Csv(source) => write!(f, "failed to write CSV report: {source}"),
            AudioIoError::Flush(source) => write!(f, "failed to flush output file: {source}"),
            AudioIoError::InvalidFormat(message) => write!(f, "invalid WAV format: {message}"),
        }
    }
}

impl std::error::Error for AudioIoError {}

pub fn load_wav_mono(path: impl AsRef<Path>) -> Result<DecodedAudio, AudioIoError> {
    let path_ref = path.as_ref();
    let mut reader = hound::WavReader::open(path_ref).map_err(|source| AudioIoError::Open {
        path: path_ref.display().to_string(),
        source,
    })?;
    let spec = reader.spec();
    if spec.channels == 0 {
        return Err(AudioIoError::InvalidFormat(
            "channel count must be greater than zero".to_string(),
        ));
    }
    if spec.sample_rate == 0 {
        return Err(AudioIoError::InvalidFormat(
            "sample rate must be greater than zero".to_string(),
        ));
    }

    let channels = spec.channels as usize;
    let samples = match spec.sample_format {
        hound::SampleFormat::Float => {
            let raw = reader
                .samples::<f32>()
                .collect::<Result<Vec<_>, _>>()
                .map_err(AudioIoError::Decode)?;
            mix_to_mono(raw.into_iter(), channels)
        }
        hound::SampleFormat::Int => {
            if spec.bits_per_sample == 0 || spec.bits_per_sample > 32 {
                return Err(AudioIoError::InvalidFormat(format!(
                    "unsupported integer bit depth: {}",
                    spec.bits_per_sample
                )));
            }
            let scale = ((1_i64 << (spec.bits_per_sample - 1)) - 1).max(1) as f32;
            let raw = reader
                .samples::<i32>()
                .collect::<Result<Vec<_>, _>>()
                .map_err(AudioIoError::Decode)?;
            mix_to_mono(
                raw.into_iter().map(|sample| sample as f32 / scale),
                channels,
            )
        }
    };

    Ok(DecodedAudio {
        duration_seconds: samples.len() as f64 / spec.sample_rate as f64,
        samples,
        samplerate: spec.sample_rate,
    })
}

pub fn save_wav_mono(
    path: impl AsRef<Path>,
    samples: &[f32],
    samplerate: u32,
) -> Result<(), AudioIoError> {
    let path_ref = path.as_ref();
    ensure_parent_dir(path_ref)?;
    let spec = hound::WavSpec {
        channels: 1,
        sample_rate: samplerate,
        bits_per_sample: 16,
        sample_format: hound::SampleFormat::Int,
    };
    let mut writer =
        hound::WavWriter::create(path_ref, spec).map_err(|source| AudioIoError::Create {
            path: path_ref.display().to_string(),
            source,
        })?;
    for sample in samples {
        let scaled = (sample.clamp(-1.0, 1.0) * i16::MAX as f32).round() as i16;
        writer.write_sample(scaled).map_err(AudioIoError::Write)?;
    }
    writer.finalize().map_err(AudioIoError::Write)
}

pub fn save_report_csv(path: impl AsRef<Path>, events: &[NoiseEvent]) -> Result<(), AudioIoError> {
    let path_ref = path.as_ref();
    ensure_parent_dir(path_ref)?;
    let mut file = fs::File::create(path_ref).map_err(|source| AudioIoError::CreateFile {
        path: path_ref.display().to_string(),
        source,
    })?;
    file.write_all(&[0xEF, 0xBB, 0xBF])
        .map_err(AudioIoError::Flush)?;
    let mut writer = csv::Writer::from_writer(file);
    writer
        .write_record([
            "序号",
            "保留",
            "来源",
            "类型",
            "疑似录制混入",
            "原始起始",
            "原始结束",
            "时长(秒)",
            "峰值(dBFS)",
            "平均(dBFS)",
            "低频占比",
            "高频占比",
        ])
        .map_err(AudioIoError::Csv)?;
    for (idx, event) in events.iter().enumerate() {
        writer
            .write_record([
                (idx + 1).to_string(),
                if event.keep { "是" } else { "否" }.to_string(),
                if event.manual { "手动" } else { "自动" }.to_string(),
                event_kind_label(event.kind).to_string(),
                if event.suspect_self { "是" } else { "" }.to_string(),
                format_hms(event.start),
                format_hms(event.end),
                format!("{:.2}", event.duration()),
                format!("{:.1}", event.peak_dbfs),
                format!("{:.1}", event.rms_dbfs),
                format!("{:.2}", event.low_ratio),
                format!("{:.2}", event.high_ratio),
            ])
            .map_err(AudioIoError::Csv)?;
    }
    writer.flush().map_err(AudioIoError::Flush)
}

fn mix_to_mono<I>(samples: I, channels: usize) -> Vec<f32>
where
    I: IntoIterator<Item = f32>,
{
    let mut mono = Vec::new();
    let mut frame_sum = 0.0_f32;
    let mut frame_count = 0usize;

    for sample in samples {
        frame_sum += sample;
        frame_count += 1;
        if frame_count == channels {
            mono.push((frame_sum / channels as f32).clamp(-1.0, 1.0));
            frame_sum = 0.0;
            frame_count = 0;
        }
    }
    mono
}

fn ensure_parent_dir(path: &Path) -> Result<(), AudioIoError> {
    if let Some(parent) = path.parent()
        && !parent.as_os_str().is_empty()
    {
        fs::create_dir_all(parent).map_err(|source| AudioIoError::CreateDir {
            path: parent.display().to_string(),
            source,
        })?;
    }
    Ok(())
}

fn format_hms(seconds: f64) -> String {
    let total_ms = (seconds.max(0.0) * 1000.0).round() as u64;
    let hours = total_ms / 3_600_000;
    let minutes = (total_ms % 3_600_000) / 60_000;
    let secs = (total_ms % 60_000) / 1000;
    let millis = total_ms % 1000;
    format!("{hours:02}:{minutes:02}:{secs:02}.{millis:03}")
}

fn event_kind_label(kind: EventKind) -> &'static str {
    match kind {
        EventKind::Rumble => "低频闷响",
        EventKind::Thud => "重击/敲击",
        EventKind::Drag => "拖拽/摩擦",
        EventKind::Transient => "短促瞬态",
        EventKind::Other => "其他",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;
    use tempfile::TempDir;

    fn temp_wav_path(name: &str) -> (TempDir, PathBuf) {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join(name);
        (dir, path)
    }

    #[test]
    fn loads_mono_i16_wav_as_normalized_f32() {
        let (_dir, path) = temp_wav_path("mono.wav");
        let spec = hound::WavSpec {
            channels: 1,
            sample_rate: 8000,
            bits_per_sample: 16,
            sample_format: hound::SampleFormat::Int,
        };
        let mut writer = hound::WavWriter::create(&path, spec).unwrap();
        writer.write_sample(0_i16).unwrap();
        writer.write_sample(16_384_i16).unwrap();
        writer.write_sample(-16_384_i16).unwrap();
        writer.finalize().unwrap();

        let audio = load_wav_mono(&path).unwrap();

        assert_eq!(audio.samplerate, 8000);
        assert_eq!(audio.samples.len(), 3);
        assert!((audio.samples[1] - 0.5).abs() < 0.001);
        assert!((audio.samples[2] + 0.5).abs() < 0.001);
    }

    #[test]
    fn downmixes_stereo_to_mono() {
        let (_dir, path) = temp_wav_path("stereo.wav");
        let spec = hound::WavSpec {
            channels: 2,
            sample_rate: 8000,
            bits_per_sample: 16,
            sample_format: hound::SampleFormat::Int,
        };
        let mut writer = hound::WavWriter::create(&path, spec).unwrap();
        writer.write_sample(16_384_i16).unwrap();
        writer.write_sample(0_i16).unwrap();
        writer.write_sample(0_i16).unwrap();
        writer.write_sample(-16_384_i16).unwrap();
        writer.finalize().unwrap();

        let audio = load_wav_mono(&path).unwrap();

        assert_eq!(audio.samples.len(), 2);
        assert!((audio.samples[0] - 0.25).abs() < 0.001);
        assert!((audio.samples[1] + 0.25).abs() < 0.001);
    }

    #[test]
    fn saves_wav_roundtrip() {
        let (_dir, path) = temp_wav_path("out.wav");

        save_wav_mono(&path, &[0.0, 0.5, -0.5], 8000).unwrap();
        let audio = load_wav_mono(&path).unwrap();

        assert_eq!(audio.samplerate, 8000);
        assert_eq!(audio.samples.len(), 3);
        assert!((audio.samples[1] - 0.5).abs() < 0.001);
    }

    #[test]
    fn saves_csv_report_with_bom() {
        let (_dir, path) = temp_wav_path("report.csv");
        let event = NoiseEvent {
            start: 1.2,
            end: 1.7,
            peak_dbfs: -8.2,
            rms_dbfs: -18.4,
            low_ratio: 0.3,
            high_ratio: 0.1,
            kind: EventKind::Drag,
            suspect_self: false,
            keep: true,
            manual: true,
        };

        save_report_csv(&path, &[event]).unwrap();
        let raw = fs::read(&path).unwrap();
        let text = String::from_utf8(raw[3..].to_vec()).unwrap();

        assert_eq!(&raw[..3], &[0xEF, 0xBB, 0xBF]);
        assert!(text.contains("拖拽/摩擦"));
        assert!(text.contains("00:00:01.200"));
    }
}
