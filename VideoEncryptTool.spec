# -*- mode: python ; coding: utf-8 -*-

import os

_project_root = SPECPATH

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[
        (os.path.join(_project_root, 'ffmpeg', 'ffmpeg.exe'), 'ffmpeg'),
        (os.path.join(_project_root, 'ffmpeg', 'ffprobe.exe'), 'ffmpeg'),
    ],
    datas=[('Config', 'Config')],
    hiddenimports=['core', 'pyaes', 'crypto_layer'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['flask', 'werkzeug', 'jinja2', 'markupsafe'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='VideoEncryptTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir='.',
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
    version='version.txt',
)
