use noise_types::{DetectConfig, EventKind, NoiseEvent};

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
            EventKind::Drag
        } else {
            EventKind::Other
        },
        suspect_self: false,
        keep: true,
        manual,
    })
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
}
