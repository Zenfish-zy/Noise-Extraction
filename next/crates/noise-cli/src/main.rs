use std::env;
use std::fs;
use std::path::PathBuf;
use std::process;

use noise_types::{AnalyzeResult, AppConfig, ExportResult, ProcessMode};

fn main() {
    if let Err(err) = run() {
        eprintln!("{err}");
        process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let mut args = env::args().skip(1);
    let Some(command) = args.next() else {
        return Err(usage());
    };

    match command.as_str() {
        "analyze-synthetic" => {
            let config_path = parse_config_arg(args.collect())?;
            let config = read_config(&config_path)?;
            let (samples, samplerate, duration_seconds) = synthetic_close_peaks();
            let work = noise_core::reduce_noise(&samples, samplerate, &config.denoise);
            let events = noise_core::detect_events(&work, samplerate, &config.detect);
            let result = AnalyzeResult {
                samplerate,
                duration_seconds,
                events,
            };
            let json = serde_json::to_string_pretty(&result).map_err(|err| err.to_string())?;
            println!("{json}");
            Ok(())
        }
        "analyze-audio" | "analyze-wav" => {
            let parsed = parse_analyze_wav_args(args.collect())?;
            let config = read_config(&parsed.config_path)?;
            let audio = noise_io::load_audio_mono(&parsed.input_path)
                .map_err(|err| format!("failed to load input audio: {err}"))?;
            let work = noise_core::reduce_noise(&audio.samples, audio.samplerate, &config.denoise);
            let events = noise_core::detect_events(&work, audio.samplerate, &config.detect);
            let result = AnalyzeResult {
                samplerate: audio.samplerate,
                duration_seconds: audio.duration_seconds,
                events,
            };
            let json = serde_json::to_string_pretty(&result).map_err(|err| err.to_string())?;
            println!("{json}");
            Ok(())
        }
        "export-audio" | "export-wav" => {
            let parsed = parse_export_wav_args(args.collect())?;
            let config = read_config(&parsed.config_path)?;
            let result = export_wav(
                &parsed.input_path,
                &parsed.output_path,
                parsed.csv_path.as_ref(),
                &config,
            )?;
            let json = serde_json::to_string_pretty(&result).map_err(|err| err.to_string())?;
            println!("{json}");
            Ok(())
        }
        _ => Err(usage()),
    }
}

fn usage() -> String {
    "usage: noise-cli analyze-synthetic --config <path>\n       noise-cli analyze-audio --input <audio> --config <path>\n       noise-cli export-audio --input <audio> --output <wav> --config <path> [--csv <report.csv>]".to_string()
}

fn parse_config_arg(args: Vec<String>) -> Result<PathBuf, String> {
    let mut iter = args.into_iter();
    while let Some(arg) = iter.next() {
        if arg == "--config" {
            let Some(path) = iter.next() else {
                return Err("missing value for --config".to_string());
            };
            return Ok(PathBuf::from(path));
        }
    }
    Err("missing required --config <path>".to_string())
}

struct AnalyzeWavArgs {
    input_path: PathBuf,
    config_path: PathBuf,
}

struct ExportWavArgs {
    input_path: PathBuf,
    output_path: PathBuf,
    config_path: PathBuf,
    csv_path: Option<PathBuf>,
}

fn parse_analyze_wav_args(args: Vec<String>) -> Result<AnalyzeWavArgs, String> {
    let mut input_path = None;
    let mut config_path = None;
    let mut iter = args.into_iter();
    while let Some(arg) = iter.next() {
        match arg.as_str() {
            "--input" => {
                let Some(path) = iter.next() else {
                    return Err("missing value for --input".to_string());
                };
                input_path = Some(PathBuf::from(path));
            }
            "--config" => {
                let Some(path) = iter.next() else {
                    return Err("missing value for --config".to_string());
                };
                config_path = Some(PathBuf::from(path));
            }
            _ => return Err(format!("unknown argument: {arg}")),
        }
    }
    Ok(AnalyzeWavArgs {
        input_path: input_path.ok_or_else(|| "missing required --input <audio>".to_string())?,
        config_path: config_path.ok_or_else(|| "missing required --config <path>".to_string())?,
    })
}

fn parse_export_wav_args(args: Vec<String>) -> Result<ExportWavArgs, String> {
    let mut input_path = None;
    let mut output_path = None;
    let mut config_path = None;
    let mut csv_path = None;
    let mut iter = args.into_iter();
    while let Some(arg) = iter.next() {
        match arg.as_str() {
            "--input" => {
                let Some(path) = iter.next() else {
                    return Err("missing value for --input".to_string());
                };
                input_path = Some(PathBuf::from(path));
            }
            "--output" => {
                let Some(path) = iter.next() else {
                    return Err("missing value for --output".to_string());
                };
                output_path = Some(PathBuf::from(path));
            }
            "--config" => {
                let Some(path) = iter.next() else {
                    return Err("missing value for --config".to_string());
                };
                config_path = Some(PathBuf::from(path));
            }
            "--csv" => {
                let Some(path) = iter.next() else {
                    return Err("missing value for --csv".to_string());
                };
                csv_path = Some(PathBuf::from(path));
            }
            _ => return Err(format!("unknown argument: {arg}")),
        }
    }
    Ok(ExportWavArgs {
        input_path: input_path.ok_or_else(|| "missing required --input <audio>".to_string())?,
        output_path: output_path.ok_or_else(|| "missing required --output <wav>".to_string())?,
        config_path: config_path.ok_or_else(|| "missing required --config <path>".to_string())?,
        csv_path,
    })
}

fn read_config(path: &PathBuf) -> Result<AppConfig, String> {
    let raw = fs::read_to_string(path)
        .map_err(|err| format!("failed to read config '{}': {err}", path.display()))?;
    serde_json::from_str(&raw)
        .map_err(|err| format!("failed to parse config '{}': {err}", path.display()))
}

fn export_wav(
    input_path: &PathBuf,
    output_path: &PathBuf,
    csv_path: Option<&PathBuf>,
    config: &AppConfig,
) -> Result<ExportResult, String> {
    let audio = noise_io::load_audio_mono(input_path)
        .map_err(|err| format!("failed to load input audio: {err}"))?;
    let samples = noise_core::reduce_noise(&audio.samples, audio.samplerate, &config.denoise);
    let events = if config.mode == ProcessMode::Highlight {
        noise_core::detect_events(&samples, audio.samplerate, &config.detect)
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

    noise_io::save_wav_mono(output_path, &built.samples, built.samplerate)
        .map_err(|err| format!("failed to save WAV: {err}"))?;
    let csv_path = if config.mode == ProcessMode::Highlight {
        if let Some(path) = csv_path {
            noise_io::save_report_csv(path, &events)
                .map_err(|err| format!("failed to save CSV: {err}"))?;
            Some(path.display().to_string())
        } else {
            None
        }
    } else {
        None
    };

    Ok(ExportResult {
        wav_path: output_path.display().to_string(),
        csv_path,
        kept_events: events.iter().filter(|event| event.keep).count(),
        duration_seconds: built.samples.len() as f64 / built.samplerate as f64,
    })
}

fn synthetic_close_peaks() -> (Vec<f32>, u32, f64) {
    let samplerate = 8000_u32;
    let duration_seconds = 3.0_f64;
    let mut samples = vec![0.0_f32; samplerate as usize * duration_seconds as usize];
    let first_start = (1.0 * samplerate as f64) as usize;
    let first_end = (1.05 * samplerate as f64) as usize;
    let second_start = (1.45 * samplerate as f64) as usize;
    let second_end = (1.50 * samplerate as f64) as usize;
    samples[first_start..first_end].fill(0.7);
    samples[second_start..second_end].fill(0.65);
    (samples, samplerate, duration_seconds)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::Value;

    #[test]
    fn synthetic_analysis_matches_expected_fixture_ranges() {
        let fixture_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("..")
            .join("fixtures");
        let config = read_config(&fixture_dir.join("synthetic-close-peaks.config.json")).unwrap();
        let expected: Value = serde_json::from_str(
            &fs::read_to_string(fixture_dir.join("synthetic-close-peaks.expected.json")).unwrap(),
        )
        .unwrap();

        let (samples, samplerate, duration_seconds) = synthetic_close_peaks();
        let work = noise_core::reduce_noise(&samples, samplerate, &config.denoise);
        let events = noise_core::detect_events(&work, samplerate, &config.detect);

        assert_eq!(samplerate, expected["samplerate"].as_u64().unwrap() as u32);
        assert!((duration_seconds - expected["duration_seconds"].as_f64().unwrap()).abs() < 1e-9);
        let expected_events = expected["events"].as_array().unwrap();
        assert_eq!(events.len(), expected_events.len());
        for (event, expected_event) in events.iter().zip(expected_events) {
            let start_range = expected_event["start_range"].as_array().unwrap();
            let end_range = expected_event["end_range"].as_array().unwrap();
            assert!(event.start >= start_range[0].as_f64().unwrap());
            assert!(event.start <= start_range[1].as_f64().unwrap());
            assert!(event.end >= end_range[0].as_f64().unwrap());
            assert!(event.end <= end_range[1].as_f64().unwrap());
            assert_eq!(event.manual, expected_event["manual"].as_bool().unwrap());
            assert_eq!(event.keep, expected_event["keep"].as_bool().unwrap());
        }
    }
}
