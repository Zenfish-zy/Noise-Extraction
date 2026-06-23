from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from noise_evidence.config import ClassifyConfig, DetectConfig, ExportConfig, GainConfig
from noise_evidence.detect import NoiseEvent, detect_events, make_manual_event
from noise_evidence.export import export_full_wav, export_highlight_wav, export_report_csv

ROOT = Path(__file__).resolve().parent.parent


class CoreWorkflowTest(unittest.TestCase):
    def test_close_peaks_merge_into_one_event(self) -> None:
        sr = 8000
        data = np.zeros(sr * 3, dtype=np.float32)
        data[int(1.0 * sr): int(1.05 * sr)] = 0.7
        data[int(1.45 * sr): int(1.50 * sr)] = 0.65

        cfg = DetectConfig(
            sensitivity="high",
            merge_gap_seconds=0.8,
            pad_seconds=0.1,
            min_peak_dbfs=-60.0,
        )
        events = detect_events(data, sr, cfg, ClassifyConfig())

        self.assertEqual(len(events), 1)
        self.assertLessEqual(events[0].start, 1.0)
        self.assertGreaterEqual(events[0].end, 1.5)

    def test_manual_event_accepts_reverse_drag_order(self) -> None:
        sr = 8000
        data = np.zeros(sr * 3, dtype=np.float32)
        data[int(1.8 * sr): int(2.0 * sr)] = 0.4

        event = make_manual_event(data, sr, 2.0, 1.8, ClassifyConfig())

        self.assertIsNotNone(event)
        assert event is not None
        self.assertTrue(event.manual)
        self.assertAlmostEqual(event.start, 1.8)
        self.assertAlmostEqual(event.end, 2.0)

    def test_full_and_highlight_exports_write_expected_files(self) -> None:
        sr = 8000
        data = np.zeros(sr * 2, dtype=np.float32)
        data[int(0.5 * sr): int(0.7 * sr)] = 0.5
        event = NoiseEvent(
            start=0.5,
            end=0.7,
            peak_dbfs=-6.0,
            rms_dbfs=-12.0,
            low_ratio=0.7,
            high_ratio=0.1,
            kind="thud",
        )

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            full_path = out / "full.wav"
            clip_path = out / "clip.wav"
            csv_path = out / "report.csv"

            export_full_wav(
                data,
                sr,
                full_path,
                ExportConfig(),
                GainConfig(enabled=True, mode="global"),
            )
            export_highlight_wav(data, sr, [event], clip_path, ExportConfig(), GainConfig())
            export_report_csv([event], csv_path)

            full_data, full_sr = sf.read(full_path)
            clip_data, clip_sr = sf.read(clip_path)
            self.assertEqual(full_sr, sr)
            self.assertEqual(clip_sr, sr)
            self.assertGreater(len(full_data), len(clip_data))
            self.assertGreater(len(clip_data), 0)

            with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.reader(f))
            self.assertIn("来源", rows[0])
            self.assertEqual(rows[1][2], "自动")

    def test_fixture_contract_close_peaks(self) -> None:
        config_path = ROOT / "next" / "fixtures" / "synthetic-close-peaks.config.json"
        expected_path = ROOT / "next" / "fixtures" / "synthetic-close-peaks.expected.json"
        with config_path.open("r", encoding="utf-8") as f:
            raw_config = json.load(f)
        with expected_path.open("r", encoding="utf-8") as f:
            expected = json.load(f)

        sr = int(expected["samplerate"])
        duration = float(expected["duration_seconds"])
        data = np.zeros(int(sr * duration), dtype=np.float32)
        data[int(1.0 * sr): int(1.05 * sr)] = 0.7
        data[int(1.45 * sr): int(1.50 * sr)] = 0.65

        detect_cfg = raw_config["detect"]
        cfg = DetectConfig(
            frame_ms=detect_cfg["frame_ms"],
            hop_ms=detect_cfg["hop_ms"],
            sensitivity=detect_cfg["sensitivity"],
            min_event_seconds=detect_cfg["min_event_seconds"],
            merge_gap_seconds=detect_cfg["merge_gap_seconds"],
            pad_seconds=detect_cfg["pad_seconds"],
            min_peak_dbfs=detect_cfg["min_peak_dbfs"],
        )
        events = detect_events(data, sr, cfg, ClassifyConfig())

        self.assertEqual(len(events), len(expected["events"]))
        for event, expected_event in zip(events, expected["events"], strict=True):
            start_min, start_max = expected_event["start_range"]
            end_min, end_max = expected_event["end_range"]
            self.assertGreaterEqual(event.start, start_min)
            self.assertLessEqual(event.start, start_max)
            self.assertGreaterEqual(event.end, end_min)
            self.assertLessEqual(event.end, end_max)
            self.assertEqual(event.manual, expected_event["manual"])
            self.assertEqual(event.keep, expected_event["keep"])


if __name__ == "__main__":
    unittest.main()
