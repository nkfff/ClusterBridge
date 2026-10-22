from __future__ import annotations

import traceback
from datetime import datetime
from pathlib import Path

LOG_DIR = Path.home() / ".clusterbridge" / "logs"
LOG_FILE = LOG_DIR / "startup.log"


def _append_startup_log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"[{datetime.now().isoformat()}] {message}\n")


def _show_fallback_error(message: str) -> None:
    try:
        import tkinter
        from tkinter import messagebox

        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror("ClusterBridge startup failed", message)
        root.destroy()
        return
    except Exception:
        pass

    print(message)


def run() -> None:
    try:
        from .ui import main as ui_main

        ui_main()
    except Exception:
        details = traceback.format_exc()
        _append_startup_log(details)
        _show_fallback_error(
            "ClusterBridge failed to start.\n"
            f"Details were written to:\n{LOG_FILE}"
        )
