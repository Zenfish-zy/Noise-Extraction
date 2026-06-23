# Python Legacy Version

**此版本已归档，不再维护。**

这是楼上噪音取证助手的 Python/PySide6 实现，作为原型版本开发。

## 为什么归档？

Rust 版本提供了：
- 更好的性能（10x+ 处理速度）
- 更小的安装包体积
- 更好的跨平台支持
- 更现代的 UI 框架（React + Tauri）
- 统一的类型系统和配置协议

## 如何使用

如果您需要运行此版本：

```bash
# 安装依赖
uv sync

# 运行
uv run python main.py
```

## 迁移到 Rust 版本

请使用根目录的 Rust 实现：

```bash
cd ../../desktop
pnpm tauri dev
```

详见主项目 [README.md](../../README.md)。
