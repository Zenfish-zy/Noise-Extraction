use noise_types::{
    AnalyzeResult, AppConfig, AudioPreviewResult, DetectConfig, ExportResult, NoiseEvent,
    ProcessMode, Sensitivity, WaveformBin, WaveformResult,
};
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};
use tauri::Emitter;

#[tauri::command]
fn app_version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[tauri::command]
fn analyze_synthetic() -> AnalyzeResult {
    let (samples, samplerate, duration_seconds) = synthetic_demo_signal();
    let cfg = DetectConfig {
        sensitivity: Sensitivity::High,
        merge_gap_seconds: 0.8,
        pad_seconds: 0.1,
        min_peak_dbfs: -60.0,
        ..DetectConfig::default()
    };
    let mut events = noise_core::detect_events(&samples, samplerate, &cfg);
    if let Some(manual) = noise_core::make_manual_event(&samples, samplerate, 5.6, 6.2) {
        events.push(manual);
    }
    AnalyzeResult {
        samplerate,
        duration_seconds,
        events,
    }
}

#[tauri::command]
fn inspect_audio(input_path: String) -> Result<AnalyzeResult, String> {
    let audio = noise_io::load_audio_mono(&input_path).map_err(|err| err.to_string())?;
    Ok(AnalyzeResult {
        samplerate: audio.samplerate,
        duration_seconds: audio.duration_seconds,
        events: Vec::new(),
    })
}

#[tauri::command]
async fn inspect_audio_with_progress(
    input_path: String,
    bins: usize,
    config: AppConfig,
    window: tauri::Window,
) -> Result<(AnalyzeResult, WaveformResult, AudioPreviewResult), String> {
    let input_path_clone = input_path.clone();
    let config_clone = config.clone();

    // Step 1: Load audio metadata
    let _ = window.emit("import_progress", serde_json::json!({"stage": "正在读取音频信息", "percent": 10}));
    let audio = noise_io::load_audio_mono(&input_path).map_err(|err| err.to_string())?;
    let result = AnalyzeResult {
        samplerate: audio.samplerate,
        duration_seconds: audio.duration_seconds,
        events: Vec::new(),
    };

    // Step 2: Generate waveform
    let _ = window.emit("import_progress", serde_json::json!({"stage": "正在生成波形", "percent": 40}));
    let audio = noise_io::load_audio_mono(&input_path_clone).map_err(|err| err.to_string())?;
    let samples = noise_core::reduce_noise(&audio.samples, audio.samplerate, &config_clone.denoise);
    let waveform = WaveformResult {
        samplerate: audio.samplerate,
        duration_seconds: audio.duration_seconds,
        bins: build_waveform_bins(&samples, bins),
    };

    // Step 3: Prepare preview
    let _ = window.emit("import_progress", serde_json::json!({"stage": "正在准备预览", "percent": 70}));
    let audio = noise_io::load_audio_mono(&input_path_clone).map_err(|err| err.to_string())?;
    let samples = noise_core::reduce_noise(&audio.samples, audio.samplerate, &config.denoise);
    let wav_path = preview_wav_path();
    noise_io::save_wav_mono(&wav_path, &samples, audio.samplerate)
        .map_err(|err| err.to_string())?;
    let preview = AudioPreviewResult {
        wav_path: wav_path.display().to_string(),
        samplerate: audio.samplerate,
        duration_seconds: audio.duration_seconds,
    };

    let _ = window.emit("import_progress", serde_json::json!({"stage": "完成", "percent": 100}));

    Ok((result, waveform, preview))
}

#[tauri::command]
fn waveform_peaks(
    input_path: String,
    bins: usize,
    config: AppConfig,
) -> Result<WaveformResult, String> {
    let audio = noise_io::load_audio_mono(&input_path).map_err(|err| err.to_string())?;
    let samples = noise_core::reduce_noise(&audio.samples, audio.samplerate, &config.denoise);
    Ok(WaveformResult {
        samplerate: audio.samplerate,
        duration_seconds: audio.duration_seconds,
        bins: build_waveform_bins(&samples, bins),
    })
}

