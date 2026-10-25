"""'Sky Now' live layer -> build/data/skynow.json (pre-generated; widget may refresh launches client-side)

1. Starlink (CelesTrak GP JSON, GROUP=starlink) + skyfield: positions at generation time; flag satellites
   that are sunlit while the ground below is dark (sun < -6 deg) = 'possibly visible to the naked eye'.
   The 4 most recent Starlink launches (highest COSPAR numbers this year) are drawn as 'trains' with
   +-45 min ground tracks of their middle satellite.
   This is a geometric visibility proxy, not a brightness model.
2. Launch Library 2 (The Space Devs, ll.thespacedevs.com 2.3.0): launches of the last 30 days and next 30 days.
3. NASA/JPL CNEOS Fireball API: events of the last 365 days (API has no CORS header -> pre-generated only).
"""
import json, urllib.request, datetime as dt, collections, math, time
from common import *

UA = {"User-Agent": UA}

class NoCache(Exception):
    """Download failed and there is no cache file to fall back to."""

def _retryable(err):
    if isinstance(err, urllib.error.HTTPError):
        return err.code in (408, 429, 500, 502, 503, 504)
    return True

def get(url, cache_name=None, max_age_s=0):
    """Fetch JSON. A fresh cache file is used as-is. A failed download is retried,
    then the cache file is used at any age. No cache at all raises NoCache so the
    caller can keep the last published block instead of failing the job."""
    path = os.path.join(CACHE, cache_name) if cache_name else None
    if path and os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_s:
        return json.load(open(path, encoding="utf-8"))
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
            if path: json.dump(data, open(path, "w", encoding="utf-8"))
            return data
        except Exception as e:
            last = e
            print(f"  fetch attempt {attempt + 1} failed ({cache_name or url}): {e!r}")
            if attempt == 2 or not _retryable(e):
                break
            time.sleep(5 * (attempt + 1))
    if path and os.path.exists(path):
        age_h = (time.time() - os.path.getmtime(path)) / 3600
        print(f"::warning::using cached {cache_name} ({age_h:.1f} h old) after {last!r}")
        return json.load(open(path, encoding="utf-8"))
    raise NoCache(f"{cache_name or url}: {last!r}")

def starlink(now):
    from skyfield.api import load, EarthSatellite, wgs84
    from skyfield.api import Loader
    ts = load.timescale()
    eph = Loader(CACHE)("de421.bsp")   # JPL DE421 ephemeris, cached
    sun, earth = eph["sun"], eph["earth"]
    gp = get("https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=json", "celestrak-starlink.json", 2 * 3600)
    t = ts.from_datetime(now)
    pts, trains = [], collections.defaultdict(list)
    sats = []
    for rec in gp:
        try:
            s = EarthSatellite.from_omm(ts, rec)
        except Exception:
            continue
        sats.append((rec, s))
    vis = lit = 0
    for rec, s in sats:
        g = s.at(t)
        sp = wgs84.subpoint_of(g)
        la, lo = sp.latitude.degrees, sp.longitude.degrees
        if not (math.isfinite(la) and math.isfinite(lo)): continue
        sunlit = bool(g.is_sunlit(eph))
        ground = (earth + wgs84.latlon(la, lo)).at(t).observe(sun).apparent().altaz()[0].degrees
        v = sunlit and ground < -6
        lit += sunlit; vis += v
        pts.append([round(lo, 2), round(la, 2), 1 if v else 0, rec.get("OBJECT_ID", ""), rec.get("OBJECT_NAME", "")])
    return gp, sats, pts, vis, lit, t, ts, eph

def _prev():
    path = os.path.join(OUT, "skynow.json")
    if not os.path.exists(path):
        return None
    return json.load(open(path, encoding="utf-8"))

