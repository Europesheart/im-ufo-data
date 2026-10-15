"""Official US items (PURSUE + AARO) at REGION level -> stage/official.geojson

PURSUE: data-src/raw/pursue-uap-data.csv, the CSV the official page https://www.war.gov/UFO/ loads
        (https://www.war.gov/Portals/1/Interactive/2026/UFO/uap-data.csv?release=6v5, 450 rows,
        fetched 2026-10-15 with headless Chrome because curl gets 403). Fields used: Title, Agency,
        Release Date, Incident Date, Incident Location, Description Blurb, PDF | Image Link.
AARO  : items transcribed from https://www.aaro.mil/UAP-Cases/Official-UAP-Imagery/ and
        .../UAP-Case-Resolution-Reports/ (WebFetch 2026-10-15). Only items whose page text gives
        BOTH a year and a place/region are mapped.
Geo   : hand-set region anchor points (REGION below) with a large geo_precision_km; the widget draws
        a circle, not a pin. Items in space/Moon, 'Various', whole-US/North-America, multi-region or
        undated rows are NOT mapped (counted in stats).
Rights: U.S. federal works (17 U.S.C. 105). Attribution kept.
"""
import re, collections
import pandas as pd
from common import *

REGION = {  # name -> (lat, lon, precision_km, country)
 "western united states": (39.5, -114.0, 900, "US"), "westen united states": (39.5, -114.0, 900, "US"),
 "las vegas, nevada": (36.17, -115.14, 30, "US"), "centcom": (29.0, 48.0, 1500, None),
 "middle east": (29.0, 45.0, 1500, None), "iraq": (33.2, 43.7, 400, "IQ"), "arabian gulf": (27.0, 51.5, 300, None),
 "northeastern united states": (42.5, -73.5, 500, "US"), "syria": (35.0, 38.5, 300, "SY"),
 "yellow sea": (35.5, 123.5, 300, None), "colorado": (39.0, -105.5, 300, "US"),
 "eastern united states": (38.0, -79.0, 800, "US"), "washington, d.c.": (38.9, -77.04, 20, "US"),
 "texas": (31.0, -99.0, 500, "US"), "pacific ocean": (20.0, -150.0, 3000, None),
 "east china sea": (29.0, 125.0, 300, None), "colorado springs, colorado, u.s.": (38.83, -104.82, 20, "US"),
 "colorado springs, colorado": (38.83, -104.82, 20, "US"), "tremonton, utah": (41.71, -112.17, 15, "US"),
 "ussr": (55.75, 37.6, 2500, "SU"), "new mexico": (34.4, -106.1, 300, "US"), "bahia, brazil": (-12.5, -41.7, 400, "BR"),
 "atlantic ocean": (30.0, -50.0, 3000, None), "greece": (39.0, 22.0, 300, "GR"),
 "southeastern united states": (32.5, -84.0, 600, "US"), "north atlantic ocean": (45.0, -35.0, 2000, None),
 "cape kennedy, florida": (28.4, -80.6, 15, "US"), "boston, massachusetts": (42.36, -71.06, 20, "US"),
 "germany": (51.0, 10.4, 400, "DE"), "azerbaijan": (40.3, 47.7, 200, "AZ"), "budapest, hungary": (47.5, 19.04, 20, "HU"),
 "caribbean sea": (15.0, -75.0, 1200, None), "mediterranean sea": (35.5, 18.0, 1200, None),
 "gulf of oman": (24.8, 58.0, 200, None), "aegean sea": (38.5, 25.0, 250, None), "arabian sea": (16.0, 63.0, 800, None),
 "gulf of aden": (12.5, 47.5, 300, None), "strait of hormuz": (26.57, 56.25, 60, None), "virginia": (37.5, -78.8, 300, "US"),
 "united arab emirates": (24.3, 54.3, 200, "AE"), "kazakhstan": (48.0, 67.0, 1000, "KZ"), "houston, texas": (29.76, -95.37, 30, "US"),
 "netherlands": (52.2, 5.3, 150, "NL"), "detroit, mi": (42.33, -83.05, 20, "US"), "baku, azerbaijan": (40.41, 49.87, 20, "AZ"),
 "harare, zimbabwe": (-17.83, 31.05, 20, "ZW"), "hungary": (47.2, 19.4, 250, "HU"), "australia": (-25.0, 134.0, 2000, "AU"),
 "iran": (32.5, 53.7, 800, "IR"), "sweden": (62.0, 15.5, 600, "SE"), "djibouti": (11.6, 43.1, 80, "DJ"),
 "southern united states": (32.0, -90.0, 900, "US"), "japan": (36.2, 138.2, 600, "JP"), "eucom": (50.0, 15.0, 2500, None),
 "afghanistan": (34.0, 66.0, 500, "AF"), "midwestern united states": (41.5, -91.0, 800, "US"),
 "south china sea": (13.0, 114.0, 800, None), "gulf of america": (25.5, -90.0, 600, None),
 "new jersey, united states": (40.1, -74.6, 120, "US"), "washington state, united states": (47.4, -120.5, 300, "US"),
 "papua new guinea": (-6.5, 145.5, 500, "PG"), "georgia": (41.72, 44.79, 30, "GE"),  # row = Tbilisi cable
 "turkmenistan": (39.0, 59.5, 400, "TM"), "mexico": (23.6, -102.5, 1200, "MX"), "africom": (5.0, 20.0, 3000, None),
 "europe": (50.0, 15.0, 2500, None), "africa": (5.0, 20.0, 3000, None),
}
SKIP_LOC = {"moon", "low earth orbit", "low-earth orbit", "cislunar space", "various", "pacific time zone",
            "united states", "north america", "northcom", "indo-pacom", "indopacom", "montana, utah",
            "ladakh, nepal | sikkim, india | bhutam", "northeastern u.s.; afghanistan", "nan", ""}
