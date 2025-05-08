# setup_cxfreeze.py
from cx_Freeze import setup, Executable
import os, site

base = "Win32GUI"
EMBED_ROOT = os.path.abspath(os.path.dirname(__file__))

# Discover where site-packages are installed on the runner
site_packages = site.getsitepackages()

build_exe_options = {
    # Search for modules in these paths
    "path": site_packages,
    # Include entire packages your app depends on
    "packages": [
        "fitz",           # PyMuPDF
        "cv2",            # OpenCV
        "numpy",
        "paddleocr",
        "paddle",
        "ppocr",          # OCR subpackage
        "ppstructure",    # OCR structure subpackage
        "pandas",
    ],
    # Exclude unused standard libraries
    "excludes": ["tkinter","email","http","xml","unittest"],
    # Data files and folders to include in build
    "include_files": [
        ("poppler-24.08.0", "poppler-24.08.0"),
        ("paddle_models", "paddle_models"),
    ],
    # Include Microsoft Visual C++ runtime DLLs
    "include_msvcr": True,
}

setup(
    name="ExtratorFaturas",
    version="1.0",
    description="OCR de faturas com PaddleOCR",
    options={"build_exe": build_exe_options},
    executables=[Executable("main_processor.py", base=base)]
)
