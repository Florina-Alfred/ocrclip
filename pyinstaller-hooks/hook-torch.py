# PyInstaller hook for torch: collect dynamic libs and submodules
from PyInstaller.utils.hooks import (
    collect_dynamic_libs,
    collect_submodules,
    collect_data_files,
)

binaries = collect_dynamic_libs("torch")
hiddenimports = collect_submodules("torch")
datas = collect_data_files("torch")
