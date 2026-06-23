use std::fmt;

use noise_types::{DenoiseConfig, DetectConfig, ExportConfig, GainConfig, GainMode, NoiseEvent};

#[derive(Clone, Debug, PartialEq)]
pub struct BuiltAudio {
    pub samples: Vec<f32>,
    pub samplerate: u32,
}

#[derive(Debug)]
pub enum ExportBuildError {
    EmptyAudio,
    NoKeptEvents,
}

impl fmt::Display for ExportBuildError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ExportBuildError::EmptyAudio => write!(f, "no audio samples to export"),
            ExportBuildError::NoKeptEvents => write!(f, "no kept events to export"),
        }
    }
}

impl std::error::Error for ExportBuildError {}

pub fn detect_events(samples: &[f32], sample_rate: u32, cfg: &DetectConfig) -> Vec<NoiseEvent> {
    if samples.is_empty() || sample_rate == 0 {
        return Vec::new();
    }

    let frame = ((cfg.frame_ms * sample_rate as f64 / 1000.0).round() as usize).max(1);
    let hop = ((cfg.hop_ms * sample_rate as f64 / 1000.0).round() as usize).max(1);
    let hop_sec = hop as f64 / sample_rate as f64;
    let db = frame_rms_db(samples, frame, hop);
    let floor = percentile(&db, 20.0);
    let threshold = floor + cfg.margin_db();
    let hot: Vec<bool> = db.iter().map(|value| *value > threshold).collect();
    let spans = merge_and_filter(&hot, hop_sec, cfg);
    let total_sec = samples.len() as f64 / sample_rate as f64;

    spans
        .into_iter()
        .filter_map(|(start, end)| {
            let start = (start - cfg.pad_seconds).max(0.0);
            let end = (end + cfg.pad_seconds).min(total_sec);
            make_event(samples, sample_rate, start, end, false)
        })
        .filter(|event| event.peak_dbfs >= cfg.min_peak_dbfs)
        .collect()
}

pub fn make_manual_event(
    samples: &[f32],
    sample_rate: u32,
    start: f64,
    end: f64,
) -> Option<NoiseEvent> {
    let (lo, hi) = if start <= end {
        (start, end)
    } else {
        (end, start)
    };
    make_event(samples, sample_rate, lo, hi, true)
}

pub fn reduce_noise(samples: &[f32], sample_rate: u32, cfg: &DenoiseConfig) -> Vec<f32> {
    if !cfg.enabled || samples.is_empty() || sample_rate == 0 {
        return samples.to_vec();
    }

    let noise = quietest_window(samples, sample_rate, cfg.noise_sample_seconds);
    let floor = rms(noise).max(1e-6) as f32;
    let strength = cfg.prop_decrease.clamp(0.0, 1.0) as f32;
    samples
        .iter()
        .map(|sample| {
            let abs = sample.abs();
            let noise_ratio = floor / (abs + floor);
            let attenuation = 1.0 - strength * noise_ratio;
            (sample * attenuation).clamp(-1.0, 1.0)
        })
        .collect()
}

pub fn build_full_export(
    samples: &[f32],
    sample_rate: u32,
    export: &ExportConfig,
    gain: Option<&GainConfig>,
) -> Result<BuiltAudio, ExportBuildError> {
    if samples.is_empty() || sample_rate == 0 {
        return Err(ExportBuildError::EmptyAudio);
    }
    let mut out = samples.to_vec();
    if let Some(gain) = gain
        && gain.enabled
        && gain.mode != GainMode::Off
    {
        out = apply_global_gain(&out, gain).0;
    }
    let out_samplerate = export.out_samplerate.unwrap_or(sample_rate);
    out = resample_if_needed(&out, sample_rate, out_samplerate);
    Ok(BuiltAudio {
        samples: out,
        samplerate: out_samplerate,
    })
}

