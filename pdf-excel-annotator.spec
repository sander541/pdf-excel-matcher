# -*- mode: python ; coding: utf-8 -*-
import certifi
import re
from pathlib import Path

# Read version without importing the package (avoids sys.path issues in PyInstaller)
_version_text = Path('pdf_excel_annotator/version.py').read_text(encoding='utf-8')
__version__ = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', _version_text).group(1)

a = Analysis(
    ['gui.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('pdf_excel_annotator', 'pdf_excel_annotator'),
        (certifi.where(), 'certifi'),  # Bundle CA certs for SSL in frozen app
    ],
    hiddenimports=[],
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
    name='pdf-excel-annotator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='pdf-excel-annotator',
)
app = BUNDLE(
    coll,
    name='pdf-excel-annotator.app',
    icon=None,
    bundle_identifier='com.zerano.pdf-excel-annotator',
    info_plist={
        'CFBundleName': 'PDF Excel Annotator',
        'CFBundleDisplayName': 'PDF Excel Annotator',
        'CFBundleShortVersionString': __version__,
        'CFBundleVersion': __version__,
        'NSHighResolutionCapable': True,
        'NSPrincipalClass': 'NSApplication',
        'NSHumanReadableCopyright': f'Copyright © 2025 Zerano',
    },
)
