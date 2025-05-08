# setup_cxfreeze.py
from cx_Freeze import setup, Executable
import os, site

base = "Win32GUI"
EMBED_ROOT = os.path.abspath(os.path.dirname(__file__))

# aponta para onde o runner instalou site‑packages
site_packages = site.getsitepackages()

build_exe_options = {
    # caminho extra onde procurar pacotes
    "path": site_packages,
    # bibliotecas que seu código importa
    "packages": [
        "fitz",      # PyMuPDF
        "cv2",       # OpenCV
        "numpy",
        "paddleocr",
        "paddle",
        "pandas",
    ],
    # módulos puros que precisam ser forçados
    "includes": [
        "paddle", 
        "paddleocr.tools",
        "ppocr",
        "ppstructure"
    ],
    # pacotes que não interessam
    "excludes": ["tkinter","email","http","xml","unittest"],
    # arquivos/diretórios de dados a copiar
    "include_files": [
        ("poppler-24.08.0","poppler-24.08.0"),
        ("paddle_models","paddle_models"),
    ],
    "include_msvcr": True,
}

setup(
    name="ExtratorFaturas",
    version="1.0",
    description="OCR de faturas com PaddleOCR",
    options={"build_exe": build_exe_options},
    executables=[Executable("main_processor.py", base=base)]
)