#[tauri::command]
fn prepare_audio_preview(
    input_path: String,
    config: AppConfig,
) -> Result<AudioPreviewResult, String> {
    let audio = noise_io::load_audio_mono(&input_path).map_err(|err| err.to_string())?;
    let samples = noise_core::reduce_noise(&audio.samples, audio.samplerate, &config.denoise);
    let wav_path = preview_wav_path();
    noise_io::save_wav_mono(&wav_path, &samples, audio.samplerate)
        .map_err(|err| err.to_string())?;
    Ok(AudioPreviewResult {
        wav_path: wav_path.display().to_string(),
        samplerate: audio.samplerate,
        duration_seconds: audio.duration_seconds,
    })
}

#[tauri::command]
fn analyze_audio(input_path: String, config: AppConfig) -> Result<AnalyzeResult, String> {
    let audio = noise_io::load_audio_mono(&input_path).map_err(|err| err.to_string())?;
    let samples = noise_core::reduce_noise(&audio.samples, audio.samplerate, &config.denoise);
    let events = noise_core::detect_events(&samples, audio.samplerate, &config.detect);
    Ok(AnalyzeResult {
        samplerate: audio.samplerate,
        duration_seconds: audio.duration_seconds,
        events,
    })
}

#[tauri::command]
fn manual_event(
    input_path: String,
    start: f64,
    end: f64,
    config: AppConfig,
) -> Result<NoiseEvent, String> {
    let audio = noise_io::load_audio_mono(&input_path).map_err(|err| err.to_string())?;
    let samples = noise_core::reduce_noise(&audio.samples, audio.samplerate, &config.denoise);
    noise_core::make_manual_event(&samples, audio.samplerate, start, end)
        .ok_or_else(|| "框选区间为空，无法新增事件。".to_string())
}

#[tauri::command]
fn export_audio(
    input_path: String,
    wav_path: String,
    csv_path: Option<String>,
    config: AppConfig,
    events: Option<Vec<NoiseEvent>>,
) -> Result<ExportResult, String> {
    let audio = noise_io::load_audio_mono(&input_path).map_err(|err| err.to_string())?;
    let samples = noise_core::reduce_noise(&audio.samples, audio.samplerate, &config.denoise);
    let events = if config.mode == ProcessMode::Highlight {
        events.unwrap_or_else(|| {
            noise_core::detect_events(&samples, audio.samplerate, &config.detect)
        })
    } else {
        Vec::new()
    };
    let built = match config.mode {
        ProcessMode::FullDenoise => {
            noise_core::build_full_export(&samples, audio.samplerate, &config.export, None)
        }
        ProcessMode::FullAmplify => noise_core::build_full_export(
            &samples,
            audio.samplerate,
            &config.export,
            Some(&config.gain),
        ),
        ProcessMode::Highlight => noise_core::build_highlight_export(
            &samples,
            audio.samplerate,
            &events,
            &config.export,
            Some(&config.gain),
        ),
    }
    .map_err(|err| err.to_string())?;

    noise_io::save_wav_mono(&wav_path, &built.samples, built.samplerate)
        .map_err(|err| err.to_string())?;
    let csv_path = if config.mode == ProcessMode::Highlight {
        if let Some(path) = csv_path {
            noise_io::save_report_csv(&path, &events).map_err(|err| err.to_string())?;
            Some(path)
        } else {
            None
        }
    } else {
        None
    };

    Ok(ExportResult {
        wav_path,
        csv_path,
        kept_events: events.iter().filter(|event| event.keep).count(),
        duration_seconds: built.samples.len() as f64 / built.samplerate as f64,
    })
}

