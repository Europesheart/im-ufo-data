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

def get(url, cache_name=None, max_age_s=0):
    path = os.path.join(CACHE, cache_name) if cache_name else None
    if path and os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_s:
        return json.load(open(path, encoding="utf-8"))
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        data = json.loads(r.read().decode("utf-8"))
    if path: json.dump(data, open(path, "w", encoding="utf-8"))
    return data

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

def main():
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    out = {"generated_utc": now.isoformat().replace("+00:00", "Z"), "attribution": [ATTR["celestrak"], ATTR["ll2"], ATTR["jpl"]],
           "cors": {"celestrak": "ACAO: * (Client-Fetch technisch m\u00f6glich, aber CelesTrak bittet um max. 1 Abruf / 2 h -> nur Pipeline)",
                    "ll2": "ACAO: * (Widget l\u00e4dt Starts live nach, Fallback = diese Datei; Limit 15 Abrufe/h pro IP)",
                    "jpl": "kein ACAO-Header -> nur Pipeline"}}
    # --- launches (LL2) ---
    ll2 = "https://ll.thespacedevs.com/2.3.0/launches/"
    prev = get(ll2 + "previous/?limit=40&mode=normal", "ll2-previous.json", 3600)   # date filters time out server-side
    time.sleep(2)
    up = get(ll2 + "upcoming/?limit=40&mode=normal", "ll2-upcoming.json", 3600)
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
    lo_t, hi_t = (now - dt.timedelta(days=30)).isoformat(), (now + dt.timedelta(days=30)).isoformat()
    def within(x): return lo_t[:19] <= (x.get("net") or "")[:19] <= hi_t[:19]
    launches = [f for f in (L(x, "recent") for x in prev.get("results", []) if within(x)) if f] + \
               [f for f in (L(x, "upcoming") for x in up.get("results", []) if within(x)) if f]
    out["launches"] = {"type": "FeatureCollection", "features": launches}
    # --- fireballs (JPL) ---
    fb = get("https://ssd-api.jpl.nasa.gov/fireball.api?date-min=" + (now - dt.timedelta(days=365)).strftime("%Y-%m-%d") + "&req-loc=true", "jpl-fireball.json", 3600)
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
    # --- starlink ---
    gp, sats, pts, vis, lit, t, ts, eph = starlink(now)
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
                       "note": "Sichtbar m\u00f6glich = Satellit in der Sonne, Boden darunter dunkel (Sonne < -6\u00b0). Geometrischer Proxy, kein Helligkeitsmodell."}
    n = write_json(os.path.join(OUT, "skynow.json"), out)
    print(f"skynow: starlink {len(pts)} (sunlit {lit}, maybe visible {vis}), trains {[(x['launch'], x['n']) for x in tracks]}, "
          f"launches {len(launches)} (recent {sum(f['properties']['when']=='recent' for f in launches)}), fireballs {len(fbs)}, {n} bytes")

if __name__ == "__main__":
    main()
