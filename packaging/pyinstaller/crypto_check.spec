# PyInstaller build recipe. Run from the project root:
#     pyinstaller packaging/pyinstaller/crypto_check.spec
# Output: dist/CryptoCheck/  (a folder with the CryptoCheck executable + its files)

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH).resolve().parent.parent

a = Analysis(
    [str(ROOT / "packaging" / "pyinstaller" / "launch.py")],
    pathex=[str(ROOT)],
    datas=[
        (str(ROOT / "crypto_check" / "assets"), "crypto_check/assets"),
        *collect_data_files("customtkinter"),  # CustomTkinter's theme .json files
    ],
    # Pillow loads this lazily when showing images in Tk, so PyInstaller can't see it on its own.
    hiddenimports=["PIL._tkinter_finder"],
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CryptoCheck",
    console=False,  # GUI app: no terminal window on Windows
    icon=str(ROOT / "crypto_check" / "assets" / "icon.ico") if sys.platform == "win32" else None,
)

coll = COLLECT(exe, a.binaries, a.datas, name="CryptoCheck")
