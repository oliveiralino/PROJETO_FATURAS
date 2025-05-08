# hooks/hook-paddle.py
from PyInstaller.utils.hooks import collect_all

# Vai recolher: 
#  - todos os módulos Python (pure e binary) de paddle
#  - toda a pasta paddle/libs com as DLLs (mklml.dll, etc.)
datas, binaries, hiddenimports = collect_all('paddle')
