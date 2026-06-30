#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

echo "=== CircleCity — KML live sync ==="
echo ""
echo "Starts HTTP NetworkLink server + Google Earth Pro."
echo "Drag stations in GE, then Save (Ctrl+S) — GE writes ~/.googleearth/myplaces.kml"
echo ""
echo "  NetworkLink: http://127.0.0.1:8765/link.kml"
echo ""
echo "Close Google Earth to save My Places and stop sync (or Ctrl+C)."
echo ""

exec python3 kml_sync.py --watch