#!/usr/bin/env python3
"""Keep station-attached KML geometry in sync when Stations layer points move."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from pathlib import Path

import xml.etree.ElementTree as ET

KML_NS = "http://www.opengis.net/kml/2.2"
NS = f"{{{KML_NS}}}"

BIN_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BIN_DIR.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
KML_PATH = DATA_DIR / "seismic_network.kml"
LINK_KML_PATH = DATA_DIR / "seismic_network_link.kml"
CACHE_PATH = DATA_DIR / ".station_positions.json"

LINE_ALT_M = 100000
CIRCLE_RADIUS_M = 33966
CIRCLE_ALT_M = 100000
ARC_POINTS = 65
EARTH_R = 6371000.0

ZERO_POINT_CODE = "ZeroPoint"
INTERNAL_SOURCES = {ZERO_POINT_CODE}

RAINBOW_RINGS = [
    (150, "red", "rainbowRed", "ff0000ff", 3),
    (99, "orange", "rainbowOrange", "ff007fff", 3),
    (66, "yellow", "rainbowYellow", "ff00ffff", 2),
    (42, "green", "rainbowGreen", "ff00ff00", 2),
    (33, "blue", "rainbowBlue", "ffff0000", 2),
    (13, "violet", "rainbowViolet", "ffff008f", 2),
]
RAINBOW_GROUND_ALT = 0

DEFAULT_SERVER_PORT = 8765


def txt(parent: ET.Element, tag: str, value: str) -> ET.Element:
    el = ET.SubElement(parent, tag)
    el.text = value
    return el


def parse_coord(text: str) -> tuple[float, float, float]:
    lon, lat, alt = text.strip().split(",")
    return float(lat), float(lon), float(alt)


def extended_data(pm: ET.Element) -> dict[str, str]:
    out: dict[str, str] = {}
    for data in pm.findall(f"{NS}ExtendedData/{NS}Data"):
        key = data.get("name")
        val = data.find(f"{NS}value")
        if key and val is not None and val.text:
            out[key] = val.text
    return out


def set_extended_data(pm: ET.Element, key: str, value: str) -> None:
    ext = pm.find(f"{NS}ExtendedData")
    if ext is None:
        ext = ET.SubElement(pm, f"{NS}ExtendedData")
    for data in ext.findall(f"{NS}Data"):
        if data.get("name") == key:
            val = data.find(f"{NS}value")
            if val is None:
                val = ET.SubElement(data, f"{NS}value")
            val.text = value
            return
    data = ET.SubElement(ext, f"{NS}Data", name=key)
    txt(data, f"{NS}value", value)


def placemark_code(pm: ET.Element, name_text: str) -> str:
    meta = extended_data(pm)
    if "station_code" in meta:
        return meta["station_code"]
    m = re.match(r"IU/(\w+)", name_text)
    if m:
        return m.group(1)
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name_text).strip("_")[:48]
    return slug or "site"


def station_code_from_name(name: str) -> str | None:
    m = re.match(r"IU/(\w+)", name)
    if m:
        return m.group(1)
    if name == ZERO_POINT_CODE or name.startswith(ZERO_POINT_CODE):
        return ZERO_POINT_CODE
    return None


def anchor_from_placemark(pm: ET.Element) -> dict | None:
    name_el = pm.find(f"{NS}name")
    coord_el = pm.find(f".//{NS}coordinates")
    if name_el is None or coord_el is None or not coord_el.text:
        return None
    name = name_el.text or ""
    lat, lon, _ = parse_coord(coord_el.text)
    code = placemark_code(pm, name)
    set_extended_data(pm, "station_code", code)
    return {
        "code": code,
        "name": name,
        "lat": lat,
        "lon": lon,
        "placemark": pm,
        "internal": code in INTERNAL_SOURCES,
    }


def parse_line_endpoints(name: str) -> tuple[str, str] | None:
    if "→" not in name:
        return None
    left, right = name.split("→", 1)
    a = left.strip().split()[-1]
    if right.strip().startswith(ZERO_POINT_CODE):
        return a, ZERO_POINT_CODE
    b = right.strip().split(" ")[0]
    return a, b


def destination(lat: float, lon: float, bearing_deg: float, dist_m: float) -> tuple[float, float]:
    br = math.radians(bearing_deg)
    lat1, lon1 = math.radians(lat), math.radians(lon)
    ang = dist_m / EARTH_R
    lat2 = math.asin(
        math.sin(lat1) * math.cos(ang)
        + math.cos(lat1) * math.sin(ang) * math.cos(br)
    )
    lon2 = lon1 + math.atan2(
        math.sin(br) * math.sin(ang) * math.cos(lat1),
        math.cos(ang) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lat2), math.degrees(lon2)


def circle_ring(lat: float, lon: float, radius_m: float, alt: float, n: int = 64) -> str:
    pts = [destination(lat, lon, i * 360 / n, radius_m) for i in range(n)]
    pts.append(pts[0])
    return " ".join(f"{lo:.8f},{la:.8f},{alt:.0f}" for la, lo in pts)


def latlon_to_vec(lat: float, lon: float) -> tuple[float, float, float]:
    lr, ln = math.radians(lat), math.radians(lon)
    return (
        math.cos(lr) * math.cos(ln),
        math.cos(lr) * math.sin(ln),
        math.sin(lr),
    )


def vec_to_latlon(x: float, y: float, z: float) -> tuple[float, float]:
    return math.degrees(math.asin(max(-1.0, min(1.0, z)))), math.degrees(math.atan2(y, x))


def great_circle(lat1: float, lon1: float, lat2: float, lon2: float, alt: float) -> str:
    v1 = latlon_to_vec(lat1, lon1)
    v2 = latlon_to_vec(lat2, lon2)
    dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(v1, v2))))
    omega = math.acos(dot)
    if omega < 1e-12:
        pts = [(lat1, lon1), (lat2, lon2)]
    else:
        sw = math.sin(omega)
        pts = []
        for i in range(ARC_POINTS):
            f = i / (ARC_POINTS - 1)
            a = math.sin((1 - f) * omega) / sw
            b = math.sin(f * omega) / sw
            x = a * v1[0] + b * v2[0]
            y = a * v1[1] + b * v2[1]
            z = a * v1[2] + b * v2[2]
            m = math.sqrt(x * x + y * y + z * z)
            pts.append(vec_to_latlon(x / m, y / m, z / m))
    return " ".join(f"{lon:.6f},{lat:.6f},{alt:.0f}" for lat, lon in pts)


def find_folder(doc: ET.Element, folder_name: str) -> ET.Element | None:
    for folder in doc.findall(f"{NS}Folder"):
        name = folder.find(f"{NS}name")
        if name is not None and name.text == folder_name:
            return folder
    return None


def read_stations_layer(doc: ET.Element) -> dict[str, dict]:
    folder = find_folder(doc, "Stations")
    if folder is None:
        raise RuntimeError("Stations folder not found")

    stations: dict[str, dict] = {}
    for pm in folder.findall(f"{NS}Placemark"):
        anchor = anchor_from_placemark(pm)
        if anchor is None:
            continue
        stations[anchor["code"]] = anchor
    return stations


def read_zeropoint(doc: ET.Element) -> dict | None:
    folder = find_folder(doc, "Reference Points")
    if folder is None:
        return None
    for pm in folder.findall(f"{NS}Placemark"):
        name_el = pm.find(f"{NS}name")
        if name_el is None or (name_el.text or "") != ZERO_POINT_CODE:
            continue
        anchor = anchor_from_placemark(pm)
        if anchor is None:
            return None
        anchor["internal"] = True
        return anchor
    return None


def read_anchors(doc: ET.Element) -> dict[str, dict]:
    """All attachment anchors: every Stations placemark + internal ZeroPoint."""
    anchors = dict(read_stations_layer(doc))
    zp = read_zeropoint(doc)
    if zp:
        anchors[ZERO_POINT_CODE] = zp
    return anchors


def read_rainbow_targets(doc: ET.Element) -> dict[str, dict]:
    """Stations layer placemarks + ZeroPoint (internal, rainbow only)."""
    return read_anchors(doc)


def station_pos(anchors: dict[str, dict], code: str) -> tuple[float, float]:
    if code not in anchors:
        raise KeyError(f"Unknown anchor code: {code}")
    a = anchors[code]
    return a["lat"], a["lon"]


def update_station_description(pm: ET.Element, lat: float, lon: float, code: str) -> None:
    desc = pm.find(f"{NS}description")
    if desc is None:
        desc = ET.SubElement(pm, f"{NS}description")
    if code == "RSSD":
        desc.text = "Center point (SD station)"
    elif code == ZERO_POINT_CODE:
        desc.text = f"Internal reference — {lat}, {lon}"
    else:
        desc.text = f"Lat: {lat}, Lon: {lon}"


def update_circle(pm: ET.Element, lat: float, lon: float, alt: float, radius_m: float) -> None:
    ring = pm.find(f".//{NS}LinearRing/{NS}coordinates")
    if ring is None:
        return
    ring.text = circle_ring(lat, lon, radius_m, alt)


def attachment_code_from_name(name: str, stations: dict[str, dict]) -> str | None:
    meta_match = re.search(r"\b([A-Z0-9_]+)\b", name)
    if name.endswith(" circle"):
        prefix = name[:-7]
        m = re.match(r"IU/(\w+)", prefix)
        if m:
            return m.group(1)
        for code, s in stations.items():
            if s["name"] == prefix or prefix in s["name"]:
                return code
    code = station_code_from_name(name)
    if code and code in stations:
        return code
    for code, s in stations.items():
        if s["name"] in name:
            return code
    return None


def rainbow_ring_placemark(
    code: str, diameter_m: int, color_name: str, style_id: str, lat: float, lon: float
) -> ET.Element:
    pm = ET.Element(f"{NS}Placemark")
    txt(pm, f"{NS}name", f"{diameter_m} m {color_name}")
    txt(pm, f"{NS}description", f"{diameter_m} m diameter {color_name} ring")
    txt(pm, f"{NS}styleUrl", f"#{style_id}")
    set_extended_data(pm, "station_code", code)
    set_extended_data(pm, "diameter_m", str(diameter_m))
    poly = ET.SubElement(pm, f"{NS}Polygon")
    txt(poly, f"{NS}altitudeMode", "clampToGround")
    txt(poly, f"{NS}tessellate", "1")
    outer = ET.SubElement(poly, f"{NS}outerBoundaryIs")
    ring = ET.SubElement(outer, f"{NS}LinearRing")
    txt(ring, f"{NS}coordinates", circle_ring(lat, lon, diameter_m / 2, RAINBOW_GROUND_ALT))
    return pm


def ensure_rainbow_styles(doc: ET.Element) -> None:
    existing = {s.get("id") for s in doc.findall(f"{NS}Style")}
    for _d, _c, style_id, color, width in RAINBOW_RINGS:
        if style_id in existing:
            continue
        style = ET.SubElement(doc, f"{NS}Style", id=style_id)
        ls = ET.SubElement(style, f"{NS}LineStyle")
        txt(ls, f"{NS}color", color)
        txt(ls, f"{NS}width", str(width))
        ps = ET.SubElement(style, f"{NS}PolyStyle")
        txt(ps, f"{NS}color", "00000000")
        txt(ps, f"{NS}fill", "0")
        txt(ps, f"{NS}outline", "1")


def rainbow_folder_label(anchor: dict) -> str:
    if anchor.get("internal"):
        return ZERO_POINT_CODE
    m = re.match(r"(IU/\w+)", anchor["name"])
    return m.group(1) if m else anchor["name"]


def rebuild_rainbow_rings(doc: ET.Element, targets: dict[str, dict]) -> None:
    ensure_rainbow_styles(doc)
    for folder in list(doc.findall(f"{NS}Folder")):
        name = folder.find(f"{NS}name")
        if name is not None and name.text == "Rainbow Rings":
            doc.remove(folder)

    root_folder = ET.SubElement(doc, f"{NS}Folder")
    txt(root_folder, f"{NS}name", "Rainbow Rings")
    txt(
        root_folder,
        f"{NS}description",
        "Ground rings for every Stations placemark plus internal ZeroPoint.",
    )

    for code in sorted(targets, key=lambda c: (targets[c].get("internal", False), c)):
        anchor = targets[code]
        sf = ET.SubElement(root_folder, f"{NS}Folder")
        txt(sf, f"{NS}name", rainbow_folder_label(anchor))
        txt(sf, f"{NS}description", anchor["name"])
        set_extended_data(sf, "station_code", code)
        for diameter_m, color_name, style_id, _color, _width in RAINBOW_RINGS:
            sf.append(
                rainbow_ring_placemark(
                    code, diameter_m, color_name, style_id, anchor["lat"], anchor["lon"]
                )
            )


def sync_rainbow_rings(doc: ET.Element, targets: dict[str, dict], changed: set[str]) -> None:
    root = find_folder(doc, "Rainbow Rings")
    if root is None:
        rebuild_rainbow_rings(doc, targets)
        return

    known_codes = set()
    for sf in root.findall(f"{NS}Folder"):
        code = extended_data(sf).get("station_code")
        if not code:
            name = sf.find(f"{NS}name")
            code = station_code_from_name(name.text or "") if name is not None else None
            if name is not None and name.text == ZERO_POINT_CODE:
                code = ZERO_POINT_CODE
        if not code:
            continue
        known_codes.add(code)
        if code not in targets:
            continue
        if code not in changed:
            continue
        lat, lon = station_pos(targets, code)
        for pm in sf.findall(f"{NS}Placemark"):
            meta = extended_data(pm)
            diam = meta.get("diameter_m")
            if not diam:
                continue
            update_circle(pm, lat, lon, RAINBOW_GROUND_ALT, int(diam) / 2)

    missing = set(targets) - known_codes
    if missing:
        rebuild_rainbow_rings(doc, targets)


def update_line(pm: ET.Element, a: str, b: str, anchors: dict[str, dict], alt: float) -> None:
    lat1, lon1 = station_pos(anchors, a)
    lat2, lon2 = station_pos(anchors, b)
    coords = pm.find(f".//{NS}LineString/{NS}coordinates")
    if coords is not None:
        coords.text = great_circle(lat1, lon1, lat2, lon2, alt)


def load_cache() -> dict[str, list[float]]:
    if not CACHE_PATH.exists():
        return {}
    return json.loads(CACHE_PATH.read_text())


def save_cache(anchors: dict[str, dict]) -> None:
    payload = {code: [a["lat"], a["lon"]] for code, a in sorted(anchors.items())}
    CACHE_PATH.write_text(json.dumps(payload, indent=2) + "\n")


def moved_anchors(anchors: dict[str, dict], cache: dict[str, list[float]], eps: float = 1e-9) -> set[str]:
    moved: set[str] = set()
    for code, a in anchors.items():
        prev = cache.get(code)
        if prev is None:
            moved.add(code)
            continue
        if abs(prev[0] - a["lat"]) > eps or abs(prev[1] - a["lon"]) > eps:
            moved.add(code)
    return moved


def ensure_network_link(
    link_path: Path = LINK_KML_PATH,
    target_path: Path = KML_PATH,
    *,
    bump_refresh: bool = False,
) -> bool:
    """Point NetworkLink href at the absolute file URI so onChange refresh works."""
    ET.register_namespace("", KML_NS)
    target_uri = target_path.resolve().as_uri()
    tree = ET.parse(link_path)
    root = tree.getroot()
    href_el = root.find(f".//{NS}NetworkLink/{NS}Link/{NS}href")
    if href_el is None:
        href_el = root.find(".//{*}NetworkLink/{*}Link/{*}href")
    if href_el is None:
        raise RuntimeError(f"No NetworkLink href in {link_path}")

    changed = href_el.text != target_uri
    href_el.text = target_uri

    if bump_refresh:
        desc = root.find(f"{NS}Document/{NS}description")
        if desc is None:
            desc = root.find("{*}Document/{*}description")
        if desc is not None:
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            base = (desc.text or "").split("Last sync refresh:")[0].rstrip()
            desc.text = f"{base}\n\nLast sync refresh: {stamp}"
            changed = True

    if changed:
        ET.indent(tree, space="  ")
        with open(link_path, "wb") as f:
            f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(ET.tostring(root, encoding="utf-8"))
    return changed


def write_tree(tree: ET.ElementTree, path: Path) -> None:
    ET.register_namespace("", KML_NS)
    ET.indent(tree, space="  ")
    with open(path, "wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(ET.tostring(tree.getroot(), encoding="utf-8"))


def sync_document(doc: ET.Element, *, force_all: bool = False) -> list[str]:
    stations = read_stations_layer(doc)
    anchors = read_anchors(doc)
    cache = load_cache()
    changed = set(anchors) if force_all or not cache else moved_anchors(anchors, cache)

    if not changed:
        return []

    line_alt = LINE_ALT_M
    line_folder = find_folder(doc, "Line Layer")
    if line_folder is not None:
        data = line_folder.find(f".//{NS}Data[@name='shared_altitude_m']/{NS}value")
        if data is not None and data.text:
            line_alt = int(float(data.text))

    for code in changed:
        if code not in anchors:
            continue
        anchor = anchors[code]
        if anchor.get("placemark") is not None:
            update_station_description(anchor["placemark"], anchor["lat"], anchor["lon"], code)

    circle_alt = CIRCLE_ALT_M
    circle_folder = find_folder(doc, "Circle Layer")
    if circle_folder is not None:
        data = circle_folder.find(f".//{NS}Data[@name='shared_altitude_m']/{NS}value")
        if data is not None and data.text:
            circle_alt = int(float(data.text))
        for pm in circle_folder.findall(f"{NS}Placemark"):
            name = pm.find(f"{NS}name")
            if name is None:
                continue
            code = attachment_code_from_name(name.text or "", stations)
            if code and code in changed:
                lat, lon = station_pos(anchors, code)
                update_circle(pm, lat, lon, circle_alt, CIRCLE_RADIUS_M)

    if line_folder is not None:
        for pm in line_folder.findall(f"{NS}Placemark"):
            name_el = pm.find(f"{NS}name")
            if name_el is None:
                continue
            endpoints = parse_line_endpoints(name_el.text or "")
            if not endpoints:
                continue
            a, b = endpoints
            if a in changed or b in changed:
                update_line(pm, a, b, anchors, line_alt)

    rainbow_targets = {k: v for k, v in anchors.items()}
    sync_rainbow_rings(doc, rainbow_targets, changed)

    save_cache(anchors)
    return sorted(changed)


def sync_kml(path: Path = KML_PATH, force_all: bool = False, *, persist: bool = True) -> list[str]:
    tree = ET.parse(path)
    doc = tree.getroot().find(f"{NS}Document")
    if doc is None:
        raise RuntimeError("Document element not found")
    changed = sync_document(doc, force_all=force_all)
    if changed and persist:
        write_tree(tree, path)
    return changed


def pull_from_myplaces(
    state,
    myplaces_path: Path,
    *,
    source: str,
    persist_backup: bool = True,
) -> list[str]:
    """Import GE edits from myplaces.kml, redraw attachments, serve via HTTP."""
    from myplaces_import import apply_positions_to_document, read_myplaces_anchors

    doc = state.root.find(f"{NS}Document")
    if doc is None:
        raise RuntimeError("Document element not found")

    positions = read_myplaces_anchors(myplaces_path)
    if not positions:
        print(f"[{source}] No station anchors found in {myplaces_path}")
        return []

    imported = apply_positions_to_document(doc, positions)
    if not imported:
        return []

    changed = sync_document(doc)
    state.bump()
    if persist_backup and (changed or imported):
        write_tree(state.tree, KML_PATH)
    if changed:
        print(f"[{source}] Redrew attachments for: {', '.join(changed)}")
    else:
        print(f"[{source}] Updated station positions: {', '.join(sorted(imported))}")
    return changed or sorted(imported)


def ensure_earth_open(open_url: str) -> None:
    from earth_launcher import ensure_google_earth

    try:
        print(ensure_google_earth(open_url, lock_dir=DATA_DIR))
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"Warning: {exc}", file=sys.stderr)


def watch(
    path: Path = KML_PATH,
    interval: float = 0.5,
    debounce_s: float = 0.5,
    *,
    open_earth: bool = True,
    port: int = DEFAULT_SERVER_PORT,
    host: str = "127.0.0.1",
) -> None:
    from kml_server import KmlServer, KmlState
    from myplaces_import import MYPLACES_PATH

    tree = ET.parse(path)
    state = KmlState()
    state.set_tree(tree)

    pending_source: str | None = None
    pending_at = 0.0
    myplaces_mtime = (
        MYPLACES_PATH.stat().st_mtime if MYPLACES_PATH.is_file() else 0.0
    )

    def schedule_pull(source: str) -> None:
        nonlocal pending_source, pending_at
        pending_source = source
        pending_at = time.time()

    def on_ping(_query: dict) -> None:
        schedule_pull("NetworkLink ping")

    server = KmlServer(state, host=host, port=port, on_ping=on_ping)
    server.start()
    link_url = server.link_url

    print("CircleCity HTTP NetworkLink (Google Earth pulls KML from here; does not edit disk live)")
    print(f"  {link_url}")
    print(f"Watching Google Earth saves in: {MYPLACES_PATH}")
    print("  Drag stations in GE, then Save (Ctrl+S) — GE writes myplaces.kml, not data/seismic_network.kml")

    if open_earth:
        ensure_earth_open(link_url)

    while True:
        try:
            if pending_source and (time.time() - pending_at) >= debounce_s:
                source = pending_source
                pending_source = None
                pull_from_myplaces(state, MYPLACES_PATH, source=source)
                if MYPLACES_PATH.is_file():
                    myplaces_mtime = MYPLACES_PATH.stat().st_mtime

            if MYPLACES_PATH.is_file():
                current = MYPLACES_PATH.stat().st_mtime
                if current != myplaces_mtime:
                    myplaces_mtime = current
                    schedule_pull("myplaces.kml")

            time.sleep(interval)
        except KeyboardInterrupt:
            print("\nStopped.")
            break


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync KML attachments to moved stations")
    parser.add_argument("--watch", action="store_true", help="Watch KML file and sync on save")
    parser.add_argument("--force-all", action="store_true", help="Redraw all attachments")
    parser.add_argument("--init", action="store_true", help="Initialize position cache only")
    parser.add_argument(
        "--build-rainbow", action="store_true", help="Build or rebuild Rainbow Rings layer"
    )
    parser.add_argument(
        "--no-earth",
        action="store_true",
        help="Do not start or focus Google Earth when watching",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_SERVER_PORT,
        help="HTTP port for NetworkLink KML server (default: 8765)",
    )
    args = parser.parse_args()

    if args.build_rainbow:
        tree = ET.parse(KML_PATH)
        doc = tree.getroot().find(f"{NS}Document")
        targets = read_rainbow_targets(doc)
        rebuild_rainbow_rings(doc, targets)
        save_cache(read_anchors(doc))
        ET.indent(tree, space="  ")
        with open(KML_PATH, "wb") as f:
            f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(ET.tostring(tree.getroot(), encoding="utf-8"))
        station_n = sum(1 for t in targets.values() if not t.get("internal"))
        print(
            f"Built Rainbow Rings: {station_n} stations + "
            f"{1 if ZERO_POINT_CODE in targets else 0} internal ZeroPoint"
        )
        return

    if args.init:
        tree = ET.parse(KML_PATH)
        doc = tree.getroot().find(f"{NS}Document")
        save_cache(read_anchors(doc))
        print(f"Initialized {CACHE_PATH}")
        return

    if args.watch:
        watch(open_earth=not args.no_earth, port=args.port)
        return

    changed = sync_kml(force_all=args.force_all)
    if changed:
        print(f"Updated attachments for: {', '.join(changed)}")
    else:
        print("No station movement detected.")


if __name__ == "__main__":
    main()