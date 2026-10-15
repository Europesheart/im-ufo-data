"""Polite once-daily GEIPAN export fetch.

- 2 requests per run (cases + testimonies), 15 s apart, identifying User-Agent.
- On 429/5xx: one retry after the Retry-After header (max 120 s), then give up.
- A download replaces the committed file only if it is a readable XLSX with >= 90 % of the old row count.
- Any failure keeps the last committed file and exits 0 (the workflow must not fail hard).
"""
import io, os, sys, time, urllib.request, urllib.error
from common import RAW, UA

EXPORTS = [("https://www.cnes-geipan.fr/fr/cnes/export/cas", "geipan_export_cas.xlsx"),
           ("https://www.cnes-geipan.fr/fr/cnes/export/temoignages", "geipan_export_temoignages.xlsx")]

def rows(blob):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(blob), read_only=True)
    return wb.active.max_row

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
            print(f"  ::warning::GEIPAN {name}: kein gueltiger Export, behalte letzte Datei"); continue
        try:
            new_n = rows(blob)
            old_n = rows(open(path, "rb").read()) if os.path.exists(path) else 0
        except Exception as e:
            print(f"  ::warning::GEIPAN {name}: XLSX unlesbar ({e!r}), behalte letzte Datei"); continue
        if old_n and new_n < 0.9 * old_n:
            print(f"  ::warning::GEIPAN {name}: nur {new_n} statt {old_n} Zeilen, behalte letzte Datei"); continue
        old = open(path, "rb").read() if os.path.exists(path) else b""
        # XLSX zips carry timestamps; compare the parsed sheet, not the bytes
        import pandas as pd
        same = bool(old) and pd.read_excel(io.BytesIO(old)).equals(pd.read_excel(io.BytesIO(blob)))
        if same:
            print(f"  unveraendert ({new_n} Zeilen)"); continue
        open(path, "wb").write(blob); changed += 1
        print(f"  aktualisiert: {old_n} -> {new_n} Zeilen")
    print("geipan changed files:", changed)
    return 0

if __name__ == "__main__":
    sys.exit(main())
