import os
from pathlib import Path
import sys


def data_directory():
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/delphi"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share").expanduser().resolve() / "delphi"


def model_directory():
    return data_directory() / "models/all-MiniLM-L6-v2"


def index_root():
    return Path(os.environ.get("DELPHI_INDEX_ROOT") or data_directory() / "indexes").expanduser().resolve()

