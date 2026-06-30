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

Sync starts Google Earth Pro automatically (or opens `data/seismic_network_link.kml` in an already-running instance). Drag stations under **Stations**, then **Save** (Ctrl+S). Attached lines, circles, and rainbow rings redraw automatically; the network link reloads within a few seconds.

## Commands

| Command | Purpose |
|---------|---------|
| `./tools/bin/start-earth-sync.sh` | Watch `data/seismic_network.kml` and sync on save |
| `python3 tools/bin/kml_sync.py --watch` | Same as above |
| `python3 tools/bin/kml_sync.py --watch --no-earth` | Watch only; skip Google Earth launch |
| `python3 tools/bin/kml_sync.py --init` | Initialize position cache |
| `python3 tools/bin/kml_sync.py --force-all` | Redraw all attachments |
| `python3 tools/bin/kml_sync.py --build-rainbow` | Rebuild Rainbow Rings layer |

## Files

- `data/seismic_network_link.kml` — open this in Google Earth (auto-reloads)
- `data/seismic_network.kml` — main geometry (saved on edit)
- `tools/bin/kml_sync.py` — station move → attachment sync
- `data/seismo.json` — IU station metadata (FDSN source)