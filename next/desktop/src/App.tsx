import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import { useEffect, useState, type ReactNode } from "react";
import {
  Download,
  FileAudio,
  Info,
  ListChecks,
  Play,
  ScanLine,
  Scissors,
  Settings2,
  Trash2,
  Volume2,
} from "lucide-react";

type EventKind = "rumble" | "thud" | "drag" | "transient" | "other";
type Sensitivity = "low" | "medium" | "high";

type CoreNoiseEvent = {
  start: number;
  end: number;
  kind: EventKind;
  peak_dbfs: number;
  keep: boolean;
  manual: boolean;
};

type AnalyzeResult = {
  samplerate: number;
  duration_seconds: number;
  events: CoreNoiseEvent[];
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

type NoiseEvent = {
  id: number;
  start: number;
  end: number;
  kind: EventKind;
  peakDbfs: number;
  keep: boolean;
  manual: boolean;
};

const fallbackEvents: NoiseEvent[] = [
  { id: 1, start: 12.4, end: 13.8, kind: "rumble", peakDbfs: -8.4, keep: true, manual: false },
  { id: 2, start: 25.1, end: 26.0, kind: "thud", peakDbfs: -5.8, keep: true, manual: false },
  { id: 3, start: 38.6, end: 40.2, kind: "drag", peakDbfs: -12.1, keep: true, manual: true },
  { id: 4, start: 55.3, end: 55.9, kind: "transient", peakDbfs: -3.2, keep: false, manual: false },
];

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

function App() {
  const [version, setVersion] = useState("0.1.0");
  const [analysis, setAnalysis] = useState<AnalyzeResult | null>(null);
  const [fileLabel, setFileLabel] = useState("20260603_233810.m4a");
  const [inputPath, setInputPath] = useState<string | null>(null);
  const [status, setStatus] = useState("加载 Rust 合成样例");
  const [error, setError] = useState<string | null>(null);
  const [sensitivity, setSensitivity] = useState<Sensitivity>("medium");
  const [mergeGap, setMergeGap] = useState(0.8);
  const [padSeconds, setPadSeconds] = useState(0.6);
  const [minPeakDbfs, setMinPeakDbfs] = useState(-45);

  useEffect(() => {
    void invoke<string>("app_version")
      .then(setVersion)
      .catch(() => undefined);
    void invoke<AnalyzeResult>("analyze_synthetic")
      .then((result) => {
        setAnalysis(result);
        setFileLabel("Rust synthetic");
        setStatus("样例分析已完成");
      })
      .catch(() => {
        setStatus("使用前端预览数据");
      });
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

  async function analyzeCurrentWav(path: string) {
    setError(null);
    setStatus("正在分析 WAV");
    try {
      const result = await invoke<AnalyzeResult>("analyze_wav", {
        inputPath: path,
        detect: detectConfig(),
      });
      setAnalysis(result);
      setFileLabel(path.split(/[\\/]/).pop() ?? path);
      setInputPath(path);
      setStatus(`WAV 分析完成 · ${result.events.length} 段`);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      setStatus("WAV 分析失败");
    }
  }

  async function importWav() {
    setError(null);
    const selected = await open({
      multiple: false,
      directory: false,
      title: "选择 WAV 录音",
      filters: [{ name: "WAV 音频", extensions: ["wav"] }],
    });
    if (typeof selected !== "string") {
      return;
    }

    await analyzeCurrentWav(selected);
  }

  const events = analysis
    ? analysis.events.map((event, index) => ({
        id: index + 1,
        start: event.start,
        end: event.end,
        kind: event.kind,
        peakDbfs: event.peak_dbfs,
        keep: event.keep,
        manual: event.manual,
      }))
    : fallbackEvents;
  const selected = events[0] ?? fallbackEvents[0];
  const kept = events.filter((event) => event.keep);
  const keptSeconds = kept.reduce((sum, event) => sum + event.end - event.start, 0);
  const durationSeconds = Math.max(analysis?.duration_seconds ?? 70, 1);

  return (
    <main className="appShell">
      <section className="topBar" aria-label="全局操作">
        <div className="brandBlock">
          <div className="appMark">
            <Volume2 size={22} />
          </div>
          <div>
            <h1>楼上噪音取证助手</h1>
            <p>Next workspace · v{version}</p>
          </div>
        </div>

        <div className="modeGroup" aria-label="处理模式">
          <button className="modeButton">整段降噪</button>
          <button className="modeButton">整段放大</button>
          <button className="modeButton active">智能切片</button>
        </div>

        <div className="topActions">
          <button className="primaryButton" onClick={importWav}>
            <FileAudio size={18} />
            导入录音
          </button>
          <button className="ghostButton">
            <Download size={18} />
            导出
          </button>
        </div>
      </section>

      <section className="workspace">
        <aside className="flowRail" aria-label="流程">
          <Step active icon={<FileAudio size={18} />} label="导入" value="已加载" />
          <Step active icon={<Settings2 size={18} />} label="预处理" value="已完成" />
          <Step active icon={<ScanLine size={18} />} label="检测" value={`${events.length} 段`} />
          <Step icon={<ListChecks size={18} />} label="复核" value={`${kept.length} 保留`} />
          <Step icon={<Download size={18} />} label="导出" value="待确认" />
        </aside>

        <section className="mainPanel">
          <div className="toolbar">
            <div className="fileMeta">
              <strong>{fileLabel}</strong>
              <span>
                {status} · {durationSeconds.toFixed(1)}s
              </span>
            </div>
            <div className="toolButtons">
              <button>
                <Play size={17} />
                播放
              </button>
              <button
                onClick={() => {
                  if (inputPath) {
                    void analyzeCurrentWav(inputPath);
                  }
                }}
                disabled={!inputPath}
              >
                <ScanLine size={17} />
                检测事件
              </button>
              <button>
                <Scissors size={17} />
                框选新增
              </button>
            </div>
          </div>

          {error ? <div className="errorBanner">{error}</div> : null}

          <div className="waveform" aria-label="波形时间轴">
            <div className="waveGrid" />
            {events.map((event) => (
              <div
                key={event.id}
                className={`eventBlock ${event.keep ? "" : "muted"}`}
                style={{
                  left: `${(event.start / durationSeconds) * 100}%`,
                  width: `${((event.end - event.start) / durationSeconds) * 100}%`,
                  backgroundColor: kindTone[event.kind],
                }}
              />
            ))}
            <div className="playhead" style={{ left: "18%" }} />
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
              <div className="tableRow" role="row" key={event.id}>
                <span className={event.keep ? "pill keep" : "pill off"}>{event.keep ? "是" : "否"}</span>
                <span>{formatTime(event.start)}</span>
                <span>{(event.end - event.start).toFixed(2)}s</span>
                <span>{event.manual ? "手动" : "自动"}</span>
                <span className="kind" style={{ color: kindTone[event.kind] }}>
                  {kindLabel[event.kind]}
                </span>
                <span>{event.peakDbfs.toFixed(1)} dB</span>
                <button className="iconButton" aria-label="删除事件">
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>
        </section>

        <aside className="sidePanel" aria-label="当前事件">
          <div className="sideHeader">
            <h2>事件 #{selected.id}</h2>
            <button className="iconButton" aria-label="事件说明">
              <Info size={16} />
            </button>
          </div>
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
              <dd>{selected.peakDbfs.toFixed(1)} dBFS</dd>
            </div>
          </dl>
          <div className="settingsBox">
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
        </aside>
      </section>

      <section className="exportBar" aria-label="导出摘要">
        <div>
          <strong>{kept.length} 段保留</strong>
          <span>合集约 {keptSeconds.toFixed(1)} 秒 · WAV + CSV</span>
        </div>
        <button className="primaryButton">
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

function formatTime(value: number) {
  const minutes = Math.floor(value / 60);
  const seconds = value - minutes * 60;
  return `${minutes.toString().padStart(2, "0")}:${seconds.toFixed(2).padStart(5, "0")}`;
}

export default App;
