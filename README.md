# 楼上噪音取证助手

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Rust](https://img.shields.io/badge/rust-2024-orange.svg)
![Platform](https://img.shields.io/badge/platform-Windows-blue.svg)

**专业的楼上噪音录音分析与取证工具** — 智能检测、降噪处理、可视化分析、一键导出

> 基于 **Rust + Tauri** 构建，高性能、低资源占用、原生体验

---

## ✨ 功能特性

### 🎯 智能检测
- 自动识别录音中的噪音事件（撞击、拖拽、摩擦等）
- 可调节灵敏度、响度门限、合并间隔
- 支持手动框选添加/删除事件

### 🔇 降噪处理
- 基于 RNN 深度学习的底噪抑制
- 可选启用，提升取证音频清晰度
- 智能采样背景噪音

### 📊 可视化分析
- 实时波形预览
- 事件标记与时间轴
- 音频播放与定位

### 📦 三种处理模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| **整段降噪** | 保留完整录音 + 底噪抑制 | 需要完整时间线，但录音有底噪 |
| **整段放大** | 保留完整录音 + 归一化增益 | 录音音量太小，需要放大 |
| **智能切片** | 提取噪音片段 + 合成导出 | 长时间录音，只需要噪音部分 |

### 📤 批量导出
- **WAV 音频** - 处理后的取证音频
- **CSV 清单** - 事件时间、类型、响度等详细信息
- 支持蜂鸣间隔、增益控制

---

## 🚀 快速开始

### 方式一：直接安装（推荐）

1. 下载最新版本的安装包：  
   👉 [Releases](https://github.com/Zenfish-zy/Noise-Extraction/releases)

2. 双击 `楼上噪音取证助手_*_x64-setup.exe` 运行安装向导

3. 安装完成后，从开始菜单启动应用

### 方式二：从源码构建

**环境要求：**
- Rust 1.70+
- Node.js 18+
- Windows 10/11

**构建步骤：**

```bash
# 1. 克隆仓库
git clone https://github.com/Zenfish-zy/Noise-Extraction.git
cd Noise-Extraction

# 2. 安装前端依赖
cd desktop
npm install -g pnpm
pnpm install

# 3. 开发模式（热重载）
pnpm tauri dev

# 4. 构建发布版
pnpm tauri build
```

构建产物位于：
- **可执行文件**: `desktop/src-tauri/target/release/noise-evidence-next.exe`
- **安装包**: `desktop/src-tauri/target/release/bundle/nsis/*.exe`

---

## 📖 使用指南

### 基本流程

1. **导入录音** - 点击”导入录音”按钮，选择音频文件（支持 WAV/MP3/M4A/FLAC 等）
2. **查看检测结果** - 系统自动分析并标记噪音事件
3. **调整参数**（可选）- 调节灵敏度、响度门限、降噪开关等
4. **人工复核** - 在波形上框选新增事件，或删除误检
5. **导出证据** - 点击”导出”，生成 WAV 音频和 CSV 清单

### 命令行工具（高级）

```bash
# 构建 CLI
cargo build --release -p noise-cli

# 分析音频
./target/release/noise-cli export-audio \
  --input recording.wav \
  --config config.json \
  --output output.wav \
  --csv events.csv
```

**配置文件示例** (`config.json`):

```json
{
  “mode”: “highlight”,
  “denoise”: {
    “enabled”: true,
    “noise_sample_seconds”: 1,
    “prop_decrease”: 0.8,
    “stationary”: true
  },
  “detect”: {
    “frame_ms”: 30,
    “hop_ms”: 10,
    “sensitivity”: “medium”,
    “min_event_seconds”: 0.08,
    “merge_gap_seconds”: 1.0,
    “pad_seconds”: 0.1,
    “min_peak_dbfs”: -30
  },
  “gain”: {
    “enabled”: true,
    “mode”: “per_event”,
    “target_peak_dbfs”: -1,
    “max_gain_db”: 36
  },
  “export”: {
    “gap_seconds”: 0.5,
    “insert_beep”: true,
    “beep_hz”: 880,
    “beep_seconds”: 0.12
  }
}
```

详细参数说明见 [数据协议文档](docs/data-contracts.md)。

---

## 🏗️ 项目结构

```
.
├── desktop/              # Tauri 桌面应用（主版本）
│   ├── src/             # React + TypeScript 前端
│   ├── src-tauri/       # Rust 后端
│   └── package.json
├── crates/              # Rust 核心库
│   ├── noise-types/    # 类型定义
│   ├── noise-core/     # 核心算法（检测、降噪、增益）
│   ├── noise-io/       # 音频 I/O
│   └── noise-cli/      # 命令行工具
├── fixtures/            # 测试夹具
├── docs/                # 文档
│   ├── architecture-next.md
│   ├── data-contracts.md
│   └── migration-plan.md
└── archive/             # 归档代码
    └── python-legacy/  # Python 旧版本（已停止维护）
```

---

## 🔧 技术栈

### 后端
- **Rust** - 高性能系统编程语言
- [nnnoiseless](https://github.com/jneem/nnnoiseless) - RNN 降噪
- [hound](https://github.com/ruuda/hound) - WAV 编解码
- [rustfft](https://github.com/ejmahler/RustFFT) - FFT 频谱分析

### 前端
- **React** - UI 框架
- **TypeScript** - 类型安全
- **Vite** - 构建工具

### 桌面框架
- **Tauri v2** - 轻量级桌面框架
- **NSIS** - Windows 安装包

---

## 📚 文档

- [架构设计](docs/architecture-next.md) - 系统架构与模块划分
- [数据协议](docs/data-contracts.md) - API 接口与配置规范
- [迁移计划](docs/migration-plan.md) - Python → Rust 迁移记录

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## ⚖️ 取证边界

本工具用于辅助定位和整理录音中的可疑噪音事件。事件分类和”疑似录制混入”只提供声学线索，不能单独证明声音来源；最终证据判断仍应结合原始录音、录制时间、环境记录和人工复核。

---

## 📜 License

MIT License - 详见 [LICENSE](LICENSE) 文件

---

## 🗂️ 归档说明

Python 版本（位于 `archive/python-legacy/`）已停止维护，仅保留作为参考。

当前主版本为 **Rust 实现**，具有更好的性能和跨平台支持。

---

## 📮 联系方式

- GitHub Issues: [提交问题](https://github.com/Zenfish-zy/Noise-Extraction/issues)
- 作者: Zenfish
