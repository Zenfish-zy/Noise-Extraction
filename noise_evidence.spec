# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配方：楼上噪音取证助手。

关键点（打包后能正常解码 m4a + 播放音频）:
  1. 把 imageio_ffmpeg 自带的 ffmpeg.exe 原样收进 imageio_ffmpeg/binaries/，
     因为 get_ffmpeg_exe() 是按"模块目录/binaries/<名字>"去找的。
  2. 收齐 PySide6 的多媒体后端与平台插件（QMediaPlayer 播放所需）。
  3. 单目录(onedir)模式：启动快、易排查；体积虽大但都在一个文件夹里。
"""

import os

from PyInstaller.utils.hooks import collect_dynamic_libs

import imageio_ffmpeg

block_cipher = None

# --- 1. 内置 ffmpeg 二进制，放回它期望的相对路径 ---
_ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
_ffmpeg_name = os.path.basename(_ffmpeg_exe)
binaries = [(_ffmpeg_exe, os.path.join("imageio_ffmpeg", "binaries"))]

# --- 2. soundfile 自带的 libsndfile 动态库 ---
binaries += collect_dynamic_libs("soundfile")

# --- 3. 应用资源（图标），收进 noise_evidence/assets/ 供 resources.asset_path 找到 ---
datas = [("noise_evidence/assets", "noise_evidence/assets")]

_icon = os.path.join("noise_evidence", "assets", "icon.ico")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "PySide6.QtMultimedia",
        "soundfile",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 砍掉用不到的大块，给体积瘦身
    excludes=[
        "matplotlib",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.Qt3DCore",
        "PySide6.QtCharts",
        "PySide6.QtDesigner",
        "PySide6.QtHelp",
        "PySide6.QtOpenGL",
        "PySide6.QtOpenGLWidgets",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtPrintSupport",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuick3D",
        "PySide6.QtQuickControls2",
        "PySide6.QtSql",
        "PySide6.QtSvg",
        "PySide6.QtSvgWidgets",
        "PySide6.QtTest",
        "PySide6.QtDataVisualization",
        "tkinter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="楼上噪音取证助手",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI 程序，不弹黑窗
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="楼上噪音取证助手",
)
