"""Custom PyInstaller hook for VisPy.

Ensures all GLSL shaders and the PyQt6 backend module are included.
PyInstaller's built-in vispy hook may miss the backend selector when
vispy.use('PyQt6') is called at import time in globe_3d.py.
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files('vispy')

hiddenimports = (
    collect_submodules('vispy.app.backends')
    + collect_submodules('vispy.visuals')
    + collect_submodules('vispy.scene')
    + ['vispy.app.backends._pyqt6']
)
