# -*- mode: python ; coding: utf-8 -*-

import os
import shutil

APP_NAME = "MiniCMD"

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        "webview",
        "flask",
        "jinja2",
        "werkzeug",
        "click",
        "itsdangerous"
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)

# Copiar carpetas directo al lado del .exe
dist_path = os.path.join("dist", APP_NAME)

for folder in ["web", "commads", "system"]:
    src = folder
    dst = os.path.join(dist_path, folder)

    if os.path.exists(dst):
        shutil.rmtree(dst)

    if os.path.exists(src):
        shutil.copytree(src, dst)