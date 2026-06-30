#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

echo "=== CircleCity — KML live sync ==="
echo ""
echo "Starting Google Earth Pro (or opening the network link if already running)..."
echo "Then drag stations under Stations and Save (Ctrl+S)."
echo ""
DATA_DIR="$(cd "$(dirname "$(readlink -f "$0")")/../.." && pwd)/data"
echo "  KML: ${DATA_DIR}/seismic_network_link.kml"
echo ""
echo "Press Ctrl+C to stop."
echo ""

exec python3 kml_sync.py --watch