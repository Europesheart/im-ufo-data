"""GEIPAN (CNES) cases -> stage/geipan.geojson

Input : raw/geipan_export_cas.xlsx (https://www.cnes-geipan.fr/fr/cnes/export/cas)
        raw/geipan_export_temoignages.xlsx (shape + witness count per case)
Rights: 'Tous droits reserves (c) CNES'. Used by Patrice's decision (option C) with
        the source note ATTR['geipan'] on every popup and in the legend.
Case link pattern https://www.cnes-geipan.fr/fr/cas/<ID Etude de Cas> verified
        2026-10-15 (1951-06-00002 + one recent case, see README).
Privacy: only title (commune + dept), GEIPAN 'Identification' line and class
        explanation are kept. Free-text 'Details' and testimony texts are NOT exported;
        honorific+name patterns are stripped defensively.
"""
import re, collections
import pandas as pd
from common import *
from geipan_gloss import GLOSS

CLASS_TXT = {
    "A": "A \u2013 clearly identified",
    "B": "B \u2013 probably identified",
    "C": "C \u2013 not identifiable (insufficient data)",
    "D": "D \u2013 unexplained after investigation",
}
IFO_STATUS = {"A": "identified", "B": "probable", "C": "insufficient", "D": "unexplained"}

SHAPES = [  # GEIPAN 'Forme globale' -> normalised shape key
    ("Sph\u00e9rique", "sphere"), ("Rond", "circle"), ("Ovo\u00efde", "oval"), ("Ovale", "oval"),
    ("Ponctuel", "light"), ("Multiples traits", "lights"), ("Faisceau", "beam"),
    ("Conique", "cone"), ("Cylindrique", "cylinder"), ("Cigare", "cigar"),
    ("Triangulaire", "triangle"), ("Rectangulaire", "rectangle"), ("Disque", "disc"),
    ("Halo", "light"),
]
NAME_RX = re.compile(r"\b(?:M\.|Mme|Mlle|Mr|Monsieur|Madame|Mademoiselle)\s+[A-Z\u00c0-\u00dd][\w\u00c0-\u00ff'-]+(?:\s+[A-Z\u00c0-\u00dd][\w\u00c0-\u00ff'-]+)?")

def shape_of(v):
    v = str(v)
    for k, s in SHAPES:
        if k in v:
            return s
    return None

def strip_names(s):
    s = NAME_RX.sub(lambda m: m.group(0) if m.group(0).split()[1] in ("Observation", "Observations", "Le", "La", "Les", "Probable", "Ce", "Cette") else "[name removed]", s)
    return s

def parse_date(s):
    m = re.match(r"(\-\-|\d{2})/(\-\-|\d{2})/(\d{4})", str(s))
    if not m:
        return None, None
    d, mo, y = m.groups()
    if mo == "--":
        return y, "year"
    if d == "--":
        return f"{y}-{mo}", "month"
    return f"{y}-{mo}-{d}", "day"

def place_of(title):
    t = re.sub(r"^\[[^\]]*\]\s*", "", str(title))
    t = re.sub(r"\s+[\d\-]{2}\.[\d\-]{2}\.\d{4}.*$", "", t)
    return t.strip()

def main():
    cas = pd.read_excel(os.path.join(RAW, "geipan_export_cas.xlsx"))
    tem = pd.read_excel(os.path.join(RAW, "geipan_export_temoignages.xlsx"))
    tem["case"] = tem["T\u00e9moignage"].astype(str).str.replace(r"\s+T\d+\s*$", "", regex=True).str.strip()
    wit = tem.groupby("case").size().to_dict()
    shp = {}
    for c, g in tem.groupby("case"):
        cnt = collections.Counter(s for s in (shape_of(v) for v in g["Forme globale"]) if s)
        if cnt:
            shp[c] = cnt.most_common(1)[0][0]
    feats, skipped = [], 0
    for _, r in cas.iterrows():
        lat, lon = r["Latitude"], r["Longitude"]
        if pd.isna(lat) or pd.isna(lon):
            skipped += 1; continue
        cid = str(r["ID Etude de Cas"]).strip()
        cls = str(r["Classification"]).strip()
        date, prec = parse_date(r["Date d'observation"])
        title = str(r["Titre du Cas"]).strip()
        kind = str(r["Type de cas"])
        expl = clip(r["Ph\u00e9nom\u00e8ne"], 120) if not pd.isna(r["Ph\u00e9nom\u00e8ne"]) else None
        flags = []
        if cls in ("A", "B"):
            flags.append("geipan_" + cls)
        feats.append(feature(float(lon), float(lat),
            id="geipan:" + cid, source="geipan",
            source_url="https://www.cnes-geipan.fr/fr/cas/" + cid,
            official=True, date_utc=date, date_precision=prec,
            year=int(r["Ann\u00e9e"]) if not pd.isna(r["Ann\u00e9e"]) else (int(date[:4]) if date else None),
            location_name=place_of(title) + (" \u00b7 " + str(r["D\u00e9partement"]) if not pd.isna(r["D\u00e9partement"]) else ""),
            country="FR", geo_precision_km=11,  # GEIPAN publishes 0.01-0.1 deg; commune centroid level
            shape=shp.get(title), witnesses=int(wit.get(title, 0)) or None,
            media=("docs" if str(r["Cas contenant des documents"]) == "Oui" else None),
            summary=clip(strip_names(str(r["Identification"]))),
            classification={"scheme": "GEIPAN", "value": cls, "label": CLASS_TXT.get(cls), "explanation": expl, "explanation_en": GLOSS.get(str(r["Ph\u00e9nom\u00e8ne"]).strip()) if expl else None},
            credibility=None,
            ifo={"status": IFO_STATUS.get(cls), "flags": flags, "score": None,
                 "basis": "GEIPAN classification (CNES)"},
            kind=("aero" if "a\u00e9ro" in kind.lower() else "maritime" if "marit" in kind.lower() else "ground"),
            license=ATTR["geipan"]))
    n = write_json(os.path.join(STAGE, "geipan.geojson"), fc(feats, source="geipan", attribution=ATTR["geipan"], input_sha1=file_stamp(os.path.join(RAW, "geipan_export_cas.xlsx"))))
    print(f"geipan: {len(feats)} features, {skipped} skipped (no coords), {n} bytes")
    print(" classes:", collections.Counter(f['properties']['classification']['value'] for f in feats))
    print(" shapes :", collections.Counter(f['properties']['shape'] for f in feats).most_common(8))

if __name__ == "__main__":
    main()