def main():
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    prev = _prev()
    kept = []
    out = {"generated_utc": now.isoformat().replace("+00:00", "Z"), "attribution": [ATTR["celestrak"], ATTR["ll2"], ATTR["jpl"]],
           "cors": {"celestrak": "ACAO: * (client fetch possible, but CelesTrak asks for <= 1 download / 2 h -> pipeline only)",
                    "ll2": "ACAO: * (widget refreshes launches live, fallback = this file; limit 15 requests/h per IP)",
                    "jpl": "no ACAO header -> pipeline only"}}
    # --- launches (LL2) ---
    ll2 = "https://ll.thespacedevs.com/2.3.0/launches/"
    try:
        recent = get(ll2 + "previous/?limit=40&mode=normal", "ll2-previous.json", 3600)   # date filters time out server-side
        time.sleep(2)
        up = get(ll2 + "upcoming/?limit=40&mode=normal", "ll2-upcoming.json", 3600)
    except NoCache as e:
        print(f"::warning::launches unavailable ({e}). Keeping the published block.")
        if not prev or "launches" not in prev:
            raise SystemExit(0 if prev else 1)
        out["launches"] = prev["launches"]
        kept.append("launches")
        recent = up = None
    def L(x, when):
        pad = x.get("pad") or {}
        try: la, lo = float(pad.get("latitude")), float(pad.get("longitude"))
        except (TypeError, ValueError): return None
        st = (x.get("status") or {}).get("abbrev")
        prov = ((x.get("launch_service_provider") or {}).get("name"))
        rk = (((x.get("rocket") or {}).get("configuration") or {}).get("full_name"))
        mission = (x.get("mission") or {}).get("name")
        orbit = (((x.get("mission") or {}).get("orbit")) or {}).get("abbrev")
        return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(lo, 4), round(la, 4)]},
                "properties": {"id": "ll2:" + x.get("id", ""), "source": "ll2", "when": when, "name": x.get("name"),
                               "net": x.get("net"), "status": st, "provider": prov, "rocket": rk, "mission": mission,
                               "orbit": orbit, "pad": pad.get("name"), "location": ((pad.get("location") or {}).get("name")),
                               "starlink": "starlink" in (x.get("name") or "").lower(),
                               "source_url": "https://ll.thespacedevs.com/2.3.0/launches/" + x.get("id", "") + "/",
                               "license": ATTR["ll2"]}}
    if recent is not None:
        lo_t, hi_t = (now - dt.timedelta(days=30)).isoformat(), (now + dt.timedelta(days=30)).isoformat()
        def within(x): return lo_t[:19] <= (x.get("net") or "")[:19] <= hi_t[:19]
        launches = [f for f in (L(x, "recent") for x in recent.get("results", []) if within(x)) if f] + \
                   [f for f in (L(x, "upcoming") for x in up.get("results", []) if within(x)) if f]
        out["launches"] = {"type": "FeatureCollection", "features": launches}
    else:
        launches = out["launches"]["features"]
    # --- fireballs (JPL) ---
    try:
        fb = get("https://ssd-api.jpl.nasa.gov/fireball.api?date-min=" + (now - dt.timedelta(days=365)).strftime("%Y-%m-%d") + "&req-loc=true", "jpl-fireball.json", 3600)
    except NoCache as e:
        print(f"::warning::fireballs unavailable ({e}). Keeping the published block.")
        if not prev or "fireballs" not in prev:
            raise SystemExit(0 if prev else 1)
        out["fireballs"] = prev["fireballs"]
        kept.append("fireballs")
        fb = None
    if fb is not None:
        fl = fb.get("fields", [])
        fbs = []
        for row in fb.get("data", []):
            r = dict(zip(fl, row))
            try:
                la = float(r["lat"]) * (1 if r["lat-dir"] == "N" else -1)
                lo = float(r["lon"]) * (1 if r["lon-dir"] == "E" else -1)
            except (TypeError, ValueError, KeyError):
                continue
            d = r["date"].replace(" ", "T") + "Z"
            fbs.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lo, la]},
                        "properties": {"id": "jpl:" + d, "source": "jpl", "date_utc": d, "energy_kt": r.get("impact-e"),
                                       "radiated_j10": r.get("energy"), "alt_km": r.get("alt"), "vel_kms": r.get("vel"),
                                       "source_url": "https://cneos.jpl.nasa.gov/fireballs/", "license": ATTR["jpl"]}})
        out["fireballs"] = {"type": "FeatureCollection", "features": fbs}
    else:
        fbs = out["fireballs"]["features"]
    # --- starlink ---
    try:
        gp, sats, pts, vis, lit, t, ts, eph = starlink(now)
    except NoCache as e:
        print(f"::warning::starlink unavailable ({e}). Keeping the published block.")
        if not prev or "starlink" not in prev:
            raise SystemExit(0 if prev else 1)
        out["starlink"] = prev["starlink"]
        kept.append("starlink")
        pts = None
        vis = lit = 0
        tracks = prev["starlink"].get("fresh_trains") or []
    else:
        # fresh trains: COSPAR launch numbers (YYYY-NNN) rise monotonically, so the 4 highest Starlink launch ids of the
        # current year are the 4 most recent Starlink launches (young 'trains' are the classic UFO mis-report).
        from skyfield.api import wgs84
        ids = collections.Counter(r[3][:8] for r in pts if r[3])
        yr = str(now.year)
        fresh_launch_ids = sorted([k for k in ids if k.startswith(yr)], reverse=True)[:4]
        tracks = []
        for lid in fresh_launch_ids:
            group = [s for rec, s in sats if rec.get("OBJECT_ID", "").startswith(lid)]
            if not group: continue
            s = group[len(group) // 2]
            line = []
            for m in range(-45, 46, 3):
                sp = wgs84.subpoint_of(s.at(ts.from_datetime(now + dt.timedelta(minutes=m))))
                line.append([round(sp.longitude.degrees, 2), round(sp.latitude.degrees, 2)])
            tracks.append({"launch": lid, "n": len(group), "track": line})
        out["starlink"] = {"epoch_utc": out["generated_utc"], "total": len(pts), "sunlit": int(lit), "maybe_visible": int(vis), "points_fields": ["lon", "lat", "name"],
                           "points": [[x[0], x[1], x[4]] for x in pts if x[2]], "fresh_trains": tracks,
                           "note": "Possibly visible = satellite sunlit while the ground below is dark (Sun < -6\u00b0). Geometric proxy, not a brightness model."}
    if len(kept) == 3:
        print("skynow: every source failed open. Published file left unchanged.")
        return
    n = write_json(os.path.join(OUT, "skynow.json"), out)
    n_star = len(pts) if pts is not None else out["starlink"].get("total")
    print(f"skynow: starlink {n_star} (sunlit {lit}, maybe visible {vis}), trains {[(x['launch'], x['n']) for x in tracks]}, "
          f"launches {len(launches)} (recent {sum(f['properties']['when']=='recent' for f in launches)}), fireballs {len(fbs)}, {n} bytes")

if __name__ == "__main__":
    main()
