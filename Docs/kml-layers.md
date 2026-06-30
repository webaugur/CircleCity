# KML layers (`data/seismic_network.kml`)

## Anchor points (sources of truth for position)

| Folder | Placemarks | Sync role |
|--------|------------|-----------|
| **Stations** | 75 IU network points on the ground | **Anchors.** Dragging these in Google Earth is the primary edit. Every `Point` here is tracked by `station_code` in ExtendedData. |
| **Reference Points** | `ZeroPoint` (0°, 0°) | **Internal anchor.** Not listed under Stations, but included in rainbow rings and lines that name `ZeroPoint`. |

When an anchor moves, `kml_sync.py` redraws everything that references its `station_code`.

## Attached geometry (redrawn by sync)

| Folder | Altitude | What moves with anchor |
|--------|----------|------------------------|
| **Line Layer** | 100 km (`shared_altitude_m` in folder metadata) | Great-circle arcs. Names use `CODE_A → CODE_B (...)` so `parse_line_endpoints()` can find endpoints. Includes RSSD→station spokes (6000 mi visibility rule baked into KML), KBS→KEV, KEV→KIEV, RSSD→ZeroPoint. |
| **Circle Layer** | 100 km | One circle per station; 33,966 m radius. Named `IU/CODE circle`. |
| **Rainbow Rings** | Ground (0 m) | Six concentric rings per anchor (150/99/66/42/33/13 m diameter, red→violet). One subfolder per station + ZeroPoint. |

## Network link (separate file)

`data/seismic_network_link.kml` does not contain geometry. It only links to `seismic_network.kml` with `refreshMode=onChange` so Google Earth reloads the main file after sync rewrites it.