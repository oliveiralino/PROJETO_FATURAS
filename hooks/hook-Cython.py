# hooks/hook-Cython.py
from PyInstaller.utils.hooks import collect_data_files

# coleta todos os arquivos (incluindo .c) do pacote Cython
datas = collect_data_files('Cython')