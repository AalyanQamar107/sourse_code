# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

# Collect all llama-cpp-python files
llama_datas, llama_binaries, llama_hidden = collect_all('llama_cpp')

# Collect all pywebview files
webview_datas, webview_binaries, webview_hidden = collect_all('webview')

# Collect all gi files (system GTK bindings)
gi_datas = collect_data_files('gi', include_py_files=True)
gi_hidden = collect_submodules('gi')

a = Analysis(
    ['desktop.py'],
    pathex=[],
    binaries=llama_binaries + webview_binaries,
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
    ] + llama_datas + webview_datas + gi_datas,
    hiddenimports=[
        'collectors.linux',
        'collectors.linux.browser',
        'collectors.linux.system',
        'collectors.linux.usb',
        'llama_cpp',
        'llama_cpp.llama',
        'webview',
        'webview.platforms.gtk',
        'flask',
        'sqlite3',
        'ctypes',
        'xml.etree.ElementTree',
        'concurrent.futures',
    ] + llama_hidden + webview_hidden + gi_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

# Build as a directory (not a single file) to avoid extraction issues
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ForensiChat',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
    # DO NOT add 'onefile' argument – this builds a directory
)