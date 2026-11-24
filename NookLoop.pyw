import subprocess
import ctypes
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = ROOT / ".venv" / "Scripts" / "pythonw.exe"

if PYTHON.exists():
    subprocess.Popen(
        [str(PYTHON), str(ROOT / "main.py")],
        cwd=ROOT
    )
else:
    ctypes.windll.user32.MessageBoxW(
        None,
        "找不到 Python 虛擬環境，請先建立 .venv。",
        "Nook Loop",
        0x10
    )
