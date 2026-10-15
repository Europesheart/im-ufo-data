# Anleitung: UFO-Karten-Daten auf GitHub Pages

Du brauchst ca. 15 Minuten. Du brauchst kein Terminal, alles geht im Browser.
Account: Europesheart, Repo: https://github.com/Europesheart/im-ufo-data

## 1. Repo anlegen
1. Gehe auf https://github.com/new.
2. Trage als Repository name `im-ufo-data` ein und wähle **Public**. Pages ist im Gratis-Konto nur für öffentliche Repos verfügbar.
3. Setze keinen Haken bei README, .gitignore oder License. Klicke auf **Create repository**.

## 2. Dateien hochladen
**Variante A, Web-Upload:**
1. Entpacke `im-ufo-data-repo.zip`.
2. Klicke im neuen Repo auf **uploading an existing file**.
3. Ziehe den **Inhalt** des Ordners `im-ufo-data` ins Fenster, also `docs`, `pipeline`, `data-src`, `widget`, `README.md` usw., nicht den Ordner selbst.
4. Klicke auf **Commit changes**.

⚠️ Beim Web-Upload fehlen oft die versteckten Ordner und Dateien, deren Name mit einem Punkt beginnt: `.github` und `docs/.nojekyll`.
- Prüfe nach dem Upload, ob `.github/workflows/` im Repo zu sehen ist.
- Fehlt der Ordner, geh auf **Add file → Create new file** und gib als Name `.github/workflows/skynow.yml` ein.
- Kopiere den Inhalt der Datei aus dem ZIP hinein.
- Mach dasselbe für `daily.yml` und `nara.yml`.
- `docs/.nojekyll` legst du genauso an, die Datei bleibt leer.

**Variante B, git** (lädt auch die versteckten Dateien automatisch hoch):
```
cd im-ufo-data
git init -b main && git add -A && git commit -m "init"
git remote add origin https://github.com/Europesheart/im-ufo-data.git
git push -u origin main
```

## 3. Pages einschalten
1. Öffne **Settings → Pages**.
2. Wähle unter **Build and deployment → Source** die Option **Deploy from a branch**.
3. Stelle Branch **main** und Ordner **/docs** ein und klicke auf **Save**.
4. Nach 1–2 Minuten steht oben: „Your site is live at https://europesheart.github.io/im-ufo-data/“.

## 4. Actions einschalten und Schreibrecht geben
1. Öffne den Tab **Actions**. Wenn GitHub fragt, klicke auf „I understand my workflows, go ahead and enable them“.
2. Zur Sicherheit: Öffne **Settings → Actions → General → Workflow permissions**, wähle **Read and write permissions** und klicke auf **Save**.
   Die Workflows verlangen `contents: write` zwar selbst. Falls ein Lauf trotzdem mit „Permission denied“ beim Push abbricht, liegt es an dieser Einstellung.
3. Teste einmal von Hand:
   - Öffne **Actions → skynow (every 2h)** und klicke auf **Run workflow**.
   - Mach dasselbe mit **daily (GEIPAN + PURSUE)**.

## 5. Prüfen, ob es läuft
- Öffne `https://europesheart.github.io/im-ufo-data/data/meta.json`. Dort muss JSON mit `"counts"` erscheinen.
- Öffne `https://europesheart.github.io/im-ufo-data/`. Dort muss die Karte mit Zahlen erscheinen. Das ist die Testseite.
- Im Tab **Actions** muss jeder Lauf grün sein.
  - Ein gelbes ⚠️ bei „daily“ ist normal. Es bedeutet, dass GEIPAN (429) oder war.gov (403) gerade gesperrt hat und die letzte Datei bleibt.
- In der Commit-Liste sollte ungefähr alle 2 Stunden ein Commit „skynow: …“ vom Bot auftauchen.
- Auf der Karte unter **24H** zeigt der Wert **AGE** das Alter der Daten. Er sollte unter etwa 2 h liegen.

## 6. Widget im Blog
1. Öffne `widget/ufo-world-map.html`.
2. Ändere **nur** die markierte Zeile:
   ```
   var DATA_BASE = "https://europesheart.github.io/im-ufo-data/data/";
   ```
   Beispiel für den Benutzernamen `patrice`: `https://patrice.github.io/im-ufo-data/data/`. Der abschliessende `/` muss bleiben.
3. Steht dort noch der Platzhalter, nimmt das Widget relative Daten (`./data/`). Das funktioniert nur in der Preview und auf der Testseite, **nicht** im Blog.

**CORS:** GitHub Pages sendet `Access-Control-Allow-Origin: *`. Ich habe das am 15.10.2026 an github.io-Seiten geprüft. Der Blog darf die Daten deshalb direkt laden. Einen Proxy brauchst du nicht.

## Gut zu wissen
- **GEIPAN** wird einmal pro Tag höflich abgefragt: 2 Abrufe, 15 s Pause, 1 Wiederholung. Bei 429 bleibt die letzte Datei im Repo, und der Lauf schlägt nicht fehl.
- **PURSUE (war.gov)** blockt Server oft mit 403. Der Lauf versucht es danach mit einem Headless-Browser. Klappt beides nicht, bleibt die letzte CSV. Neue PURSUE-Tranchen kommen dann erst, wenn ein Abruf wieder durchgeht.
- **Blue Book** ist ein abgeschlossenes Archiv. Es wird nur von Hand neu gebaut: **Actions → nara (manual) → Run workflow**.
- **Repo-Grösse:** Sky Now läuft alle 2 Stunden (ca. 90 MB Git-Historie pro Jahr). Stündlich ginge mit `cron: "17 * * * *"` in `.github/workflows/skynow.yml`.
- **GitHub pausiert geplante Workflows bei öffentlichen Repos nach 60 Tagen ohne Aktivität.** Ob die Bot-Commits als Aktivität zählen, ist nicht garantiert. Kommt eine Mail „scheduled workflows disabled“, schaltest du sie im Tab **Actions** mit einem Klick wieder ein. Ein eigener Commit alle paar Wochen verhindert das sicher.
