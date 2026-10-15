# im-ufo-data

Data hosting for the **UFO world map** widget on information-machine.blogspot.com.
GitHub Pages serves `docs/` → `https://europesheart.github.io/im-ufo-data/`. GitHub Actions refreshes the data.

| Path | What |
|---|---|
| `docs/data/meta.json` | counts, attributions, decade index (widget loads this first) |
| `docs/data/skynow.json` | Starlink visibility, launches ±30 d, fireballs 365 d (every 2 h) |
| `docs/data/archive/<decade>.geojson` | GEIPAN + Blue Book + PURSUE + AARO, schema RESEARCH.md §5.2 (lazy-loaded per decade) |
| `docs/index.html` + `docs/hud.css` | test page: the widget with relative data (`./data/`) |
| `docs/.nojekyll` | serve files as-is |
| `widget/ufo-world-map.html` | the Blogger widget; edit only the marked `DATA_BASE` line |
| `data-src/raw/` | committed inputs = last good copy (GEIPAN XLSX, PURSUE CSV) |
| `data-src/stage/` | per-layer GeoJSON (`nara.geojson` is committed; NARA is rebuilt manually) |
| `pipeline/` | Python 3.12, `requirements.txt` |

## Workflows (`permissions: contents: write`, shared `concurrency: data-commit`, commit only if `git diff --cached` is non-empty)

| Workflow | When | Does | Failure behaviour |
|---|---|---|---|
| `skynow.yml` | every 2 h at :17 UTC + manual | CelesTrak (cached 2 h via `actions/cache`), LL2, JPL → `skynow.json`, `meta.json` | an API failure fails the run; the last published file stays online |
| `daily.yml` | 04:41 UTC + manual | GEIPAN export (2 requests, 15 s apart, one retry on 429), PURSUE CSV (urllib, then headless Chromium) → rebuild archive | 403/429/bad file → keep the committed file, emit `::warning::`, job stays green |
| `nara.yml` | manual only | downloads the 90.8 MB NARA export + GeoNames cities500 at runtime (not committed), rebuilds Blue Book | — |

All outputs are deterministic (no clock stamps in archive files), so an unchanged input produces no commit.
`skynow.json` changes every run (satellite positions). That is about 21 KB gzip per commit, roughly 180 MB of git history per year.
If that becomes a problem, change the cron to `17 */2 * * *` or move to `actions/deploy-pages` artifacts.

## Local run

```
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
bash pipeline/run_skynow.sh      # hourly part
bash pipeline/run_daily.sh       # GEIPAN + PURSUE (+ playwright optional: pip install playwright && python -m playwright install chromium)
bash pipeline/run_nara.sh        # Blue Book (90.8 MB download)
```

## CORS
GitHub Pages sends `Access-Control-Allow-Origin: *`; checked 2026-10-15 on `pages.github.com` and `octocat.github.io`.
So `fetch()` from `information-machine.blogspot.com` works without a proxy.

## Sources & rights
- **GEIPAN:** © CNES/GEIPAN, *Tous droits réservés*. Used with the note "© CNES/GEIPAN – source: geipan.fr, educational use"; this is the owner's decision, not a licence.
- **NARA:** republish with attribution.
- **PURSUE / AARO:** U.S. federal works.
- **CelesTrak · Launch Library 2 · NASA/JPL CNEOS · GeoNames:** CC BY 4.0.

NUFORC, MUFON and other civilian databases are **not** included (licence).
