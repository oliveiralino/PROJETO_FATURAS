# setup_cxfreeze.py
from cx_Freeze import setup, Executable
import os, site, shutil

base = "Win32GUI"
EMBED_ROOT = os.path.abspath(os.path.dirname(__file__))

# Discover where site-packages live
site_packages = site.getsitepackages()
sp_path = site_packages[0] if site_packages else EMBED_ROOT

# Build list of data files (poppler, paddle_models, and full packages)
include_files = []
# Include poppler and paddle_models folders
for folder in ("poppler-24.08.0", "paddle_models"):
    src = os.path.join(EMBED_ROOT, folder)
    if os.path.isdir(src):
        include_files.append((src, folder))

# Also include entire packages that finder fails on
for pkg in ("numpy", "cv2", "fitz", "pandas", "paddle", "paddleocr"):
    src = os.path.join(sp_path, pkg)
    if os.path.exists(src):
        include_files.append((src, pkg))

build_exe_options = {
    # ensure module search also checks site-packages
    "path": site_packages,
    # modules to include automatically
    "packages": ["numpy", "cv2", "fitz", "pandas", "paddle", "paddleocr"],
    # exclude unwanted
    "excludes": ["tkinter", "email", "http", "xml", "unittest"],
    # data files and package directories
    "include_files": include_files,
    # include MSVC runtime
    "include_msvcr": True,
    # keep these packages as loose files (not zipped)
    "zip_exclude_packages": ["numpy", "cv2", "fitz", "pandas", "paddle", "paddleocr"],
    # zip everything else
    "zip_include_packages": ["*"]
}

setup(
    name="ExtratorFaturas",
    version="1.0",
    description="OCR de faturas com PaddleOCR",
    options={"build_exe": build_exe_options},
    executables=[Executable("main_processor.py", base=base)]
)

    options={"build_exe": build_exe_options},
    executables=[Executable("main_processor.py", base=base)]
)
