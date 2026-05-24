"""Root Streamlit entrypoint for Streamlit Cloud and local runs.

Cannot use `from app.streamlit_app import *`: Python's module cache would
prevent Streamlit from re-executing the UI rendering code on every rerun,
causing the dashboard and chat to appear frozen after first load.

Run from project root:
    python -m streamlit run streamlit_app.py
"""
from __future__ import annotations

from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_app_file = _ROOT / "app" / "streamlit_app.py"
exec(compile(_app_file.read_text(), str(_app_file), "exec"))  # noqa: S102
