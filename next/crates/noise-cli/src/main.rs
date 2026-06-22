use std::env;
use std::fs;
use std::path::PathBuf;
use std::process;

use noise_types::{AnalyzeResult, AppConfig};

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
            let events = noise_core::detect_events(&samples, samplerate, &config.detect);
            let result = AnalyzeResult {
                samplerate,
                duration_seconds,
                events,
            };
            let json = serde_json::to_string_pretty(&result).map_err(|err| err.to_string())?;
            println!("{json}");
            Ok(())
        }
        _ => Err(usage()),
    }
}

fn usage() -> String {
    "usage: noise-cli analyze-synthetic --config <path>".to_string()
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

fn read_config(path: &PathBuf) -> Result<AppConfig, String> {
    let raw = fs::read_to_string(path)
        .map_err(|err| format!("failed to read config '{}': {err}", path.display()))?;
    serde_json::from_str(&raw)
        .map_err(|err| format!("failed to parse config '{}': {err}", path.display()))
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
