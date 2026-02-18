# PyInstaller hook for easyocr: collect submodules and data files
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = collect_submodules("easyocr")
datas = collect_data_files("easyocr")
