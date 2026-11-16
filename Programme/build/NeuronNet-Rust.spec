# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path


# PyInstaller setzt SPECPATH beim Aufruf dieser SPEC-Datei auf den
# Build-Ordner; die Projektdateien liegen eine Ebene darüber.
project_root = Path(SPECPATH).resolve().parent
version_information = project_root / 'build' / 'version_info.txt'
build_flavor = os.environ.get("NEURONNET_BUILD_FLAVOR", "author")
if build_flavor not in {"public", "author"}:
    raise ValueError(f"Unbekannte NeuronNet-Buildfassung: {build_flavor}")
author_modules = ["authorhtmlexport", "forwardhtmlexport", "trainingclipexport", "characteristicclipexport"]
datas = [
    (str(project_root / 'hilfe.md'), '.'),
    (str(project_root / 'hilfe_de.md'), '.'),
    (str(project_root / 'hilfe_en.md'), '.'),
    (str(project_root / 'languages.json'), '.'),
    (str(project_root / 'VERSION.txt'), '.'),
    (str(project_root / 'assets' / 'startup_neural_automation.png'), 'assets')
]

tutorials_directory = project_root / 'tutorials'
if tutorials_directory.is_dir():
    datas.append((str(tutorials_directory), 'tutorials'))


a = Analysis(
    ['..\\main.py'],
    pathex=[],
    binaries=[(str(project_root / 'rust' / 'training.dll'), 'rust')],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=author_modules if build_flavor == "public" else [],
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
    name='NeuronNet',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=['training.dll'],
    runtime_tmpdir=None,
    console=False,
    # Die BAT-Datei erzeugt diese Datei vor dem regulären Build. Direkte
    # Entwickler-Builds bleiben auch ohne vorbereitete Versionsdaten möglich.
    version=str(version_information) if version_information.is_file() else None,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
