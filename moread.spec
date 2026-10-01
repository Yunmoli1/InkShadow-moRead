# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: 打包墨读 MoRead 为单文件可执行程序
#   构建: pyinstaller moread.spec --noconfirm
#   输出: dist/moread.exe (前端资源内嵌于 web/dist)

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
ROOT = os.path.abspath(SPECPATH)

# 网页转小说(OCR)：RapidOCR 的 ONNX 模型与配置文件必须整体内嵌
ocr_datas = collect_data_files('rapidocr_onnxruntime')

a = Analysis(
    [os.path.join(ROOT, 'backend', 'run.py')],
    pathex=[os.path.join(ROOT, 'backend')],
    binaries=[],
    datas=[
        # 前端构建产物整体内嵌，运行时从 web/dist 提供
        (os.path.join(ROOT, 'frontend', 'dist'), 'web/dist'),
        # ffmpeg/ffprobe（yt-dlp 音视频合并用），解压到 bin/ 并在 PATH 前部
        (os.path.join(ROOT, 'tools', 'ffmpeg'), 'bin'),
    ] + ocr_datas,
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'aiosqlite',
        'anyio._backends._asyncio',
        # 网页转小说(OCR) 内置工具
        'trafilatura',
        'rapidocr_onnxruntime',
        'onnxruntime',
    ] + collect_submodules('rapidocr_onnxruntime'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='moread',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,          # 双击运行时保留控制台窗口（显示日志与退出提示）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
