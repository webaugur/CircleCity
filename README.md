# CircleCity

IU seismograph network KML for Google Earth Pro, with live geometry sync when station anchors are dragged.

## Quick start

```bash
./start-earth-sync.sh
```

Open `seismic_network_link.kml` in Google Earth Pro, drag stations under **Stations**, then **Save** (Ctrl+S). Attached lines, circles, and rainbow rings redraw automatically; the network link reloads within a few seconds.

## Commands

| Command | Purpose |
|---------|---------|
| `./start-earth-sync.sh` | Watch `seismic_network.kml` and sync on save |
| `python3 kml_sync.py --watch` | Same as above |
| `python3 kml_sync.py --init` | Initialize position cache |
| `python3 kml_sync.py --force-all` | Redraw all attachments |
| `python3 kml_sync.py --build-rainbow` | Rebuild Rainbow Rings layer |

## Files

- `seismic_network_link.kml` — open this in Google Earth (auto-reloads)
- `seismic_network.kml` — main geometry (saved on edit)
- `kml_sync.py` — station move → attachment sync
- `seismo.json` — IU station metadata (FDSN source)