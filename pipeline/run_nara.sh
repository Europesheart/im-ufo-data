#!/usr/bin/env bash
# Manual only: downloads the 90.8 MB NARA export + GeoNames cities500 at runtime (never committed).
set -euo pipefail
cd "$(dirname "$0")/.."
python pipeline/nara.py
python pipeline/build.py
