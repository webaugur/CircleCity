#!/usr/bin/env python3
"""Trigger Google Earth Save (Ctrl+S) so My Places flushes pin positions."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

WINDOW_QUERIES: tuple[tuple[str, ...], ...] = (
    ("search", "--class", "googleearth"),
    ("search", "--class", "Googleearth"),
    ("search", "--name", "Google Earth"),
    ("search", "--classname", "google-earth"),
)


def display_backend() -> str:
    return os.environ.get("XDG_SESSION_TYPE", "x11").strip().lower() or "x11"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=False,
    )


def _which(name: str) -> str | None:
    return shutil.which(name)


def find_google_earth_window() -> str | None:
    if _which("xdotool") is None:
        return None
    for query in WINDOW_QUERIES:
        result = _run(["xdotool", *query])
        if result.returncode != 0 or not result.stdout.strip():
            continue
        for wid in result.stdout.strip().splitlines():
            if wid.isdigit():
                return wid
    return None


def autosave_backend() -> str | None:
    """Return the tool name that will be used, or None if unavailable."""
    if display_backend() == "wayland":
        if _which("wtype"):
            return "wtype"
        if _which("ydotool"):
            return "ydotool"
        return None
    if _which("xdotool"):
        return "xdotool"
    return None


def autosave_google_earth(*, quiet: bool = True) -> bool:
    """Send Ctrl+S so ~/.googleearth/myplaces.kml picks up moved pins."""
    backend = display_backend()
    if backend == "wayland":
        return _autosave_wayland(quiet=quiet)
    return _autosave_x11(quiet=quiet)


def _autosave_wayland(*, quiet: bool) -> bool:
    """Wayland: wtype targets the focused window; ydotool uses uinput globally."""
    wtype = _which("wtype")
    if wtype:
        # GE should be focused while dragging pins; wtype sends Ctrl+S there.
        result = _run([wtype, "-M", "ctrl", "-k", "s", "-p", "s"])
        if result.returncode == 0:
            return True
        if not quiet:
            print(f"wtype autosave failed: {result.stderr.strip()}", file=sys.stderr)

    ydotool = _which("ydotool")
    if ydotool:
        # 29=left ctrl, 31=s (linux input codes)
        result = _run([ydotool, "key", "29:1", "31:1", "31:0", "29:0"])
        if result.returncode == 0:
            return True
        if not quiet:
            print(f"ydotool autosave failed: {result.stderr.strip()}", file=sys.stderr)

    return False


def _autosave_x11(*, quiet: bool) -> bool:
    wid = find_google_earth_window()
    if wid is None:
        return False
    result = _run(["xdotool", "key", "--window", wid, "ctrl+s"])
    if result.returncode != 0:
        if not quiet:
            print(f"xdotool autosave failed: {result.stderr.strip()}", file=sys.stderr)
        return False
    return True


def autosave_help() -> str:
    backend = display_backend()
    if backend == "wayland":
        return (
            "Wayland session — install wtype: sudo apt install wtype\n"
            "  (keep Google Earth focused while dragging; wtype sends Ctrl+S to focused app)\n"
            "  Or: ydotool + ydotoold for global keys; or use --no-auto-save and Save manually"
        )
    return "X11 session — requires xdotool"