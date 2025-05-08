# setup_cxfreeze.py
from cx_Freeze import setup, Executable
import os, site

base = "Win32GUI"
EMBED_ROOT = os.path.abspath(os.path.dirname(__file__))

# Discover site-packages paths on runner
site_packages = site.getsitepackages()
sp = site_packages[0] if site_packages else EMBED_ROOT

# Helper to include an installed package directory
def pkg_dir(pkg_name):
    src = os.path.join(sp, pkg_name)
    if os.path.isdir(src): return (src, pkg_name)
    # try top-level with hyphen/underscore
    alt = os.path.join(sp, pkg_name.replace('-', '_'))
    if os.path.isdir(alt): return (alt, pkg_name)
    raise FileNotFoundError(f"Package folder for {pkg_name} not found in {sp}")

# Build include_files list
include_files = []
# poppler and OCR model data
include_files.append((os.path.join(EMBED_ROOT, "poppler-24.08.0"), "poppler-24.08.0"))
include_files.append((os.path.join(EMBED_ROOT, "paddle_models"), "paddle_models"))
# Also include full package folders for modules that cx_Freeze misses
for pkg in ["numpy", "cv2", "fitz", "pandas", "paddle", "paddleocr"]:
    include_files.append(pkg_dir(pkg))

build_exe_options = {
    # search paths for module finder
    "path": site_packages,
    # explicitly include modules
    "packages": ["numpy", "cv2", "fitz", "pandas", "paddleocr"],
    # exclude unwanted
    "excludes": ["tkinter", "email", "http", "xml", "unittest"],
    # include data files
    "include_files": include_files,
    # include MSVC redistributables
    "include_msvcr": True,
}

setup(
    name="ExtratorFaturas",
    version="1.0",
    description="OCR de faturas com PaddleOCR",
    options={"build_exe": build_exe_options},
    executables=[Executable("main_processor.py", base=base)]
)
