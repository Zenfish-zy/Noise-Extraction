# Noise Evidence

楼上噪音取证助手。用于导入录音、预处理底噪、检测噪音事件、人工复核事件，并导出可听的 WAV 证据文件。

## 功能

- 三种处理模式：
  - 整段·只滤底噪：导出完整 WAV。
  - 整段·滤底噪+放大：导出完整 WAV，并做不失真整体放大。
  - 智能切片合集：手动触发事件检测，导出噪音合集 WAV 和 CSV 证据报告。
- 检测参数可调：
  - 检测灵敏度
  - 最小响度门限
  - 相邻峰值合并间隔
  - 事件起止缓冲
- 支持人工编辑事件：
  - 在波形上框选新增事件
  - 在事件表中删除误检事件
  - 勾选保留或排除事件
- 支持多格式音频导入：
  - `m4a`
  - `mp3`
  - `wav`
  - `flac`
  - `aac`
  - `mp4`
  - `ogg`

## 环境

```powershell
uv sync
```

项目要求 Python `>=3.13`。依赖由 `uv.lock` 固定。

## 运行

```powershell
uv run noise-evidence
```

也可以直接运行入口脚本：

```powershell
uv run python main.py
```

## 测试

```powershell
uv run python -m unittest discover -s tests
```

## 打包

```powershell
uv run pyinstaller noise_evidence.spec
```

打包产物会生成在 `dist/`，该目录不会提交到 Git。

## 版本管理约定

- 源码、图标资源、锁文件和打包配置纳入 Git。
- 本地录音、导出结果、测试截图、导入耗时日志、虚拟环境和构建产物不纳入 Git。
- `main` 分支推送后会通过 GitHub Actions 自动运行编译检查和核心测试。
- 当前首个版本为 `0.1.0`。

## 下一代重构方向

下一代版本规划在 `next/` 下推进，目标架构为 `Tauri + React/TypeScript + Rust core`。当前 Python/PySide6 版本保留为稳定版和行为基准。

详见：

- `docs/architecture-next.md`
- `docs/migration-plan.md`
- `docs/data-contracts.md`

## 取证边界

本工具用于辅助定位和整理录音中的可疑噪音事件。事件分类和“疑似录制混入”只提供声学线索，不能单独证明声音来源；最终证据判断仍应结合原始录音、录制时间、环境记录和人工复核。
