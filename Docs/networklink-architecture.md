# NetworkLink architecture

Google Earth does **not** write dragged station coordinates back to `data/seismic_network.kml`. Edits land in **`~/.googleearth/myplaces.kml`** when you Save (Ctrl+S).

CircleCity therefore uses a **local HTTP NetworkLink** — not a file watcher on the canonical KML.

## Data flow

```
Google Earth                         CircleCity sync
─────────────                        ───────────────
Drag station (in memory)
     │
Save (Ctrl+S) ─────────────────────► ~/.googleearth/myplaces.kml  (mtime watch)
     │                                        │
     │                                        ├─ import station positions
     │                                        ├─ redraw attachments in memory
     │                                        └─ serve updated KML over HTTP
     │
GET http://127.0.0.1:8765/main.kml ◄──────── NetworkLink refresh (every 3 s)
     │
GET …/main.kml?ping=1 ◄──────────────────── viewRefresh onStop (GE tells us)
```

## When you do X → Y (code + data)

| When you… | Then… | Code | Data |
|-----------|-------|------|------|
| Run `./tools/bin/start-earth-sync.sh` | HTTP server starts; GE opens `http://127.0.0.1:8765/link.kml` | `kml_server.KmlServer`, `earth_launcher.ensure_google_earth` | served `/link.kml`, `/main.kml` |
| GE loads NetworkLink | GE GETs `/main.kml` (initial + every 3 s) | `KmlServer` handler | in-memory `KmlState` |
| GE view stops moving | GE GETs `/main.kml?ping=1…` (viewFormat) | `on_ping` → `schedule_pull` | — |
| Drag station + Save in GE | `myplaces.kml` mtime changes | `watch()` mtime poll | `~/.googleearth/myplaces.kml` |
| myplaces or ping fires | Import positions → sync attachments → bump generation | `pull_from_myplaces`, `sync_document` | myplaces → memory; backup optional `data/seismic_network.kml` |
| Attachments redrawn | Next GE refresh GET receives new KML bytes | `KmlState.bump()`, `refreshMode=onInterval` | HTTP response body |

## Why not watch `data/seismic_network.kml`?

- GE holds network-linked content **in memory**.
- Save writes to **My Places**, not the linked source file.
- Rewriting `data/seismic_network.kml` on disk while GE is open fights GE's in-memory copy.

## Backup

After a successful pull, sync optionally persists to `data/seismic_network.kml` as a **backup** only. The live document GE displays is the HTTP-served KML.