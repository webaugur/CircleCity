#!/usr/bin/env python3
"""Import station anchor positions from Google Earth myplaces.kml."""

from __future__ import annotations

import re
import shutil
import time
import xml.etree.ElementTree as ET
from pathlib import Path

KML_NS = "http://www.opengis.net/kml/2.2"
NS = f"{{{KML_NS}}}"

MYPLACES_PATH = Path.home() / ".googleearth" / "myplaces.kml"
MYPLACES_SAVED_NAME = "myplaces_saved.kml"
ZERO_POINT_CODE = "ZeroPoint"


def save_myplaces_copy(dest: Path) -> Path | None:
    """Archive ~/.googleearth/myplaces.kml to dest (GE writes this on Save and on exit)."""
    if not MYPLACES_PATH.is_file():
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MYPLACES_PATH, dest)
    return dest


def wait_for_myplaces_flush(since_mtime: float, timeout_s: float = 4.0) -> float:
    """After GE exits it may flush myplaces.kml; wait for mtime to settle."""
    deadline = time.monotonic() + timeout_s
    latest = since_mtime
    while time.monotonic() < deadline:
        if MYPLACES_PATH.is_file():
            latest = max(latest, MYPLACES_PATH.stat().st_mtime)
            if latest > since_mtime:
                time.sleep(0.4)
                if MYPLACES_PATH.is_file():
                    return MYPLACES_PATH.stat().st_mtime
        time.sleep(0.2)
    return latest


def _placemark_coord(pm: ET.Element) -> tuple[float, float] | None:
    coord_el = pm.find(f".//{NS}coordinates")
    if coord_el is None:
        coord_el = pm.find(".//{*}coordinates")
    if coord_el is None or not coord_el.text:
        return None
    lon, lat, *_ = coord_el.text.strip().split(",")
    return float(lat), float(lon)


def _code_from_name(name: str) -> str | None:
    m = re.match(r"IU/(\w+)", name)
    if m:
        return m.group(1)
    if name == ZERO_POINT_CODE or name.startswith(ZERO_POINT_CODE):
        return ZERO_POINT_CODE
    return None


def read_myplaces_anchors(path: Path = MYPLACES_PATH) -> dict[str, tuple[float, float]]:
    """Return {station_code: (lat, lon)} from every Stations/Reference Points placemark."""
    if not path.is_file():
        return {}

    root = ET.parse(path).getroot()
    positions: dict[str, tuple[float, float]] = {}

    for folder in root.iter(NS + "Folder"):
        name_el = folder.find(f"{NS}name")
        if name_el is None:
            name_el = folder.find("{*}name")
        if name_el is None:
            continue
        folder_name = name_el.text or ""

        if folder_name == "Stations":
            for pm in folder.findall(f"{NS}Placemark"):
                pm_name = pm.find(f"{NS}name")
                if pm_name is None:
                    pm_name = pm.find("{*}name")
                if pm_name is None:
                    continue
                code = _code_from_name(pm_name.text or "")
                if not code:
                    continue
                coord = _placemark_coord(pm)
                if coord:
                    positions[code] = coord

        if folder_name == "Reference Points":
            for pm in folder.findall(f"{NS}Placemark"):
                pm_name = pm.find(f"{NS}name")
                if pm_name is None:
                    pm_name = pm.find("{*}name")
                if pm_name is None or (pm_name.text or "") != ZERO_POINT_CODE:
                    continue
                coord = _placemark_coord(pm)
                if coord:
                    positions[ZERO_POINT_CODE] = coord

    return positions


def apply_positions_to_document(
    doc: ET.Element,
    positions: dict[str, tuple[float, float]],
    *,
    eps: float = 1e-9,
) -> set[str]:
    """Write imported positions into the served KML Document; return changed codes."""
    from kml_sync import (
        NS,
        ZERO_POINT_CODE,
        find_folder,
        placemark_code,
        set_extended_data,
    )

    changed: set[str] = set()

    stations_folder = find_folder(doc, "Stations")
    if stations_folder is not None:
        for pm in stations_folder.findall(f"{NS}Placemark"):
            name_el = pm.find(f"{NS}name")
            if name_el is None:
                continue
            code = placemark_code(pm, name_el.text or "")
            if code not in positions:
                continue
            lat, lon = positions[code]
            coord_el = pm.find(f".//{NS}coordinates")
            if coord_el is None:
                continue
            parts = coord_el.text.strip().split(",")
            alt = parts[2] if len(parts) > 2 else "0"
            old_lat, old_lon, _ = (float(parts[1]), float(parts[0]), alt)
            if abs(old_lat - lat) > eps or abs(old_lon - lon) > eps:
                coord_el.text = f"{lon:.8f},{lat:.8f},{alt}"
                set_extended_data(pm, "station_code", code)
                changed.add(code)

    ref_folder = find_folder(doc, "Reference Points")
    if ref_folder is not None and ZERO_POINT_CODE in positions:
        for pm in ref_folder.findall(f"{NS}Placemark"):
            name_el = pm.find(f"{NS}name")
            if name_el is None or (name_el.text or "") != ZERO_POINT_CODE:
                continue
            lat, lon = positions[ZERO_POINT_CODE]
            coord_el = pm.find(f".//{NS}coordinates")
            if coord_el is None:
                continue
            parts = coord_el.text.strip().split(",")
            alt = parts[2] if len(parts) > 2 else "0"
            old_lat, old_lon = float(parts[1]), float(parts[0])
            if abs(old_lat - lat) > eps or abs(old_lon - lon) > eps:
                coord_el.text = f"{lon:.8f},{lat:.8f},{alt}"
                changed.add(ZERO_POINT_CODE)

    return changed