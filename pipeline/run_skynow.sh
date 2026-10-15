#!/usr/bin/env bash
# Hourly: Starlink (CelesTrak, cached 2 h), Launch Library 2, JPL fireballs -> docs/data/skynow.json + meta.json
set -euo pipefail
cd "$(dirname "$0")/.."
python pipeline/skynow.py
python pipeline/build.py
