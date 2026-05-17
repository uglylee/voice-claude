# -*- mode: python ; coding: utf-8 -*-

import os

project_dir = os.path.dirname(os.path.abspath(SPECPATH))

a = Analysis(
    ['speech_recognition_app.py'],
    pathex=[project_dir],
    binaries=[
        ('.venv/Lib/site-packages/vosk/libvosk.dll', '.'),
        ('.venv/Lib/site-packages/vosk/libgcc_s_seh-1.dll', '.'),
        ('.venv/Lib/site-packages/vosk/libstdc++-6.dll', '.'),
        ('.venv/Lib/site-packages/vosk/libwinpthread-1.dll', '.'),
    ],
    datas=[
        ('config.json', '.'),
        ('vosk_model', 'vosk_model'),
    ],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'pyaudio',
        'vosk',
        'pyautogui',
        'pyperclip',
        'pystray',
        'pystray._util',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'winsound',
        'queue',
        'threading',
        'json',
        'ctypes',
        'shutil',
        'cffi',
        'websockets',
        'srt',
        'tqdm',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # No heavy deps to exclude — Vosk is lightweight
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='语音识别',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
