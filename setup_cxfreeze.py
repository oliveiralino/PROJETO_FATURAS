# setup_cxfreeze.py
from cx_Freeze import setup, Executable
import os

# Use "Win32GUI" to suppress console window (Tkinter GUI). If you want console, use None or "Console"
base = "Win32GUI"

# Base path of this script
EMBED_ROOT = os.path.abspath(os.path.dirname(__file__))

# Options for build_exe
build_exe_options = {
    # pacotes Python que seu app importa diretamente
    "packages": [
        "fitz",      # PyMuPDF
        "cv2",       # OpenCV
        "numpy",     # NumPy
        "paddleocr", # PaddleOCR
        "paddle",    # Paddle engine
        "pandas",    # pandas
        "tkinter",   # interface GUI
        "re",        # regex (stdlib)
        "unicodedata",
        "logging",
        "pathlib",
    ],
    # módulos Cython, hooks garantirão coleta de dados
    "includes": [],
    # pacotes que não usamos e podem ser excluídos
    "excludes": ["certifi", "zipextimporter", "unittest", "email", "http", "xml"],
    # garante que o Python embutido seja encontrado
    "path": [
        os.path.join(EMBED_ROOT, "Lib"),
        os.path.join(EMBED_ROOT, "Lib", "site-packages")
    ],
    # inclui arquivos externos necessários (Poppler)
    "include_files": [
        ("poppler-24.08.0", "poppler-24.08.0"),
        # se não usar Tesseract, remova-o daqui
    ],
    # inclui runtime Visual C++
    "include_msvcr": True,
}

setup(
    name="ExtratorFaturas",
    version="1.0",
    description="OCR de faturas com PaddleOCR",
    options={"build_exe": build_exe_options},
    executables=[Executable("main_processor.py", base=base)]
)
