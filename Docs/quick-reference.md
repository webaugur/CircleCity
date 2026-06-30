# Quick reference — when you do X, then Y

Each row: **action → intended outcome → code → data**.

---

## Daily workflow (HTTP NetworkLink — see [networklink-architecture.md](networklink-architecture.md))

| When you… | Then… | Code | Data |
|-----------|-------|------|------|
| Run `./tools/bin/start-earth-sync.sh` | HTTP server + watch start; GE opens NetworkLink URL | `start-earth-sync.sh` → `kml_sync.watch()` | `http://127.0.0.1:8765/link.kml` |
| GE loads NetworkLink | GE GETs `/main.kml` every 3 s (`refreshMode=onInterval`) | `kml_server.KmlServer` | in-memory `KmlState` |
| GE view stops | GE GETs `/main.kml?ping=1…` (`viewRefreshMode=onStop`) | `on_ping` → `schedule_pull` | — |
| Drag station + **Save** (Ctrl+S) | GE writes **My Places**, not `data/seismic_network.kml` | Google Earth save | `~/.googleearth/myplaces.kml` |
| myplaces or ping fires (watch) | Import positions → redraw attachments → serve new KML over HTTP | `pull_from_myplaces`, `sync_document`, `KmlState.bump` | myplaces → memory; backup `data/seismic_network.kml` |
| Sync redraws moved `CODE` | Lines, circles, rainbow rings update; next GE refresh shows them | `sync_document` | HTTP `/main.kml` response |

---

## CLI commands

| When you… | Then… | Code | Data |
|-----------|-------|------|------|
| `python3 tools/bin/kml_sync.py --watch` | Same as `start-earth-sync.sh` (includes Earth launch) | `main()` → `watch(open_earth=True)` | `data/seismic_network.kml`, `data/seismic_network_link.kml` |
| `python3 tools/bin/kml_sync.py --watch --no-earth` | Watch only; no Google Earth detect/launch | `watch(open_earth=False)` | `data/seismic_network.kml` |
| `python3 tools/bin/kml_sync.py --init` | Snapshot all anchor lat/lons into the cache; no KML rewrite | `save_cache(read_anchors(doc))` | Writes `data/.station_positions.json` from `data/seismic_network.kml` |
| `python3 tools/bin/kml_sync.py --force-all` | Treat every anchor as moved; redraw all attachments once | `sync_kml(force_all=True)` | `data/seismic_network.kml`, `data/.station_positions.json` |
| `python3 tools/bin/kml_sync.py --build-rainbow` | Delete and rebuild the entire Rainbow Rings folder | `rebuild_rainbow_rings()` | `data/seismic_network.kml` |
| `python3 tools/bin/kml_sync.py` (no flags) | One-shot sync if cache shows movement since last run | `sync_kml()` | `data/seismic_network.kml`, `data/.station_positions.json` |

---

## Sync internals (what moves what)

| When you move anchor… | Then these attachments update | Code | Data (KML folder) |
|---------------------|---------------------------------|------|-------------------|
| Any **Stations** placemark (`station_code`) | Description `Lat/Lon` text on that placemark | `update_station_description()` | **Stations** |
| Same | Circle centered on new position (33,966 m radius, 100 km alt) | `update_circle()` via `attachment_code_from_name()` on `IU/CODE circle` | **Circle Layer** |
| Same | Every line whose name parses as `A → B` where `A` or `B` equals that code | `update_line()` → `great_circle()` | **Line Layer** |
| Same | All six ground rings in that station's rainbow subfolder | `sync_rainbow_rings()` | **Rainbow Rings** |
| **ZeroPoint** in Reference Points | Rainbow rings and lines naming `ZeroPoint` (e.g. `RSSD → ZeroPoint`); not a Stations placemark | `read_zeropoint()`, `INTERNAL_SOURCES` | **Reference Points**, **Rainbow Rings**, **Line Layer** |

Line endpoint parsing: placemark names like `RSSD → KBS (Ny-Alesund, …)` → codes `RSSD`, `KBS` via `parse_line_endpoints()`.

---

## Google Earth launcher

| When you… | Then… | Code | Data |
|-----------|-------|------|------|
| Launch on Linux with GE installed | `find_google_earth()` resolves `/usr/bin/google-earth-pro` or `/opt/google/earth/pro/google-earth-pro` | `earth_launcher.py` | — |
| Check if GE is running (Linux) | Collect live `googleearth-bin` PIDs via `pgrep -x`; skip zombies (`/proc/PID/stat` state `Z`) | `google_earth_pids()` / `is_google_earth_running()` | — |
| Launch while another sync holds the lock | Wait for `googleearth-bin`; do not spawn another wrapper | `data/.earth_launch.lock` (`fcntl`) in `ensure_google_earth()` | `data/.earth_launch.lock` |
| Earth binary missing | Warning on stderr; watch continues | `ensure_earth_open()` catches `RuntimeError` | — |
| Link KML missing | `FileNotFoundError` warning; watch continues | `ensure_google_earth()` | `data/seismic_network_link.kml` |

---

## Timing constants

| Constant | Value | Where | Effect |
|----------|-------|-------|--------|
| Watch poll interval | 0.5 s | `watch(interval=…)` | How often mtime is checked |
| Save debounce | 0.4 s | `watch(debounce_s=…)` | Wait after last mtime change before syncing |
| Earth startup wait | 2.0 s | `ensure_google_earth(startup_wait_s=…)` | Pause after spawning new GE process |
| NetworkLink refresh | 2 s | `seismic_network_link.kml` `<refreshInterval>` | GE reload cadence after file change |

---

## Geometry constants (sync defaults)

| Constant | Value | Code | Used for |
|----------|-------|------|----------|
| `LINE_ALT_M` | 100,000 m | `kml_sync.py` | Great-circle arcs (overridable via Line Layer `shared_altitude_m`) |
| `CIRCLE_ALT_M` / radius | 100,000 m / 33,966 m | `kml_sync.py` | Station circles (overridable via Circle Layer `shared_altitude_m`) |
| Rainbow diameters | 150, 99, 66, 42, 33, 13 m | `RAINBOW_RINGS` | Ground rings per anchor |
| `ARC_POINTS` | 65 | `great_circle()` | Vertices per line arc |

---

## Related docs

- [data-inventory.md](data-inventory.md) — file list under `data/`
- [kml-layers.md](kml-layers.md) — folder structure inside the main KML