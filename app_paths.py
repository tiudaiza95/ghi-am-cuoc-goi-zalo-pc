"""Keep runtime data beside the application, including source-based runs."""
from pathlib import Path
import sys


def app_root():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    here = Path(__file__).resolve().parent
    return here.parent if here.name.casefold() == 'source' else here


def resolve_recording_folder(value):
    path = Path(value)
    return path if path.is_absolute() else app_root() / path


def stored_recording_folder(value):
    path = Path(value).resolve()
    try:
        return str(path.relative_to(app_root()))
    except ValueError:
        return str(path)
