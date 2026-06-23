use noise_types::{AnalyzeResult, AppConfig, DetectConfig, ExportResult, ProcessMode, Sensitivity};

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
fn analyze_audio(input_path: String, detect: DetectConfig) -> Result<AnalyzeResult, String> {
    let audio = noise_io::load_audio_mono(&input_path).map_err(|err| err.to_string())?;
    let events = noise_core::detect_events(&audio.samples, audio.samplerate, &detect);
    Ok(AnalyzeResult {
        samplerate: audio.samplerate,
        duration_seconds: audio.duration_seconds,
        events,
    })
}

#[tauri::command]
fn export_audio(
    input_path: String,
    wav_path: String,
    csv_path: Option<String>,
    config: AppConfig,
) -> Result<ExportResult, String> {
    let audio = noise_io::load_audio_mono(&input_path).map_err(|err| err.to_string())?;
    let events = if config.mode == ProcessMode::Highlight {
        noise_core::detect_events(&audio.samples, audio.samplerate, &config.detect)
    } else {
        Vec::new()
    };
    let built = match config.mode {
        ProcessMode::FullDenoise => {
            noise_core::build_full_export(&audio.samples, audio.samplerate, &config.export, None)
        }
        ProcessMode::FullAmplify => noise_core::build_full_export(
            &audio.samples,
            audio.samplerate,
            &config.export,
            Some(&config.gain),
        ),
        ProcessMode::Highlight => noise_core::build_highlight_export(
            &audio.samples,
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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            app_version,
            analyze_synthetic,
            analyze_audio,
            export_audio
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