pub fn build_highlight_export(
    samples: &[f32],
    sample_rate: u32,
    events: &[NoiseEvent],
    export: &ExportConfig,
    gain: Option<&GainConfig>,
) -> Result<BuiltAudio, ExportBuildError> {
    if samples.is_empty() || sample_rate == 0 {
        return Err(ExportBuildError::EmptyAudio);
    }

    let kept: Vec<&NoiseEvent> = events.iter().filter(|event| event.keep).collect();
    if kept.is_empty() {
        return Err(ExportBuildError::NoKeptEvents);
    }

    let gap = vec![0.0_f32; seconds_to_samples(export.gap_seconds, sample_rate)];
    let sep = if export.insert_beep {
        beep(sample_rate, export)
    } else {
        Vec::new()
    };
    let per_event = gain.is_some_and(|cfg| cfg.enabled && cfg.mode == GainMode::PerEvent);
    let mut out = Vec::new();

    for (idx, event) in kept.iter().enumerate() {
        if idx > 0 {
            out.extend_from_slice(&gap);
            if !sep.is_empty() {
                out.extend_from_slice(&sep);
                out.extend_from_slice(&gap);
            }
        }
        let start = seconds_to_samples(event.start, sample_rate).min(samples.len());
        let end = seconds_to_samples(event.end, sample_rate).min(samples.len());
        if end <= start {
            continue;
        }
        let segment = &samples[start..end];
        if per_event {
            out.extend(amplify_segment(
                segment,
                gain.expect("checked by per_event"),
            ));
        } else {
            out.extend_from_slice(segment);
        }
    }

    if out.is_empty() {
        return Err(ExportBuildError::NoKeptEvents);
    }
    if let Some(gain) = gain
        && gain.enabled
        && gain.mode == GainMode::Global
    {
        out = apply_global_gain(&out, gain).0;
    }

    let out_samplerate = export.out_samplerate.unwrap_or(sample_rate);
    out = resample_if_needed(&out, sample_rate, out_samplerate);
    Ok(BuiltAudio {
        samples: out,
        samplerate: out_samplerate,
    })
}

pub fn apply_global_gain(samples: &[f32], cfg: &GainConfig) -> (Vec<f32>, f64) {
    let target = db_to_linear(cfg.target_peak_dbfs);
    let max_gain = db_to_linear(cfg.max_gain_db);
    let gain = gain_for(peak(samples), target, max_gain);
    (
        samples
            .iter()
            .map(|sample| (sample * gain).clamp(-1.0, 1.0))
            .collect(),
        20.0 * ((gain as f64) + 1e-12).log10(),
    )
}

pub fn amplify_segment(samples: &[f32], cfg: &GainConfig) -> Vec<f32> {
    if !cfg.enabled || cfg.mode == GainMode::Off || samples.is_empty() {
        return samples.to_vec();
    }
    let target = db_to_linear(cfg.target_peak_dbfs);
    let max_gain = db_to_linear(cfg.max_gain_db);
    let gain = gain_for(peak(samples), target, max_gain);
    samples
        .iter()
        .map(|sample| (sample * gain).clamp(-1.0, 1.0))
        .collect()
}

fn frame_rms_db(samples: &[f32], frame: usize, hop: usize) -> Vec<f64> {
    let count = 1 + samples.len().saturating_sub(frame) / hop;
    let mut out = Vec::with_capacity(count);
    for i in 0..count {
        let start = i * hop;
        let end = (start + frame).min(samples.len());
        let seg = &samples[start..end];
        let mean = seg
            .iter()
            .map(|sample| {
                let v = *sample as f64;
                v * v
            })
            .sum::<f64>()
            / seg.len().max(1) as f64;
        let rms = mean.sqrt();
        out.push(20.0 * (rms + 1e-10).log10());
    }
    out
}

fn quietest_window(samples: &[f32], sample_rate: u32, win_sec: f64) -> &[f32] {
    let win = ((win_sec.max(0.001) * sample_rate as f64).round() as usize)
        .max(1)
        .min(samples.len());
    if samples.len() <= win {
        return samples;
    }
    let step = (win / 4).max(1);
    let mut best_start = 0usize;
    let mut best_energy = f64::INFINITY;
    for start in (0..=samples.len() - win).step_by(step) {
        let energy = samples[start..start + win]
            .iter()
            .map(|sample| {
                let value = *sample as f64;
                value * value
            })
            .sum::<f64>()
            / win as f64;
        if energy < best_energy {
            best_energy = energy;
            best_start = start;
        }
    }
    &samples[best_start..best_start + win]
}

fn rms(samples: &[f32]) -> f64 {
    if samples.is_empty() {
        return 0.0;
    }
    (samples
        .iter()
        .map(|sample| {
            let value = *sample as f64;
            value * value
        })
        .sum::<f64>()
        / samples.len() as f64)
        .sqrt()
}

fn percentile(values: &[f64], percentile: f64) -> f64 {
    if values.is_empty() {
        return -120.0;
    }
    let mut sorted = values.to_vec();
    sorted.sort_by(|a, b| a.total_cmp(b));
    let pos = ((sorted.len() - 1) as f64 * percentile / 100.0).round() as usize;
    sorted[pos]
}

