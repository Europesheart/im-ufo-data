"""Offline geocoder on GeoNames cities500 (CC BY 4.0, geonames.org). No network calls."""
import csv, io, os, re, zipfile, unicodedata, collections
from common import CACHE

def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\bst\.?\s", "saint ", s)
    s = re.sub(r"\bft\.?\s", "fort ", s)
    s = re.sub(r"\bmt\.?\s", "mount ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

class Geo:
    def __init__(self):
        self.by = collections.defaultdict(list)     # name -> [(pop, lat, lon, cc, a1, name)]
        self.alt = collections.defaultdict(list)
        z = zipfile.ZipFile(os.path.join(CACHE, "cities500.zip"))
        with z.open("cities500.txt") as f:
            for row in csv.reader(io.TextIOWrapper(f, "utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE):
                rec = (int(row[14] or 0), float(row[4]), float(row[5]), row[8], row[10], row[1])
                keys = {norm(row[1]), norm(row[2])}
                for k in keys:
                    self.by[k].append(rec)
                for a in row[3].split(","):
                    ka = norm(a)
                    if ka and ka not in keys and len(ka) > 3:
                        self.alt[ka].append(rec)
        self.countries = {}
        for line in open(os.path.join(CACHE, "countryInfo.txt"), encoding="utf-8"):
            if line.startswith("#"): continue
            p = line.rstrip("\n").split("\t")
            if len(p) > 4: self.countries[norm(p[4])] = p[0]
        self.admin1 = {}
        for line in open(os.path.join(CACHE, "admin1CodesASCII.txt"), encoding="utf-8"):
            p = line.rstrip("\n").split("\t")
            cc, a1 = p[0].split(".")
            self.admin1.setdefault(norm(p[2]), (cc, a1))

    def find(self, place, cc=None, a1=None):
        k = norm(place)
        for table in (self.by, self.alt):
            c = [r for r in table.get(k, []) if (cc is None or r[3] == cc) and (a1 is None or r[4] == a1)]
            if c:
                return max(c, key=lambda r: r[0])
        return None
