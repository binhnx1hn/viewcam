# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect all data files and submodules
block_cipher = None

a = Analysis(
    ['multiplecam.py'],
    pathex=[],
    binaries=[
        ('libvlc.dll', '.'),
        ('libvlccore.dll', '.'),
    ],
    datas=[
        ('camera.json', '.'),
        ('department_mapping.json', '.'),
        ('logo.ico', '.'),
        ('logo.svg', '.'),
        ('plugins', 'plugins'),
        ('img', 'img'),
    ],
    hiddenimports=[
        'hooks.use_socket',
        'hooks.__init__',
        'department_mapping',
        'socketio',
        'engineio',
        'python_engineio',
        'python_socketio',
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtNetwork',
        'vlc',
    ],
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
    name='multiplecam',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo.ico' if os.path.exists('logo.ico') else None,
)
