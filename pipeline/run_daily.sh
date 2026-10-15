#!/usr/bin/env bash
# GEIPAN + PURSUE: fetch (polite, never fails hard), rebuild layers, rebuild archive. Needs no secrets.
set -euo pipefail
cd "$(dirname "$0")/.."
python pipeline/fetch_geipan.py
python pipeline/fetch_pursue.py
python pipeline/geipan.py
python pipeline/official.py
python pipeline/build.py