#[tauri::command]
async fn ai_enhance_events(
    events: Vec<NoiseEvent>,
    config: AppConfig,
) -> Result<Vec<NoiseEvent>, String> {
    if !config.ai.enabled || config.ai.api_key.is_empty() {
        return Ok(events);
    }

    let client = reqwest::Client::new();
    let mut enhanced = Vec::new();

    for event in events {
        let prompt = format!(
            "You are a noise classification expert. Based on the following audio features, classify the noise type.\n\n\
            Duration: {:.2}s\n\
            Peak level: {:.1} dBFS\n\
            RMS level: {:.1} dBFS\n\
            Low frequency ratio: {:.2}\n\
            High frequency ratio: {:.2}\n\
            Current type: {:?}\n\n\
            Reply with ONLY ONE of these types:\n\
            - Drag: dragging or friction sounds\n\
            - Thud: sudden impacts or knocks\n\
            - Rumble: low-frequency continuous sounds\n\
            - Other: unclassified sounds\n\n\
            Reply with just the type name, nothing else.",
            event.end - event.start,
            event.peak_dbfs,
            event.rms_dbfs,
            event.low_ratio,
            event.high_ratio,
            event.kind
        );

        let request_body = serde_json::json!({
            "model": config.ai.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 20
        });

        match client
            .post(&config.ai.api_endpoint)
            .header("Authorization", format!("Bearer {}", config.ai.api_key))
            .header("Content-Type", "application/json")
            .json(&request_body)
            .send()
            .await
        {
            Ok(response) => {
                if let Ok(json) = response.json::<serde_json::Value>().await {
                    if let Some(content) = json["choices"][0]["message"]["content"].as_str() {
                        let ai_kind = match content.trim().to_lowercase().as_str() {
                            "drag" => noise_types::EventKind::Drag,
                            "impact" | "thud" => noise_types::EventKind::Thud,
                            "rumble" => noise_types::EventKind::Rumble,
                            _ => event.kind,
                        };
                        enhanced.push(NoiseEvent { kind: ai_kind, ..event });
                        continue;
                    }
                }
                enhanced.push(event);
            }
            Err(_) => {
                enhanced.push(event);
            }
        }
    }

    Ok(enhanced)
}

fn synthetic_demo_signal() -> (Vec<f32>, u32, f64) {
    let samplerate = 8000_u32;
    let duration_seconds = 8.0_f64;
    let mut samples = vec![0.0_f32; (samplerate as f64 * duration_seconds) as usize];
    fill_span(&mut samples, samplerate, 1.0, 1.05, 0.7);
    fill_span(&mut samples, samplerate, 1.45, 1.50, 0.65);
    fill_span(&mut samples, samplerate, 3.4, 3.9, 0.5);
    fill_span(&mut samples, samplerate, 5.6, 6.2, 0.35);
    (samples, samplerate, duration_seconds)
}

fn fill_span(samples: &mut [f32], samplerate: u32, start: f64, end: f64, value: f32) {
    let i0 = (start * samplerate as f64) as usize;
    let i1 = (end * samplerate as f64) as usize;
    let len = samples.len();
    let start = i0.min(len);
    let end = i1.min(len);
    samples[start..end].fill(value);
}

fn build_waveform_bins(samples: &[f32], bins: usize) -> Vec<WaveformBin> {
    if samples.is_empty() || bins == 0 {
        return Vec::new();
    }

    let len = samples.len();
    (0..bins)
        .filter_map(|idx| {
            let start = idx * len / bins;
            let mut end = ((idx + 1) * len / bins).max(start + 1);
            if start >= len {
                return None;
            }
            end = end.min(len);
            let (mut min, mut max) = (f32::INFINITY, f32::NEG_INFINITY);
            for sample in &samples[start..end] {
                min = min.min(*sample);
                max = max.max(*sample);
            }
            Some(WaveformBin { min, max })
        })
        .collect()
}

