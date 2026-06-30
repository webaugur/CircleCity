#!/usr/bin/env python3
"""Trigger Google Earth Save (Ctrl+S) so My Places flushes pin positions."""

from __future__ import annotations

import subprocess
import sys

WINDOW_QUERIES: tuple[tuple[str, ...], ...] = (
    ("search", "--class", "googleearth"),
    ("search", "--class", "Googleearth"),
    ("search", "--name", "Google Earth"),
    ("search", "--classname", "google-earth"),
)


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=False,
    )


def find_google_earth_window() -> str | None:
    if not _run(["which", "xdotool"]).returncode == 0:
        return None
    for query in WINDOW_QUERIES:
        result = _run(["xdotool", *query])
        if result.returncode != 0 or not result.stdout.strip():
            continue
        for wid in result.stdout.strip().splitlines():
            if wid.isdigit():
                return wid
    return None


def autosave_google_earth(*, quiet: bool = True) -> bool:
    """Send Ctrl+S to GE so ~/.googleearth/myplaces.kml picks up moved pins."""
    wid = find_google_earth_window()
    if wid is None:
        return False
    result = _run(["xdotool", "key", "--window", wid, "ctrl+s"])
    if result.returncode != 0:
        if not quiet:
            print(f"autosave failed: {result.stderr.strip()}", file=sys.stderr)
        return False
    return True