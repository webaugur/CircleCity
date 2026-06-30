# Quick reference — when you do X, then Y

Each row: **action → intended outcome → code → data**.

---

## Daily workflow

| When you… | Then… | Code | Data |
|-----------|-------|------|------|
| Run `./tools/bin/start-earth-sync.sh` | Shell `cd`s to `tools/bin/`, prints the link KML path, and starts watch mode | `start-earth-sync.sh` → `kml_sync.py --watch` | — |
| Start watch (above) | NetworkLink `href` set to absolute `file://` URI; GE gets editable main KML + link sidecar | `ensure_network_link()` then `ensure_google_earth(link, edit)` | `data/seismic_network.kml`, `data/seismic_network_link.kml` |
| Start watch, GE **not** running | Spawns GE with `seismic_network.kml`, then non-blocking open of link KML for reload | `_spawn_earth(edit_kml)` → `_open_kml_nonblocking(link_kml)` | `data/seismic_network.kml`, `data/seismic_network_link.kml` |
| Start watch, GE **already** running | Checks `/proc/PID/cmdline`; opens missing files via non-blocking `google-earth-pro` (no second `googleearth-bin`) | `ge_opened_paths()` → `_open_kml_nonblocking()` | same |
| Start watch (with Earth launch) | Terminal prints `Watching … seismic_network.kml` and polls for saves | `kml_sync.watch()` | `data/seismic_network.kml` |
| Edit **seismic_network.kml** directly in Google Earth (opened by sync) | Drag/save writes to the watched file — not only through the NetworkLink tree | Google Earth save | `data/seismic_network.kml` (Stations folder `Point/coordinates`) |
| Drag a station under **Stations** and **Save** (Ctrl+S) | `mtime` changes on main and/or link KML; watcher debounces 0.4 s | Google Earth save | `data/seismic_network.kml` |
| Save after dragging (watch running) | Sync compares anchors to cache, redraws attachments, bumps NetworkLink timestamp | `watch()` → `sync_kml()` → `ensure_network_link()` | `data/seismic_network.kml`, `data/.station_positions.json`, `data/seismic_network_link.kml` |
| Sync rewrites KML | Watcher ignores self-writes for 1.5 s (`_sync_write_until`); GE NetworkLink `onChange` sees `file://` href target change | `_sync_write_until` guard in `watch()` | `data/seismic_network.kml` |
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