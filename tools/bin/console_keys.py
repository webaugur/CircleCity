#!/usr/bin/env python3
"""Non-blocking single-key input for the sync console."""

from __future__ import annotations

import queue
import sys
import threading


class KeyListener:
    def __init__(self) -> None:
        self._queue: queue.Queue[str] = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def poll(self) -> list[str]:
        keys: list[str] = []
        while True:
            try:
                keys.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return keys

    def _run(self) -> None:
        if not sys.stdin.isatty():
            return
        try:
            import select
            import termios
            import tty
        except ImportError:
            return

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while not self._stop.is_set():
                ready, _, _ = select.select([sys.stdin], [], [], 0.12)
                if not ready:
                    continue
                ch = sys.stdin.read(1)
                if ch:
                    self._queue.put(ch.lower())
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)