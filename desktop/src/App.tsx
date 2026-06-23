import { convertFileSrc, invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
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
  Sparkles,
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

type AIConfig = {
  enabled: boolean;
  api_endpoint: string;
  api_key: string;
  model: string;
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
  ai: AIConfig;
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
  const [sensitivity, setSensitivity] = useState<Sensitivity>(() => {
    return (localStorage.getItem("sensitivity") as Sensitivity) || "medium";
  });
  const [mergeGap, setMergeGap] = useState(() => {
    const saved = localStorage.getItem("mergeGap");
    return saved ? Number(saved) : 0.8;
  });
  const [padSeconds, setPadSeconds] = useState(() => {
    const saved = localStorage.getItem("padSeconds");
    return saved ? Number(saved) : 0.6;
  });
  const [minPeakDbfs, setMinPeakDbfs] = useState(() => {
    const saved = localStorage.getItem("minPeakDbfs");
    return saved ? Number(saved) : -45;
  });
  const [denoiseEnabled, setDenoiseEnabled] = useState(true);
  const [amplifyEnabled, setAmplifyEnabled] = useState(false);
  const [sliceEnabled, setSliceEnabled] = useState(false);
  const [importProgress, setImportProgress] = useState<{ stage: string; percent: number } | null>(null);
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [aiEnabled, setAiEnabled] = useState(() => {
    const saved = localStorage.getItem("aiEnabled");
    return saved ? JSON.parse(saved) : false;
  });
  const [aiFormat, setAiFormat] = useState<"openai" | "anthropic" | "custom">(() => {
    return (localStorage.getItem("aiFormat") as "openai" | "anthropic" | "custom") || "openai";
  });
  const [aiBaseUrl, setAiBaseUrl] = useState(() => {
    return localStorage.getItem("aiBaseUrl") || "https://api.openai.com";
  });
  const [aiEndpoint, setAiEndpoint] = useState(() => {
    return localStorage.getItem("aiEndpoint") || "https://api.openai.com/v1/chat/completions";
  });
  const [aiKey, setAiKey] = useState(() => {
    return localStorage.getItem("aiKey") || "";
  });
  const [aiModel, setAiModel] = useState(() => {
    return localStorage.getItem("aiModel") || "gpt-4o-mini";
  });
  const [proxyEnabled, setProxyEnabled] = useState(() => {
    const saved = localStorage.getItem("proxyEnabled");
    return saved ? JSON.parse(saved) : false;
  });
  const [proxyUrl, setProxyUrl] = useState(() => {
    return localStorage.getItem("proxyUrl") || "";
  });
  const [proxyScanning, setProxyScanning] = useState(false);
  const [proxyResults, setProxyResults] = useState<Array<{ url: string; available: boolean; name: string }>>([]);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [modeMenuOpen, setModeMenuOpen] = useState(false);
  const [settingsTab, setSettingsTab] = useState<"detect" | "ai" | "export" | "about">("detect");

  // Save AI settings to localStorage
  useEffect(() => {
    localStorage.setItem("aiEnabled", JSON.stringify(aiEnabled));
  }, [aiEnabled]);

  useEffect(() => {
    localStorage.setItem("aiFormat", aiFormat);
  }, [aiFormat]);

  useEffect(() => {
    localStorage.setItem("aiBaseUrl", aiBaseUrl);
  }, [aiBaseUrl]);

  useEffect(() => {
    // Auto-complete endpoint based on format
    let fullEndpoint = "";
    if (aiFormat === "openai") {
      fullEndpoint = `${aiBaseUrl.replace(/\/$/, "")}/v1/responses`;
    } else if (aiFormat === "anthropic") {
      fullEndpoint = `${aiBaseUrl.replace(/\/$/, "")}/v1/messages`;
    } else {
      fullEndpoint = aiBaseUrl; // custom: no auto-complete
    }
    setAiEndpoint(fullEndpoint);
    localStorage.setItem("aiEndpoint", fullEndpoint);
  }, [aiFormat, aiBaseUrl]);

  useEffect(() => {
    localStorage.setItem("aiKey", aiKey);
  }, [aiKey]);

  useEffect(() => {
    localStorage.setItem("aiModel", aiModel);
  }, [aiModel]);

  useEffect(() => {
    localStorage.setItem("proxyEnabled", JSON.stringify(proxyEnabled));
  }, [proxyEnabled]);

  useEffect(() => {
    localStorage.setItem("proxyUrl", proxyUrl);
  }, [proxyUrl]);

  // Save detection parameters to localStorage
  useEffect(() => {
    localStorage.setItem("sensitivity", sensitivity);
  }, [sensitivity]);

  useEffect(() => {
    localStorage.setItem("mergeGap", String(mergeGap));
  }, [mergeGap]);

  useEffect(() => {
    localStorage.setItem("padSeconds", String(padSeconds));
  }, [padSeconds]);

  useEffect(() => {
    localStorage.setItem("minPeakDbfs", String(minPeakDbfs));
  }, [minPeakDbfs]);

  useEffect(() => {
    void invoke<string>("app_version")
      .then(setVersion)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    const handleClickOutside = () => {
      setModeMenuOpen(false);
      setExportMenuOpen(false);
    };
    if (modeMenuOpen || exportMenuOpen) {
      document.addEventListener("click", handleClickOutside);
      return () => document.removeEventListener("click", handleClickOutside);
    }
  }, [modeMenuOpen, exportMenuOpen]);

  useEffect(() => {
    const unlisten = listen<{ stage: string; percent: number }>("import_progress", (event) => {
      setStatus(event.payload.stage);
      setImportProgress(event.payload);
      if (event.payload.percent >= 100) {
        setTimeout(() => setImportProgress(null), 800);
      }
    });
    return () => {
      void unlisten.then((fn) => fn());
    };
  }, []);

  useEffect(() => {
    const handleClickOutside = () => {
      if (exportMenuOpen) {
        setExportMenuOpen(false);
      }
    };
    if (exportMenuOpen) {
      document.addEventListener("click", handleClickOutside);
      return () => document.removeEventListener("click", handleClickOutside);
    }
  }, [exportMenuOpen]);

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
      ai: {
        enabled: aiEnabled,
        api_endpoint: aiEndpoint,
        api_key: aiKey,
        model: aiModel,
      },
    };
  }

  async function inspectCurrentAudio(path: string, config = appConfig()) {
    setError(null);
    setStatus("正在准备导入");
    try {
      const [result, waveform, preview] = await invoke<[AnalyzeResult, WaveformResult, AudioPreviewResult]>(
        "inspect_audio_with_progress",
        {
          inputPath: path,
          bins: waveformBinCount,
          config,
        }
      );
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

  async function refreshPreview(path: string, config = appConfig()) {
    setError(null);
    setStatus("正在刷新预览");
    setImportProgress({ stage: "正在刷新预览", percent: 30 });
    try {
      const [waveform, preview] = await Promise.all([
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
      setImportProgress({ stage: "预览已更新", percent: 100 });
      setTimeout(() => setImportProgress(null), 800);
      setWaveformBins(waveform.bins);
      setAudioSrc(convertFileSrc(preview.wav_path));
      setIsPlaying(false);
      setPlayheadSec(0);
      setStatus("预览已更新");
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      setStatus("预览刷新失败");
    }
  }

  async function analyzeCurrentAudio(path: string) {
    setError(null);
    setStatus("正在分析音频");
    setImportProgress({ stage: "正在分析音频", percent: 50 });
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
      setImportProgress({ stage: `分析完成 · ${result.events.length} 段`, percent: 100 });
      setTimeout(() => setImportProgress(null), 800);
      setStatus(`音频分析完成 · ${result.events.length} 段`);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      setImportProgress(null);
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

  async function exportEvidence(exportType: "audio" | "csv" | "both" = "both") {
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

    let wavPath: string | null = null;
    if (exportType === "audio" || exportType === "both") {
      wavPath = await save({
        title: "保存导出 WAV",
        defaultPath: `${base}_${sliceEnabled ? "噪音提取" : "整段处理"}.wav`,
        filters: [{ name: "WAV 音频", extensions: ["wav"] }],
      });
      if (!wavPath) {
        return;
      }
    }

    let csvPath: string | null = null;
    if ((exportType === "csv" || exportType === "both") && sliceEnabled) {
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

    if (!wavPath && !csvPath) {
      return;
    }

    setStatus("正在导出");
    setImportProgress({ stage: "正在导出音频", percent: 60 });
    try {
      const result = await invoke<ExportResult>("export_audio", {
        inputPath,
        wavPath: wavPath ?? "",
        csvPath,
        config: appConfig(),
        events: sliceEnabled ? events.map(toCoreEvent) : null,
      });
      setImportProgress({ stage: "导出完成", percent: 100 });
      setTimeout(() => setImportProgress(null), 800);
      setStatus(
        result.csv_path
          ? `导出完成 · ${result.kept_events} 段 · WAV + CSV`
          : `导出完成 · ${result.duration_seconds.toFixed(1)}s · WAV`,
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      setImportProgress(null);
      setStatus("导出失败");
    }
  }

  function selectAndPlayEvent(id: number) {
    const event = events.find((e) => e.id === id);
    if (!event) return;

    setSelectedEventId(id);
    if (audioRef.current) {
      audioRef.current.currentTime = event.start;
      void audioRef.current.play();
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
    if (inputPath) {
      await refreshPreview(inputPath, appConfig({ denoiseEnabled: enabled }));
    }
  }

  async function changeAmplifyEnabled(enabled: boolean) {
    setAmplifyEnabled(enabled);
    if (inputPath) {
      await refreshPreview(inputPath);
    }
  }

  async function changeSliceEnabled(enabled: boolean) {
    setSliceEnabled(enabled);
    if (inputPath) {
      await refreshPreview(inputPath);
    }
  }

  async function redetectEvents() {
    if (!inputPath) return;
    setError(null);
    setStatus("正在重新检测事件");
    setImportProgress({ stage: "正在重新检测事件", percent: 50 });
    try {
      const result = await invoke<AnalyzeResult>("analyze_audio", {
        inputPath,
        config: appConfig(),
      });
      const mapped = mapCoreEvents(result.events);
      setEvents(mapped);
      setSelectedEventId(mapped[0]?.id ?? 0);
      setImportProgress({ stage: `检测完成 · ${result.events.length} 段`, percent: 100 });
      setTimeout(() => setImportProgress(null), 800);
      setStatus(`检测完成 · ${result.events.length} 段`);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      setImportProgress(null);
      setStatus("检测失败");
    }
  }

  async function aiEnhanceEvents() {
    if (events.length === 0) {
      setError("请先检测事件再使用 AI 增强");
      return;
    }
    if (!aiEnabled) {
      setError("请先开启 AI 识别功能");
      return;
    }
    if (!aiKey) {
      setError("请先配置 API Key");
      return;
    }

    setError(null);
    setStatus("正在使用 AI 增强识别");
    setImportProgress({ stage: "AI 正在分析事件类型", percent: 50 });
    try {
      const coreEvents = events.map(toCoreEvent);
      const enhanced = await invoke<CoreNoiseEvent[]>("ai_enhance_events", {
        events: coreEvents,
        config: appConfig(),
      });
      const mapped = mapCoreEvents(enhanced);
      setEvents(mapped);
      setImportProgress({ stage: "AI 增强完成", percent: 100 });
      setTimeout(() => setImportProgress(null), 800);
      setStatus("AI 增强完成");
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      setImportProgress(null);
      setStatus("AI 增强失败");
    }
  }

  async function aiProcessAudio() {
    if (!inputPath) {
      setError("请先导入录音文件");
      return;
    }
    if (!aiEnabled) {
      setError("请先开启 AI 功能");
      return;
    }
    if (!aiKey) {
      setError("请先配置 API Key");
      return;
    }

    setError(null);
    setStatus("正在使用 AI 处理音频");
    setImportProgress({ stage: "AI 正在增强音频", percent: 50 });
    try {
      // TODO: 调用后端 AI 音频处理接口
      // const result = await invoke("ai_process_audio", { inputPath, config: appConfig() });
      // await inspectCurrentAudio(inputPath);

      setImportProgress({ stage: "AI 处理完成", percent: 100 });
      setTimeout(() => setImportProgress(null), 800);
      setStatus("AI 处理完成");

      // 临时提示
      setError("AI 音频处理功能正在开发中");
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      setImportProgress(null);
      setStatus("AI 处理失败");
    }
  }

  async function scanLocalProxy() {
    setProxyScanning(true);
    setProxyResults([]);
    try {
      // TODO: 调用后端扫描本地代理
      // const results = await invoke<Array<{ url: string; available: boolean; name: string }>>("scan_local_proxy");
      // setProxyResults(results);

      // 临时模拟结果（实际需要后端实现）
      await new Promise((resolve) => setTimeout(resolve, 1500));
      const mockResults = [
        { url: "http://127.0.0.1:7890", available: true, name: "Clash" },
        { url: "socks5://127.0.0.1:10808", available: true, name: "V2Ray SOCKS5" },
        { url: "http://127.0.0.1:10809", available: false, name: "V2Ray HTTP" },
        { url: "socks5://127.0.0.1:1080", available: false, name: "Shadowsocks" },
      ];
      setProxyResults(mockResults);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(`代理扫描失败: ${message}`);
    } finally {
      setProxyScanning(false);
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

          <div className="processingToggles">
            {!aiEnabled && (
              <>
                <label className="toggleSetting">
                  <span>滤底噪</span>
                  <label className="toggleSwitch">
                    <input
                      type="checkbox"
                      checked={denoiseEnabled}
                      onChange={(event) => {
                        void changeDenoiseEnabled(event.target.checked);
                      }}
                      disabled={!inputPath}
                    />
                    <span className="toggleSlider"></span>
                  </label>
                </label>

                <label className="toggleSetting">
                  <span>放大</span>
                  <label className="toggleSwitch">
                    <input
                      type="checkbox"
                      checked={amplifyEnabled}
                      onChange={(event) => {
                        void changeAmplifyEnabled(event.target.checked);
                      }}
                      disabled={!inputPath}
                    />
                    <span className="toggleSlider"></span>
                  </label>
                </label>
              </>
            )}

            {aiEnabled && (
              <button
                className="primaryButton"
                onClick={() => void aiProcessAudio()}
                disabled={!inputPath}
                title="使用 AI 智能增强音频（替代滤噪+放大）"
              >
                <Sparkles size={18} />
                AI 处理
              </button>
            )}

            <label className="toggleSetting">
              <span>切片</span>
              <label className="toggleSwitch">
                <input
                  type="checkbox"
                  checked={sliceEnabled}
                  onChange={(event) => {
                    void changeSliceEnabled(event.target.checked);
                  }}
                  disabled={!inputPath}
                />
                <span className="toggleSlider"></span>
              </label>
            </label>
          </div>

          <label className="toggleSetting">
            <span>启用 AI 功能</span>
            <label className="toggleSwitch">
              <input
                type="checkbox"
                checked={aiEnabled}
                onChange={(event) => setAiEnabled(event.target.checked)}
              />
              <span className="toggleSlider"></span>
            </label>
          </label>

          <button
            className="ghostButton"
            onClick={() => void redetectEvents()}
            disabled={!inputPath}
            title={aiEnabled ? "使用 AI 识别噪音事件" : "使用传统算法检测事件"}
          >
            <ScanLine size={18} />
            检测事件
          </button>

          <button
            className="ghostButton"
            onClick={() => setSettingsOpen(true)}
            aria-label="设置"
          >
            <Settings2 size={18} />
            设置
          </button>
        </div>
      </section>

      {settingsOpen && (
        <div className="modalOverlay">
          <div className="modalContent">
            <div className="modalHeader">
              <h2>⚙️ 设置</h2>
              <button className="iconButton" onClick={() => setSettingsOpen(false)} aria-label="关闭">
                ×
              </button>
            </div>

            <div className="modalTabs">
              <button
                className={`modalTab ${settingsTab === "detect" ? "active" : ""}`}
                onClick={() => setSettingsTab("detect")}
              >
                参数配置
              </button>
              <button
                className={`modalTab ${settingsTab === "ai" ? "active" : ""}`}
                onClick={() => setSettingsTab("ai")}
              >
                AI 配置
              </button>
              <button
                className={`modalTab ${settingsTab === "export" ? "active" : ""}`}
                onClick={() => setSettingsTab("export")}
              >
                导出
              </button>
              <button
                className={`modalTab ${settingsTab === "about" ? "active" : ""}`}
                onClick={() => setSettingsTab("about")}
              >
                关于
              </button>
            </div>

            <div className="modalBody">
              {settingsTab === "detect" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
                  <section className="settingsGroup">
                    <h3>检测参数</h3>
                    <label>
                      <span>灵敏度 · {sensitivity === "high" ? "高" : sensitivity === "low" ? "低" : "中"}</span>
                      <select
                        value={sensitivity}
                        onChange={(event) => {
                          setSensitivity(event.target.value as Sensitivity);
                        }}
                      >
                        <option value="low">低</option>
                        <option value="medium">中</option>
                        <option value="high">高</option>
                      </select>
                    </label>
                    <label>
                      <span>最小响度 · {minPeakDbfs} dBFS</span>
                      <input
                        type="range"
                        min="-60"
                        max="-20"
                        step="1"
                        value={minPeakDbfs}
                        onChange={(event) => setMinPeakDbfs(Number(event.target.value))}
                      />
                    </label>
                  </section>

                  <section className="settingsGroup">
                    <h3>切片参数</h3>
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
                  </section>
                </div>
              )}

              {settingsTab === "ai" && (
                <section className="settingsGroup">
                  <h3>AI 配置</h3>
                  <p style={{ color: "var(--color-text-secondary)", fontSize: "14px", marginBottom: "16px" }}>
                    启用 AI 功能后：
                    <br />• AI 处理：智能增强音频（替代滤噪+放大）
                    <br />• 检测事件：使用 AI 识别噪音（替代传统算法）
                  </p>
                  <label className="toggleSetting">
                    <span>启用 AI 功能 · {aiEnabled ? "开" : "关"}</span>
                    <label className="toggleSwitch">
                      <input
                        type="checkbox"
                        checked={aiEnabled}
                        onChange={(event) => setAiEnabled(event.target.checked)}
                      />
                      <span className="toggleSlider"></span>
                    </label>
                  </label>
                  {aiEnabled && (
                    <>
                      <label>
                        <span>API 格式</span>
                        <select
                          value={aiFormat}
                          onChange={(event) => setAiFormat(event.target.value as "openai" | "anthropic" | "custom")}
                        >
                          <option value="openai">OpenAI 格式 (自动补全 /v1/responses)</option>
                          <option value="anthropic">Anthropic 格式 (自动补全 /v1/messages)</option>
                          <option value="custom">自定义格式 (完整 URL)</option>
                        </select>
                      </label>
                      <label>
                        <span>{aiFormat === "custom" ? "完整端点 URL" : "Base URL"}</span>
                        <input
                          type="text"
                          value={aiFormat === "custom" ? aiEndpoint : aiBaseUrl}
                          onChange={(event) => {
                            if (aiFormat === "custom") {
                              setAiEndpoint(event.target.value);
                            } else {
                              setAiBaseUrl(event.target.value);
                            }
                          }}
                          placeholder={
                            aiFormat === "openai"
                              ? "https://api.openai.com"
                              : aiFormat === "anthropic"
                                ? "https://api.anthropic.com"
                                : "https://your-api.com/v1/chat/completions"
                          }
                        />
                      </label>
                      {aiFormat !== "custom" && (
                        <div style={{ fontSize: "13px", color: "var(--color-text-muted)", marginTop: "-8px" }}>
                          完整端点：{aiEndpoint}
                        </div>
                      )}
                      <label>
                        <span>API Key</span>
                        <input
                          type="password"
                          value={aiKey}
                          onChange={(event) => setAiKey(event.target.value)}
                          placeholder="sk-..."
                        />
                      </label>
                      <label>
                        <span>模型</span>
                        <input
                          type="text"
                          value={aiModel}
                          onChange={(event) => setAiModel(event.target.value)}
                          placeholder="gpt-4o-mini"
                        />
                      </label>

                      <div style={{ marginTop: "var(--space-md)", paddingTop: "var(--space-md)", borderTop: "1px solid var(--color-border)" }}>
                        <label className="toggleSetting">
                          <span>启用代理 · {proxyEnabled ? "开" : "关"}</span>
                          <label className="toggleSwitch">
                            <input
                              type="checkbox"
                              checked={proxyEnabled}
                              onChange={(event) => setProxyEnabled(event.target.checked)}
                            />
                            <span className="toggleSlider"></span>
                          </label>
                        </label>
                        {proxyEnabled && (
                          <>
                            <label style={{ marginTop: "var(--space-md)" }}>
                              <span>代理地址</span>
                              <div style={{ display: "flex", gap: "8px" }}>
                                <input
                                  type="text"
                                  value={proxyUrl}
                                  onChange={(event) => setProxyUrl(event.target.value)}
                                  placeholder="http://127.0.0.1:7890 或 socks5://127.0.0.1:1080"
                                  style={{ flex: 1 }}
                                />
                                <button
                                  type="button"
                                  className="ghostButton"
                                  onClick={() => void scanLocalProxy()}
                                  disabled={proxyScanning}
                                  style={{ whiteSpace: "nowrap" }}
                                >
                                  {proxyScanning ? "扫描中..." : "扫描"}
                                </button>
                              </div>
                              <div style={{ fontSize: "13px", color: "var(--color-text-muted)", marginTop: "4px" }}>
                                支持 HTTP/HTTPS 和 SOCKS5 代理
                              </div>
                            </label>

                            {proxyResults.length > 0 && (
                              <div style={{ marginTop: "var(--space-md)" }}>
                                <div style={{ fontSize: "13px", fontWeight: 500, color: "var(--color-text-secondary)", marginBottom: "8px" }}>
                                  扫描结果：
                                </div>
                                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                                  {proxyResults.map((result, index) => (
                                    <button
                                      key={index}
                                      type="button"
                                      onClick={() => {
                                        if (result.available) {
                                          setProxyUrl(result.url);
                                        }
                                      }}
                                      disabled={!result.available}
                                      style={{
                                        display: "flex",
                                        alignItems: "center",
                                        gap: "8px",
                                        padding: "8px 12px",
                                        border: "1px solid var(--color-border)",
                                        borderRadius: "6px",
                                        background: result.available ? "white" : "var(--color-surface)",
                                        cursor: result.available ? "pointer" : "not-allowed",
                                        textAlign: "left",
                                        fontSize: "13px",
                                        opacity: result.available ? 1 : 0.5,
                                      }}
                                    >
                                      <span style={{ color: result.available ? "#10b981" : "#ef4444" }}>
                                        {result.available ? "✓" : "×"}
                                      </span>
                                      <span style={{ flex: 1, fontFamily: "monospace", color: "var(--color-text)" }}>
                                        {result.url}
                                      </span>
                                      <span style={{ fontSize: "12px", color: "var(--color-text-muted)" }}>
                                        {result.name}
                                      </span>
                                    </button>
                                  ))}
                                </div>
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    </>
                  )}
                </section>
              )}

              {settingsTab === "export" && (
                <section className="settingsGroup">
                  <h3>导出设置</h3>
                  <p style={{ color: "#8b8374", fontSize: "14px" }}>导出相关配置将在后续版本中添加</p>
                </section>
              )}

              {settingsTab === "about" && (
                <section className="settingsGroup">
                  <h3>关于寻音殿</h3>
                  <dl style={{ fontSize: "14px", lineHeight: "1.8" }}>
                    <div>
                      <dt style={{ fontWeight: "600", color: "#4a463d" }}>版本</dt>
                      <dd style={{ color: "#6b7077", marginLeft: "0" }}>{version}</dd>
                    </div>
                    <div style={{ marginTop: "12px" }}>
                      <dt style={{ fontWeight: "600", color: "#4a463d" }}>描述</dt>
                      <dd style={{ color: "#6b7077", marginLeft: "0" }}>智能噪音检测与分类工具</dd>
                    </div>
                  </dl>
                </section>
              )}
            </div>

            <div className="modalFooter">
              <button className="primaryButton" onClick={() => setSettingsOpen(false)}>
                完成
              </button>
            </div>
          </div>
        </div>
      )}

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
        <aside className={`flowRail ${leftCollapsed ? "collapsed" : ""}`} aria-label="流程">
          <button className="collapseToggle" onClick={() => setLeftCollapsed(!leftCollapsed)} aria-label="折叠面板">
            {leftCollapsed ? "›" : "‹"}
          </button>
          {!leftCollapsed && (
            <>
              <Step active={hasInput} icon={<FileAudio size={18} />} label="导入" value={hasInput ? "已加载" : "待导入"} />
              <Step active={hasInput} icon={<Settings2 size={18} />} label="预处理" value={hasInput ? (denoiseEnabled ? "滤底噪" : "原始") : "待处理"} />
              <Step active={events.length > 0} icon={<ScanLine size={18} />} label="检测" value={hasInput ? `${events.length} 段` : "待检测"} />
              <Step active={kept.length > 0} icon={<ListChecks size={18} />} label="复核" value={`${kept.length} 保留`} />
              <Step icon={<Download size={18} />} label="导出" value="待确认" />
            </>
          )}
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
            {importProgress && (
              <div className="progressBanner">
                <div className="progressContent">
                  <span className="progressIcon">⚙️</span>
                  <span className="progressLabel">{importProgress.stage}</span>
                  <span className="progressPercent">{importProgress.percent}%</span>
                </div>
                <div className="progressTrack">
                  <div className="progressFill" style={{ width: `${importProgress.percent}%` }} />
                </div>
              </div>
            )}
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
                onClick={() => selectAndPlayEvent(event.id)}
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
                onClick={() => selectAndPlayEvent(event.id)}
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

        <aside className={`sidePanel ${rightCollapsed ? "collapsed" : ""}`} aria-label="参数与事件">
          <button className="collapseToggle" onClick={() => setRightCollapsed(!rightCollapsed)} aria-label="折叠面板">
            {rightCollapsed ? "‹" : "›"}
          </button>
          {!rightCollapsed && (
            <>
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
            </>
          )}
        </aside>
      </section>

      <section className="exportBar" aria-label="导出摘要">
        <div>
          <strong>{kept.length} 段保留</strong>
          <span>{exportSummary}</span>
        </div>
        <div className="exportDropdown">
          <button
            className="primaryButton"
            onClick={(e) => {
              e.stopPropagation();
              setExportMenuOpen(!exportMenuOpen);
            }}
            disabled={!hasInput || (sliceEnabled && events.length === 0)}
          >
            <Download size={18} />
            导出
          </button>
          {exportMenuOpen && (
            <div className="dropdownMenu" onClick={(e) => e.stopPropagation()}>
              <button
                onClick={() => {
                  setExportMenuOpen(false);
                  void exportEvidence("audio");
                }}
              >
                仅导出音频
              </button>
              {sliceEnabled && (
                <button
                  onClick={() => {
                    setExportMenuOpen(false);
                    void exportEvidence("csv");
                  }}
                >
                  仅导出 CSV
                </button>
              )}
              <button
                onClick={() => {
                  setExportMenuOpen(false);
                  void exportEvidence("both");
                }}
              >
                {sliceEnabled ? "导出音频 + CSV" : "导出音频"}
              </button>
            </div>
          )}
        </div>
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
