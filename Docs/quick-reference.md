# Quick reference — when you do X, then Y

Each row: **action → intended outcome → code → data**.

---

## Daily workflow

| When you… | Then… | Code | Data |
|-----------|-------|------|------|
| Run `./tools/bin/start-earth-sync.sh` | Shell `cd`s to `tools/bin/`, prints the link KML path, and starts watch mode | `start-earth-sync.sh` → `kml_sync.py --watch` | — |
| Start watch (above) and Google Earth is **not** running | One `google-earth-pro` wrapper is spawned; sync waits for a live `googleearth-bin` PID | `earth_launcher.ensure_google_earth()` → `_spawn_earth()` → `_wait_for_earth_bin()` | `data/seismic_network_link.kml` |
| Start watch and Google Earth **is** already running | **No launch.** Sync reports existing `googleearth-bin` PID(s) and continues | `earth_launcher.google_earth_pids()` → early return (no `exec`) | — |
| Start watch (with Earth launch) | Terminal prints `Watching … seismic_network.kml` and polls for saves | `kml_sync.watch()` | `data/seismic_network.kml` |
| Expand **seismic_network.kml** in Google Earth under the network link | You see Stations, Line Layer, Circle Layer, Rainbow Rings, Reference Points | Google Earth NetworkLink loader | `data/seismic_network_link.kml` → `data/seismic_network.kml` |
| Drag a station under **Stations** and **Save** (Ctrl+S) | Google Earth writes new coordinates into the main KML; file mtime changes | Google Earth save | `data/seismic_network.kml` (Stations folder `Point/coordinates`) |
| Save after dragging (watch running) | After 0.4 s debounce, sync compares anchors to cache, redraws attachments for moved codes, rewrites KML, updates cache | `watch()` → `sync_kml()` | Reads/writes `data/seismic_network.kml`; reads/writes `data/.station_positions.json` |
| Save but coordinates unchanged | Terminal: `File saved — no station coordinate changes detected.` | `sync_kml()` → `moved_anchors()` returns empty | `data/.station_positions.json` unchanged |
| Sync redraws a moved station `CODE` | Station description text, circle, any lines touching `CODE`, and rainbow rings for `CODE` are recomputed at the new lat/lon | `update_station_description`, `update_circle`, `update_line`, `sync_rainbow_rings` in `kml_sync.py` | `data/seismic_network.kml` (Circle Layer, Line Layer, Rainbow Rings folders) |
| Sync finishes a redraw | Google Earth NetworkLink detects file change and reloads within ~2 s | Google Earth `refreshMode=onChange` on the link | `data/seismic_network_link.kml` → `data/seismic_network.kml` |

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