fn preview_wav_path() -> PathBuf {
    let nonce = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_nanos())
        .unwrap_or_default();
    std::env::temp_dir().join(format!(
        "noise-evidence-next-preview-{}-{nonce}.wav",
        std::process::id()
    ))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            app_version,
            analyze_synthetic,
            inspect_audio,
            inspect_audio_with_progress,
            waveform_peaks,
            prepare_audio_preview,
            analyze_audio,
            manual_event,
            export_audio,
            ai_enhance_events
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use super::*;
    use noise_types::{DenoiseConfig, EventKind, ExportConfig, GainConfig, GainMode};
    use std::fs;
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn export_audio_uses_reviewed_events_from_frontend() {
        let input_path = temp_path("review-input.wav");
        let wav_path = temp_path("review-output.wav");
        let csv_path = temp_path("review-output.csv");
        let _cleanup = TempFiles::new([&input_path, &wav_path, &csv_path]);

        noise_io::save_wav_mono(&input_path, &[0.5; 16_000], 8_000).unwrap();
        let inspected = inspect_audio(path_string(&input_path)).unwrap();
        let config = highlight_config();
        let waveform = waveform_peaks(path_string(&input_path), 4, config.clone()).unwrap();
        let preview = prepare_audio_preview(path_string(&input_path), config.clone()).unwrap();
        let result = export_audio(
            path_string(&input_path),
            path_string(&wav_path),
            Some(path_string(&csv_path)),
            config,
            Some(vec![
                test_event(0.0, 0.25, true, false),
                test_event(0.5, 0.75, false, true),
            ]),
        )
        .unwrap();

        let exported = noise_io::load_audio_mono(&wav_path).unwrap();
        let csv = fs::read_to_string(&csv_path).unwrap();

        assert_eq!(inspected.samplerate, 8_000);
        assert!(inspected.events.is_empty());
        assert_eq!(waveform.bins.len(), 4);
        assert!(waveform.bins.iter().all(|bin| bin.max > 0.49));
        let preview_audio = noise_io::load_audio_mono(&preview.wav_path).unwrap();
        assert_eq!(preview.samplerate, 8_000);
        assert!((preview_audio.duration_seconds - inspected.duration_seconds).abs() < 0.01);
        assert_eq!(result.kept_events, 1);
        assert!((result.duration_seconds - 0.25).abs() < 0.01);
        assert!((exported.duration_seconds - 0.25).abs() < 0.01);
        assert!(csv.contains("手动"));
        assert!(csv.contains("否"));
        let _ = fs::remove_file(preview.wav_path);
    }

    fn highlight_config() -> AppConfig {
        AppConfig {
            mode: ProcessMode::Highlight,
            denoise: DenoiseConfig {
                enabled: false,
                noise_sample_seconds: 1.0,
                prop_decrease: 0.9,
                stationary: true,
            },
            detect: DetectConfig::default(),
            gain: GainConfig {
                enabled: false,
                mode: GainMode::Off,
                target_peak_dbfs: -1.0,
                max_gain_db: 36.0,
            },
            export: ExportConfig {
                gap_seconds: 0.0,
                insert_beep: false,
                beep_hz: 880.0,
                beep_seconds: 0.0,
                out_samplerate: None,
            },
        }
    }

    fn test_event(start: f64, end: f64, keep: bool, manual: bool) -> NoiseEvent {
        NoiseEvent {
            start,
            end,
            peak_dbfs: -6.0,
            rms_dbfs: -12.0,
            low_ratio: 0.2,
            high_ratio: 0.1,
            kind: EventKind::Other,
            suspect_self: false,
            keep,
            manual,
        }
    }

    fn temp_path(name: &str) -> PathBuf {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        std::env::temp_dir().join(format!("noise-next-{nonce}-{name}"))
    }

    fn path_string(path: &PathBuf) -> String {
        path.display().to_string()
    }

    struct TempFiles {
        paths: Vec<PathBuf>,
    }

    impl TempFiles {
        fn new<const N: usize>(paths: [&PathBuf; N]) -> Self {
            Self {
                paths: paths.into_iter().cloned().collect(),
            }
        }
    }

    impl Drop for TempFiles {
        fn drop(&mut self) {
            for path in &self.paths {
                let _ = fs::remove_file(path);
            }
        }
    }
}
