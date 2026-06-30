# NetworkLink architecture

Google Earth does **not** write dragged station coordinates back to `data/seismic_network.kml`. Edits land in **`~/.googleearth/myplaces.kml`** when you Save (Ctrl+S).

CircleCity therefore uses a **local HTTP NetworkLink** — not a file watcher on the canonical KML.

## Data flow

```
Google Earth                         CircleCity sync
─────────────                        ───────────────
Drag station (in memory)
     │
Pin drag (GE flushes My Places) ───► ~/.googleearth/myplaces.kml  (coordinate poll)
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

## Live pin watch + git undo

Sync polls **station pin coordinates** in `~/.googleearth/myplaces.kml` every 0.2 s (not file mtimes). When a pin moves relative to the served KML:

1. Attachments redraw in memory
2. HTTP `/main.kml` updates (GE sees it on next refresh)
3. `data/seismic_network.kml` is committed to git

**Console keys** (while sync is running):

| Key | Action |
|-----|--------|
| `u` | Undo last committed move (`git reset --hard HEAD~1`, reload KML) |
| `u` × N | Undo N moves one step at a time |
| `q` | Quit sync |

## Usage checklist

1. `./tools/bin/start-earth-sync.sh`
2. Google Earth opens `http://127.0.0.1:8765/link.kml` (NetworkLink)
3. Expand **seismic_network** — stations load from `/main.kml`
4. Drag a station pin (GE writes My Places when the drag completes)
5. Terminal: `[pins] KBS — attachments updated, committed (press u to undo…)`
6. Within ~3 s GE refresh shows updated lines/circles/rings

Manual one-shot import: `python3 tools/bin/kml_sync.py --pull-now`

## Stop on Google Earth exit

When sync started Google Earth (`--watch` without `--no-earth`), closing GE:

1. Waits for `myplaces.kml` flush (GE saves My Places on exit)
2. Imports final station positions + redraws attachments
3. Archives `~/.googleearth/myplaces.kml` → `data/myplaces_saved.kml`
4. Persists backup `data/seismic_network.kml`
5. Stops the HTTP server and watcher