NON_SIGHTING = re.compile(r"AAWSAP|DIRD|Committee|Correspondence|Progress Report|Analysis of|Presentation|Transcript|"
                          r"Statement of Objectives|Solicitation|Contract|Briefing|Memo(randum)? for", re.I)
MONTHS = {m: i + 1 for i, m in enumerate("january february march april may june july august september october november december".split())}

def parse_date(s):
    s = str(s).strip()
    if s in ("nan", "Undated", ""): return None, None, None
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})\b", s)
    if m:
        mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100: y += 1900 if y > 30 else 2000
        rng = "-" in s
        return y, f"{y}-{mo:02d}-{d:02d}", "day" if not rng else "range"
    m = re.match(r"^([A-Za-z]+),?\s+(\d{4})$", s)
    if m and m.group(1).lower() in MONTHS:
        y = int(m.group(2)); return y, f"{y}-{MONTHS[m.group(1).lower()]:02d}", "month"
    m = re.match(r"^(\d{4})$", s)
    if m: return int(s), s, "year"
    m = re.match(r"^(?:Late|Early|Mid)\s+(\d{4})$", s)
    if m: return int(m.group(1)), m.group(1), "year"
    m = re.search(r"\b(19\d{2}|20\d{2})\b", s)   # ranges like '1952-1953', 'June 3-7, 1965'
    if m: return int(m.group(1)), m.group(1), "range"
    m = re.match(r"^(\d{4})s$", s)
    if m: return int(m.group(1)), m.group(1), "decade"
    return None, None, None

