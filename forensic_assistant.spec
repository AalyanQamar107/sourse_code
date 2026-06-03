# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_all

# ------------------------------------------------------------
# 1. Collect ALL llama-cpp-python files (DLLs + Python modules)
# ------------------------------------------------------------
llama_datas, llama_binaries, llama_hidden = collect_all('llama_cpp')

# ------------------------------------------------------------
# 2. Analysis
# ------------------------------------------------------------
a = Analysis(
    ['desktop.py'],
    pathex=[],
    binaries=llama_binaries,                 # includes llama.dll
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('collectors', 'collectors'),
        ('database.py', '.'),
        ('rag.py', '.'),
        ('report.py', '.'),
        ('forensic.py', '.'),
        ('import_export.py', '.'),
        ('paths.py', '.'),
        ('app.py', '.'),
    ] + llama_datas,
    hiddenimports=[
        'collectors.windows',
        'collectors.windows.browser',
        'collectors.windows.events',
        'collectors.windows.prefetch',
        'collectors.windows.recent',
        'collectors.windows.usb',
        'collectors.linux',
        'collectors.linux.browser',
        'collectors.linux.system',
        'collectors.linux.usb',
        'llama_cpp',
        'llama_cpp.llama',
        'webview',
        'flask',
        'win32evtlog',
        'wmi',
        'ctypes',
        'xml.etree.ElementTree',
        'sqlite3',
    ] + llama_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

# ------------------------------------------------------------
# 3. PYZ
# ------------------------------------------------------------
pyz = PYZ(a.pure)

# ------------------------------------------------------------
# 4. EXE – output name "forensiChat.exe", no manifest
# ------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='forensiChat',          # <-- produces forensiChat.exe
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,               # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='myicon.ico',           # Ensure this file is present
)