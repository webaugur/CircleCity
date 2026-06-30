# Data inventory

All geometry and metadata live under `data/`. Scripts in `tools/bin/` read and write here.

| File | Role | Written by |
|------|------|------------|
| `data/seismic_network.kml` | Main KML: stations, lines, circles, rainbow rings | Google Earth (save after drag); `kml_sync.py` (attachment redraw) |
| `data/seismic_network_link.kml` | Thin NetworkLink wrapper; auto-reloads main KML in GE | Hand-edited rarely |
| `data/.station_positions.json` | Lat/lon cache for change detection (gitignored) | `kml_sync.py` (`save_cache`, `--init`) |
| `data/seismo.json` | IU station list/metadata from FDSN (source for original build) | External API / manual refresh |
| `data/seismic.kml` | Early 12-station prototype | Archive |
| `data/Circle City Geometry - 2026-06-25.kmz` | Prior geometry export | Archive |

Path resolution in code (`kml_sync.py`):

```
PROJECT_ROOT = tools/bin/../..   → repo root
DATA_DIR     = PROJECT_ROOT/data
```