fn merge_and_filter(hot: &[bool], hop_sec: f64, cfg: &DetectConfig) -> Vec<(f64, f64)> {
    let mut spans = Vec::new();
    let mut in_event = false;
    let mut start_idx = 0usize;

    for (i, is_hot) in hot.iter().enumerate() {
        if *is_hot && !in_event {
            in_event = true;
            start_idx = i;
        } else if !*is_hot && in_event {
            in_event = false;
            spans.push((start_idx as f64 * hop_sec, i as f64 * hop_sec));
        }
    }
    if in_event {
        spans.push((start_idx as f64 * hop_sec, hot.len() as f64 * hop_sec));
    }

    let mut merged: Vec<(f64, f64)> = Vec::new();
    for (start, end) in spans {
        if let Some(last) = merged.last_mut()
            && start - last.1 <= cfg.merge_gap_seconds
        {
            last.1 = end;
            continue;
        }
        merged.push((start, end));
    }

    merged
        .into_iter()
        .filter(|(start, end)| end - start >= cfg.min_event_seconds)
        .collect()
}

fn make_event(
    samples: &[f32],
    sample_rate: u32,
    start: f64,
    end: f64,
    manual: bool,
) -> Option<NoiseEvent> {
    if samples.is_empty() || sample_rate == 0 {
        return None;
    }
    let total_sec = samples.len() as f64 / sample_rate as f64;
    let start = start.clamp(0.0, total_sec);
    let end = end.clamp(0.0, total_sec);
    if end <= start {
        return None;
    }
    let i0 = (start * sample_rate as f64).floor() as usize;
    let i1 = (end * sample_rate as f64).ceil() as usize;
    let seg = &samples[i0.min(samples.len())..i1.min(samples.len())];
    if seg.is_empty() {
        return None;
    }

    let peak = seg.iter().map(|v| v.abs()).fold(0.0_f32, f32::max) as f64;
    let peak_dbfs = 20.0 * (peak + 1e-10).log10();
    let rms = (seg
        .iter()
        .map(|sample| {
            let v = *sample as f64;
            v * v
        })
        .sum::<f64>()
        / seg.len() as f64)
        .sqrt();

    Some(NoiseEvent {
        start,
        end,
        peak_dbfs,
        rms_dbfs: 20.0 * (rms + 1e-10).log10(),
        low_ratio: 0.0,
        high_ratio: 0.0,
        kind: if end - start >= 0.5 {
            noise_types::EventKind::Drag
        } else {
            noise_types::EventKind::Other
        },
        suspect_self: false,
        keep: true,
        manual,
    })
}

fn db_to_linear(db: f64) -> f32 {
    10.0_f32.powf((db / 20.0) as f32)
}

fn peak(samples: &[f32]) -> f32 {
    samples
        .iter()
        .map(|sample| sample.abs())
        .fold(0.0, f32::max)
}

fn gain_for(sample_peak: f32, target: f32, max_gain: f32) -> f32 {
    if sample_peak <= 1e-9 {
        return 1.0;
    }
    (target / sample_peak).min(max_gain)
}

fn seconds_to_samples(seconds: f64, sample_rate: u32) -> usize {
    (seconds.max(0.0) * sample_rate as f64) as usize
}

fn beep(sample_rate: u32, cfg: &ExportConfig) -> Vec<f32> {
    let len = seconds_to_samples(cfg.beep_seconds, sample_rate).max(1);
    let fade = (len / 10).max(1);
    let mut out = Vec::with_capacity(len);
    for i in 0..len {
        let t = i as f32 / sample_rate as f32;
        let tone = 0.2 * (2.0 * std::f32::consts::PI * cfg.beep_hz as f32 * t).sin();
        let env = if i < fade {
            i as f32 / fade as f32
        } else if i >= len.saturating_sub(fade) {
            (len - 1 - i) as f32 / fade as f32
        } else {
            1.0
        };
        out.push(tone * env.clamp(0.0, 1.0));
    }
    out
}

