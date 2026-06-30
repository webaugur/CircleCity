#!/usr/bin/env python3
"""Detect Google Earth Pro by PID and launch at most one instance."""

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
EARTH_WRAPPER_COMM = "google-earth-pro"
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
    # Third field in stat is process state; Z = zombie.
    return stat_path.read_text().split()[2] != "Z"


def _pids_for_comm(comm: str) -> list[int]:
    if sys.platform == "darwin":
        return []
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
    pids: list[int] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line.isdigit():
            continue
        pid = int(line)
        if _pid_alive(pid):
            pids.append(pid)
    return sorted(pids)


def google_earth_pids() -> list[int]:
    """Live googleearth-bin PIDs (the real Google Earth process)."""
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                [
                    "osascript",
                    "-e",
                    'tell application "System Events" to get the unix id of '
                    'every process whose name contains "Google Earth"',
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return []
            return sorted(
                int(pid)
                for pid in result.stdout.replace(",", " ").split()
                if pid.strip().isdigit() and _pid_alive(int(pid))
            )
        except FileNotFoundError:
            return []

    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq googleearth.exe", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False,
            )
            pids: list[int] = []
            for line in result.stdout.splitlines():
                parts = [p.strip('"') for p in line.split(",")]
                if len(parts) >= 2 and parts[0].lower() == "googleearth.exe" and parts[1].isdigit():
                    pid = int(parts[1])
                    if _pid_alive(pid):
                        pids.append(pid)
            return sorted(pids)
        except FileNotFoundError:
            return []

    return _pids_for_comm(EARTH_BIN_COMM)


def is_google_earth_running() -> bool:
    return bool(google_earth_pids())


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


def _spawn_earth(earth_bin: Path, kml_path: Path) -> int:
    proc = subprocess.Popen(
        [str(earth_bin), str(kml_path)],
        env=os.environ.copy(),
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.pid


def ensure_google_earth(kml_path: Path, *, startup_wait_s: float = STARTUP_TIMEOUT_S) -> str:
    """Launch Google Earth once when no live instance exists; never spawn a second."""
    kml_path = kml_path.resolve()
    if not kml_path.is_file():
        raise FileNotFoundError(f"KML not found: {kml_path}")

    earth_bin = find_google_earth()
    if earth_bin is None:
        raise RuntimeError(
            "Google Earth Pro not found. Install it or open "
            f"{kml_path} manually, then re-run sync."
        )

    running = google_earth_pids()
    if running:
        pid_text = ", ".join(str(pid) for pid in running)
        return (
            f"Google Earth Pro already running (PID {pid_text}); "
            f"not launching again. Ensure {kml_path.name} is loaded in that window."
        )

    lock = _LaunchLock(kml_path.parent / LOCK_NAME)
    if not lock.acquire():
        pids = _wait_for_earth_bin(timeout_s=startup_wait_s)
        if pids:
            return (
                f"Google Earth Pro started by another sync (PID "
                f"{', '.join(str(p) for p in pids)}); not launching again."
            )
        return "Google Earth Pro launch already in progress; not starting another instance."

    try:
        running = google_earth_pids()
        if running:
            pid_text = ", ".join(str(pid) for pid in running)
            return (
                f"Google Earth Pro already running (PID {pid_text}); "
                f"not launching again."
            )

        wrapper_pid = _spawn_earth(earth_bin, kml_path)
        pids = _wait_for_earth_bin(timeout_s=startup_wait_s)
        if pids:
            return (
                f"Started Google Earth Pro (PID {', '.join(str(p) for p in pids)}, "
                f"wrapper {wrapper_pid}) with {kml_path.name}"
            )
        return (
            f"Launched Google Earth wrapper (PID {wrapper_pid}) with {kml_path.name}; "
            "googleearth-bin not detected yet — check Google Earth manually."
        )
    finally:
        lock.release()