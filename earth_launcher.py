#!/usr/bin/env python3
"""Detect Google Earth Pro and open the CircleCity network-link KML."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

EARTH_PROCESS_NAMES = ("googleearth-bin", "Google Earth")
EARTH_CANDIDATES = (
    Path("/usr/bin/google-earth-pro"),
    Path("/opt/google/earth/pro/google-earth-pro"),
)


def find_google_earth() -> Path | None:
    for candidate in EARTH_CANDIDATES:
        if candidate.is_file():
            return candidate
    found = shutil.which("google-earth-pro")
    return Path(found) if found else None


def is_google_earth_running() -> bool:
    if sys.platform == "darwin":
        script = 'application processes whose name contains "Google Earth"'
        try:
            result = subprocess.run(
                ["osascript", "-e", f'count {script}'],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0 and result.stdout.strip() not in {"", "0"}
        except FileNotFoundError:
            return False

    if sys.platform == "win32":
        try:
            result = subprocess.run(
                [
                    "tasklist",
                    "/FI",
                    "IMAGENAME eq googleearth.exe",
                    "/NH",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            return "googleearth.exe" in result.stdout.lower()
        except FileNotFoundError:
            return False

    for name in EARTH_PROCESS_NAMES:
        try:
            if subprocess.run(["pgrep", "-x", name], capture_output=True).returncode == 0:
                return True
        except FileNotFoundError:
            break
    try:
        return (
            subprocess.run(
                ["pgrep", "-f", r"googleearth-bin|google-earth-pro"],
                capture_output=True,
            ).returncode
            == 0
        )
    except FileNotFoundError:
        return False


def _run_earth(earth_bin: Path, kml_path: Path, *, background: bool) -> None:
    cmd = [str(earth_bin), str(kml_path)]
    env = os.environ.copy()
    if background:
        subprocess.Popen(
            cmd,
            env=env,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    subprocess.run(cmd, env=env, check=False)


def ensure_google_earth(kml_path: Path, *, startup_wait_s: float = 2.0) -> str:
    """Start Google Earth or open *kml_path* in the running instance."""
    kml_path = kml_path.resolve()
    if not kml_path.is_file():
        raise FileNotFoundError(f"KML not found: {kml_path}")

    earth_bin = find_google_earth()
    if earth_bin is None:
        raise RuntimeError(
            "Google Earth Pro not found. Install it or open "
            f"{kml_path} manually, then re-run sync."
        )

    if is_google_earth_running():
        _run_earth(earth_bin, kml_path, background=False)
        return f"Opened {kml_path.name} in running Google Earth Pro"

    _run_earth(earth_bin, kml_path, background=True)
    if startup_wait_s > 0:
        time.sleep(startup_wait_s)
    return f"Started Google Earth Pro with {kml_path.name}"