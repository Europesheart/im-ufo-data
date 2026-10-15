"""Daily PURSUE CSV fetch (the file https://www.war.gov/UFO/ itself loads).

war.gov answers 403 to plain HTTP clients (seen 2026-10-15 from a datacenter IP). Order:
  1. plain urllib with browser-like headers
  2. headless Chromium via Playwright, if installed (loads the public page, captures the CSV response)
  3. give up: keep the last committed CSV, print a warning, exit 0.
The new CSV replaces the old one only if it parses and has >= 90 % of the old row count.
The CSV URL carries '?release=...'; the page is the source of truth, so step 2 also follows URL changes.
"""
import io, os, re, sys, urllib.request
from common import RAW

PAGE = "https://www.war.gov/UFO/"
CSV = "https://www.war.gov/Portals/1/Interactive/2026/UFO/uap-data.csv"
PATH = os.path.join(RAW, "pursue-uap-data.csv")
BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"

def via_urllib():
    try:
        req = urllib.request.Request(CSV, headers={"User-Agent": BROWSER_UA, "Referer": PAGE, "Accept": "text/csv,*/*"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:
        print("  urllib:", repr(e)); return None

def via_browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  playwright nicht installiert"); return None
    got = {}
    try:
        with sync_playwright() as p:
            exe = os.environ.get("CHROME_PATH")  # local testing with a system Chrome; Actions uses bundled Chromium
            b = p.chromium.launch(headless=True, **({"executable_path": exe} if exe else {}))
            pg = b.new_page(user_agent=BROWSER_UA)
            def on(r):
                if "uap-data.csv" in r.url and r.status == 200:
                    try: got["csv"] = r.text()
                    except Exception: pass
            pg.on("response", on)
            pg.goto(PAGE, wait_until="networkidle", timeout=90000)
            pg.wait_for_timeout(3000)
            b.close()
    except Exception as e:
        print("  browser:", repr(e))
    return got.get("csv")

def valid(text):
    import pandas as pd
    try:
        d = pd.read_csv(io.StringIO(text))
    except Exception:
        return 0
    return len(d) if {"Title", "Incident Location", "Incident Date"} <= set(d.columns) else 0

def main():
    old = open(PATH, encoding="utf-8", newline="").read() if os.path.exists(PATH) else ""
    old_n = valid(old) if old else 0
    for name, fn in (("urllib", via_urllib), ("browser", via_browser)):
        txt = fn()
        n = valid(txt) if txt else 0
        if n and n >= 0.9 * old_n:
            if txt == old:
                print(f"PURSUE unveraendert ({n} Zeilen, via {name})"); return 0
            open(PATH, "w", encoding="utf-8", newline="").write(txt)
            print(f"PURSUE aktualisiert via {name}: {old_n} -> {n} Zeilen"); return 0
        if txt:
            print(f"  {name}: Antwort unbrauchbar ({n} Zeilen)")
    print(f"::warning::PURSUE nicht abrufbar (vermutlich 403). Letzte Datei bleibt ({old_n} Zeilen).")
    return 0

if __name__ == "__main__":
    sys.exit(main())
