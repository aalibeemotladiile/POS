# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller recipe for Sales Manager (HDM POS).
#
#   pyinstaller build_windows.spec --noconfirm --clean
#
# Produces dist\SalesManager\SalesManager.exe (onedir — faster to start and far
# easier for antivirus to accept than a single-file build).

import os
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

datas, binaries, hiddenimports = [], [], []

# Streamlit and friends load a lot at runtime that static analysis misses:
# static assets, entry points, vendored JS. Collect broadly rather than guess
# — a missing piece shows up as a blank window, not an import error. The app
# charts with Plotly (plotly.js must travel too), writes PDF reports and
# receipts with reportlab, reads Excel price lists with openpyxl, and uses
# tzdata for local (Gaborone) time on Windows.
for pkg in ["streamlit", "plotly", "pyarrow", "pandas", "numpy",
            "tornado", "blinker", "watchdog", "validators", "toml",
            "click", "git", "pydeck", "tenacity", "cachetools",
            "reportlab", "PIL", "openpyxl", "et_xmlfile", "tzdata"]:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

# The native window. clr_loader/pythonnet back pywebview's WinForms host.
for pkg in ["webview", "clr_loader", "pythonnet", "proxy_tools"]:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

hiddenimports += collect_submodules("streamlit")
hiddenimports += collect_submodules("plotly")
# The frozen-app crash "init pandas._libs.tslibs.offsets (ImportError)" happens
# when even one of pandas' compiled Cython submodules is not bundled. Pulling in
# every _libs submodule (and numpy's) removes the guesswork.
hiddenimports += collect_submodules("pandas")
hiddenimports += collect_submodules("pandas._libs")
hiddenimports += collect_submodules("pandas._libs.tslibs")
hiddenimports += collect_submodules("numpy")
hiddenimports += collect_submodules("openpyxl")
hiddenimports += [
    "clr",
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
    "webview.platforms.mshtml",
    "streamlit.web.cli",
    "streamlit.runtime.scriptrunner.magic_funcs",
    "zoneinfo",
    "sqlite3",
    "pandas._libs.tslibs.base",
    "pandas._libs.tslibs.np_datetime",
    "pandas._libs.tslibs.nattype",
    "pandas._libs.tslibs.timezones",
    "pandas._libs.tslibs.tzconversion",
    "pandas._libs.tslibs.timestamps",
    "pandas._libs.tslibs.timedeltas",
    "pandas._libs.tslibs.offsets",
    "pandas._libs.tslibs.period",
    "pandas._libs.tslibs.conversion",
    "pandas._libs.tslibs.fields",
    "pandas._libs.tslibs.parsing",
    "pandas._libs.tslibs.strptime",
    "pandas._libs.tslibs.vectorized",
    "pandas._libs.tslibs.ccalendar",
    "pandas._libs.tslibs.dtypes",
    "pandas._libs.interval",
    "pandas._libs.hashtable",
    "pandas._libs.missing",
    "pandas._libs.lib",
    "pandas._libs.ops",
    "pandas._libs.properties",
    "pandas._libs.pandas_parser",
    "pandas._libs.pandas_datetime",
]

# importlib.metadata lookups (streamlit.__version__ and friends) need dist-info.
for meta in ["streamlit", "pandas", "numpy", "pyarrow", "plotly", "reportlab",
             "pillow", "openpyxl", "tzdata", "pywebview", "pythonnet", "tornado",
             "click", "blinker"]:
    try:
        datas += copy_metadata(meta)
    except Exception:
        pass

# The app itself and its icon travel with the bundle.
for extra in ["SalesManager.py", "logo.ico"]:
    if os.path.exists(extra):
        datas.append((extra, "."))

_icon = "logo.ico" if os.path.exists("logo.ico") else None

a = Analysis(
    ["run_desktop.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SalesManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # windowed app — no console flashes up
    disable_windowed_traceback=False,
    icon=_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SalesManager",
)
