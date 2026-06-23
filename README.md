# 楼上噪音取证助手

专业的楼上噪音录音分析与取证工具，基于 **Rust + Tauri** 构建。

## 功能特性

- **智能检测**：自动识别录音中的噪音事件（撞击、拖拽、摩擦等）
- **降噪处理**：可选的底噪抑制，提升取证音频清晰度
- **三种处理模式**：
  - 整段降噪：保留完整录音并降噪
  - 整段放大：保留完整录音并归一化增益
  - 智能切片：提取噪音片段并合成
- **可视化波形**：实时预览音频波形与检测结果
- **人工复核**：在波形上框选新增事件、删除误检、勾选保留
- **批量导出**：生成 WAV 音频和 CSV 事件清单

## 项目结构

```
.
├── desktop/          # Tauri 桌面应用（主版本）
│   ├── src/         # React + TypeScript 前端
│   └── src-tauri/   # Rust 后端
├── crates/          # Rust 核心库
│   ├── noise-types/ # 类型定义
│   ├── noise-core/  # 核心算法（检测、降噪、增益）
│   ├── noise-io/    # 音频 I/O
│   └── noise-cli/   # 命令行工具
├── fixtures/        # 测试夹具
├── docs/            # 文档
└── archive/         # 归档代码
    └── python-legacy/  # Python 旧版本（已停止维护）
```

## 快速开始

### 安装依赖

```bash
# Rust 工具链（需要 1.70+）
rustup update stable

# Node.js（需要 18+）
npm install -g pnpm

# 安装前端依赖
cd desktop
pnpm install
```

### 开发模式

```bash
cd desktop
pnpm tauri dev
```

### 构建发布版

```bash
cd desktop
pnpm tauri build
```

**构建产物：**
- 可执行文件: `desktop/src-tauri/target/release/noise-evidence-next.exe`
- 安装包: `desktop/src-tauri/target/release/bundle/nsis/楼上噪音取证助手 Next_*_x64-setup.exe`

### 命令行工具

```bash
# 构建 CLI
cargo build --release -p noise-cli

# 运行
./target/release/noise-cli export-audio \
  --input recording.wav \
  --config config.json \
  --output output.wav \
  --csv events.csv
```

## 配置示例

详见 [数据协议文档](docs/data-contracts.md)。

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
  }
}
```

## 技术栈

- **后端**: Rust
  - [nnnoiseless](https://github.com/jneem/nnnoiseless) - RNN 降噪
  - [hound](https://github.com/ruuda/hound) - WAV 编解码
  - [rustfft](https://github.com/ejmahler/RustFFT) - FFT 频谱分析
- **前端**: React + TypeScript + Vite
- **桌面框架**: Tauri v2
- **打包**: NSIS

## 文档

- [架构设计](docs/architecture-next.md)
- [数据协议](docs/data-contracts.md)
- [迁移计划](docs/migration-plan.md)

## 归档说明

Python 版本（位于 `archive/python-legacy/`）已停止维护，仅保留作为参考。

当前主版本为 **Rust 实现**，具有更好的性能和跨平台支持。

## 取证边界

本工具用于辅助定位和整理录音中的可疑噪音事件。事件分类和”疑似录制混入”只提供声学线索，不能单独证明声音来源；最终证据判断仍应结合原始录音、录制时间、环境记录和人工复核。

## License

MIT
