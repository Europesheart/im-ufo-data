"""NARA Project Blue Book file units (RG 341, T1206) -> stage/nara.geojson

Input : .cache/bluebook (downloaded at runtime, not committed: 90.8 MB)-597821.json  (https://catalog.archives.gov/medialz/bulk-downloads/uaps/JSON/catalog-export-597821.json,
        90.8 MB, 10,622 file units). The export is not strictly valid JSON (missing commas between
        records) so records are read one by one with raw_decode.
Method: title = "Place, State/Country, Month Year". Explicit lat/lon in the title is used directly;
        otherwise the place is geocoded OFFLINE against GeoNames cities500 constrained to the
        state/country. Rows without a parsable year or without a confident place match are DROPPED
        (counted, never invented). Several file units for the same place+month are merged (dup_of).
Rights: NARA: "downloadable and can be republished with attribution to NARA".
Blue Book metadata carries no official explanation per case, so no IFO flag/credibility is set.
"""
import json, re, collections, unicodedata
from common import *
from geonames import Geo, norm

MONTHS = {m: i + 1 for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"])}
US = {"alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO",
      "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
      "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
      "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
      "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
      "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY", "north carolina": "NC",
      "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
      "rhode island": "RI", "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
      "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
      "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC", "d c": "DC", "dc": "DC"}
ABBR = {"calif": "CA", "cal": "CA", "mass": "MA", "pa": "PA", "penn": "PA", "penna": "PA", "la": "LA", "n m": "NM",
        "nm": "NM", "n mex": "NM", "n mexico": "NM", "ga": "GA", "fla": "FL", "n y": "NY", "ny": "NY", "mo": "MO",
        "tenn": "TN", "tennesse": "TN", "tennassee": "TN", "mich": "MI", "n c": "NC", "nc": "NC", "va": "VA",
        "n j": "NJ", "nj": "NJ", "ill": "IL", "wash": "WA", "miss": "MS", "s c": "SC", "wisc": "WI", "wis": "WI",
        "md": "MD", "minn": "MN", "conn": "CT", "w va": "WV", "w virginia": "WV", "ala": "AL", "colo": "CO",
        "okla": "OK", "ind": "IN", "ky": "KY", "me": "ME", "n d": "ND", "s d": "SD", "ore": "OR", "ariz": "AZ",
        "nev": "NV", "n h": "NH", "ark": "AR", "tex": "TX", "s carolina": "SC", "l i new york": "NY",
        "long island ny": "NY", "t h": "HI", "kans": "KS", "kan": "KS", "nebr": "NE", "neb": "NE", "mont": "MT",
        "wyo": "WY", "ida": "ID", "vt": "VT", "del": "DE", "r i": "RI", "ri": "RI", "ia": "IA", "oh": "OH",
        "tx": "TX", "ca": "CA", "fl": "FL", "az": "AZ", "co": "CO", "wa": "WA", "or": "OR", "nd": "ND", "sd": "SD"}
COUNTRY_X = {"england": "GB", "scotland": "GB", "wales": "GB", "korea": "KR", "okinawa": "JP", "ussr": "RU",
             "newfoundland": "CA", "labrador": "CA", "nfld": "CA", "phillipines": "PH", "french morocco": "MA",
             "columbia": "CO", "west germany": "DE", "holland": "NL", "formosa": "TW", "south australia": "AU"}

def region_code(geo, s):
    k = norm(re.sub(r"\b(area|state)\b", "", s, flags=re.I))
    k = re.sub(r"\s*\(.*$", "", k).strip()
    if k in US: return ("US", US[k])
    if k in ABBR: return ("US", ABBR[k])
    if k in COUNTRY_X: return (COUNTRY_X[k], None)
    if k in geo.countries: return (geo.countries[k], None)
    if k in ("puerto rico",): return ("PR", None)
    if k in ("guam",): return ("GU", None)
    if k in ("bermuda",): return ("BM", None)
    if k in geo.admin1:
        cc, a1 = geo.admin1[k]
        if cc in ("CA", "AU", "DE", "JP", "MX", "GB"): return (cc, a1)
    return None

def coords(t):
    t2 = t.upper().replace("\u00b0", "DEG")
    m = re.search(r"(\d{1,2})\s*DEG\s*(\d{1,2})?'?\s*([NS])[\s\-/,]*(\d{1,3})\s*DEG\s*(\d{1,2})?'?\s*([EW])", t2)
    if m:
        la = int(m.group(1)) + int(m.group(2) or 0) / 60.0
        lo = int(m.group(4)) + int(m.group(5) or 0) / 60.0
    else:
        m = re.search(r"(\d{1,2}(?:\.\d+)?)\s*([NS])[\s\-/,]+(\d{1,3}(?:\.\d+)?)\s*([EW])\b", t2)
        if not m: return None
        la, lo = float(m.group(1)), float(m.group(3))
        m = type("M", (), {"group": lambda self, i, g=m: {3: g.group(2), 6: g.group(4)}[i]})()
    if m.group(3) == "S": la = -la
    if m.group(6) == "W": lo = -lo
    if abs(la) > 90 or abs(lo) > 180: return None
    return la, lo

CLEAN = [r"^\(.*?\)\s*", r"\bnear\b", r"\bvicinity( of)?\b", r"\barea\b", r"^\d+(\.\d+)?\s*(mi|miles|nm|km)\.?\s+[NSEW]{1,3}\s+of\s+",
         r"^[NSEW]{1,3}\s+of\s+", r"^[NSEW]{1,3}\s+", r"\(#?\d+\)", r"\(.*?\)", r"\b(afb|afs|a f b|air force base|air base|ab|nas|naval air station|airport|ap)\b",
         r"^(north|south|east|west)ern\s+", r"\boutskirts of\b", r"\bdowntown\b"]

def clean_place(p):
    s = p
    for rx in CLEAN:
        s = re.sub(rx, " ", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip(" .-#")

NARA_URL = "https://catalog.archives.gov/medialz/bulk-downloads/uaps/JSON/catalog-export-597821.json"

def ensure_inputs():
    import urllib.request
    for url, name in ((NARA_URL, "bluebook-597821.json"),
                      ("https://download.geonames.org/export/dump/cities500.zip", "cities500.zip"),
                      ("https://download.geonames.org/export/dump/admin1CodesASCII.txt", "admin1CodesASCII.txt"),
                      ("https://download.geonames.org/export/dump/countryInfo.txt", "countryInfo.txt")):
        p = os.path.join(CACHE, name)
        if not os.path.exists(p):
            print("download", url)
            urllib.request.urlretrieve(url, p)

def main():
    ensure_inputs()
    raw = open(os.path.join(CACHE, "bluebook-597821.json"), encoding="utf-8").read()
    dec, i, recs = json.JSONDecoder(), raw.index("[") + 1, []
    while True:
        i = re.compile(r"[\s,]*").match(raw, i).end()
        if i >= len(raw) or raw[i] == "]": break
        o, i = dec.raw_decode(raw, i); recs.append(o)
    geo = Geo()
    stats = collections.Counter(total=len(recs))
    groups = collections.OrderedDict()
    for r in recs:
        title = (r.get("title") or "").strip()
        t = re.sub(r"\s*-\s*Incident Number.*$", "", title, flags=re.I)
        m = re.search(r",\s*([A-Za-z]+)\.?\s*,?\s*(\d{4})\s*$", t)
        if not m or m.group(1).lower() not in MONTHS:
            m2 = re.search(r",\s*(\d{4})\s*$", t)
            if not m2: stats["no_date"] += 1; continue
            year, month, head = int(m2.group(1)), None, t[:m2.start()]
        else:
            year, month, head = int(m.group(2)), MONTHS[m.group(1).lower()], t[:m.start()]
        if not 1940 <= year <= 1970: stats["no_date"] += 1; continue
        if "[BLANK]" in head.upper() or "ILLEGIBLE" in head.upper() and len(head) < 14:
            stats["no_place"] += 1; continue
        c = coords(head)
        hit, prec, cc = None, None, None
        if c:
            hit, prec = (c[0], c[1], head.strip()), 10
            cc = None
        else:
            parts = [p.strip() for p in head.split(",") if p.strip()]
            reg = region_code(geo, parts[-1]) if len(parts) >= 2 else None
            places = parts[:-1] if reg else []
            if not reg and len(parts) == 1:
                # single token: accept only a city that is itself unambiguous? -> drop (no state given)
                stats["no_region"] += 1; continue
            if not reg:
                stats["no_region"] += 1; continue
            cc, a1 = reg
            for p in places + [p2 for p in places for p2 in re.split(r"\s+(?:and|&|to|-)\s+|/", p) if p2 != p]:
                q = clean_place(p)
                if len(q) < 3: continue
                g = geo.find(q, cc, a1)
                if g:
                    hit = (g[1], g[2], g[5]); prec = 25 if re.search(r"\b(near|of|area|vicinity)\b", p, re.I) else 10
                    if re.search(r"\b(afb|afs|air force|air base|nas)\b", p, re.I): prec = 25
                    break
            if not hit:
                stats["no_geocode"] += 1; continue
        key = (norm(head), year, month)
        naid = r.get("naId")
        if key in groups:
            groups[key]["properties"]["files"].append(naid); stats["dup_merged"] += 1; continue
        date = f"{year}-{month:02d}" if month else str(year)
        f = feature(hit[1], hit[0], id=f"nara:{naid}", source="nara",
                    source_url=f"https://catalog.archives.gov/id/{naid}", official=True,
                    date_utc=date, date_precision="month" if month else "year", year=year,
                    location_name=clip(head, 90), country=cc, geo_precision_km=prec,
                    summary=clip(f"Project Blue Book Fallakte (NARA T1206): {title}"),
                    classification={"scheme": "BLUEBOOK", "value": None, "label": "Blue Book Akte",
                                    "explanation": None},
                    credibility=None, ifo={"status": None, "flags": [], "score": None,
                                           "basis": "Blue-Book-Metadaten enthalten keine Fallerkl\u00e4rung"},
                    geocode="coords-in-title" if c else f"geonames:{hit[2]}",
                    license=ATTR["nara"], kind="ground")
        f["properties"]["files"] = [naid]
        groups[key] = f
    feats = list(groups.values())
    for f in feats:
        if len(f["properties"]["files"]) == 1: f["properties"].pop("files")
    stats["mapped"] = len(feats)
    n = write_json(os.path.join(STAGE, "nara.geojson"), fc(feats, source="nara", attribution=ATTR["nara"], stats=dict(stats)))
    print("nara:", dict(stats), n, "bytes")
    print(" by decade:", sorted(collections.Counter(f['properties']['year'] // 10 * 10 for f in feats).items()))

if __name__ == "__main__":
    main()
