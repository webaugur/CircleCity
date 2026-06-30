#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

echo "=== CircleCity — KML live sync ==="
echo ""
echo "1. Open in Google Earth Pro:"
echo "     $(pwd)/seismic_network_link.kml"
echo ""
echo "2. Drag stations under Stations, then Save (Ctrl+S)."
echo ""
echo "3. This watcher redraws lines, circles, and rainbow rings."
echo "   The NetworkLink reloads seismic_network.kml automatically."
echo ""
echo "Press Ctrl+C to stop."
echo ""

exec python3 kml_sync.py --watch