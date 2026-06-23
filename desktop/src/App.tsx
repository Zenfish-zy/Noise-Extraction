import { convertFileSrc, invoke } from "@tauri-apps/api/core";
import { open, save } from "@tauri-apps/plugin-dialog";
import { useEffect, useRef, useState, type PointerEvent, type ReactNode } from "react";
import {
  Download,
  FileAudio,
  Info,
  ListChecks,
  Pause,
  Play,
  ScanLine,
  Scissors,
  Settings2,
  Trash2,
  Volume2,
} from "lucide-react";

type EventKind = "rumble" | "thud" | "drag" | "transient" | "other";
type ProcessMode = "full_denoise" | "full_amplify" | "highlight";
type Sensitivity = "low" | "medium" | "high";
type GainMode = "off" | "global" | "per_event";

type CoreNoiseEvent = {
  start: number;
  end: number;
  kind: EventKind;
  peak_dbfs: number;
  rms_dbfs: number;
  low_ratio: number;
  high_ratio: number;
  suspect_self: boolean;
  keep: boolean;
  manual: boolean;
};

type AnalyzeResult = {
  samplerate: number;
  duration_seconds: number;
  events: CoreNoiseEvent[];
};

type WaveformBin = {
  min: number;
  max: number;
};

type WaveformResult = {
  samplerate: number;
  duration_seconds: number;
  bins: WaveformBin[];
};

type AudioPreviewResult = {
  wav_path: string;
  samplerate: number;
  duration_seconds: number;
};

type AppConfig = {
  mode: ProcessMode;
  denoise: {
    enabled: boolean;
    noise_sample_seconds: number;
    prop_decrease: number;
    stationary: boolean;
  };
  detect: DetectConfig;
  gain: GainConfig;
  export: ExportConfig;
};

type DetectConfig = {
  frame_ms: number;
  hop_ms: number;
  sensitivity: Sensitivity;
  min_event_seconds: number;
  merge_gap_seconds: number;
  pad_seconds: number;
  min_peak_dbfs: number;
};

type GainConfig = {
  enabled: boolean;
  mode: GainMode;
  target_peak_dbfs: number;
  max_gain_db: number;
};

type ExportConfig = {
  gap_seconds: number;
  insert_beep: boolean;
  beep_hz: number;
  beep_seconds: number;
  out_samplerate: number | null;
};

type ExportResult = {
  wav_path: string;
  csv_path: string | null;
  kept_events: number;
  duration_seconds: number;
};

type NoiseEvent = {
  id: number;
  start: number;
  end: number;
  kind: EventKind;
  peak_dbfs: number;
  rms_dbfs: number;
  low_ratio: number;
  high_ratio: number;
  suspect_self: boolean;
  keep: boolean;
  manual: boolean;
};

const kindLabel: Record<EventKind, string> = {
  rumble: "低频闷响",
  thud: "重击",
  drag: "拖拽",
  transient: "瞬态",
  other: "其他",
};

const kindTone: Record<EventKind, string> = {
  rumble: "#507e70",
  thud: "#b07b52",
  drag: "#7a6d94",
  transient: "#6a8e7a",
  other: "#968e7e",
};

const audioExtensions = ["m4a", "mp4", "aac", "mp3", "wav", "flac", "ogg", "oga"];
const waveformBinCount = 720;

