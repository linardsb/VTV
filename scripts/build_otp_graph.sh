#!/usr/bin/env bash
set -euo pipefail

# Build OpenTripPlanner graph for Latvia
# Downloads OSM + GTFS data, then builds the OTP routing graph.
# Run once before starting OTP: ./scripts/build_otp_graph.sh

GRAPH_DIR="otp/graphs"
mkdir -p "$GRAPH_DIR"

echo "==> Downloading Latvia OSM extract..."
curl -fSL "https://download.geofabrik.de/europe/latvia-latest.osm.pbf" \
  -o "$GRAPH_DIR/latvia-latest.osm.pbf"

echo "==> Downloading Riga GTFS..."
curl -fSL "https://data.gov.lv/dati/dataset/marsrutu-saraksti-rigas-satiksme/resource/gtfs.zip" \
  -o "$GRAPH_DIR/gtfs.zip"

echo "==> Building OTP graph (this may take several minutes)..."
docker run --rm \
  -v "$(pwd)/$GRAPH_DIR:/var/otp/graphs" \
  opentripplanner/opentripplanner:2.6.0 \
  --build --save /var/otp/graphs

echo "==> OTP graph built successfully in $GRAPH_DIR/"
