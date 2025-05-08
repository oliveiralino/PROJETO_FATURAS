# setup_cxfreeze.py
from cx_Freeze import setup, Executable
import os, site

# Suppress console window; use None if console is desired
base = "Win32GUI"
# Root of this script
EMBED_ROOT = os.path.abspath(os.path.dirname(__file__))

# Determine potential site-packages directories
site_packages = []
# standard location(s)
for p in site.getsitepackages():
    # ensure path ends in site-packages
    if p.lower().endswith("site-packages"):
        site_packages.append(p)
# fallback: consider EMBED_ROOT/Lib/site-packages
fallback = os.path.join(EMBED_ROOT, "Lib", "site-packages")
if os.path.isdir(fallback):
    site_packages.append(fallback)
# if still empty, use EMBED_ROOT
if not site_packages:
    site_packages = [EMBED_ROOT]

# Helper to locate a package folder within site-packages
def pkg_dir(pkg_name):
    for sp in site_packages:
        # try direct
        src = os.path.join(sp, pkg_name)
        if os.path.isdir(src):
            return (src, pkg_name)
        # try underscore/hyphen variant
        alt = os.path.join(sp, pkg_name.replace('-', '_'))
        if os.path.isdir(alt):
            return (alt, pkg_name)
    # not found
    raise FileNotFoundError(f"Package folder for {pkg_name} not found in {site_packages}")

# Build include_files list: data and full package dirs
include_files = []
# Poppler data
include_files.append((os.path.join(EMBED_ROOT, "poppler-24.08.0"), "poppler-24.08.0"))
# OCR models
include_files.append((os.path.join(EMBED_ROOT, "paddle_models"), "paddle_models"))
# Include entire packages to ensure finder picks them up
for pkg in ["numpy", "cv2", "fitz", "pandas", "paddle", "paddleocr"]:
    include_files.append(pkg_dir(pkg))

# cx_Freeze build options
build_exe_options = {
    # where to search for imports
    "path": site_packages,
    # top-level packages to include
    "packages": ["numpy", "cv2", "fitz", "pandas", "paddleocr"],
    # exclude unwanted
    "excludes": ["tkinter", "email", "http", "xml", "unittest"],
    # include data files and package dirs
    "include_files": include_files,
    # bundle MSVC runtime
    "include_msvcr": True,
}

setup(
    name="ExtratorFaturas",
    version="1.0",
    description="OCR de faturas com PaddleOCR e extração digital",
    options={"build_exe": build_exe_options},
    executables=[Executable("main_processor.py", base=base)]
)