function App() {
  const waveformRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const [version, setVersion] = useState("0.1.0");
  const [analysis, setAnalysis] = useState<AnalyzeResult | null>(null);
  const [waveformBins, setWaveformBins] = useState<WaveformBin[]>([]);
  const [events, setEvents] = useState<NoiseEvent[]>([]);
  const [selectedEventId, setSelectedEventId] = useState<number>(0);
  const [selectingSpan, setSelectingSpan] = useState(false);
  const [dragSpan, setDragSpan] = useState<{ start: number; end: number } | null>(null);
  const [audioSrc, setAudioSrc] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playheadSec, setPlayheadSec] = useState(0);
  const [fileLabel, setFileLabel] = useState("等待导入录音");
  const [inputPath, setInputPath] = useState<string | null>(null);
  const [status, setStatus] = useState("请先导入录音文件");
  const [error, setError] = useState<string | null>(null);
  const [sensitivity, setSensitivity] = useState<Sensitivity>("medium");
  const [mergeGap, setMergeGap] = useState(0.8);
  const [padSeconds, setPadSeconds] = useState(0.6);
  const [minPeakDbfs, setMinPeakDbfs] = useState(-45);
  const [denoiseEnabled, setDenoiseEnabled] = useState(true);
  const [amplifyEnabled, setAmplifyEnabled] = useState(false);
  const [sliceEnabled, setSliceEnabled] = useState(false);

  useEffect(() => {
    void invoke<string>("app_version")
      .then(setVersion)
      .catch(() => undefined);
  }, []);

  function detectConfig(): DetectConfig {
    return {
      frame_ms: 30,
      hop_ms: 10,
      sensitivity,
      min_event_seconds: 0.08,
      merge_gap_seconds: mergeGap,
      pad_seconds: padSeconds,
      min_peak_dbfs: minPeakDbfs,
    };
  }

  function gainConfig(): GainConfig {
    if (!amplifyEnabled) {
      return {
        enabled: false,
        mode: "off",
        target_peak_dbfs: -1,
        max_gain_db: 36,
      };
    }
    return {
      enabled: true,
      mode: sliceEnabled ? "per_event" : "global",
      target_peak_dbfs: -1,
      max_gain_db: 36,
    };
  }

  function exportConfig(): ExportConfig {
    return {
      gap_seconds: 0.5,
      insert_beep: true,
      beep_hz: 880,
      beep_seconds: 0.12,
      out_samplerate: null,
    };
  }

  function appConfig(options?: { denoiseEnabled?: boolean }): AppConfig {
    const mode: ProcessMode = sliceEnabled ? "highlight" : (denoiseEnabled ? "full_denoise" : "full_amplify");
    return {
      mode,
      denoise: {
        enabled: options?.denoiseEnabled ?? denoiseEnabled,
        noise_sample_seconds: 1,
        prop_decrease: 0.9,
        stationary: true,
      },
      detect: detectConfig(),
      gain: gainConfig(),
      export: exportConfig(),
    };
  }

  async function inspectCurrentAudio(path: string, config = appConfig()) {
    setError(null);
    setStatus("正在读取音频信息");
    try {
      const [result, waveform, preview] = await Promise.all([
        invoke<AnalyzeResult>("inspect_audio", {
          inputPath: path,
        }),
        invoke<WaveformResult>("waveform_peaks", {
          inputPath: path,
          bins: waveformBinCount,
          config,
        }),
        invoke<AudioPreviewResult>("prepare_audio_preview", {
          inputPath: path,
          config,
        }),
      ]);
      setAnalysis(result);
      setWaveformBins(waveform.bins);
      setEvents([]);
      setSelectedEventId(0);
      setAudioSrc(convertFileSrc(preview.wav_path));
      setIsPlaying(false);
      setPlayheadSec(0);
      setFileLabel(path.split(/[\\/]/).pop() ?? path);
      setInputPath(path);
      setStatus("录音已导入 · 请配置参数后检测");
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      setAnalysis(null);
      setWaveformBins([]);
      setEvents([]);
      setSelectedEventId(0);
      setAudioSrc(null);
      setIsPlaying(false);
      setPlayheadSec(0);
      setFileLabel("等待导入录音");
      setInputPath(null);
      setStatus("录音导入失败");
    }
  }

  async function analyzeCurrentAudio(path: string) {
    setError(null);
    setStatus("正在分析音频");
    try {
      const result = await invoke<AnalyzeResult>("analyze_audio", {
        inputPath: path,
        config: appConfig(),
      });
      const mapped = mapCoreEvents(result.events);
      setAnalysis(result);
      setEvents(mapped);
      setSelectedEventId(mapped[0]?.id ?? 0);
      setFileLabel(path.split(/[\\/]/).pop() ?? path);
      setInputPath(path);
      setStatus(`音频分析完成 · ${result.events.length} 段`);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      setStatus("音频分析失败");
    }
  }

  async function importAudio() {
    setError(null);
    const selected = await open({
      multiple: false,
      directory: false,
      title: "选择录音文件",
      filters: [{ name: "音频文件", extensions: audioExtensions }],
    });
    if (typeof selected !== "string") {
      return;
    }

    await inspectCurrentAudio(selected);
  }

  async function exportEvidence() {
    setError(null);
    if (!inputPath) {
      setError("请先导入录音文件。");
      setStatus("等待导入录音");
      return;
    }
    if (sliceEnabled && events.length === 0) {
      setError("请先点击「检测事件」，再导出智能切片合集。");
      setStatus("等待检测事件");
      return;
    }
    if (sliceEnabled && events.every((event) => !event.keep)) {
      setError("请至少保留一个事件后再导出智能切片合集。");
      setStatus("等待复核事件");
      return;
    }

    const base = stripExtension(fileLabel || "noise-evidence");
    const wavPath = await save({
      title: "保存导出 WAV",
      defaultPath: `${base}_${sliceEnabled ? "噪音提取" : "整段处理"}.wav`,
      filters: [{ name: "WAV 音频", extensions: ["wav"] }],
    });
    if (!wavPath) {
      return;
    }

    let csvPath: string | null = null;
    if (sliceEnabled) {
      const selectedCsvPath = await save({
        title: "保存 CSV 证据报告",
        defaultPath: `${base}_证据报告.csv`,
        filters: [{ name: "CSV 报告", extensions: ["csv"] }],
      });
      if (!selectedCsvPath) {
        return;
      }
      csvPath = selectedCsvPath;
    }

    setStatus("正在导出");
    try {
      const result = await invoke<ExportResult>("export_audio", {
        inputPath,
        wavPath,
        csvPath,
        config: appConfig(),
        events: sliceEnabled ? events.map(toCoreEvent) : null,
      });
      setStatus(
        result.csv_path
          ? `导出完成 · ${result.kept_events} 段 · WAV + CSV`
          : `导出完成 · ${result.duration_seconds.toFixed(1)}s · WAV`,
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      setStatus("导出失败");
    }
  }

  function toggleKeep(id: number) {
    setEvents((current) => current.map((event) => (event.id === id ? { ...event, keep: !event.keep } : event)));
  }

  function deleteEvent(id: number) {
    setEvents((current) => {
      const next = current.filter((event) => event.id !== id);
      if (selectedEventId === id) {
        setSelectedEventId(next[0]?.id ?? 0);
      }
      return next;
    });
  }

  function pointToSeconds(event: PointerEvent<HTMLElement>) {
    const rect = waveformRef.current?.getBoundingClientRect();
    if (!rect) {
      return 0;
    }
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
    return ratio * durationSeconds;
  }

  function beginSpanSelection(event: PointerEvent<HTMLElement>) {
    if (!selectingSpan) {
      const sec = pointToSeconds(event);
      setPlayheadSec(sec);
      if (audioRef.current) {
        audioRef.current.currentTime = sec;
      }
      return;
    }
    const start = pointToSeconds(event);
    setDragSpan({ start, end: start });
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function updateSpanSelection(event: PointerEvent<HTMLElement>) {
    if (!dragSpan || !selectingSpan) {
      return;
    }
    setDragSpan((span) => (span ? { ...span, end: pointToSeconds(event) } : span));
  }

  async function finishSpanSelection(event: PointerEvent<HTMLElement>) {
    if (!dragSpan || !selectingSpan) {
      return;
    }
    const end = pointToSeconds(event);
    const start = Math.min(dragSpan.start, end);
    const stop = Math.max(dragSpan.start, end);
    setDragSpan(null);
    setSelectingSpan(false);
    if (stop - start < 0.05) {
      setStatus("框选区间太短，已忽略");
      return;
    }
    if (!inputPath) {
      setError("请先导入真实录音，再框选新增事件。");
      return;
    }
    setStatus("正在新增手动事件");
    try {
      const created = await invoke<CoreNoiseEvent>("manual_event", {
        inputPath,
        start,
        end: stop,
        config: appConfig(),
      });
      setEvents((current) => {
        const nextId = current.reduce((max, item) => Math.max(max, item.id), 0) + 1;
        const next = [...current, { ...created, id: nextId }].sort((a, b) => a.start - b.start);
        setSelectedEventId(nextId);
        return next;
      });
      setStatus(`已新增手动事件 · ${formatTime(start)} - ${formatTime(stop)}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      setStatus("新增事件失败");
    }
  }

  async function togglePlayback() {
    const audio = audioRef.current;
    if (!audioSrc || !audio) {
      return;
    }
    try {
      if (audio.paused) {
        await audio.play();
        setIsPlaying(true);
      } else {
        audio.pause();
        setIsPlaying(false);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      setStatus("播放失败");
      setIsPlaying(false);
    }
  }

  async function changeDenoiseEnabled(enabled: boolean) {
    setDenoiseEnabled(enabled);
    setError(null);
    if (inputPath) {
      await inspectCurrentAudio(inputPath, appConfig({ denoiseEnabled: enabled }));
    }
  }

  async function changeAmplifyEnabled(enabled: boolean) {
    setAmplifyEnabled(enabled);
    setError(null);
    if (inputPath) {
      await inspectCurrentAudio(inputPath);
    }
  }

  async function changeSliceEnabled(enabled: boolean) {
    setSliceEnabled(enabled);
    setError(null);
    if (inputPath) {
      await inspectCurrentAudio(inputPath);
    }
  }

  const hasInput = inputPath !== null;
  const kept = events.filter((event) => event.keep);
  const keptSeconds = kept.reduce((sum, event) => sum + event.end - event.start, 0);
  const durationSeconds = Math.max(analysis?.duration_seconds ?? 1, 1);
  const selected = events.find((event) => event.id === selectedEventId) ?? events[0] ?? null;
  const dragLeft = dragSpan ? (Math.min(dragSpan.start, dragSpan.end) / durationSeconds) * 100 : 0;
  const dragWidth = dragSpan ? (Math.abs(dragSpan.end - dragSpan.start) / durationSeconds) * 100 : 0;
  const playheadLeft = (Math.max(0, Math.min(playheadSec, durationSeconds)) / durationSeconds) * 100;
  const exportSummary =
    !hasInput
      ? "等待导入录音"
      : sliceEnabled
      ? `合集约 ${keptSeconds.toFixed(1)} 秒 · WAV + CSV`
      : `${durationSeconds.toFixed(1)} 秒 · 仅 WAV`;

  return (
    <main className="appShell">
      <section className="topBar" aria-label="全局操作">
        <div className="brandBlock">
          <div className="appMark">
            <Volume2 size={22} />
          </div>
          <div>
            <h1>寻音殿</h1>
            <p>v{version}</p>
          </div>
        </div>

        <div className="topActions">
          <button className="primaryButton" onClick={importAudio}>
            <FileAudio size={18} />
            导入录音
          </button>
          <button className="ghostButton" onClick={exportEvidence}>
            <Download size={18} />
            导出
          </button>
        </div>
      </section>

      <section className="workspace">
        {audioSrc ? (
          <audio
            ref={audioRef}
            src={audioSrc}
            onTimeUpdate={(event) => setPlayheadSec(event.currentTarget.currentTime)}
            onPause={() => setIsPlaying(false)}
            onPlay={() => setIsPlaying(true)}
            onEnded={() => setIsPlaying(false)}
          />
        ) : null}
        <aside className="flowRail" aria-label="流程">
          <Step active={hasInput} icon={<FileAudio size={18} />} label="导入" value={hasInput ? "已加载" : "待导入"} />
          <Step active={hasInput} icon={<Settings2 size={18} />} label="预处理" value={hasInput ? (denoiseEnabled ? "滤底噪" : "原始") : "待处理"} />
          <Step active={events.length > 0} icon={<ScanLine size={18} />} label="检测" value={hasInput ? `${events.length} 段` : "待检测"} />
          <Step active={kept.length > 0} icon={<ListChecks size={18} />} label="复核" value={`${kept.length} 保留`} />
          <Step icon={<Download size={18} />} label="导出" value="待确认" />
        </aside>

        <section className="mainPanel">
          <div className="toolbar">
            <div className="fileMeta">
              <strong>{fileLabel}</strong>
              <span>{hasInput ? `${status} · ${durationSeconds.toFixed(1)}s` : status}</span>
            </div>
            <div className="toolButtons">
              <button onClick={() => void togglePlayback()} disabled={!audioSrc}>
                {isPlaying ? <Pause size={17} /> : <Play size={17} />}
                {isPlaying ? "暂停" : "播放"}
              </button>
              <button
                onClick={() => {
                  if (inputPath) {
                    void analyzeCurrentAudio(inputPath);
                  }
                }}
                disabled={!inputPath}
              >
                <ScanLine size={17} />
                检测事件
              </button>
              <button
                className={selectingSpan ? "activeTool" : ""}
                onClick={() => {
                  setSelectingSpan((value) => !value);
                  setDragSpan(null);
                  setError(null);
                }}
                disabled={!inputPath}
              >
                <Scissors size={17} />
                框选新增
              </button>
            </div>
          </div>

          {error ? <div className="errorBanner">{error}</div> : null}

          <div
            ref={waveformRef}
            className={`waveform ${selectingSpan ? "selecting" : ""}`}
            aria-label="波形时间轴"
            onPointerDown={beginSpanSelection}
            onPointerMove={updateSpanSelection}
            onPointerUp={(event) => {
              void finishSpanSelection(event);
            }}
            onPointerCancel={() => {
              setDragSpan(null);
              setSelectingSpan(false);
            }}
          >
            <div className="waveGrid" />
            {!hasInput ? (
              <div className="emptyWaveform">
                <FileAudio size={30} />
                <strong>等待导入录音</strong>
              </div>
            ) : null}
            <div className="waveBars" aria-hidden="true">
              {waveformBins.map((bin, index) => {
                const min = clamp(bin.min, -1, 1);
                const max = clamp(bin.max, -1, 1);
                const top = ((1 - max) / 2) * 100;
                const height = Math.max(((max - min) / 2) * 100, 1.2);
                return (
                  <span
                    key={index}
                    className="waveBar"
                    style={{
                      left: `${(index / Math.max(waveformBins.length, 1)) * 100}%`,
                      width: `${100 / Math.max(waveformBins.length, 1)}%`,
                      top: `${top}%`,
                      height: `${height}%`,
                    }}
                  />
                );
              })}
            </div>
            {events.map((event) => (
              <div
                key={event.id}
                className={`eventBlock ${event.keep ? "" : "muted"} ${event.id === selected?.id ? "selected" : ""}`}
                style={{
                  left: `${(event.start / durationSeconds) * 100}%`,
                  width: `${((event.end - event.start) / durationSeconds) * 100}%`,
                  backgroundColor: kindTone[event.kind],
                }}
                onClick={() => setSelectedEventId(event.id)}
              />
            ))}
            {dragSpan ? <div className="selectionBlock" style={{ left: `${dragLeft}%`, width: `${dragWidth}%` }} /> : null}
            <div className="playhead" style={{ left: `${playheadLeft}%` }} />
          </div>

          <div className="reviewTable" role="table" aria-label="事件列表">
            <div className="tableHead" role="row">
              <span>保留</span>
              <span>开始</span>
              <span>时长</span>
              <span>来源</span>
              <span>类型</span>
              <span>峰值</span>
              <span />
            </div>
            {events.map((event) => (
              <div
                className={`tableRow ${event.id === selected?.id ? "selected" : ""}`}
                role="row"
                key={event.id}
                onClick={() => setSelectedEventId(event.id)}
              >
                <button
                  className={event.keep ? "pill keep" : "pill off"}
                  onClick={(clickEvent) => {
                    clickEvent.stopPropagation();
                    toggleKeep(event.id);
                  }}
                >
                  {event.keep ? "保留" : "排除"}
                </button>
                <span>{formatTime(event.start)}</span>
                <span>{(event.end - event.start).toFixed(2)}s</span>
                <span>{event.manual ? "手动" : "自动"}</span>
                <span className="kind" style={{ color: kindTone[event.kind] }}>
                  {kindLabel[event.kind]}
                </span>
                <span>{event.peak_dbfs.toFixed(1)} dB</span>
                <button
                  className="iconButton"
                  aria-label="删除事件"
                  onClick={(clickEvent) => {
                    clickEvent.stopPropagation();
                    deleteEvent(event.id);
                  }}
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>
        </section>

        <aside className="sidePanel" aria-label="设置与事件">
          <div className="settingsSection">
            <h3>功能设置</h3>
            <label className="toggleSetting">
              <span>滤底噪 · {denoiseEnabled ? "开" : "关"}</span>
              <input
                type="checkbox"
                checked={denoiseEnabled}
                onChange={(event) => {
                  void changeDenoiseEnabled(event.target.checked);
                }}
              />
            </label>
            <label className="toggleSetting">
              <span>整段放大 · {amplifyEnabled ? "开" : "关"}</span>
              <input
                type="checkbox"
                checked={amplifyEnabled}
                onChange={(event) => {
                  void changeAmplifyEnabled(event.target.checked);
                }}
              />
            </label>
            <label className="toggleSetting">
              <span>切片 · {sliceEnabled ? "开" : "关"}</span>
              <input
                type="checkbox"
                checked={sliceEnabled}
                onChange={(event) => {
                  void changeSliceEnabled(event.target.checked);
                }}
              />
            </label>
            <label>
              <span>灵敏度 · {sensitivity === "high" ? "高" : sensitivity === "low" ? "低" : "中"}</span>
              <select value={sensitivity} onChange={(event) => setSensitivity(event.target.value as Sensitivity)}>
                <option value="low">低</option>
                <option value="medium">中</option>
                <option value="high">高</option>
              </select>
            </label>
            <label>
              <span>合并间隔 · {mergeGap.toFixed(1)}s</span>
              <input
                type="range"
                min="0"
                max="5"
                step="0.1"
                value={mergeGap}
                onChange={(event) => setMergeGap(Number(event.target.value))}
              />
            </label>
            <label>
              <span>起止缓冲 · {padSeconds.toFixed(1)}s</span>
              <input
                type="range"
                min="0"
                max="3"
                step="0.1"
                value={padSeconds}
                onChange={(event) => setPadSeconds(Number(event.target.value))}
              />
            </label>
            <label>
              <span>最小响度 · {minPeakDbfs} dBFS</span>
              <input
                type="range"
                min="-90"
                max="-10"
                step="1"
                value={minPeakDbfs}
                onChange={(event) => setMinPeakDbfs(Number(event.target.value))}
              />
            </label>
          </div>

          <div className="eventSection">
            <div className="sideHeader">
              <h3>{selected ? `事件 #${selected.id}` : "未选择事件"}</h3>
              <button className="iconButton" aria-label="事件说明">
                <Info size={16} />
              </button>
            </div>
            {selected ? (
              <dl className="detailList">
                <div>
                  <dt>时间</dt>
                  <dd>
                    {formatTime(selected.start)} - {formatTime(selected.end)}
                  </dd>
                </div>
                <div>
                  <dt>类型</dt>
                  <dd>{kindLabel[selected.kind]}</dd>
                </div>
                <div>
                  <dt>峰值</dt>
                  <dd>{selected.peak_dbfs.toFixed(1)} dBFS</dd>
                </div>
              </dl>
            ) : (
              <div className="emptyState">暂无事件</div>
            )}
          </div>
        </aside>
      </section>

      <section className="exportBar" aria-label="导出摘要">
        <div>
          <strong>{kept.length} 段保留</strong>
          <span>{exportSummary}</span>
        </div>
        <button className="primaryButton" onClick={exportEvidence} disabled={!hasInput || (sliceEnabled && events.length === 0)}>
          <Download size={18} />
          导出证据
        </button>
      </section>
    </main>
  );
}

function Step(props: { active?: boolean; icon: ReactNode; label: string; value: string }) {
  return (
    <div className={`step ${props.active ? "active" : ""}`}>
      <div className="stepIcon">{props.icon}</div>
      <div>
        <strong>{props.label}</strong>
        <span>{props.value}</span>
      </div>
    </div>
  );
}

function mapCoreEvents(events: CoreNoiseEvent[]): NoiseEvent[] {
  return events.map((event, index) => ({ ...event, id: index + 1 }));
}

function toCoreEvent(event: NoiseEvent): CoreNoiseEvent {
  const { id: _id, ...coreEvent } = event;
  return coreEvent;
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function formatTime(value: number) {
  const minutes = Math.floor(value / 60);
  const seconds = value - minutes * 60;
  return `${minutes.toString().padStart(2, "0")}:${seconds.toFixed(2).padStart(5, "0")}`;
}

function stripExtension(value: string) {
  return value.replace(/\.[^/.\\]+$/, "");
}

export default App;
