#!/usr/bin/env python3
"""Detect Google Earth Pro by PID; launch once; open KML/URL via single-instance protocol."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    import fcntl
except ImportError:
    fcntl = None  # type: ignore[assignment]

EARTH_BIN_COMM = "googleearth-bin"
EARTH_CANDIDATES = (
    Path("/usr/bin/google-earth-pro"),
    Path("/opt/google/earth/pro/google-earth-pro"),
)
STARTUP_TIMEOUT_S = 45.0
STARTUP_POLL_S = 0.5
LOCK_NAME = ".earth_launch.lock"


def find_google_earth() -> Path | None:
    for candidate in EARTH_CANDIDATES:
        if candidate.is_file():
            return candidate
    found = shutil.which("google-earth-pro")
    return Path(found) if found else None


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True,
                text=True,
                check=False,
            )
            return str(pid) in result.stdout
        except FileNotFoundError:
            return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    if sys.platform == "darwin":
        return True
    stat_path = Path(f"/proc/{pid}/stat")
    if not stat_path.exists():
        return False
    return stat_path.read_text().split()[2] != "Z"


def _pids_for_comm(comm: str) -> list[int]:
    try:
        result = subprocess.run(
            ["pgrep", "-x", comm],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return []
    if result.returncode != 0:
        return []
    return sorted(
        int(line)
        for line in result.stdout.splitlines()
        if line.strip().isdigit() and _pid_alive(int(line.strip()))
    )


def google_earth_pids() -> list[int]:
    if sys.platform == "darwin":
        return []
    if sys.platform == "win32":
        return []
    return _pids_for_comm(EARTH_BIN_COMM)


def is_google_earth_running() -> bool:
    return bool(google_earth_pids())


def ge_opened_targets() -> list[str]:
    """KML paths or URLs on the googleearth-bin command line."""
    targets: list[str] = []
    for pid in google_earth_pids():
        if sys.platform not in ("linux", "linux2"):
            continue
        try:
            raw = Path(f"/proc/{pid}/cmdline").read_bytes()
        except OSError:
            continue
        for part in raw.split(b"\0"):
            if not part:
                continue
            text = part.decode(errors="replace")
            if text.startswith("http://") or text.startswith("https://"):
                targets.append(text)
            elif text.endswith(".kml") or text.endswith(".kmz"):
                targets.append(str(Path(text).resolve()))
    return targets


def _target_is_open(target: str, opened: list[str]) -> bool:
    norm = target.rstrip("/")
    for item in opened:
        if item.rstrip("/") == norm:
            return True
        if norm in item or item in norm:
            return True
    return False


def _wait_for_earth_bin(timeout_s: float = STARTUP_TIMEOUT_S) -> list[int]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        pids = google_earth_pids()
        if pids:
            return pids
        time.sleep(STARTUP_POLL_S)
    return []


class _LaunchLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a+", encoding="utf-8")
        if fcntl is None:
            return True
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            self._fh.close()
            self._fh = None
            return False

    def release(self) -> None:
        if self._fh is None:
            return
        if fcntl is not None:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        self._fh.close()
        self._fh = None


def _open_nonblocking(earth_bin: Path, target: str) -> int:
    proc = subprocess.Popen(
        [str(earth_bin), target],
        env=os.environ.copy(),
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.pid


def ensure_google_earth(
    open_target: str | Path,
    *,
    lock_dir: Path | None = None,
    startup_wait_s: float = STARTUP_TIMEOUT_S,
) -> str:
    """Open a KML path or http:// NetworkLink URL in Google Earth (single instance)."""
    target = str(open_target)
    if not target.startswith("http://") and not target.startswith("https://"):
        path = Path(target).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"KML not found: {path}")
        target = str(path)

    earth_bin = find_google_earth()
    if earth_bin is None:
        raise RuntimeError(
            "Google Earth Pro not found. Install it or open "
            f"{target} manually, then re-run sync."
        )

    opened = ge_opened_targets()
    running = google_earth_pids()

    if running:
        pid_text = ", ".join(str(pid) for pid in running)
        if _target_is_open(target, opened):
            return f"Google Earth Pro (PID {pid_text}) already has {target}"
        _open_nonblocking(earth_bin, target)
        return f"Google Earth Pro (PID {pid_text}): opened {target}"

    lock_path = (lock_dir or Path.home()) / LOCK_NAME
    lock = _LaunchLock(lock_path)
    if not lock.acquire():
        pids = _wait_for_earth_bin(timeout_s=startup_wait_s)
        if pids:
            return ensure_google_earth(open_target, lock_dir=lock_dir, startup_wait_s=startup_wait_s)
        return "Google Earth Pro launch already in progress; not starting another instance."

    try:
        if google_earth_pids():
            return ensure_google_earth(open_target, lock_dir=lock_dir, startup_wait_s=startup_wait_s)

        wrapper_pid = _open_nonblocking(earth_bin, target)
        pids = _wait_for_earth_bin(timeout_s=startup_wait_s)
        if pids:
            return (
                f"Started Google Earth Pro (PID {', '.join(str(p) for p in pids)}, "
                f"wrapper {wrapper_pid}) with {target}"
            )
        return (
            f"Launched Google Earth wrapper (PID {wrapper_pid}) with {target}; "
            "googleearth-bin not detected yet."
        )
    finally:
        lock.release()