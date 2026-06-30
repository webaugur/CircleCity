#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

echo "=== CircleCity — KML live sync ==="
echo ""
echo "Starts HTTP NetworkLink server + Google Earth Pro."
echo "Drag station pins in GE — sync polls positions live (no manual save)."
echo "  u = undo last move (repeat for each step)   q = quit"
echo ""
echo "  NetworkLink: http://127.0.0.1:8765/link.kml"
echo ""
echo "Close Google Earth to archive My Places and stop (or press q / Ctrl+C)."
echo ""

exec python3 kml_sync.py --watch