def pursue(stats):
    d = pd.read_csv(os.path.join(RAW, "pursue-uap-data.csv"))
    out = []
    for _, r in d.iterrows():
        title = str(r["Title"]).strip()
        loc = re.sub(r"\s+", " ", str(r["Incident Location"])).strip()
        if NON_SIGHTING.search(title): stats["pursue_skip_document"] += 1; continue
        if loc.lower() in SKIP_LOC: stats["pursue_skip_location"] += 1; continue
        if loc.lower() not in REGION: stats["pursue_skip_unknown_region"] += 1; print("  ? region", loc); continue
        y, date, prec = parse_date(r["Incident Date"])
        if not y:
            m = re.search(r"\b(19\d{2}|20\d{2})\b", title)   # year in official title, e.g. '..., 2020'
            if m: y, date, prec = int(m.group(1)), m.group(1), "year"
        if not y: stats["pursue_skip_undated"] += 1; continue
        la, lo, km, cc = REGION[loc.lower()]
        link = str(r["PDF | Image Link"]).strip()
        rid = title.split(",")[0].strip()
        out.append(feature(lo, la, id="pursue:" + re.sub(r"\W+", "-", title)[:80], source="pursue",
            source_url=link if link.startswith("https://www.war.gov/") else "https://www.war.gov/UFO/",
            official=True, date_utc=date, date_precision=prec, year=y, location_name=loc, country=cc,
            geo_precision_km=km, media=str(r["Type"]).strip().lower() or None,
            summary=clip(r["Description Blurb"]) if str(r["Description Blurb"]) != "nan" else clip(title),
            title=clip(title, 120), agency=str(r["Agency"]).strip(), released=str(r["Release Date"]).strip(),
            classification={"scheme": "PURSUE", "value": "unresolved", "label": "PURSUE \u2013 unresolved (per DoW)",
                            "explanation": None},
            ifo={"status": "unresolved", "flags": [], "score": None, "basis": "PURSUE publishes unresolved cases only"},
            kind="region", license=ATTR["aaro"].replace("AARO", "PURSUE")))
        stats["pursue_mapped"] += 1
    return out

# AARO page items: (id, title, year, date, precision, region-key or (lat,lon,km), status, explanation)
AARO = [
 ("PR-018", "Unresolved UAP Report, Europe 2024", 2024, "2024", "year", "europe", "unresolved", None),
 ("PR-017", "Unresolved UAP Report, Europe 2024", 2024, "2024", "year", "europe", "unresolved", None),
 ("PR-016", "Resolved as Birds, Europe 2023", 2023, "2023", "year", "europe", "identified", "birds"),
 ("PR-015", "Unresolved UAP Report, Europe 2022", 2022, "2022", "year", "europe", "unresolved", None),
 ("PR-014", "Unresolved UAP Report, Europe 2022", 2022, "2022", "year", "europe", "unresolved", None),
 ("PR-013", "Unresolved UAP Report, Europe 2022", 2022, "2022", "year", "europe", "unresolved", None),
 ("PR-012", "Unresolved UAP Report, Europe 2022", 2022, "2022", "year", "europe", "unresolved", None),
 ("PR-011", "UAP Report Undergoing Analysis, Europe 2021", 2021, "2021", "year", "europe", "pending", None),
 ("PR-010", "UAP Report Resolved as a Balloon, Europe 2022", 2022, "2022", "year", "europe", "identified", "balloon"),
 ("PR-009", "UAP Report Resolved as a Balloon, Europe 2022", 2022, "2022", "year", "europe", "identified", "balloon"),
 ("PR-008", "Unresolved UAP Report, Europe 2022", 2022, "2022", "year", "europe", "unresolved", None),
 ("PR-007", "UAP Report Closed as Not Anomalous, Europe 2022", 2022, "2022", "year", "europe", "identified", "not anomalous (aircraft-like performance)"),
 ("PR-006", "UAP Report Resolved as a Balloon, Europe 2022", 2022, "2022", "year", "europe", "identified", "balloon"),
 ("PR-005", "UAP Report Resolved as a Balloon, Europe 2022", 2022, "2022", "year", "europe", "identified", "balloon"),
 ("PR-004", "UAP Report Resolved as a Balloon, Europe 2022", 2022, "2022", "year", "europe", "identified", "balloon"),
 ("PR-003", "Resolved as Migratory Birds, Africa 2023 (page text contradictory)", 2023, "2023", "year", "africa", "identified", "migratory birds (per title; the description calls the case unresolved)"),
 ("PR-002", "Resolved as Migratory Birds, Africa 2024", 2024, "2024", "year", "africa", "identified", "migratory birds"),
 ("PR-001", "Unresolved UAP Report, Africa 2022", 2022, "2022", "year", "africa", "unresolved", None),
 ("ME-RB-2024", "Middle East Red Balloon 2024", 2024, "2024", "year", "middle east", "identified", "foil balloon"),
 ("ME-2024", "Unresolved UAP Report: Middle East 2024", 2024, "2024", "year", "middle east", "unresolved", None),
 ("ME-2023", "Unresolved UAP Report: Middle East 2023", 2023, "2023", "year", "middle east", "unresolved", None),
 ("AL-TAQADDUM", "Al Taqaddum Object (Iraq)", 2017, "2017-10-23", "day", (33.34, 43.60, 10), "identified", "balloon cluster"),
 ("MT-ETNA", "Mt. Etna Object (Mediterranean south of Sicily)", 2018, "2018-12", "month", (36.9, 14.9, 150), "identified", "balloon (moderate confidence)"),
 ("PUERTO-RICO", "Puerto Rico Object (Aguadilla)", 2013, "2013-04-26", "day", (18.49, -67.13, 10), "identified", "two objects moving at wind speed, not anomalous"),
 ("GOFAST", "GoFast (Atlantic off Florida)", 2015, "2015-01", "month", (30.0, -79.0, 300), "identified", "not anomalous (AARO case resolution)"),
]
AARO_SKIPPED = ["Eglin (no year on page)", "Southeast Asia Triangles (no year)", "Western United States (no year)",
                "Atmospheric Wake (region contradictory: Middle East/Mediterranean vs. 'South Asian')",
                "Middle East Object (no year)", "Navy 2021 Flyby (no location)", "FLIR / Gimbal (neither place nor year on page)"]

