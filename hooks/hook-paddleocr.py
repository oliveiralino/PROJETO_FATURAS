# hooks/hook-paddleocr.py
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# coleta todos os sub‑módulos de paddleocr (inclui paddleocr.tools)
hiddenimports = collect_submodules('paddleocr')

# coleta todos os arquivos de dados (scripts .py, recursos) do paddleocr
datas = collect_data_files('paddleocr', include_py_files=True)