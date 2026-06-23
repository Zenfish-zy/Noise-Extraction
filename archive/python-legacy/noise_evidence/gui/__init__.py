"""PySide6 图形界面。

模块划分(SOLID-单一职责):
  - worker:   后台处理线程(解码/降噪/检测)，避免界面卡死
  - waveform: 波形 + 事件高亮控件，可点击定位
  - player:   音频播放控制(基于 QtMultimedia)
  - window:   主窗口，组装上述部件并处理用户交互
"""
