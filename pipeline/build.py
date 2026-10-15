"""Merge stage/*.geojson -> build/data/archive/<decade>.geojson + build/data/meta.json"""
import json, glob, collections, gzip
from common import *

def prune(o):
    if isinstance(o, dict): return {k: prune(v) for k, v in o.items() if v not in (None, [], "")}
    if isinstance(o, list): return [prune(v) for v in o]
    return o

def main():
    layers = {}
    for p in sorted(glob.glob(os.path.join(STAGE, "*.geojson"))):
        d = json.load(open(p, encoding="utf-8"))
        layers[os.path.basename(p)[:-8]] = d
    by_dec = collections.defaultdict(list)
    hist = collections.defaultdict(collections.Counter)
    counts = collections.Counter(); cls = collections.defaultdict(collections.Counter); ifo = collections.defaultdict(collections.Counter)
    shapes = collections.Counter(); dropped = collections.Counter()
    for name, d in layers.items():
        for f in d["features"]:
            p = f["properties"]
            y = p.get("year")
            if not y or y < 1937 or y > 2026: dropped[p["source"]] += 1; continue
            by_dec[y // 10 * 10].append(prune(f))
            hist[p["source"]][y] += 1
            counts[p["source"]] += 1
            c = p.get("classification") or {}
            cls[p["source"]][str(c.get("value"))] += 1
            ifo[p["source"]][str((p.get("ifo") or {}).get("status"))] += 1
            if p.get("shape"): shapes[p["shape"]] += 1
    os.makedirs(os.path.join(OUT, "archive"), exist_ok=True)
    decades = []
    for dec in sorted(by_dec):
        feats = sorted(by_dec[dec], key=lambda f: f["properties"].get("date_utc") or "")
        path = os.path.join(OUT, "archive", f"{dec}.geojson")
        n = write_json(path, {"type": "FeatureCollection", "decade": dec, "features": feats})
        gz = len(gzip.compress(open(path, "rb").read(), 6))
        decades.append({"decade": dec, "file": f"archive/{dec}.geojson", "count": len(feats), "bytes": n, "gzip_bytes": gz,
                        "by_source": dict(collections.Counter(f["properties"]["source"] for f in feats))})
    sky = json.load(open(os.path.join(OUT, "skynow.json"), encoding="utf-8"))
    meta = {
        "archive_version": None, "schema": "RESEARCH.md \u00a75.2 (Point; fehlende Felder = nicht vorhanden)",
        "year_min": 1937, "year_max": 2026, "decades": decades,
        "counts": dict(counts), "classes": {k: dict(v) for k, v in cls.items()}, "ifo": {k: dict(v) for k, v in ifo.items()},
        "shapes": dict(shapes.most_common()), "dropped_out_of_range": dict(dropped),
        "hist": {s: {str(y): n for y, n in sorted(h.items())} for s, h in hist.items()},
        "attributions": {"geipan": ATTR["geipan"], "nara": ATTR["nara"], "pursue": ATTR["aaro"].replace("AARO", "PURSUE"),
                         "aaro": ATTR["aaro"], "celestrak": ATTR["celestrak"], "ll2": ATTR["ll2"], "jpl": ATTR["jpl"],
                         "geonames": "Geocoding: GeoNames cities500 (CC BY 4.0)", "tiles": "Tiles \u00a9 Esri \u2013 Esri, HERE, Garmin, \u00a9 OpenStreetMap contributors"},
        "stage_stats": {k: d.get("stats") for k, d in layers.items() if d.get("stats")},
        "skynow": {"file": "skynow.json", "generated_utc": sky["generated_utc"], "starlink_total": sky["starlink"]["total"],
                   "starlink_maybe_visible": sky["starlink"]["maybe_visible"], "launches": len(sky["launches"]["features"]),
                   "fireballs": len(sky["fireballs"]["features"])},
    }
    import hashlib
    meta["archive_version"] = hashlib.sha1(json.dumps([d["count"] for d in decades] + [d["bytes"] for d in decades]).encode()).hexdigest()[:12]
    write_json(os.path.join(OUT, "meta.json"), meta)
    print("archive:", dict(counts), "| decades:", [(d["decade"], d["count"], round(d["bytes"] / 1e6, 2), round(d["gzip_bytes"] / 1e3)) for d in decades])
    print("dropped:", dict(dropped))

if __name__ == "__main__":
    main()
