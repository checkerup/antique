# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for antique portable Windows build.

Produces a self-contained directory (onedir) at dist/antique-portable/
containing the antique CLI + all Python dependencies. Playwright browser
binaries are NOT bundled — they are downloaded on first run via
start.bat / the launcher.

Usage:
    pyinstaller packaging/antique.spec --noconfirm

Output:
    dist/antique-portable/antique/antique.exe   (CLI entry point)
    dist/antique-portable/antique/_internal/     (all deps + data files)
"""
import sys
from pathlib import Path

block_cipher = None

# Project root = parent of packaging/
project_root = Path(SPECPATH).parent

datas = [
    # Ship the UI dashboard templates / static files
    (str(project_root / "src" / "ui" / "templates"), "src/ui/templates"),
    (str(project_root / "src" / "ui" / "static"), "src/ui/static"),
]

# Add fingerprint corpus if present
corpus = project_root / "data" / "fingerprint_corpus"
if corpus.exists():
    for item in corpus.iterdir():
        if item.is_file():
            datas.append((str(item), "data/fingerprint_corpus"))

binaries = []

hidden_imports = [
    # Common dynamically-imported modules
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.lifespan.onloop",
    "uvicorn.lifespan.off",
    "sqlmodel",
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.dialects.sqlite.pysqlite",
    "pydantic._internal._validators",
    "email.mime.multipart",
    "email.mime.text",
    "multipart",
    "aiohttp",
    "httpx",
    "cryptography",
    "typer",
    "rich",
    "yaml",
    "dotenv",
    "playwright",
    "playwright.sync_api",
    "playwright.async_api",
]

a = Analysis(
    [str(project_root / "src" / "cli.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "pydoc",
        "doctest",
        "argparse",  # typer pulls in click, not argparse directly
        "test",
        "tests",
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
    name="antique",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,  # No code signing — see docs/packaging/SIGNING.md
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="antique",
)