def aaro(stats):
    out = []
    for cid, title, y, date, prec, where, status, expl in AARO:
        if isinstance(where, tuple): la, lo, km = where; loc = title
        else: la, lo, km, _ = REGION[where]; loc = where.title()
        url = ("https://www.aaro.mil/UAP-Cases/UAP-Case-Resolution-Reports/" if cid in ("AL-TAQADDUM", "MT-ETNA", "PUERTO-RICO", "GOFAST")
               else "https://www.aaro.mil/UAP-Cases/Official-UAP-Imagery/")
        out.append(feature(lo, la, id="aaro:" + cid, source="aaro", source_url=url, official=True,
            date_utc=date, date_precision=prec, year=y, location_name=loc, geo_precision_km=km, media="video",
            summary=clip(("AARO " + cid + ": " if cid.startswith("PR-") else "AARO: ") + title + (" \u2013 result: " + expl if expl else "")),
            title=title, agency="AARO",
            classification={"scheme": "AARO", "value": status, "label": {"identified": "AARO \u2013 resolved", "unresolved": "AARO \u2013 unresolved", "pending": "AARO \u2013 under analysis"}[status], "explanation": expl},
            ifo={"status": status, "flags": ["aaro_resolved"] if status == "identified" else [], "score": None, "basis": "AARO assessment"},
            kind="region" if km >= 100 else "site", license=ATTR["aaro"]))
        stats["aaro_mapped"] += 1
    stats["aaro_not_mapped"] = len(AARO_SKIPPED)
    return out

def main():
    stats = collections.Counter()
    feats = pursue(stats) + aaro(stats)
    n = write_json(os.path.join(STAGE, "official.geojson"), fc(feats, source="official", input_sha1=file_stamp(os.path.join(RAW, "pursue-uap-data.csv")),
                   stats=dict(stats), aaro_not_mapped=AARO_SKIPPED))
    print("official:", dict(stats), n, "bytes")

if __name__ == "__main__":
    main()
