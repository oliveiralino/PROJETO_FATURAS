# setup_cxfreeze.py
from cx_Freeze import setup, Executable
import os, sys, site

# Use "Win32GUI" to suppress console window; use None for console
base = "Win32GUI"

EMBED_ROOT = os.path.abspath(os.path.dirname(__file__))

# Determine site-packages path so cx_Freeze can find installed libraries
site_packages = site.getsitepackages()

build_exe_options = {
    # Include Python packages your app uses
    "packages": [
        "fitz",      # PyMuPDF
        "cv2",       # OpenCV
        "numpy",
        "paddleocr",
        "paddle",
        "pandas",
        # standard libs are pulled in automatically
    ],
    # Include modules explicitly if needed
    "includes": ["paddle"],
    # Exclude unnecessary packages
    "excludes": ["tkinter", "email", "http", "xml", "unittest"],
    # Add paths so cx_Freeze can locate site-packages
    "path": site_packages,
    # Data files and folders to include
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
