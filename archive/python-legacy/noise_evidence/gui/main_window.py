"""主窗口：把导入、预处理、手动检测、人工编辑与导出串成完整工作流。"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..audio_io import save_wav
from ..config import AppConfig, ProcessMode
from ..detect import TYPE_LABELS, NoiseEvent, make_manual_event
from ..export import export_full_wav, export_highlight_wav, export_report_csv, summarize
from ..gain import amplify_events_inplace
from ..resources import icon_path
from .style import build_style_sheet
from .waveform import KIND_COLORS, WaveformView
from .worker import DetectWorker, PreprocessWorker


def _fmt_time(sec: float) -> str:
    m, s = divmod(sec, 60)
    return f"{int(m):02d}:{s:05.2f}"


def _fmt_duration(sec: float) -> str:
    if sec <= 0:
        return "0.0s"
    m, s = divmod(sec, 60)
    if m >= 1:
        return f"{int(m)}m {s:.1f}s"
    return f"{s:.1f}s"


class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("楼上噪音取证助手")
        self.setWindowIcon(QIcon(icon_path()))
        self.resize(1220, 820)
        self.cfg = AppConfig()

        self._path: Path | None = None
        self._sr = 0
        self._processed = np.zeros(0, dtype=np.float32)
        self._events: list[NoiseEvent] = []
        self._busy = False
        self._preprocess_worker: PreprocessWorker | None = None
        self._detect_worker: DetectWorker | None = None

        self._tmp_wav = Path(tempfile.gettempdir()) / "noise_evidence_play.wav"
        self._player = QMediaPlayer(self)
        self._audio_out = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_out)
        self._player.positionChanged.connect(self._on_position)
        self._seg_stop_ms = -1

        self._build_ui()
        self.setStyleSheet(build_style_sheet())
        self._update_mode_controls()

    # ---------- UI ----------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        top_card, top = self._card("录音")
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(self._label("处理模式"))
        row.addWidget(self._help(
            "决定导出结果：整段模式只生成完整 WAV；智能切片模式需要检测事件后导出合集和 CSV。"
        ))
        self.cmb_mode = QComboBox()
        self.cmb_mode.setObjectName("mode")
        self.cmb_mode.addItem("整段·只滤底噪", ProcessMode.FULL_DENOISE.value)
        self.cmb_mode.addItem("整段·滤底噪+放大", ProcessMode.FULL_AMPLIFY.value)
        self.cmb_mode.addItem("智能切片合集", ProcessMode.HIGHLIGHT.value)
        self.cmb_mode.setCurrentIndex(2)
        self.cmb_mode.currentIndexChanged.connect(self._on_mode_changed)
        row.addWidget(self.cmb_mode)

        self.btn_open = QPushButton("导入录音")
        self.btn_open.setObjectName("primary")
        self.btn_open.clicked.connect(self._on_open)
        row.addWidget(self.btn_open)

        self.lbl_file = QLabel("尚未导入文件")
        self.lbl_file.setObjectName("hint")
        row.addWidget(self.lbl_file, 1)
        top.addLayout(row)
        root.addWidget(top_card)

        settings_card, settings = self._card("处理设置")
        prep = QHBoxLayout()
        prep.setSpacing(8)
        self.chk_denoise = QCheckBox("滤除底噪")
        self.chk_denoise.setChecked(True)
        prep.addWidget(self.chk_denoise)
        prep.addWidget(self._help(
            "导入后先降低持续环境底噪；整段模式固定启用，智能切片模式可自行关闭。"
        ))
        prep.addWidget(self._vline())
        self.btn_detect = QPushButton("检测事件")
        self.btn_detect.setObjectName("primary")
        self.btn_detect.clicked.connect(self._run_detection)
        prep.addWidget(self.btn_detect)
        prep.addWidget(self._help(
            "只在点击后检测噪音事件；调整灵敏度、合并间隔或缓冲后可重新点击。"
        ))
        self.btn_manual = QPushButton("框选新增")
        self.btn_manual.setObjectName("toggle")
        self.btn_manual.setCheckable(True)
        self.btn_manual.toggled.connect(self._on_manual_toggle)
        prep.addWidget(self.btn_manual)
        prep.addWidget(self._help("开启后在波形上拖拽，即可把选中的时间段加入事件列表。"))
        prep.addStretch(1)
        settings.addLayout(prep)

        params = QHBoxLayout()
        params.setSpacing(8)
        self.cmb_sens = QComboBox()
        self.cmb_sens.addItems(["宽松(少误报)", "适中", "灵敏(多框选)"])
        self.cmb_sens.setCurrentIndex(1)
        self.cmb_sens.setFixedWidth(170)
        self._add_inline_field(
            params, "检测灵敏度", self.cmb_sens,
            "控制事件阈值：宽松会减少误报，灵敏会框出更多可疑声音。",
        )

        self.spn_gate = QDoubleSpinBox()
        self.spn_gate.setRange(-90.0, -10.0)
        self.spn_gate.setSingleStep(1.0)
        self.spn_gate.setValue(self.cfg.detect.min_peak_dbfs)
        self.spn_gate.setSuffix(" dBFS")
        self.spn_gate.setFixedWidth(150)
        self._add_inline_field(
            params, "最小响度", self.spn_gate,
            "峰值低于该值的候选片段会被丢弃；越接近 0 越严格。",
        )

        self.spn_merge = QDoubleSpinBox()
        self.spn_merge.setRange(0.0, 5.0)
        self.spn_merge.setSingleStep(0.1)
        self.spn_merge.setValue(self.cfg.detect.merge_gap_seconds)
        self.spn_merge.setSuffix(" 秒")
        self.spn_merge.setFixedWidth(130)
        self._add_inline_field(
            params, "合并间隔", self.spn_merge,
            "相邻峰值间隔小于该值时合并为一次持续噪音事件。",
        )

        self.spn_pad = QDoubleSpinBox()
        self.spn_pad.setRange(0.0, 3.0)
        self.spn_pad.setSingleStep(0.1)
        self.spn_pad.setValue(self.cfg.detect.pad_seconds)
        self.spn_pad.setSuffix(" 秒")
        self.spn_pad.setFixedWidth(130)
        self._add_inline_field(
            params, "起止缓冲", self.spn_pad,
            "每个事件前后额外保留的声音，用于听清噪音起落。",
        )
        params.addStretch(1)
        settings.addLayout(params)
        root.addWidget(settings_card)

        self.wave = WaveformView()
        self.wave.seeked.connect(self._seek_seconds)
        self.wave.span_selected.connect(self._on_span_selected)
        root.addWidget(self.wave)

        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        mid = QHBoxLayout()
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["保留", "开始", "时长", "来源", "类型", "峰值dB", "复核", "操作"]
        )
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Stretch)
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.cellClicked.connect(self._on_row_clicked)
        self.table.cellDoubleClicked.connect(self._on_row_double)
        mid.addWidget(self.table, 3)

        self.lbl_stats = QLabel("导入录音后显示统计")
        self.lbl_stats.setObjectName("stats")
        self.lbl_stats.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.lbl_stats.setWordWrap(True)
        self.lbl_stats.setMinimumWidth(300)
        mid.addWidget(self.lbl_stats, 1)
        root.addLayout(mid, 1)

        play = QHBoxLayout()
        self.btn_play = QPushButton("播放/暂停")
        self.btn_play.clicked.connect(self._toggle_play)
        play.addWidget(self.btn_play)
        self.lbl_pos = QLabel("00:00.00")
        play.addWidget(self.lbl_pos)
        play.addStretch(1)
        self.btn_all = QPushButton("全选保留")
        self.btn_all.clicked.connect(lambda: self._set_all_keep(True))
        self.btn_none = QPushButton("全不选")
        self.btn_none.clicked.connect(lambda: self._set_all_keep(False))
        self.btn_delete = QPushButton("删除选中")
        self.btn_delete.setObjectName("danger")
        self.btn_delete.clicked.connect(self._delete_selected)
        play.addWidget(self.btn_all)
        play.addWidget(self.btn_none)
        play.addWidget(self.btn_delete)
        root.addLayout(play)

        export_card, export = self._card("导出")
        exp = QHBoxLayout()
        exp.setSpacing(8)
        self.chk_gain = QCheckBox("不失真放大")
        self.chk_gain.setChecked(True)
        self.chk_gain.stateChanged.connect(self._on_gain_toggle)
        exp.addWidget(self.chk_gain)
        exp.addWidget(self._help(
            "纯线性音量放大，保留波形形状；整段放大模式固定启用。"
        ))
        exp.addWidget(self._label("放大模式"))
        self.cmb_gain = QComboBox()
        self.cmb_gain.addItems(["逐段(各段一样响)", "全局(保留相对强弱)"])
        self.cmb_gain.setCurrentIndex(0)
        self.cmb_gain.currentIndexChanged.connect(self._on_gain_mode_changed)
        exp.addWidget(self.cmb_gain)
        exp.addWidget(self._help(
            "逐段适合让弱噪音也清楚；全局会保留各事件之间的强弱差异。"
        ))
        exp.addWidget(self._vline())
        self.chk_beep = QCheckBox("段间提示音")
        self.chk_beep.setChecked(True)
        exp.addWidget(self.chk_beep)
        exp.addWidget(self._help("智能切片合集里插入短提示音，标明这是剪辑合集。"))
        exp.addWidget(self._label("段间隔"))
        self.spn_gap = QDoubleSpinBox()
        self.spn_gap.setRange(0.0, 5.0)
        self.spn_gap.setSingleStep(0.25)
        self.spn_gap.setValue(self.cfg.export.gap_seconds)
        self.spn_gap.setSuffix(" 秒")
        exp.addWidget(self.spn_gap)
        exp.addWidget(self._help("智能切片合集中相邻事件之间保留的静音间隔。"))
        exp.addStretch(1)
        self.btn_export = QPushButton("导出噪音合集 + CSV")
        self.btn_export.setObjectName("primary")
        self.btn_export.clicked.connect(self._on_export)
        exp.addWidget(self.btn_export)
        export.addLayout(exp)
        root.addWidget(export_card)

        self._detect_controls = [
            self.cmb_sens, self.spn_gate, self.spn_merge, self.spn_pad,
            self.btn_detect, self.btn_manual,
        ]
        self._highlight_export_controls = [self.chk_beep, self.spn_gap]

    def _card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)
        label = QLabel(title)
        label.setObjectName("cardTitle")
        layout.addWidget(label)
        return frame, layout

    def _help(self, tip: str) -> QPushButton:
        btn = QPushButton("!")
        btn.setObjectName("help")
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setToolTip(tip)
        return btn

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def _add_inline_field(
        self, layout: QHBoxLayout, label: str, widget: QWidget, tip: str
    ) -> None:
        layout.addWidget(self._label(label))
        layout.addWidget(self._help(tip))
        layout.addWidget(widget)

    def _vline(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setObjectName("sep")
        return line

    # ---------- 模式与配置 ----------
    def _current_mode(self) -> ProcessMode:
        return ProcessMode(self.cmb_mode.currentData())

    def _on_mode_changed(self, _index: int) -> None:
        self.cfg.mode = self._current_mode()
        if self.cfg.mode.is_full:
            self._clear_events()
            self.wave.set_select_mode(False)
            self.btn_manual.setChecked(False)
        if self.cfg.mode == ProcessMode.FULL_DENOISE:
            self.chk_denoise.setChecked(True)
            self.chk_gain.setChecked(False)
        elif self.cfg.mode == ProcessMode.FULL_AMPLIFY:
            self.chk_denoise.setChecked(True)
            self.chk_gain.setChecked(True)
        self._sync_gain_cfg()
        if self._processed.size:
            self._rebuild_playback()
        self._refresh_stats()
        self._update_mode_controls()

    def _sync_preprocess_cfg(self) -> None:
        self.cfg.mode = self._current_mode()
        self.cfg.denoise.enabled = True if self.cfg.mode.is_full else self.chk_denoise.isChecked()

    def _sync_detect_cfg(self) -> None:
        self.cfg.detect.sensitivity = ["low", "medium", "high"][self.cmb_sens.currentIndex()]
        self.cfg.detect.min_peak_dbfs = self.spn_gate.value()
        self.cfg.detect.merge_gap_seconds = self.spn_merge.value()
        self.cfg.detect.pad_seconds = self.spn_pad.value()

    def _sync_gain_cfg(self) -> None:
        if self.cfg.mode == ProcessMode.FULL_DENOISE:
            self.cfg.gain.enabled = False
            self.cfg.gain.mode = "off"
        elif self.cfg.mode == ProcessMode.FULL_AMPLIFY:
            self.cfg.gain.enabled = True
            self.cfg.gain.mode = "global"
        else:
            self.cfg.gain.enabled = self.chk_gain.isChecked()
            self.cfg.gain.mode = "per_event" if self.cmb_gain.currentIndex() == 0 else "global"

    def _sync_export_cfg(self) -> None:
        self.cfg.export.insert_beep = self.chk_beep.isChecked()
        self.cfg.export.gap_seconds = self.spn_gap.value()

    def _update_mode_controls(self) -> None:
        mode = self.cfg.mode
        has_audio = self._processed.size > 0
        has_events = bool(self._events)
        can_edit_events = (not self._busy) and has_audio and not mode.is_full

        self.cmb_mode.setEnabled(not self._busy)
        self.btn_open.setEnabled(not self._busy)
        self.chk_denoise.setEnabled(not self._busy and not mode.is_full)
        for widget in self._detect_controls:
            widget.setEnabled(can_edit_events)
        self.btn_detect.setEnabled(can_edit_events)
        self.btn_manual.setEnabled(can_edit_events)
        if not can_edit_events and self.btn_manual.isChecked():
            self.btn_manual.setChecked(False)
            self.wave.set_select_mode(False)

        self.table.setEnabled(can_edit_events)
        self.btn_all.setEnabled(can_edit_events and has_events)
        self.btn_none.setEnabled(can_edit_events and has_events)
        self.btn_delete.setEnabled(can_edit_events and has_events)

        highlight_mode = mode == ProcessMode.HIGHLIGHT
        self.chk_gain.setEnabled(not self._busy and highlight_mode)
        self.cmb_gain.setEnabled(not self._busy and highlight_mode and self.chk_gain.isChecked())
        for widget in self._highlight_export_controls:
            widget.setEnabled(not self._busy and highlight_mode)

        self.btn_play.setEnabled(not self._busy and has_audio)
        self.btn_export.setText("导出整段 WAV" if mode.is_full else "导出噪音合集 + CSV")
        self.btn_export.setEnabled(not self._busy and self._can_export())

    def _can_export(self) -> bool:
        if self._processed.size == 0:
            return False
        if self.cfg.mode.is_full:
            return True
        return any(ev.keep for ev in self._events)

    # ---------- 导入、预处理、检测 ----------
    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择录音文件", "",
            "音频文件 (*.m4a *.mp3 *.wav *.flac *.aac *.mp4 *.ogg);;所有文件 (*.*)",
        )
        if not path:
            return
        self._path = Path(path)
        self.lbl_file.setText(self._path.name)
        self._run_preprocess()

    def _run_preprocess(self) -> None:
        if not self._path:
            return
        self._sync_preprocess_cfg()
        self._player.stop()
        self._processed = np.zeros(0, dtype=np.float32)
        self._sr = 0
        self._clear_events()
        self.wave.set_audio(self._processed, 0)
        self._set_busy(True)
        self._preprocess_worker = PreprocessWorker(self._path, self.cfg)
        self._preprocess_worker.progress.connect(self._on_progress)
        self._preprocess_worker.finished_ok.connect(self._on_preprocessed)
        self._preprocess_worker.failed.connect(self._on_failed)
        self._preprocess_worker.start()

    def _run_detection(self) -> None:
        if self._processed.size == 0 or self.cfg.mode.is_full:
            return
        self._sync_detect_cfg()
        self._player.pause()
        self._clear_events()
        self._set_busy(True)
        self._detect_worker = DetectWorker(self._processed, self._sr, self.cfg)
        self._detect_worker.progress.connect(self._on_progress)
        self._detect_worker.finished_ok.connect(self._on_detected)
        self._detect_worker.failed.connect(self._on_failed)
        self._detect_worker.start()

    def _on_progress(self, pct: int, msg: str) -> None:
        self.progress.setValue(pct)
        self.progress.setFormat(f"{msg}  {pct}%")

    def _on_preprocessed(self, data: np.ndarray, sr: int) -> None:
        self._processed = data
        self._sr = sr
        self.wave.set_audio(data, sr)
        self.wave.set_events([])
        self._rebuild_playback()
        self._set_busy(False)
        self._refresh_stats()

    def _on_detected(self, events: list[NoiseEvent]) -> None:
        self._events = sorted(events, key=lambda ev: (ev.start, ev.end))
        self.wave.set_events(self._events)
        self._fill_table()
        self._rebuild_playback()
        self._set_busy(False)
        self._refresh_stats()

    def _on_failed(self, msg: str) -> None:
        self._set_busy(False)
        QMessageBox.critical(self, "处理失败", msg)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.progress.setVisible(busy)
        if busy:
            self.progress.setValue(0)
        self._update_mode_controls()

    # ---------- 事件表与人工编辑 ----------
    def _clear_events(self) -> None:
        self._events = []
        if hasattr(self, "table"):
            self.table.setRowCount(0)
        if hasattr(self, "wave"):
            self.wave.set_events([])
            self.wave.set_selected(-1)

    def _fill_table(self) -> None:
        self.table.setRowCount(0)
        for ev in self._events:
            r = self.table.rowCount()
            self.table.insertRow(r)

            chk = QCheckBox()
            chk.setChecked(ev.keep)
            chk.stateChanged.connect(lambda state, e=ev: self._on_keep_changed(e, state))
            wrap = QWidget()
            lay = QHBoxLayout(wrap)
            lay.setAlignment(Qt.AlignCenter)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(chk)
            self.table.setCellWidget(r, 0, wrap)

            self.table.setItem(r, 1, self._cell(_fmt_time(ev.start)))
            self.table.setItem(r, 2, self._cell(f"{ev.duration:.2f}s"))
            self.table.setItem(r, 3, self._cell("手动" if ev.manual else "自动"))

            kind_item = self._cell(ev.label)
            kind_item.setForeground(KIND_COLORS.get(ev.kind, KIND_COLORS["other"]))
            self.table.setItem(r, 4, kind_item)
            self.table.setItem(r, 5, self._cell(f"{ev.peak_dbfs:.1f}"))
            self.table.setItem(r, 6, self._cell("疑似混入" if ev.suspect_self else ""))

            btn = QPushButton("删除")
            btn.setObjectName("smallDanger")
            btn.setToolTip("从事件列表中删除这一段。")
            btn.clicked.connect(lambda _checked=False, e=ev: self._delete_event(e))
            self.table.setCellWidget(r, 7, btn)
        self._update_mode_controls()

    def _cell(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    def _on_keep_changed(self, ev: NoiseEvent, state: int) -> None:
        ev.keep = state == Qt.Checked.value
        self.wave.set_events(self._events)
        self._rebuild_playback()
        self._refresh_stats()
        self._update_mode_controls()

    def _on_row_clicked(self, row: int, _col: int) -> None:
        self.wave.set_selected(row)

    def _on_row_double(self, row: int, _col: int) -> None:
        if 0 <= row < len(self._events):
            ev = self._events[row]
            self._play_segment(ev.start, ev.end)

    def _set_all_keep(self, keep: bool) -> None:
        for ev in self._events:
            ev.keep = keep
        self._fill_table()
        self.wave.set_events(self._events)
        self._rebuild_playback()
        self._refresh_stats()

    def _delete_selected(self) -> None:
        self._delete_row(self.table.currentRow())

    def _delete_event(self, event: NoiseEvent) -> None:
        if event in self._events:
            self._events.remove(event)
            self._after_event_delete()

    def _delete_row(self, row: int) -> None:
        if 0 <= row < len(self._events):
            del self._events[row]
            self._after_event_delete()

    def _after_event_delete(self) -> None:
        self._fill_table()
        self.wave.set_events(self._events)
        self.wave.set_selected(-1)
        self._rebuild_playback()
        self._refresh_stats()

    def _on_manual_toggle(self, checked: bool) -> None:
        if checked and (self._processed.size == 0 or self.cfg.mode.is_full):
            self.btn_manual.setChecked(False)
            return
        self.wave.set_select_mode(checked)

    def _on_span_selected(self, start: float, end: float) -> None:
        if self._processed.size == 0 or self.cfg.mode.is_full:
            return
        event = make_manual_event(self._processed, self._sr, start, end, self.cfg.classify)
        if event is None:
            return
        self._events.append(event)
        self._events.sort(key=lambda ev: (ev.start, ev.end))
        index = self._events.index(event)
        self._fill_table()
        self.table.selectRow(index)
        self.wave.set_events(self._events)
        self.wave.set_selected(index)
        self._rebuild_playback()
        self._refresh_stats()

    # ---------- 播放 ----------
    def _rebuild_playback(self) -> None:
        if self._processed.size == 0 or self._sr <= 0:
            return
        self._sync_gain_cfg()
        preview = amplify_events_inplace(self._processed, self._sr, self._events, self.cfg.gain)
        save_wav(self._tmp_wav, preview, self._sr)
        self._player.setSource(QUrl.fromLocalFile(str(self._tmp_wav)))

    def _on_gain_toggle(self, _state: int) -> None:
        self._sync_gain_cfg()
        self._update_mode_controls()
        self._rebuild_playback()

    def _on_gain_mode_changed(self, _index: int) -> None:
        self._sync_gain_cfg()
        self._rebuild_playback()

    def _seek_seconds(self, sec: float) -> None:
        self._seg_stop_ms = -1
        self._player.setPosition(int(sec * 1000))

    def _play_segment(self, start: float, end: float) -> None:
        self._player.setPosition(int(start * 1000))
        self._seg_stop_ms = int(end * 1000)
        self._player.play()

    def _toggle_play(self) -> None:
        self._seg_stop_ms = -1
        if self._player.playbackState() == QMediaPlayer.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _on_position(self, ms: int) -> None:
        sec = ms / 1000.0
        self.lbl_pos.setText(_fmt_time(sec))
        self.wave.set_cursor(sec)
        if 0 <= self._seg_stop_ms <= ms:
            self._player.pause()
            self._seg_stop_ms = -1

    # ---------- 统计 ----------
    def _refresh_stats(self) -> None:
        if self._processed.size == 0:
            self.lbl_stats.setText("导入录音后显示统计")
            return

        duration = len(self._processed) / self._sr if self._sr else 0.0
        if self.cfg.mode.is_full:
            mode_text = "整段·只滤底噪" if self.cfg.mode == ProcessMode.FULL_DENOISE else "整段·滤底噪+放大"
            self.lbl_stats.setText(
                "<br>".join([
                    f"<b>模式</b>: {mode_text}",
                    f"<b>整段时长</b>: {_fmt_duration(duration)}",
                    "<b>导出</b>: WAV",
                ])
            )
            return

        if not self._events:
            self.lbl_stats.setText(
                "<br>".join([
                    "<b>预处理完成</b>",
                    f"<b>整段时长</b>: {_fmt_duration(duration)}",
                    "<b>事件总数</b>: 0",
                ])
            )
            return

        s = summarize(self._events)
        lines = [
            f"<b>事件总数</b>: {s['total']}",
            f"<b>保留</b>: {s['kept']} 段　<b>排除</b>: {s['total'] - s['kept']} 段",
            f"<b>保留总时长</b>: {s['kept_duration']:.1f}s",
            f"<b>手动添加</b>: {s['manual']} 段",
            f"<b>疑似录制混入</b>: {s['suspect']} 段",
            "<hr>",
            "<b>按类型</b>:",
        ]
        for kind, cnt in s["by_kind"].items():
            lines.append(f"　{TYPE_LABELS.get(kind, kind)}: {cnt}")
        self.lbl_stats.setText("<br>".join(lines))

    # ---------- 导出 ----------
    def _on_export(self) -> None:
        if not self._can_export():
            QMessageBox.warning(self, "无可导出内容", "当前模式下没有可导出的内容。")
            return
        out_dir = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if not out_dir:
            return
        out = Path(out_dir)
        stem = self._path.stem if self._path else "noise"
        self._sync_export_cfg()
        self._sync_gain_cfg()

        try:
            if self.cfg.mode.is_full:
                name = f"{stem}_整段降噪.wav"
                if self.cfg.mode == ProcessMode.FULL_AMPLIFY:
                    name = f"{stem}_整段降噪放大.wav"
                wav_path = out / name
                export_full_wav(self._processed, self._sr, wav_path, self.cfg.export, self.cfg.gain)
                QMessageBox.information(
                    self,
                    "导出完成",
                    f"已导出：\n\n• WAV：{wav_path.name}\n\n目录：{out}",
                )
                return

            kept = [ev for ev in self._events if ev.keep]
            if not kept:
                QMessageBox.warning(self, "无可导出内容", "请至少保留一个噪音片段。")
                return
            tags = self._filename_tags()
            suffix = ("_" + "_".join(tags)) if tags else ""
            wav_path = out / f"{stem}_噪音提取{suffix}.wav"
            csv_path = out / f"{stem}_证据报告{suffix}.csv"
            export_highlight_wav(
                self._processed, self._sr, self._events, wav_path,
                self.cfg.export, self.cfg.gain,
            )
            export_report_csv(self._events, csv_path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "导出失败", str(exc))
            return

        QMessageBox.information(
            self,
            "导出完成",
            f"已导出：\n\n• 噪音合集：{wav_path.name}\n• CSV：{csv_path.name}\n\n目录：{out}",
        )

    def _filename_tags(self) -> list[str]:
        tags: list[str] = []
        if self.chk_denoise.isChecked():
            tags.append("降噪")
        if self.cfg.gain.enabled and self.cfg.gain.mode != "off":
            mode_cn = "逐段放大" if self.cfg.gain.mode == "per_event" else "全局放大"
            tags.append(mode_cn)
        tags.append(f"间隔{self.spn_gap.value():g}s")
        return tags
