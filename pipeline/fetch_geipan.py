"""Polite once-daily GEIPAN export fetch.

- 2 requests per run (cases + testimonies), 15 s apart, identifying User-Agent.
- On 429/5xx: one retry after the Retry-After header (max 120 s), then give up.
- A download replaces the committed file only if it is a readable XLSX, still has the
  columns the builder needs (French headers or the English aliases), and has >= 90 % of the old row count.
- Any failure keeps the last committed file and exits 0 (the workflow must not fail hard).
"""
import io, os, sys, time, urllib.request, urllib.error
from common import RAW, UA
from geipan import CAS_REQUIRED, TEM_REQUIRED, missing_columns, normalize_export

EXPORTS = [("https://www.cnes-geipan.fr/fr/cnes/export/cas", "geipan_export_cas.xlsx"),
           ("https://www.cnes-geipan.fr/fr/cnes/export/temoignages", "geipan_export_temoignages.xlsx")]

REQUIRED = {"geipan_export_cas.xlsx": CAS_REQUIRED, "geipan_export_temoignages.xlsx": TEM_REQUIRED}

def frame(blob, name):
    import pandas as pd
    df = pd.read_excel(io.BytesIO(blob))
    return normalize_export(df) if name == "geipan_export_cas.xlsx" else df

def fetch(url):
    for attempt in (1, 2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt == 1:
                wait = min(120, int(e.headers.get("Retry-After", "60") or 60))
                print(f"  {e.code} -> retry in {wait}s"); time.sleep(wait); continue
            print(f"  HTTP {e.code}"); return None
        except Exception as e:
            print(f"  error {e!r}"); return None
    return None

def main():
    changed = 0
    for i, (url, name) in enumerate(EXPORTS):
        if i: time.sleep(15)
        path = os.path.join(RAW, name)
        print("GEIPAN", url)
        blob = fetch(url)
        if not blob or blob[:2] != b"PK":
            print(f"  ::warning::GEIPAN {name}: no valid export, keeping last file"); continue
        try:
            new = frame(blob, name)
        except Exception as e:
            print(f"  ::warning::GEIPAN {name}: XLSX unreadable ({e!r}), keeping last file"); continue
        missing = missing_columns(new, REQUIRED[name])
        if missing:
            print(f"  ::warning::GEIPAN {name}: missing columns {missing}, keeping last file"); continue
        old_blob = open(path, "rb").read() if os.path.exists(path) else b""
        try:
            old = frame(old_blob, name) if old_blob else None
        except Exception as e:
            print(f"  ::warning::GEIPAN {name}: last file unreadable ({e!r})"); old = None
        old_n = 0 if old is None else len(old)
        new_n = len(new)
        if old_n and new_n < 0.9 * old_n:
            print(f"  ::warning::GEIPAN {name}: only {new_n} instead of {old_n} rows, keeping last file"); continue
        # XLSX zips carry timestamps; compare the parsed sheet (headers normalised), not the bytes
        if old is not None and new.equals(old):
            print(f"  unchanged ({new_n} rows)"); continue
        open(path, "wb").write(blob); changed += 1
        print(f"  updated: {old_n} -> {new_n} rows")
    print("geipan changed files:", changed)
    return 0

if __name__ == "__main__":
    sys.exit(main())
