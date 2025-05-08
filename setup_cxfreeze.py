# setup_cxfreeze.py
from cx_Freeze import setup, Executable
import os, site

base = "Win32GUI"
EMBED_ROOT = os.path.abspath(os.path.dirname(__file__))

# Paths where site-packages live on the runner
site_packages = site.getsitepackages()

build_exe_options = {
    # additional search paths for modules
    "path": site_packages,

    # top-level packages to include
    "packages": [
        "fitz",      # PyMuPDF
        "cv2",       # OpenCV
        "numpy",     # numeric
        "paddleocr", # OCR engine
        "paddle",    # PaddlePaddle core
        "ppocr",     # OCR subpackage
        "pandas",    # dataframes
    ],

    # modules to exclude
    "excludes": ["tkinter","email","http","xml","unittest"],

    # include entire directories or files
    "include_files": [
        ("poppler-24.08.0", "poppler-24.08.0"),
        ("paddle_models",     "paddle_models"),
    ],

    # control zipping: keep heavy packages unpacked
    "zip_include_packages": ["*"],
    "zip_exclude_packages": ["numpy","paddle","paddleocr","ppocr"],

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