fn resample_if_needed(samples: &[f32], sample_rate: u32, out_samplerate: u32) -> Vec<f32> {
    if samples.is_empty()
        || sample_rate == out_samplerate
        || sample_rate == 0
        || out_samplerate == 0
    {
        return samples.to_vec();
    }
    let out_len = ((samples.len() as f64 * out_samplerate as f64 / sample_rate as f64).round()
        as usize)
        .max(1);
    let ratio = sample_rate as f64 / out_samplerate as f64;
    (0..out_len)
        .map(|i| {
            let pos = i as f64 * ratio;
            let lo = pos.floor() as usize;
            let hi = (lo + 1).min(samples.len() - 1);
            let frac = (pos - lo as f64) as f32;
            samples[lo] * (1.0 - frac) + samples[hi] * frac
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use noise_types::Sensitivity;

    #[test]
    fn close_peaks_merge_into_one_event() {
        let sr = 8000;
        let mut samples = vec![0.0_f32; sr * 3];
        samples[(sr as f64 * 1.0) as usize..(sr as f64 * 1.05) as usize].fill(0.7);
        samples[(sr as f64 * 1.45) as usize..(sr as f64 * 1.50) as usize].fill(0.65);
        let cfg = DetectConfig {
            sensitivity: Sensitivity::High,
            merge_gap_seconds: 0.8,
            pad_seconds: 0.1,
            min_peak_dbfs: -60.0,
            ..DetectConfig::default()
        };

        let events = detect_events(&samples, sr as u32, &cfg);

        assert_eq!(events.len(), 1);
        assert!(events[0].start <= 1.05);
        assert!(events[0].end >= 1.45);
    }

    #[test]
    fn manual_event_accepts_reverse_order() {
        let sr = 8000;
        let mut samples = vec![0.0_f32; sr * 3];
        samples[(sr as f64 * 1.8) as usize..(sr as f64 * 2.0) as usize].fill(0.4);

        let event = make_manual_event(&samples, sr as u32, 2.0, 1.8).unwrap();

        assert!(event.manual);
        assert_eq!(event.start, 1.8);
        assert_eq!(event.end, 2.0);
    }

    #[test]
    fn highlight_export_keeps_only_selected_events() {
        let sr = 1000;
        let mut samples = vec![0.0_f32; sr * 3];
        samples[100..200].fill(0.2);
        samples[700..800].fill(0.3);
        let events = vec![
            NoiseEvent {
                start: 0.1,
                end: 0.2,
                peak_dbfs: -10.0,
                rms_dbfs: -20.0,
                low_ratio: 0.0,
                high_ratio: 0.0,
                kind: noise_types::EventKind::Other,
                suspect_self: false,
                keep: true,
                manual: false,
            },
            NoiseEvent {
                start: 0.7,
                end: 0.8,
                peak_dbfs: -8.0,
                rms_dbfs: -18.0,
                low_ratio: 0.0,
                high_ratio: 0.0,
                kind: noise_types::EventKind::Other,
                suspect_self: false,
                keep: false,
                manual: false,
            },
        ];
        let export = ExportConfig {
            gap_seconds: 0.5,
            insert_beep: false,
            beep_hz: 880.0,
            beep_seconds: 0.12,
            out_samplerate: None,
        };

        let built = build_highlight_export(&samples, sr as u32, &events, &export, None).unwrap();

        assert_eq!(built.samples.len(), 100);
        assert!(
            built
                .samples
                .iter()
                .all(|sample| (*sample - 0.2).abs() < 1e-6)
        );
    }

    #[test]
    fn full_export_applies_global_gain() {
        let export = ExportConfig {
            gap_seconds: 0.5,
            insert_beep: false,
            beep_hz: 880.0,
            beep_seconds: 0.12,
            out_samplerate: None,
        };
        let gain = GainConfig {
            enabled: true,
            mode: GainMode::Global,
            target_peak_dbfs: -6.0,
            max_gain_db: 36.0,
        };

        let built = build_full_export(&[0.1, -0.2], 8000, &export, Some(&gain)).unwrap();

        let peak = built
            .samples
            .iter()
            .map(|sample| sample.abs())
            .fold(0.0, f32::max);
        assert!((peak - 0.501).abs() < 0.002);
    }

    #[test]
    fn denoise_attenuates_floor_more_than_events() {
        let sr = 1000;
        let mut samples = vec![0.02_f32; sr * 2];
        samples[800..900].fill(0.5);
        let cfg = DenoiseConfig {
            enabled: true,
            noise_sample_seconds: 0.25,
            prop_decrease: 0.9,
            stationary: true,
        };

        let reduced = reduce_noise(&samples, sr as u32, &cfg);

        assert!(reduced[10].abs() < samples[10].abs() * 0.65);
        assert!(reduced[850].abs() > samples[850].abs() * 0.9);
    }

    #[test]
    fn denoise_disabled_returns_original_samples() {
        let samples = [0.1_f32, -0.2, 0.3];
        let cfg = DenoiseConfig {
            enabled: false,
            noise_sample_seconds: 1.0,
            prop_decrease: 0.9,
            stationary: true,
        };

        assert_eq!(reduce_noise(&samples, 8000, &cfg), samples);
    }
}
