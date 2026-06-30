#!/usr/bin/env python3
"""React immediately when Google Earth writes myplaces.kml."""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from typing import Callable

from myplaces_import import MYPLACES_PATH


class MyplacesNotifier:
    def __init__(self, on_change: Callable[[], None], directory: Path | None = None) -> None:
        self._on_change = on_change
        self._directory = directory or MYPLACES_PATH.parent
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._proc: subprocess.Popen[str] | None = None

    def start(self) -> bool:
        if self._thread is not None:
            return True
        if subprocess.run(["which", "inotifywait"], capture_output=True).returncode != 0:
            return False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()

    def _run(self) -> None:
        patterns = ("myplaces.kml", "myplaces.backup.kml")
        args = [
            "inotifywait",
            "-m",
            "-e",
            "close_write,move,create",
            str(self._directory),
        ]
        try:
            self._proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except OSError:
            return
        if self._proc.stdout is None:
            return
        for line in self._proc.stdout:
            if self._stop.is_set():
                break
            if not any(p in line for p in patterns):
                continue
            self._on_change()