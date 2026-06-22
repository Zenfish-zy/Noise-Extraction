use std::fmt;
use std::path::Path;

#[derive(Clone, Debug, PartialEq)]
pub struct DecodedAudio {
    pub samples: Vec<f32>,
    pub samplerate: u32,
    pub duration_seconds: f64,
}

#[derive(Debug)]
pub enum AudioIoError {
    Open { path: String, source: hound::Error },
    Decode(hound::Error),
    InvalidFormat(String),
}

impl fmt::Display for AudioIoError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            AudioIoError::Open { path, source } => {
                write!(f, "failed to open WAV '{}': {source}", path)
            }
            AudioIoError::Decode(source) => write!(f, "failed to decode WAV samples: {source}"),
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
}
