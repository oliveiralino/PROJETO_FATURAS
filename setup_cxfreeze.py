# setup_cxfreeze.py
from cx_Freeze import setup, Executable
import os, site

base = "Win32GUI"
EMBED_ROOT = os.path.abspath(os.path.dirname(__file__))

# Discover where site-packages live on the runner
site_packages = site.getsitepackages()
# Use the first site-packages path
sp_path = site_packages[0] if site_packages else EMBED_ROOT

# Prepare include_files: poppler, paddle_models, and the paddleocr & paddle packages
include_files = [
    ("poppler-24.08.0", "poppler-24.08.0"),
    ("paddle_models", "paddle_models"),
]
# Include the paddleocr and paddle package directories
for pkg in ("paddleocr", "paddle"):  
    src = os.path.join(sp_path, pkg)
    if os.path.exists(src):
        include_files.append((src, pkg))

build_exe_options = {
    # additional search paths for modules
    "path": site_packages,

    # top-level packages to include
    "packages": [
        "fitz",      # PyMuPDF
        "cv2",       # OpenCV
        "numpy",
        "paddleocr", # OCR engine
        "paddle",    # PaddlePaddle core
        "pandas",
    ],

    # modules to exclude
    "excludes": ["tkinter","email","http","xml","unittest"],

    # include additional files and directories
    "include_files": include_files,

    # include MSVC runtime
    "include_msvcr": True,
}

setup(
    name="ExtratorFaturas",
    version="1.0",
    description="OCR de faturas com PaddleOCR",
    options={"build_exe": build_exe_options},
    executables=[Executable("main_processor.py", base=base)]
)
