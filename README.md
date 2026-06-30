# CircleCity

IU seismograph network KML for Google Earth Pro, with live geometry sync when station anchors are dragged.

## Layout

```
data/              KML, KMZ, and station metadata
tools/bin/         sync scripts and Google Earth launcher
Docs/              Quick reference (when X → Y, code Z, data A)
```

See **[Docs/quick-reference.md](Docs/quick-reference.md)** for the full action → outcome map.

## Quick start

```bash
./tools/bin/start-earth-sync.sh
```

Starts a local HTTP NetworkLink server (`http://127.0.0.1:8765/link.kml`). Google Earth pulls KML from memory — **not** by editing `data/seismic_network.kml` on disk. Drag stations, then **Save** (Ctrl+S); GE writes `~/.googleearth/myplaces.kml`, which sync imports. NetworkLink refresh pushes updated attachments back to GE.

See **[Docs/networklink-architecture.md](Docs/networklink-architecture.md)**.

## Commands

| Command | Purpose |
|---------|---------|
| `./tools/bin/start-earth-sync.sh` | Watch `data/seismic_network.kml` and sync on save |
| `python3 tools/bin/kml_sync.py --watch` | Same as above |
| `python3 tools/bin/kml_sync.py --watch --no-earth` | Watch only; skip Google Earth launch |
| `python3 tools/bin/kml_sync.py --init` | Initialize position cache |
| `python3 tools/bin/kml_sync.py --force-all` | Redraw all attachments |
| `python3 tools/bin/kml_sync.py --build-rainbow` | Rebuild Rainbow Rings layer |
| `python3 tools/bin/kml_sync.py --pull-now` | Import myplaces once (no server) |

## Files

- `data/seismic_network_link.kml` — open this in Google Earth (auto-reloads)
- `data/seismic_network.kml` — main geometry (saved on edit)
- `tools/bin/kml_sync.py` — station move → attachment sync
- `data/seismo.json` — IU station metadata (FDSN source)