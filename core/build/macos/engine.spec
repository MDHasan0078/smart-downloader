# PyInstaller spec: macOS engine binary.
# Build on macOS (e.g. GitHub Actions macos-latest) from repo root:
#   pyinstaller core/build/macos/engine.spec

import os

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.dirname(os.path.dirname(SPECPATH))  # the core/ directory

a = Analysis(
    [os.path.join(ROOT, "build", "engine_launcher.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[],
    hiddenimports=collect_submodules("core"),
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="engine",
    debug=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="engine",
)
