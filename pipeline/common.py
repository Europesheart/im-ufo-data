"""Shared helpers: schema (RESEARCH.md §5.2), paths, output. Repo layout:
   data-src/raw    committed inputs (GEIPAN XLSX, PURSUE CSV) - last good copy is the fallback
   data-src/stage  per-layer GeoJSON (nara.geojson is committed; others rebuilt)
   docs/data       what GitHub Pages serves
   .cache          runtime downloads (not committed)"""
import json, os, re, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data-src", "raw")
STAGE = os.path.join(ROOT, "data-src", "stage")
CACHE = os.path.join(ROOT, ".cache")
OUT = os.path.join(ROOT, "docs", "data")
for p in (RAW, STAGE, CACHE, OUT):
    os.makedirs(p, exist_ok=True)

UA = "im-ufo-data/1.0 (+https://information-machine.blogspot.com; educational map; once-daily fetch)"

ATTR = {
    "geipan": "\u00a9 CNES/GEIPAN \u2013 source: geipan.fr, educational use",
    "nara": "Source: U.S. National Archives (NARA)",
    "aaro": "Source: U.S. Department of War / AARO (public domain, U.S. federal work)",
    "celestrak": "Orbits: CelesTrak (celestrak.org) \u00b7 skyfield",
    "ll2": "Launches: The Space Devs \u2013 Launch Library 2",
    "jpl": "Fireballs: NASA/JPL CNEOS Fireball API",
}

def now_utc():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def clip(s, n=280):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "\u2026"

def feature(lon, lat, **p):
    """Return a §5.2 feature. Unknown fields stay None, never guessed."""
    base = dict(id=None, source=None, source_url=None, official=False, date_utc=None,
                date_precision=None, year=None, location_name=None, country=None,
                geo_precision_km=None, shape=None, duration_s=None, witnesses=None,
                media=None, summary=None, classification=None, credibility=None,
                ifo=None, license=None, dup_of=None)
    base.update(p)
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(lon, 4), round(lat, 4)]},
            "properties": base}

def write_json(path, obj, compact=True):
    """Write only if content changed (keeps git diffs and commits honest)."""
    data = json.dumps(obj, ensure_ascii=False, separators=(",", ":")) if compact else json.dumps(obj, ensure_ascii=False, indent=2)
    if os.path.exists(path) and open(path, encoding="utf-8").read() == data:
        return os.path.getsize(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)
    return os.path.getsize(path)

def fc(features, **meta):
    d = {"type": "FeatureCollection", "features": features}
    d.update(meta)
    return d

def file_stamp(path):
    """Deterministic stamp for a committed input: its sha1 (not the clock)."""
    import hashlib
    return hashlib.sha1(open(path, "rb").read()).hexdigest()[:12]
