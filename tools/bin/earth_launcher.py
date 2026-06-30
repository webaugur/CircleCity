#!/usr/bin/env python3
"""Detect Google Earth Pro by PID; launch once; open KML via single-instance protocol."""

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


def ge_opened_paths() -> list[Path]:
    """KML paths passed on the googleearth-bin command line (from /proc/PID/cmdline)."""
    paths: list[Path] = []
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
            if text.endswith(".kml") or text.endswith(".kmz"):
                paths.append(Path(text).resolve())
    return paths


def _path_is_open(target: Path, opened: list[Path]) -> bool:
    resolved = target.resolve()
    return any(p == resolved for p in opened)


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


def _open_kml_nonblocking(earth_bin: Path, kml_path: Path) -> int:
    """Hand a KML to the single-instance Google Earth process (does not wait)."""
    proc = subprocess.Popen(
        [str(earth_bin), str(kml_path.resolve())],
        env=os.environ.copy(),
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.pid


def _spawn_earth(earth_bin: Path, kml_path: Path) -> int:
    return _open_kml_nonblocking(earth_bin, kml_path)


def ensure_google_earth(
    link_kml: Path,
    edit_kml: Path | None = None,
    *,
    startup_wait_s: float = STARTUP_TIMEOUT_S,
) -> str:
    """Start GE once, open the editable KML, and register the NetworkLink for reload."""
    link_kml = link_kml.resolve()
    edit_kml = (edit_kml or link_kml).resolve()
    if not link_kml.is_file():
        raise FileNotFoundError(f"NetworkLink KML not found: {link_kml}")
    if not edit_kml.is_file():
        raise FileNotFoundError(f"Editable KML not found: {edit_kml}")

    earth_bin = find_google_earth()
    if earth_bin is None:
        raise RuntimeError(
            "Google Earth Pro not found. Install it or open "
            f"{edit_kml} manually, then re-run sync."
        )

    opened = ge_opened_paths()
    edit_open = _path_is_open(edit_kml, opened)
    link_open = _path_is_open(link_kml, opened)
    running = google_earth_pids()

    if running:
        actions: list[str] = []
        if not edit_open:
            _open_kml_nonblocking(earth_bin, edit_kml)
            actions.append(f"opened editable {edit_kml.name}")
        if not link_open:
            _open_kml_nonblocking(earth_bin, link_kml)
            actions.append(f"registered NetworkLink {link_kml.name}")
        pid_text = ", ".join(str(pid) for pid in running)
        if not actions:
            return (
                f"Google Earth Pro (PID {pid_text}) already has "
                f"{edit_kml.name} and NetworkLink {link_kml.name}"
            )
        return f"Google Earth Pro (PID {pid_text}): {'; '.join(actions)}"

    lock = _LaunchLock(link_kml.parent / LOCK_NAME)
    if not lock.acquire():
        pids = _wait_for_earth_bin(timeout_s=startup_wait_s)
        if pids:
            return ensure_google_earth(link_kml, edit_kml, startup_wait_s=startup_wait_s)
        return "Google Earth Pro launch already in progress; not starting another instance."

    try:
        if google_earth_pids():
            return ensure_google_earth(link_kml, edit_kml, startup_wait_s=startup_wait_s)

        wrapper_pid = _spawn_earth(earth_bin, edit_kml)
        pids = _wait_for_earth_bin(timeout_s=startup_wait_s)
        if not pids:
            return (
                f"Launched Google Earth wrapper (PID {wrapper_pid}) with {edit_kml.name}; "
                "googleearth-bin not detected yet."
            )

        time.sleep(0.5)
        _open_kml_nonblocking(earth_bin, link_kml)
        return (
            f"Started Google Earth Pro (PID {', '.join(str(p) for p in pids)}) "
            f"with {edit_kml.name} + NetworkLink {link_kml.name}"
        )
    finally:
        lock.release()