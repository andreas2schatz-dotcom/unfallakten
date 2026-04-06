# Bug- & Fix-Dokumentation – Kanzlei Koch, Schatz & Kollegen
# Unfallakten-Verwaltungssystem
> Alle bekannten Bugs, ihre Ursachen und Fixes – damit Fehler nicht wiederholt werden.
> Format: [SESSION] Titel | Ursache | Fix | Lerneffekt

---

## Behobene Bugs

---

### [v8] `abrechnungsschreiben.id` = NULL bei allen Inserts
**Datei:** `backend/db/schema_manager.py` (Migration 5)
**Symptom:** DELETE per `WHERE id=?` traf nie etwas → Phantom-Einträge in der Liste
**Ursache:** `abrechnungsschreiben.id` hatte Typ `INT` ohne `PRIMARY KEY` (Schreibfehler in Migration 5)
**Fix:** Tabelle neu aufgebaut via `fix_db.py` im Container. Schema-Version 16.
```python
# FALSCH (Migration 5):
"id INT"

# RICHTIG:
"id INTEGER PRIMARY KEY"
```
**Fix-Kommando:**
```powershell
docker cp fix_db.py unfallakten-backend-dev:/app/fix_db.py
docker exec unfallakten-backend-dev python3 /app/fix_db.py
docker restart unfallakten-backend-dev
```
**Lerneffekt:** Bei `DELETE` oder `UPDATE WHERE id=?` immer prüfen ob `id` wirklich `INTEGER PRIMARY KEY` ist. SQLite erstellt bei `INT` (ohne PRIMARY KEY) keinen Autoinkrement.

---

### [v9] `finde_akte()` sucht Spalte `id` in `unfallakte` (existiert nicht mehr)
**Datei:** `backend/email_import/parser.py`
**Symptom:** `OperationalError: no such column: id` beim E-Mail-Import
**Ursache:** Nach Migration 5 hat `unfallakte` keinen Integer-PK mehr – PK ist `az TEXT`
```python
# FALSCH:
row = db_conn.execute("SELECT id FROM unfallakte WHERE ...").fetchone()
return row["id"]

# RICHTIG:
row = db_conn.execute(
    "SELECT az FROM unfallakte WHERE UPPER(REPLACE(az, '/', '')) LIKE ?",
    (az_basis + "%",)
).fetchone()
return row["az"]   # Rückgabe ist TEXT, nicht INT
```
**Lerneffekt:** Nach jeder Schemamigration alle Stellen prüfen, die `id` aus `unfallakte` lesen. PK = `az TEXT` seit Migration 5.

---

### [v9] `email_import_log.akte_id` als INTEGER FK (falsch seit Migration 5)
**Datei:** `backend/db/schema_manager.py`
**Symptom:** JOIN auf `unfallakte.id` schlägt fehl; `akte_id`-Typ-Mismatch
**Ursache:** `email_import_log.akte_id` war noch `INTEGER REFERENCES unfallakte(id)`
**Fix:** Migration 17 – `akte_id` auf `TEXT REFERENCES unfallakte(az)`
**Lerneffekt:** Immer wenn `unfallakte` als FK referenziert wird: `TEXT REFERENCES unfallakte(az)`, niemals `INTEGER`.

---

### [v9] SB-Kürzel im AZ stört Matching (`31/21AS` ≠ `31/21`)
**Datei:** `backend/email_import/parser.py`
**Symptom:** E-Mail mit Betreff `Az. 31/21AS` wird keiner Akte zugeordnet
**Ursache:** Versicherungen hängen Sachbearbeiterkürzel ans AZ. Normierung entfernte Kürzel nicht.
```python
# FALSCH:
def _normiere_az(az): return az.upper()

# RICHTIG:
def _normiere_az(az):
    import re
    az = az.strip().upper()
    az_basis = re.sub(r'[A-Z]{2,3}$', '', az).strip()
    return az_basis if '/' in az_basis else az
```
**Lerneffekt:** AZ-Matching immer auf Basis-AZ normieren (ohne Kürzel). Gilt für Betreff, Body und RA-Micro-Abgleich.

---

### [v9] JOIN in Import-Log auf `unfallakte.id` (existiert nicht)
**Datei:** `backend/email_import/import_service.py`
**Symptom:** `OperationalError` beim Abrufen des Import-Logs
```python
# FALSCH:
LEFT JOIN unfallakte a ON l.akte_id = a.id

# RICHTIG:
LEFT JOIN unfallakte a ON l.akte_id = a.az
```
**Lerneffekt:** Alle JOINs auf `unfallakte` immer über `az`, nicht `id`.

---

### [v10] E-Mail mit UTF-16 LE Encoding (Outlook)
**Datei:** `backend/email_import/parser.py`
**Symptom:** E-Mail-Body erscheint als Zeichensalat / leerer String
**Ursache:** Outlook sendet manchmal `text/plain` mit BOM `\xff\xfe` → `decode('utf-8')` liefert Müll
**Fix:** BOM-Erkennung, dann `decode('utf-16')`
```python
if raw_bytes[:2] in (b'\xff\xfe', b'\xfe\xff'):
    text = raw_bytes.decode('utf-16')
else:
    text = raw_bytes.decode('utf-8', errors='replace')
```
**Lerneffekt:** E-Mail-Decoding nie ohne BOM-Prüfung. Outlook ist ein häufiger Absender in Kanzlei-Kontext.

---

### [v10] E-Mail ohne `text/plain`-Teil (eingebettete Bilder)
**Datei:** `backend/email_import/parser.py`
**Symptom:** Body leer, obwohl E-Mail sichtbaren Text hat
**Ursache:** E-Mail besteht nur aus `text/html`-Teil (eingebettete Bilder, kein Plain-Text)
**Fix:** HTML-Fallback implementiert: `_html_zu_text()` strippt Tags
**Lerneffekt:** Immer HTML-Fallback vorhalten wenn `text/plain` fehlt.

---

### [v10] Mailto-Format bricht E-Mail-Regex
**Datei:** `backend/email_import/parser.py`
**Symptom:** Absender-Adresse nicht erkannt, Matching schlägt fehl
**Ursache:** Format `<email <mailto:email>>` ist kein Standard-RFC-Format
**Fix:** Bereinigung vor Regex-Suche
**Lerneffekt:** Absender-Felder immer vor dem Matching bereinigen/normalisieren.

---

### [v10] `dateityp='eml'` nicht in `GUELTIGE_DATEITYPEN`
**Datei:** `backend/pdf/upload_service.py` (o.ä.)
**Symptom:** `.eml`-Dateien wurden mit `status='fehler'` gespeichert
**Ursache:** `GUELTIGE_DATEITYPEN = ('pdf', 'docx', 'jpg', 'png')` – `eml` fehlte
**Fix:** `.eml`-Dateien als `dateityp='docx'` speichern (Workaround) oder `eml` zur Liste hinzufügen
**Lerneffekt:** Bei neuen Dateitypen sofort `GUELTIGE_DATEITYPEN` erweitern.

---

### [v10] `EMAIL_MAX_FETCH=5` – nur 5 von 7 E-Mails abgeholt
**Datei:** `.env`
**Symptom:** Fehlende E-Mails ohne Fehlermeldung – komplett unsichtbares Problem
**Ursache:** `EMAIL_MAX_FETCH` war versehentlich auf `5` gesetzt
**Fix:** `EMAIL_MAX_FETCH=50`
**Lerneffekt:** `EMAIL_MAX_FETCH` immer auf realistischen Wert setzen (≥50). Kleiner Wert erzeugt keinen Fehler, schneidet aber stillschweigend ab.

---

### [v10] App.jsx Korruption durch Patch
**Datei:** `frontend/src/App.jsx`
**Symptom:** App startet nicht mehr / Syntaxfehler nach Patch
**Ursache:** Patch wurde auf bereits korrumpierter Datei angewendet
**Fix:** Immer vom hochgeladenen Original aus dem Container starten
**Prüfung nach Patch:**
```python
assert ")}allback" not in content
assert "export default function App" in content
```
**Lerneffekt:** Vor jedem Patch App.jsx aus Container holen:
```powershell
docker cp unfallakten-frontend-dev:/app/src/App.jsx ./App.jsx
```

---

### [v11] `onInAkteImportiert is not defined` beim E-Mail-Import
**Datei:** `frontend/src/App.jsx`
**Symptom:** Klick auf „In Akte importieren" wirft ReferenceError
**Ursache:** `onInAkteImportiert` wurde als Prop an `EmailKarte` übergeben, fehlte aber in der Props-Destrukturierung
```javascript
// FALSCH:
function EmailKarte({ ..., onZuordnen, letzter }) {
// RICHTIG:
function EmailKarte({ ..., onZuordnen, onInAkteImportiert, letzter }) {
```
**Lerneffekt:** Bei neuen Props immer sowohl Aufruf-Stelle als auch Destrukturierung prüfen.

---

### [v11] E-Mail-Kachel dehnt sich beim Aufklappen auf volle Bildschirmbreite
**Datei:** `frontend/src/App.jsx`
**Symptom:** Aufgeklappte EmailKarte in der „Zugeordnet"-Spalte sprengt das 2-Spalten-Grid
**Ursache:** CSS-Grid-Items haben `min-width: auto` – breiter Inhalt dehnt die Zelle über `1fr` hinaus
```javascript
// FALSCH:
<div>  // Spalten-Container ohne Breitenbegrenzung
// RICHTIG:
<div style={{ minWidth:0, overflow:"hidden" }}>
```
**Lerneffekt:** Grid-Spalten die aufklappbaren Inhalt enthalten immer mit `minWidth: 0` versehen.

---

### [v11] Weiterleitungs-Absender „Unbekannt" – Outlook `> >` Format
**Datei:** `backend/email_import/email_parser.py`
**Symptom:** Original-Absender wird nicht extrahiert, `von_name` bleibt leer
**Ursache:** Outlook schreibt `<email <mailto:email> >` mit Leerzeichen vor dem letzten `>`. Bereinigungsregex erwartete `>>` ohne Leerzeichen.
```python
# FALSCH:
re.sub(r'<(email)\s+<mailto:[^>]+>>', r'<\1>', text)
# RICHTIG:
re.sub(r'<(email)\s+<mailto:[^>]+>\s*>', r'<\1>', text)
```
**Lerneffekt:** Outlook-Weiterleitungsformat variiert: `>>`, `> >`, manchmal auch `> >` mit mehreren Leerzeichen. `\s*` statt fester Zeichenfolge verwenden.

---

### [v11] `email_import/parser.py` → umbenannt in `email_parser.py`
**Datei:** `backend/email_import/parser.py`
**Symptom:** Nach Umbenennung: E-Mail-Text und Anhänge beim Aufklappen leer
**Ursache:** `import_service.py` importierte `from .email_parser import ...`, aber im Container hieß die Datei noch `parser.py` → ModuleNotFoundError → `/meta`-Endpunkt schlug fehl
**Fix:** `docker exec unfallakten-backend-dev mv /app/email_import/parser.py /app/email_import/email_parser.py`
**Lerneffekt:** Bei Dateiumbenennung immer: (1) alle Import-Stellen anpassen, (2) alte Datei im Container umbenennen/löschen, (3) restart.
**Datei:** `frontend/src/App.jsx`
**Symptom:** E-Mail-Log-Einträge konnten nicht mit Akte verknüpft werden
**Ursache:** DB gibt `akte_id` zurück, Frontend erwartete `akte_az`
**Fix:** `normalisiereLogEintrag()` als zentraler Mapping-Layer
**Lerneffekt:** Immer einen Normalisierungs-Layer zwischen API-Response und Frontend-State einbauen, besonders nach Schemaänderungen.

---

### [v12] `overflow: "hidden"` clippt aufgeklappten E-Mail-Karteninhalt
**Datei:** `frontend/src/App.jsx`
**Symptom:** E-Mail-Body und Anhänge verschwinden beim Aufklappen einer Kachel
**Ursache:** `overflow: "hidden"` schneidet beide Achsen ab – aufgeklappter Inhalt wächst nach unten und wird unsichtbar
```javascript
// FALSCH:
<div style={{ minWidth:0, overflow:"hidden" }}>
// RICHTIG:
<div style={{ minWidth:0, overflowX:"hidden" }}>
```
**Lerneffekt:** Für Grid-Spalten mit aufklappbarem Inhalt immer `overflowX` statt `overflow`.

---

### [v12] App.jsx mit binären String-Operationen patchen erzeugt `\"hidden\"`
**Datei:** `frontend/src/App.jsx`
**Symptom:** Vite-Syntax-Error: `overflowX:\"hidden\"` statt `overflowX:"hidden"`
**Ursache:** Binäre `bytes.replace()` hat Backslash-escaping nicht korrekt behandelt
**Fix:** App.jsx **niemals** mit binären String-Operationen patchen. Immer `str_replace` auf Textdatei oder zeilenbasierte Python-Ersetzung.
**Lerneffekt:** Bei App.jsx-Patches: `str_replace`-Tool nutzen. Falls nötig: `open(..., 'r').readlines()` → Zeile ersetzen → `writelines()`.

---

### [v12] `aktivitaeten.akte_id` INTEGER inkompatibel mit az TEXT-PK
**Datei:** `backend/db/schema_manager.py`, `backend/models/dokument.py`
**Symptom:** `registriere_dokument()` liefert `None` – Dokument-INSERT wird durch fehlgeschlagenen aktivitaeten-INSERT zurückgerollt
**Ursache:** `aktivitaeten.akte_id` war noch `INTEGER`, aber alle Akten haben seit Migration 5 `az TEXT` als PK
**Fix:** Migration 20 – Tabelle neu gebaut mit `PRAGMA foreign_keys OFF`, `CREATE aktivitaeten_neu`, `INSERT ... CAST(akte_id AS TEXT)`, `DROP`, `RENAME`
**Lerneffekt:** Bei neuen Tabellen/Migrations immer prüfen ob `akte_id` als `TEXT REFERENCES unfallakte(az)` definiert ist.

---

### [v12] `registriere_dokument()` SELECT nach INSERT findet nichts (None)
**Datei:** `backend/models/dokument.py`
**Symptom:** `'NoneType' object has no attribute 'keys'` beim Dokument-Import
**Ursache:** `get_connection()` öffnet jedes Mal eine neue SQLite-Connection. Der SELECT in einer neuen Connection sieht den noch nicht committeten INSERT der vorherigen Connection nicht.
```python
# FALSCH: SELECT in gleicher with-block sieht uncommitted INSERT nicht
with get_connection() as conn:
    cursor = conn.execute("INSERT ...")
    row = conn.execute("SELECT * WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return Dokument.from_row(row)  # row ist None!

# RICHTIG: Dokument direkt aus bekannten Inputs bauen
with get_connection() as conn:
    cursor = conn.execute("INSERT ...")
    doc_id = cursor.lastrowid
return Dokument(id=doc_id, akte_id=akte_id, ...)
```
**Lerneffekt:** Nach INSERT mit `get_connection()` nie in derselben oder neuer Connection per SELECT nachlesen. Objekt direkt aus bekannten Werten konstruieren.

---

### [v12] Import-Zähler zeigt fehlerhafte E-Mails als „neue E-Mails"
**Datei:** `frontend/src/App.jsx`
**Symptom:** Statuskachel zeigt „2 neue E-Mails" obwohl leere Kacheln ausgeblendet werden
**Ursache:** `res.details` enthält auch Fehler-Einträge ohne `betreff`
```javascript
// FALSCH:
setResult({ neu: res.details.length, ... });
// RICHTIG:
const gueltig = res.details.filter(e => e.betreff);
setResult({ neu: gueltig.length, ... });
```
**Lerneffekt:** Import-Zähler immer auf gültige Einträge filtern.

---

### [v12] `onInAkteImportiert` nutzte alte import_service.py als Basis
**Symptom:** `ModuleNotFoundError: No module named 'backend.email_import.parser'`
**Ursache:** Als Basis für `import_service.py` wurde die neu hochgeladene Originaldatei genommen statt die bereits gepatchte aus dem letzten ZIP
**Lerneffekt:** **Immer die zuletzt gelieferten Dateien aus dem letzten ZIP als Basis nehmen**, nie die frisch hochgeladenen Originale – die sind veraltet.

---
**Datei:** `backend/db/schema_manager.py`
**Symptom:** Nach DB-Reset fehlten alle Spalten aus Migrationen 1–N
**Ursache:** `reset_database()` rief nur `create_schema()` auf, nicht `run_migrations()`
```python
# FALSCH:
def reset_database(): create_schema()

# RICHTIG:
def reset_database(): init_db()   # = create_schema() + run_migrations()
```
**Lerneffekt:** `reset_database()` muss immer `init_db()` aufrufen, nie nur `create_schema()`.

---

## Offene / Nicht vollständig behobene Bugs

| ID | Problem | Status | Nächster Schritt |
|---|---|---|---|
| B-04 | RegulierungBestaetigenButton – Positions-Mapping unvollständig | 🟡 Offen | Manuell prüfen nach nächstem Import |

---

## Wiederkehrende Fehlerquellen (Checkliste)

> Diese Punkte vor jeder neuen Implementierung mental durchgehen:

- [ ] **PK von `unfallakte`:** Immer `az TEXT`, nie `id INTEGER`
- [ ] **FKs auf `unfallakte`:** Immer `TEXT REFERENCES unfallakte(az)`
- [ ] **JOINs auf `unfallakte`:** Immer `ON x.akte_id = a.az`
- [ ] **AZ-Matching:** SB-Kürzel (`31/21AS`) normieren, bevor verglichen wird
- [ ] **E-Mail-Decoding:** BOM prüfen (UTF-16), HTML-Fallback wenn kein Plain-Text
- [ ] **Neue DB-Spalten:** `ALTER TABLE` in Migration sofort einspielen, nicht erst beim INSERT
- [ ] **App.jsx-Patches:** Nur auf frischer Datei aus Container. Sanity-Check danach.
- [ ] **EMAIL_MAX_FETCH:** Niemals unter 20 setzen
- [ ] **`dateityp`-Enum:** Bei neuen Dateitypen sofort `GUELTIGE_DATEITYPEN` erweitern
- [ ] **`reset_database()`:** Muss `init_db()` aufrufen, nicht nur `create_schema()`
- [ ] **Grid-Spalten mit aufklappbarem Inhalt:** immer `minWidth: 0, overflow: hidden`
- [ ] **Neue Props in Komponenten:** sowohl Aufruf-Stelle als auch Destrukturierung prüfen
- [ ] **Datei umbenennen:** alle Import-Stellen + Container-Datei + restart
- [ ] **Outlook-Regex:** `\s*` statt `>>` bei mailto-Bereinigung
- [ ] **`aktivitaeten.akte_id`:** TEXT seit Migration 20 – kein INTEGER mehr
- [ ] **SELECT nach INSERT:** Nie in neuer `get_connection()` nachlesen – Objekt direkt aus bekannten Inputs bauen
- [ ] **Basis für Patches:** Immer letztes ZIP als Ausgangsbasis, nie neu hochgeladene Originale
- [ ] **`overflow` vs `overflowX`:** Grid-Spalten mit aufklappbarem Inhalt → `overflowX: "hidden"`, nie `overflow: "hidden"`
- [ ] **Import-Zähler:** `res.details.filter(e => e.betreff)` – Fehlereinträge rausfiltern
- [ ] **App.jsx binary patching:** Niemals mit bytes.replace() – immer str_replace oder zeilenbasierte Python-Ersetzung

---

### [v13] `RegulierungBestaetigenButton` war nie im Frontend eingebaut
**Datei:** `frontend/src/App.jsx`
**Symptom:** Button war nicht sichtbar obwohl Backend-Endpunkt und api.js-Methode existierten
**Ursache:** Die Komponente fehlte vollständig im JSX – Bug B-04 war kein Logik-Bug sondern ein vergessenes Feature
**Fix:** `RegulierungBestaetigenButton`-Komponente neu erstellt, erscheint bei `email_typ === 'regulierungsschreiben'` in der aufgeklappten EmailKarte
**Lerneffekt:** Wenn ein Endpunkt und eine api.js-Methode existieren, aber nichts sichtbar ist → zuerst prüfen ob die Komponente überhaupt gerendert wird.

---

### [v13] Floating Code nach str_replace in App.jsx
**Datei:** `frontend/src/App.jsx`
**Symptom:** Doppelter Code (ladeVorlagen etc.) außerhalb jeder Funktion nach str_replace der EinstellungenView
**Ursache:** Die alte `EinstellungenView` wurde durch neue ersetzt, aber der alte Rumpf hing noch als floating code dran
**Fix:** Alten Rumpf per Python-Zeilen-Replacement entfernt
**Lerneffekt:** Bei kompletten Komponenten-Ersetzungen immer prüfen ob der alte Code vollständig entfernt wurde. Marker: `}\n\n  const` außerhalb einer Funktion = floating code.

---

### [v14] `getattr(b, "kuerzel", "")` auf `sqlite3.Row` liefert immer `""`
**Datei:** `backend/routers/klage_routes.py`
**Symptom:** Kein Beteiligter wird als GHPV vorgeschlagen, obwohl Kürzel gesetzt
**Ursache:** `sqlite3.Row` unterstützt kein `getattr()` – nur dict-artigen Zugriff via `b["kuerzel"]`
**Fix:** `_get(key, default="")`-Hilfsfunktion mit try/except; Mandant via `dict(row)` konvertieren
**Lerneffekt:** `sqlite3.Row` → immer `b["key"]` oder `dict(row)`, niemals `getattr(b, "key")`.

---

### [v14] DOCX-Vorlage: `{{PLATZHALTER}}` durch Word auf mehrere `<w:r>` aufgeteilt
**Datei:** `backend/word/klage_service.py` – `_befuelle_vorlage()`
**Symptom:** Platzhalter wird nicht ersetzt, Klage zeigt `{{EINLEITUNG}}` im Text
**Ursache:** Word speichert `{{EINLEITUNG}}` intern als 3–5 separate `<w:r><w:t>`-Fragmente.
  Einfaches `xml.replace("{{EINLEITUNG}}", ...)` findet den String nie.
**Fix:** Zwei-Stufen-Strategie:
  1. Alle `<w:p>`-Absätze werden per Regex kollabiert (alle `<w:t>` zusammengefasst),
     Platzhalter ersetzt, Absatz als sauberer Single-Run neu geschrieben.
  2. Gesamter `<w:body>`-Inhalt durch generierten Klageschrift-Block ersetzt.
     `<w:sectPr>` (Seitenformat) aus Original übernommen.
**Lerneffekt:** Für Word-Vorlagen mit Platzhaltern IMMER Run-Kollaps oder Body-Ersatz verwenden,
  nie simples `str.replace()` auf rohem OOXML.

---

### [v14] Vorlage-Kollision: Forderungsschreiben-Inhalt im Klage-Dokument
**Datei:** `backend/word/klage_service.py`
**Symptom:** Klageschrift enthält Forderungsschreiben-Anträge zusätzlich zu Klage-Anträgen
**Ursache:** Klageschrift-Generator nutzt Forderungsschreiben als DOCX-Vorlage –
  ohne vollständigen Body-Ersatz bleibt der Forderungsschreiben-Inhalt erhalten.
**Fix:** Body-Komplettersatz: Vorlage liefert nur Styles, Fonts, Seitenränder, Beziehungen.
**Lerneffekt:** Wenn eine Vorlage als Stil-Träger genutzt wird, IMMER den kompletten
  `<w:body>` ersetzen, nicht nur Teile davon.

---

### [v14] Inline-Imports in Funktionen (`import re`, `import uuid` etc.)
**Datei:** `backend/routers/klage_routes.py`, `backend/word/klage_service.py`
**Symptom:** Kein direkter Fehler, aber schlechte Praxis, Performance-Einbußen bei wiederholtem Aufruf
**Fix:** Alle Imports auf Modulebene verschoben
**Lerneffekt:** Python cached Module-Imports, aber syntaktisch sauberer und lesbarer ist
  immer der Modulebene-Import. Bei neuen Dateien immer sofort prüfen.
- [ ] **`sqlite3.Row`:** Niemals `getattr()` verwenden – immer `row["key"]` oder `dict(row)`
- [ ] **DOCX-Platzhalter:** Word zerstückelt Text auf `<w:r>`-Ebene → Run-Kollaps oder Body-Ersatz
- [ ] **DOCX Body-Ersatz:** Wenn Vorlage nur als Stil-Träger dient → kompletten `<w:body>` ersetzen, `<w:sectPr>` bewahren
- [ ] **Blueprint-Registrierung:** Neue Router-Dateien immer in `app.py` eintragen

---

### [v14b] Schaden nicht im Klage-Tab sichtbar (Legacy-Feld)
**Datei:** `backend/word/klage_service.py`, `backend/routers/klage_routes.py`
**Symptom:** Klage-Tab zeigt keine Schadenpositionen obwohl Schaden erfasst
**Ursache:** `berechne_fahrzeugschaden()` prüfte nur `rep_gutachten_netto` und `rep_rechnung_netto`.
  Ältere Einträge die über das Legacy-Feld `reparaturkosten` erfasst wurden, wurden ignoriert.
**Fix:** `reparaturkosten` als Fallback für `rep_sv` wenn `rep_gutachten_netto == 0`.
  Gilt in `klage_service.py` und im `schaden_dict`-Aufbau in `klage_routes.py`.
**Lerneffekt:** Immer alle Schadenfelder-Varianten berücksichtigen: `reparaturkosten` (Legacy),
  `rep_gutachten_netto` (Gutachten), `rep_rechnung_netto` (Rechnung).

---

### [v14b] WDM-Klage-Variablen fehlten in `_lade_wdm_kontrollvars`
**Datei:** `backend/routers/klage_routes.py` (neue Funktion)
**Symptom:** Unfalldetails-Tab leer obwohl Daten in RA-Micro vorhanden
**Ursache:** `_lade_wdm_kontrollvars` in word_service.py enthält keine Klage-Variablen
  (`SCHILD`, `Z1–Z3`, `M-FAHRER`, `G-FAHRER`, `QUOTEG`, `VERZUGAB`, `EA-AZ` etc.)
**Fix:** Neue Funktion `_lade_wdm_klage_vars()` direkt in `klage_routes.py` mit
  allen Klage-spezifischen WDM-Variablen. GET /unfalldetails mergt WDM als Prefill.
**Lerneffekt:** WDM-Variablen für neue Module immer in einer eigenen dedizierten
  Funktion laden, nicht an die allgemeine Kontrollvars-Funktion hängen.

---

### [v14c] Beteiligte nicht im Klage-Tab – `akte_id` vs `akte.aktenzeichen`
**Datei:** `backend/routers/klage_routes.py`
**Symptom:** Klage-Tab zeigt „Keine Beteiligten erfasst" obwohl Beteiligte vorhanden
**Ursache:** Alle DB-Queries nutzen den rohen URL-Parameter `akte_id`.
  Seit Migration 5 ist `beteiligte.akte_id` TEXT = Aktenzeichen (z.B. `322/25KS`).
  Der URL-Parameter kann einen Kanzlei-Suffix enthalten, `akte.aktenzeichen`
  ist die normalisierte Form. word_service.py hat das als explizite Warnung im Kommentar:
  *„Daher immer akte.aktenzeichen verwenden, nie die numerische akte_id."*
**Fix:** Nach `hole_akte_by_id(akte_id)` wird `az = akte.aktenzeichen` gesetzt.
  Alle DB-Queries (beteiligte, abrechnungsschreiben, unfalldetails, forderung_positionen,
  regulierung_positionen, registriere_dokument) nutzen `az`.
**Lerneffekt:** In JEDEM neuen Router nach `hole_akte_by_id()` sofort
  `az = akte.aktenzeichen` setzen und nur das für alle weiteren DB-Zugriffe verwenden.
  Den rohen URL-Parameter `akte_id` nur für den initialen Akte-Lookup verwenden.
- [ ] **`akte_id` vs `akte.aktenzeichen`:** Nach `hole_akte_by_id(akte_id)` IMMER `az = akte.aktenzeichen` setzen. Nur `az` für alle DB-Queries verwenden, nie den rohen URL-Parameter.

---

### [v14d] Route `/akten/224/25/klage/daten` nicht gefunden – `<path:>` im url_prefix
**Datei:** `backend/routers/klage_routes.py`
**Symptom:** „Akte 224/25/klage/daten nicht gefunden" – Flask schluckt `/klage/daten` als Teil der akte_id
**Ursache:** `url_prefix="/akten/<path:akte_id>"` – der greedy `<path:>`-Konverter
  matcht `224/25/klage/daten` komplett als akte_id, kein Rest für die Route übrig.
**Fix:** `url_prefix="/akten"` (statisch), `<path:akte_id>` in jede Route einzeln:
  `@bp.route("/<path:akte_id>/klage/daten")` etc.
  Flask kann dann per Backtracking `224/25` als akte_id identifizieren,
  weil `/klage/daten` ein fester Suffix ist.
**Lerneffekt:** `<path:variable>` im `url_prefix` nur verwenden wenn dahinter
  ein **fester** Suffix steht (wie word_bp: `.../dokumente/word`).
  Wenn Routen unterschiedliche Suffixe haben: url_prefix statisch lassen,
  `<path:akte_id>` in jede Route einzeln einbauen.
- [ ] **`<path:>` im url_prefix:** Nur mit festem Suffix verwenden. Bei variablen Suffixen: url_prefix statisch + `<path:akte_id>` pro Route.

---

### [v14e] Beteiligte im Klage-Tab via `sqlite3.Row` statt Model-Objekt
**Datei:** `backend/routers/klage_routes.py`
**Symptom:** Klage-Tab zeigt „Keine Beteiligten" obwohl Übersicht-Tab alle anzeigt
**Ursache:** Beteiligte wurden mit rohem SQL `SELECT * FROM beteiligte` geladen.
  Die Tabelle hat kein `kuerzel`-Feld – das wird erst durch `hole_beteiligte_by_akte()`
  befüllt, das intern RA-Micro-Daten nachladen kann und Model-Objekte liefert.
  Zusätzlich wurde `b["rolle"]` auf `sqlite3.Row` genutzt (funktioniert),
  aber `getattr(b, "kuerzel", "")` liefert immer `""` → kein GHPV-Vorschlag.
**Fix:** `hole_beteiligte_by_akte(az)` nutzen wie `word_service.py` –
  liefert vollständige Model-Objekte mit `.kuerzel`, `.schaden_nr` etc.
  `_safe_row()` und rohe `beteiligte_rows`-Queries komplett entfernt.
**Lerneffekt:** Für Beteiligte IMMER `hole_beteiligte_by_akte(az)` aus `models.schaden`
  nutzen, nie direkt `SELECT * FROM beteiligte`. Das Model reichert automatisch
  RA-Micro-Daten an und befüllt `kuerzel`.
- [ ] **Beteiligte:** Immer `hole_beteiligte_by_akte(az)` nutzen, nie rohen SQL-Select.

---

## Session v14 – Zusammenfassung der Learnings

### Kritische Muster für neue Router

```python
# IMMER so starten:
akte = hole_akte_by_id(akte_id)
if not akte:
    return _err(...)
az = akte.aktenzeichen  # ← nie akte_id direkt verwenden!

# Beteiligte:
beteiligte = hole_beteiligte_by_akte(az)  # ← nie SELECT * FROM beteiligte

# RA-Micro Fallback:
if not beteiligte:
    ra = _lade_beteiligte_aus_ramicro(az) or {}
```

### Blueprint-Routing mit `<path:akte_id>`

```python
# FALSCH – greedy, schluckt z.B. "224/25/klage/daten" komplett:
klage_bp = Blueprint("klage", url_prefix="/akten/<path:akte_id>")
@klage_bp.route("/daten")  # wird nie erreicht!

# RICHTIG – fester Suffix im url_prefix:
klage_bp = Blueprint("klage", url_prefix="/akten/<path:akte_id>/klage")
@klage_bp.route("/daten")  # Flask kann backtracking machen ✓
```

### WDM-Variablen dieser Installation
- Alle Variablen haben `var`-Prefix: `varSCHILD`, `varZ1`, `varG-KZ` etc.
- Vorsteuer: `varVORST` (nicht `varSSTF`)
- Ermittlungsbehörde: `varPOLIZEI` (nicht `varEA-ADRESS.NVName`)
- Verzug: `varSCHREIBENVERZUG` bevorzugen vor `varVERZUGAB`
- HPV-Name: `varG-HV`
- Haftungsquote: `varQUOTEG` – hat `" EUR"` Suffix → `raw.replace("EUR","").strip().replace(",",".")`
- AZ in RA-Micro: **ohne** SB-Kürzel (niemals `_re.sub(r'[A-Z]{2,3}$', ...)` anwenden)

### RVG § 13 RVG – KostRÄG 2021
- Tabelle enthält aktualisierte Werte ab 01.01.2021
- Streitwert 5.001–6.000 €: Grundgebühr = **390,00 €** (war 388,50)
- RVG ist **Nebenforderung** – nicht zum Gegenstandswert addieren!
- `gebuehr_netto` = Grundgebühr × Faktor (kein separater Ausweis nötig)

### DOCX Body-Ersatz
- Klageschrift nutzt `forderungsschreiben_vorlage.docx` als Stil-Träger
- Gesamter `<w:body>` wird ersetzt, `<w:sectPr>` aus Original erhalten
- Platzhalter werden per Run-Kollaps ersetzt (Word zerstückelt Text intern)
- Neue `klagevorlage.docx` kann als eigene Vorlage genutzt werden

### Mehrere Kläger
- `rolle_klage = "klaeger"` für alle Mandanten setzen (nicht nur ersten)
- Grammatik: `mehrere_klaeger = len(klaeger_liste) > 1` → Plural-Formen
- Frontend: Kläger ohne Checkbox (feste Anzeige), Beklagte mit Checkbox

### Checkliste neue Erkenntnisse v14
- [ ] **`<path:>` Routing:** url_prefix mit festem Suffix, nie Variable am Ende wenn verschiedene Routen folgen
- [ ] **WDM var-Prefix:** Alle WDM-Variablennamen mit `var` prüfen bevor Abfrage
- [ ] **RVG als Nebenforderung:** Nicht zum Streitwert addieren
- [ ] **`hole_beteiligte_by_akte()`:** Immer nutzen, nie rohen SQL-Select
- [ ] **RA-Micro Fallback:** Bei leeren SQLite-Beteiligten `_lade_beteiligte_aus_ramicro()` aufrufen

---

## Session v15 – Bug-Fixes

### [v15-01] positionenVorlage: falsche Schaden-Keys
**Datei:** `App.jsx` – Funktion `positionenVorlage()`
**Symptom:** Schadentabelle im Schaden-Tab zeigt 0 € für Fahrzeugschaden bei Totalschaden
**Ursache:** `fahrzeugKeys = ["wbw", "restwert"]` – aber schaden-Objekt hat `wiederbeschaffung`, nicht `wbw`. Analog `"kostenpauschale"` statt `"unkostenpauschale"`.
**Fix:** `"wbw"` → `"wiederbeschaffung"`, `"kostenpauschale"` → `"unkostenpauschale"`, `getBetrag("wiederbeschaffung")` gibt `wbw` zurück.

### [v15-02] abrechnungsart wird in Fahrzeugschaden-Berechnung ignoriert
**Dateien:** `App.jsx` (3 Stellen), `klage_service.py`
**Symptom:** Dropdown-Änderung hat keinen Effekt auf Summen; Klage berechnet falschen Fahrzeugschaden
**Ursache:** `calcBrutto`, `_fzg` in UebersichtSection/AktenDetail und `berechne_fahrzeugschaden()` verwendeten immer Auto-Logik statt explizit gesetzter `abrechnungsart`
**Fix:** In allen 4 Stellen: `art = f.abrechnungsart` prüfen, bei gesetztem Wert diesen verwenden; sonst Auto-Logik als Fallback.

### [v15-03] Kläger fehlt in Klageschrift-Generierung
**Datei:** `App.jsx` – `generieren()`-Aufruf
**Symptom:** Kläger-Block leer im Word-Dokument
**Ursache:** `beklagte.filter(b => b.checked)` – Kläger haben keine Checkbox → werden gefiltert
**Fix:** `beklagte.filter(b => b.rolle_klage === "klaeger" || b.checked)`

### [v15-04] Unfalldatum/ort leer in Klageschrift
**Dateien:** `klage_routes.py`, `klage_service.py`
**Symptom:** Einleitung enthält kein Unfalldatum/ort
**Ursache 1:** `_wdm_u_tag` und `_wdm_u_ort` wurden nicht in unfalldetails-Response mitgegeben
**Ursache 2:** `_fmt_datum()` konnte WDM-Kurzformat `01.03.25` nicht parsen
**Fix:** `_wdm_u_tag`/`_wdm_u_ort` in merged-dict ergänzt; `_fmt_datum()` unterstützt jetzt YYYY-MM-DD, DD.MM.YYYY und DD.MM.YY

### [v15-05] Dokument-Löschen löscht nichts / alle
**Datei:** `App.jsx` – DokumenteSection
**Symptom:** Klick auf Trash-Button löscht entweder nichts oder zeigt keinen Fehler
**Ursache:** `catch { /* Demo */ }` verschluckte Backend-Fehler; `dispatch` lief unabhängig vom Erfolg
**Fix:** `dispatch` nur nach erfolgreichem API-Call; bei Fehler `alert()` mit Meldung

### [v15-06] _baue_tabelle liefert falsche Beträge in Klageschrift
**Datei:** `klage_routes.py` – schaden_dict in `generiere_klage()` fehlte
**Symptom:** Schadentabelle im Word-Dokument zeigt falsche/leere Positionen
**Ursache:** `schaden_dict` in `generiere_klage()` war nicht definiert (NameError), und fehlte `abrechnungsart`, USt-Felder, `wdm_extras_json`
**Fix:** Vollständiges `schaden_dict` in `generiere_klage()` aus `hole_schadenpositionen(az)` aufgebaut, alle Felder inkl. `abrechnungsart`, `sv_kosten_netto`, `unkostenpauschale` (None = 30€-Default)

### [v15-07] Gericht-Scoring: Frankfurt an der Oder statt Frankfurt am Main
**Datei:** `klage_routes.py` – `_suche_gericht_nach_ort()`
**Symptom:** Vorgeschlagenes Gericht war Frankfurt (Oder) statt Frankfurt am Main
**Ursache:** Simples `LIKE '%frankfurt%'` ohne Token-Vergleich
**Fix:** Scoring mit Token-Abweichung: `{am, main}` vs `{an, der, oder}` → 4 abweichende Tokens × 8 Abzug = Score < 0 → gefiltert

### [v15-08] Textfeld/Sidebar im Word-Dokument zerstört
**Datei:** `klage_service.py` – `_befuelle_vorlage()`
**Symptom:** Word stürzt ab oder Briefkopf-Sidebar fehlt
**Ursache:** Body-Komplettersatz löschte `<mc:AlternateContent>`-Blöcke (= Sidebar-Textboxen)
**Fix:** Neue Architektur: `klagevorlage.docx` mit sauberen Platzhaltern, `_render_docx`-System wie Forderungsschreiben – kein Body-Ersatz mehr

---

## Session v16 – Bug-Fixes

### [v16-01] app.py: Blueprint-Registrierung außerhalb erstelle_app()
**Datei:** `backend/app.py`
**Symptom:** Server startete, aber `/akten/<az>/unfalldetails` und `/firmen/vertreter` gaben HTML zurück
**Ursache:** `app.register_blueprint(klage_bp)` stand auf Zeile 30 – außerhalb von `erstelle_app()` wo `app` noch nicht existiert → NameError beim Import
**Fix:** Alle Blueprint-Registrierungen (klage_bp, unfalldetails_bp, firmen_bp) innerhalb `erstelle_app()` platziert

### [v16-02] vite.config.js: /firmen Proxy fehlte
**Datei:** `frontend/vite.config.js`
**Symptom:** `Unexpected token '<', "<!doctype "... is not valid JSON` bei jedem Lookup-Klick
**Ursache:** Vite hatte keinen Proxy-Eintrag für `/firmen` → leitete Request an React-App weiter → gab index.html zurück
**Fix:** `/firmen` und `/kuerzungsarten` als Proxy-Einträge ergänzt

### [v16-03] VertreterModal in UnfalldetailsSection verschachtelt
**Symptom:** Unfalldetails-Reiter zeigte nur Ladescreen
**Ursache:** `ManuelleVertreterEingabe` und `VertreterModal` wurden als verschachtelte Komponenten mit `useState` innerhalb `UnfalldetailsSection` platziert → React-Hooks-Violation → Render-Crash
**Fix:** Beide Komponenten als Top-Level-Funktionen zwischen `UnfalldetailsSection` und `KlageSection` ausgelagert

### [v16-04] Python 3.10+ Type-Hints auf Python 3.9
**Datei:** `backend/routers/firmen_routes.py`
**Symptom:** `Unexpected token '<'` – Flask gab HTML zurück
**Ursache:** `-> str | None` und `-> list[dict]` sind Python-3.10-Syntax, crashen auf Python 3.9 beim Import
**Fix:** Alle modernen Type-Hints entfernt

### [v16-05] firmen_routes.py: urllib POST funktioniert nicht auf handelsregister.de
**Symptom:** Lookup lief immer in Fehler oder fand nichts
**Ursache:** handelsregister.de ist ein JSF-Portal (JavaServer Faces) – braucht Browser-Session mit ViewState-Token. Direkter urllib POST wird mit HTML-Fehlerseite beantwortet
**Fix:** mechanize-basierte Implementierung (wie bundesAPI/handelsregister), mit Impressum-Fallback für bekannte Versicherer (hart kodierte Domain-Liste) + DuckDuckGo-Suche

### [v16-06] Toter State generiert/setGen in KlageSection
**Datei:** `frontend/src/App.jsx`
**Symptom:** Kein sichtbarer Fehler, aber dead code
**Ursache:** `const [generiert, setGen] = useState(false)` – `setGen` wurde nie aufgerufen
**Fix:** Entfernt

---

## Session v16 – Bug-Fixes (finale Ergänzung)

### [v16-07] WDM-Felder fehlten komplett in generiere_klage()
**Datei:** `backend/routers/klage_routes.py`
**Symptom:** Unfallort, Schadennummer, Zeugen, Fahrer, Ermittlungsakte, Haftungsbegründung leer im Word-Dokument – obwohl im Unfalldetails-Tab korrekt angezeigt
**Ursache:** `generiere_klage()` holte `unfalldetails` direkt aus SQLite (`dict(ud)`) ohne WDM-Merge. Der `hole_unfalldetails`-Endpoint macht das Merge (SQLite > WDM), `generiere_klage` tat es nicht.
**Fix:** Vollständiges WDM-Merge direkt in `generiere_klage()` für alle 13 Felder. Prio: SQLite > WDM (WDM füllt nur leere Felder).

### [v16-08] Schmerzensgeld-Block erschien nie
**Datei:** `backend/word/klage_service.py`
**Symptom:** Selbst wenn „Schmerzensgeld" im Frontend angehakt, fehlte der Block im Word
**Ursache:** Bedingung war `mit_sg AND sg_mind > 0` – bei sg_mind=0 (kein Mindestbetrag) blieb der Block leer
**Fix:** `mit_sg` allein reicht für Block; `sg_mind > 0` bestimmt nur ob Mindestbetrag genannt wird

### [v16-09] Keine Leerzeilen zwischen Klageanträgen
**Datei:** `backend/word/klage_service.py`
**Symptom:** Alle Anträge direkt hintereinander ohne Absatz
**Fix:** `_lz()` nach jedem nummerierten Antrag; `_lz()` vor UND nach „Versäumnisurteil"

### [v16-10] gegner_kz und schadennummer ohne WDM-Fallback
**Datei:** `backend/word/klage_service.py`
**Symptom:** Kennzeichen und Schadennummer leer im Einleitungstext
**Fix:** `gegner_kz` liest jetzt auch `details.get("_wdm_gegner_kz")`; `schadennummer` liest `details.get("_wdm_schadennummer")`

---

## Session v17 – Bug-Fixes

### [v17-01] Prüfbericht wird nicht in SQLite gespeichert (nur Session-State)
**Datei:** `backend/routers/abrechnungsschreiben_routes.py`
**Symptom:** Prüfbericht verschwindet nach Neuanmelden
**Ursache 1:** `_parse_datum("")` warf ValueError → 422 → Frontend fiel stumm auf lokalen State zurück
**Ursache 2:** `_pruefe_akte()` gab 404 für RA-Micro-Akten die noch nicht in SQLite sind
**Ursache 3:** `referenzwerkstatt_plz_ort` wurde nicht an `erstelle_pruefbericht()` übergeben
**Fix:** `_parse_datum` akzeptiert leeres Datum (→ heute) und DD.MM.YYYY; `_pruefe_akte` akzeptiert AZ mit `/`; `plz_ort` wird übergeben
**Lerneffekt:** Catch-Blöcke im Frontend NIE stumm lassen. Immer echten Fehler im Toast zeigen.

### [v17-02] app.py: pruefberichte_bp Import mit falscher Einrückung
**Datei:** `backend/app.py`
**Symptom:** SyntaxError beim Start → Backend startete nicht
**Ursache:** Automatischer Patch setzte `from .routers.pruefberichte_routes import pruefberichte_bp` ohne Einrückung außerhalb von `erstelle_app()`
**Fix:** Zeile auf 4 Spaces eingerückt
**Lerneffekt:** Bei app.py-Patches immer auf Einrückung innerhalb `erstelle_app()` achten. Blueprint-Imports und register_blueprint gehören beide ins Funktionsinnere.

### [v17-03] pruefberichte_bp war redundant – Route existierte bereits
**Datei:** `backend/routers/abrechnungsschreiben_routes.py`
**Symptom:** Neuer Blueprint hatte keine Wirkung; POST lief in alte Route
**Ursache:** `pruefbericht_bp` mit URL-Prefix `/akten/<akte_id>/pruefberichte` existierte bereits in `abrechnungsschreiben_routes.py`. Flask nutzt immer den zuerst registrierten Blueprint.
**Fix:** Alte Route in `abrechnungsschreiben_routes.py` direkt gepatcht. Neuer `pruefberichte_bp` nicht mehr nötig.
**Lerneffekt:** Vor dem Anlegen einer neuen Route immer prüfen ob die URL schon existiert.

### [v17-04] Beteiligter.from_row() filtert vertreter_name/funktion weg
**Datei:** `backend/models/schaden.py`
**Symptom:** Auto-Vertreter-Lookup startet bei jedem Tab-Aufruf neu, obwohl Vertreter gespeichert
**Ursache:** `from_row()` nutzt `dataclasses.fields(cls)` als Whitelist. `vertreter_name`/`vertreter_funktion` fehlten als Dataclass-Felder → werden beim Lesen aus DB still verworfen → `klage/daten` liefert immer `""`
**Fix:** Zwei Felder zur `Beteiligter`-Dataclass hinzugefügt
**Lerneffekt:** Nach jeder neuen DB-Spalte in `beteiligte` → Feld in `Beteiligter`-Dataclass eintragen, sonst wird es von `from_row()` ignoriert.

### [v17-05] unfallakte WHERE id=? in abrechnungsschreiben.py (3 Stellen)
**Datei:** `backend/models/abrechnungsschreiben.py`
**Symptom:** `sqlite3.OperationalError: no such column: id` beim Erstellen einer Abrechnung
**Ursache:** `UPDATE unfallakte SET status=... WHERE id=?` – PK ist seit Migration 5 `az TEXT`, nicht `id`
**Fix:** Alle drei Stellen auf `WHERE az=?` korrigiert
**Lerneffekt:** `unfallakte` hat KEINEN Integer-PK. PK = `az TEXT`. Gilt für alle SQL-Statements die `unfallakte` direkt adressieren.

### [v17-06] foreign key mismatch beim Erstellen von Abrechnungen
**Datei:** `backend/models/abrechnungsschreiben.py`
**Symptom:** `sqlite3.OperationalError: foreign key mismatch - "abrechnungsschreiben" referencing "dokumente"`
**Ursache:** FK auf `dokumente.id` hat Typ-Inkompatibilität (Schemaänderung)
**Fix:** `conn.execute("PRAGMA foreign_keys = OFF")` direkt vor dem INSERT (identisch zum DELETE-Pattern)
**Lerneffekt:** Bei FK-Mismatch-Fehlern immer PRAGMA foreign_keys = OFF vor kritischen INSERTs setzen. Pattern bereits beim DELETE verwendet – konsequent für INSERTs nachziehen.

### [v17-07] POSITION_KEYS zu eng – neue Keys fehlten
**Datei:** `backend/models/abrechnungsschreiben.py`
**Symptom:** `Ungültiger position_key: 'verdienstausfall'` / `'unkostenpauschale'` / `'rep_gutachten_netto'`
**Ursache:** `POSITION_KEYS` Whitelist enthielt nur Ur-Keys. Route hatte `_POSITION_KEYS_ERWEITERT`, aber Model filterte beim INSERT nochmal mit alter Liste
**Fix:** `POSITION_KEYS` um alle neuen Keys erweitert: `rep_gutachten_netto`, `rep_rechnung_netto`, `rep_rechnung_brutto`, `verdienstausfall`, `haushalt`, `unkostenpauschale`, `kostennb`, `vorschuss`, `sonstiges_wdm_1-6`
**Lerneffekt:** Neue position_keys immer an BEIDEN Stellen eintragen: Route (`_POSITION_KEYS_ERWEITERT`) UND Model (`POSITION_KEYS`).

---

## Session v18 – Bug-Fixes

### [v18-01] Dauerspinner im Kürzungskatalog – dreifache Ursache

**Datei:** `frontend/src/App.jsx` – `KuerzungskatalogSection`
**Symptom:** Kürzungskatalog-Reiter zeigt dauerhaft Ladespinner, kein Request im Network-Tab, kein Fehler sichtbar
**Ursachen (überlagert):**

**Ursache 1: `KATEGORIE_CFG` nie definiert**
Die Konstante `KATEGORIE_CFG` wurde in `KuerzungskatalogSection` verwendet (`Object.keys(KATEGORIE_CFG)`, `Object.entries(KATEGORIE_CFG)`) aber nirgends definiert. React hat den `ReferenceError` per Error Boundary abgefangen und still die Komponente neu gerendert – kein sichtbarer Fehler in der UI.
```javascript
// FEHLTE komplett – muss VOR KuerzungskatalogSection definiert sein:
const KATEGORIE_CFG = {
  fahrzeugschaden:    { label: "Fahrzeugschaden",       bg: "#dbeafe", color: "#1e40af" },
  ersatzbeschaffung:  { label: "Ersatzbeschaffung",     bg: "#d1fae5", color: "#065f46" },
  sonstiger_schaden:  { label: "Sonstiger Schaden",     bg: "#fef3c7", color: "#92400e" },
  technisch_gutachten:{ label: "Technisch / Gutachten", bg: "#fce7f3", color: "#9d174d" },
};
```

**Ursache 2: Stumme `catch`-Blöcke maskierten den Fehler**
`ladeArten` hatte `catch { setArten(DEMO_KUERZUNGSARTEN); }` – kein Fehlertext, kein Toast. Dadurch war nie erkennbar, dass der Render-Crash die Komponente unbenutzbar machte.

**Ursache 3: Kein Timeout in `request()`**
`fetch()` hat kein eingebautes Timeout. Bei hängender Verbindung wartet `await` ewig → `setLoading(false)` wird nie erreicht → Dauerspinner auch wenn der eigentliche Fehler ein anderer war.

**Fix:**
```javascript
// 1. KATEGORIE_CFG direkt vor KuerzungskatalogSection definieren
// 2. ladeArten: Promise.race mit 10s Timeout + finally + echter Toast
const ladeArten = async () => {
  setLoading(true);
  try {
    const timeout = new Promise((_, reject) =>
      setTimeout(() => reject(new Error("Timeout: Server antwortet nicht (>10 s).")), 10000)
    );
    const r = await Promise.race([apiKuerzungsarten.liste(false), timeout]);
    setArten(r?.kuerzungsarten || []);
  } catch (e) {
    setToast("Kürzungskatalog konnte nicht geladen werden: " + (e?.message || String(e)));
    setArten([]);
  } finally {
    setLoading(false);   // ← immer ausgeführt, auch bei Fehler
  }
};
// 3. save() und toggleAktiv(): Demo-Fallback entfernt, echte Fehler-Toasts
```

**Lerneffekte:**
- **Jede verwendete Konstante muss vor ihrer ersten Verwendung definiert sein.** React Error Boundaries fangen `ReferenceError` still ab – der Spinner bleibt, aber kein Fehler ist sichtbar.
- **`finally` statt `setLoading(false)` nach dem try-catch:** Ohne `finally` bleibt `loading = true` wenn ein Fehler geworfen wird.
- **Kein `catch { }` ohne Toast.** Jeder Fehler muss dem Nutzer sichtbar gemacht werden – stumme Fallbacks (Demo-Daten, leere Arrays ohne Meldung) verbergen echte Probleme.
- **`request()` hat kein Timeout.** Bei hängender Verbindung (Proxy fehlt, Docker-Netz) wartet `await fetch()` ewig. Immer `Promise.race` mit Timeout-Promise verwenden wenn der Spinner-Zustand von einem API-Call abhängt.
- **Diagnosepfad bei Dauerspinner:** (1) Browser Console auf `ReferenceError`/`TypeError` prüfen → (2) Network-Tab: kommt überhaupt ein Request raus? → (3) Backend-Logs: kommt er an? → (4) Toast-Text nach Fix lesen.

---

## Code-Review Session 2026-04-04 – Backend & Datenbank

### [CR-01] PRAGMA foreign_keys = OFF in todos_routes.py (obsoleter Workaround)
**Datei:** `backend/routers/todos_routes.py`
**Symptom:** FK-Constraints waren für jeden todos-Write deaktiviert – Todos mit ungültigem akte_az konnten eingetragen werden.
**Ursache:** Ursprünglicher Workaround für FK-Mismatch (todos.dok_id → dokumente_alt). Migration 32 hat den Root Cause behoben (Tabelle neu gebaut mit korrektem REFERENCES dokumente(id)), aber die PRAGMA-Zeilen wurden nicht entfernt.
**Fix:** Drei `conn.execute("PRAGMA foreign_keys = OFF")`-Zeilen entfernt.
**Lerneffekt:** Nach einer Migration die einen FK-Mismatch behebt immer prüfen ob der zugehörige PRAGMA-Workaround noch vorhanden ist und entfernt werden muss.

### [CR-02] Hardcoded Passwort im Quellcode
**Datei:** `backend/app.py`
**Symptom:** Passwort für Admin-Benutzer Schatz stand im Klartext im Quellcode (und damit in der Git-History).
**Fix:** `os.environ.get("ADMIN_PASSWORT_2", "As155255")` – analog zum Koch-Admin. `ADMIN_PASSWORT_2` in `.env.example` dokumentiert.
**Lerneffekt:** Alle Credentials aus dem Quellcode raus – immer Umgebungsvariablen verwenden, auch für Fallback-Werte bei initialen Admins.

### [CR-03] Doppelter Dictionary-Key 3 in MIGRATIONS
**Datei:** `backend/db/schema_manager.py`
**Symptom:** Key `3` war zweimal im MIGRATIONS-Dict definiert. Python überschreibt still den ersten Eintrag – der erste Block (email_import_log-Duplikat) war totes Code.
**Fix:** Ersten (falschen) Key-3-Block entfernt.
**Lerneffekt:** Python dicts erlauben doppelte Keys im Literal – kein Fehler, kein Warning. Bei der MIGRATIONS-Registry immer auf doppelte Keys prüfen.

### [CR-04] LEFT JOIN beteiligte ohne DISTINCT/LIMIT im Dashboard
**Datei:** `backend/routers/dashboard_routes.py`
**Symptom:** Wenn eine Akte mehrere Beteiligte mit rolle='mandant' hat, entstehen duplizierte Zeilen – dasselbe Todo oder dieselbe Akte erscheint mehrfach im Dashboard.
**Fix:** LEFT JOIN in allen vier Dashboard-Queries durch korrelierte Subquery ersetzt:
`(SELECT name FROM beteiligte WHERE akte_id = t.akte_az AND rolle = 'mandant' LIMIT 1) AS mandant_name`
**Lerneffekt:** LEFT JOIN auf beteiligte ohne GROUP BY oder DISTINCT immer auf Duplikat-Risiko prüfen. Eine Akte kann mehrere Mandanten haben.

### [CR-05] Doppelte Query in GET /akten nur zum Zählen
**Datei:** `backend/routers/akten_routes.py`
**Symptom:** `liste_akten()` wurde zweimal aufgerufen – einmal mit limit/offset, einmal mit limit=10000 nur für `len()`.
**Fix:** `gesamt: len(akten)` – gibt Anzahl der aktuellen Seite zurück. Vollständige Pagination-Zählung ist ausstehend (Frontend nutzt gesamt aus /akten aktuell nicht).
**Lerneffekt:** Vor dem Bauen einer COUNT-Query prüfen ob der Wert überhaupt vom Frontend konsumiert wird.

### [CR-06] 5 DB-Connections pro Dashboard-Request
**Datei:** `backend/routers/dashboard_routes.py`
**Symptom:** Jede der vier Hilfsfunktionen öffnete eine eigene Connection – bei SQLite bedeutet das jeweils 6 PRAGMA-Statements als Overhead.
**Fix:** Eine Connection in `action_items()` öffnen, als Parameter `conn` an alle Hilfsfunktionen weitergeben.
**Lerneffekt:** Bei zusammengehörigen Queries die in einem Request-Kontext laufen immer eine gemeinsame Connection verwenden.

### [CR-07] PRAGMA table_info bei jedem Schaden-Write
**Datei:** `backend/models/schaden.py`
**Symptom:** Schema-Introspection (`PRAGMA table_info(schadenpositionen)`) lief bei jedem Aufruf von `setze_schadenpositionen()`.
**Fix:** Ergebnis als Modul-Variable `_SCHADEN_SPALTEN_CACHE` gecacht – wird einmal beim ersten Aufruf befüllt und für die gesamte Laufzeit gehalten.
**Lerneffekt:** Schema-Introspection ist nur bei Migrationen relevant (App-Start). Im laufenden Betrieb ist das Schema stabil – Ergebnis cachen. Gilt nur wenn Container-Neustart = neue Migration (kein Hot-Reload-Betrieb).

### [CR-08] Code-Duplikation in Auth-Middleware
**Datei:** `backend/auth/middleware.py`
**Symptom:** `login_erforderlich` und `nur_admin` enthielten identischen ~20-Zeilen-Block für Token-Validierung + User-Lookup.
**Fix:** Gemeinsame Hilfsfunktion `_authentifiziere()` extrahiert – gibt `(fehler, payload, benutzer, benutzer_id)` zurück. Beide Dekoratoren rufen sie auf.
**Lerneffekt:** Auth-Logik gehört in eine einzige Funktion. Bei Änderungen (neues Feld in g, neue Exception-Typen) nur eine Stelle anfassen.

### [CR-09] Migration 7 out-of-order im MIGRATIONS-Dict
**Datei:** `backend/db/schema_manager.py`
**Symptom:** Key `7` war nach Keys 8–33 definiert. Technisch korrekt (run_migrations nutzt sorted()), aber irreführend.
**Fix:** Migration 7 an korrekte Position zwischen 6 und 8 verschoben.
**Lerneffekt:** MIGRATIONS-Dict immer in numerischer Reihenfolge halten – `sorted()` rettet die Ausführung, aber nicht die Lesbarkeit.

### [CR-10] SECRET_KEY fällt auf bekannten Wert zurück
**Datei:** `backend/app.py`
**Symptom:** `os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")` – fehlt die Env-Variable in Produktion, sind JWT-Tokens berechenbar.
**Fix:** Fehlendes SECRET_KEY wirft jetzt `RuntimeError` beim App-Start statt stillschweigend "dev-secret-key" zu verwenden.
**Lerneffekt:** Sicherheitskritische Konfiguration (JWT-Keys, Passwörter) darf keinen funktionierenden Fallback haben – lieber hartes Fail beim Start als stilles Sicherheitsproblem.

### [CR-11] Inkonsistente Blueprint-Imports in app.py
**Datei:** `backend/app.py`
**Symptom:** 13 Blueprints wurden am File-Anfang importiert, 13 weitere lazy innerhalb von `erstelle_app()`. Kein erkennbarer Grund für die Unterscheidung.
**Fix:** Alle 26 Blueprints alphabetisch sortiert an den File-Anfang verschoben. Registrierungsblock nur noch `app.register_blueprint(x)`-Aufrufe.
**Lerneffekt:** Neue Blueprints immer oben mit den anderen importieren. Lazy-Imports in `erstelle_app()` nur wenn zirkuläre Imports es erzwingen.

### [CR-11 cont.] Inkonsistente Blueprint-Imports – abgeschlossen
**Lerneffekt:** Alle Blueprints alphabetisch sortiert am Modul-Anfang importieren. Keine lazy-Imports in `erstelle_app()`.

---

## Session v46 – Bug-Fixes (6. April 2026)

---

### [v46-01] Duplikat-Gutachten durch E-Akte Auto-Import
**Datei:** `backend/routers/belege_routes.py`
**Symptom:** Akte 1031/23 hatte zwei identische Gutachten-Kacheln im Dokumente-Reiter nach Auto-Import.
**Ursache:** RA-MICRO speichert dasselbe physische PDF unter zwei verschiedenen `eakte_nr`-Werten in `tblElo_AktenArchiv` (z.B. UAkte-Unterversionen). Beide wurden importiert ohne Duplikat-Erkennung.
**Fix:** SHA-256 Hash-Check vor `registriere_dokument`: Datei einlesen → `hashlib.sha256` → `SELECT ... WHERE akte_id=? AND pdf_hash=?`. Bei Treffer: `importierte_nrs.add(nr)` + `continue` (zählt als importiert, kein zweiter Import).
```python
with open(pfad, "rb") as _fh:
    _datei_bytes = _fh.read()
_pdf_hash = _hashlib.sha256(_datei_bytes).hexdigest()
_dup = conn.execute(
    "SELECT id FROM dokumente WHERE akte_id=? AND pdf_hash=?",
    (akte_id, _pdf_hash),
).fetchone()
if _dup:
    importierte_nrs.add(nr)
    continue
```
**Lerneffekt:** E-Akte-Nummern sind keine zuverlässige Eindeutigkeitsgarantie. Immer Inhalt hashen. `pdf_hash`-Spalte existiert in `dokumente` seit Migration 24.

---

### [v46-02] SV-E-Mail fälschlich als Gutachten auto-importiert
**Datei:** `backend/routers/belege_routes.py`
**Symptom:** Akte 1031/23: E-Mail vom SV-Büro ("Vielen Dank für Ihren Auftrag") wurde als E-Akte-Dokument auto-importiert, obwohl es kein Gutachten ist.
**Ursache:** Der Klassifikator vergab `domain_match_sv_unklar` (Konfidenz ~0.72), was über dem alten (impliziten) Schwellenwert von 0 lag.
**Fix:** Explizite Konfidenz-Schwelle `>= 0.85` für Auto-Import:
```python
hat_gutachten_pos = any(
    t.get("position_key") in ("rep_gutachten_netto", "wiederbeschaffung", "restwert", "wertminderung")
    and (t.get("konfidenz") or 0) >= 0.85
    for t in treffer_liste
)
```
**Lerneffekt:** Auto-Import-Schwellen explizit definieren. `domain_match_sv_unklar` (~0.72) ist zu niedrig für automatischen Import – kann Korrespondenz, E-Mails und Angebote treffen. 0.85 lässt nur klare Dokument-Matches durch.

---

### [v46-03] SV-Rechnung nicht auto-importiert (nur manueller Import erkannte sie)
**Datei:** `backend/routers/belege_routes.py`
**Symptom:** E-Akte-Rechnung des SV-Büros wurde beim Auto-Import nicht erkannt. Manuell importiert und geparst → korrekt als `sv_rechnung` klassifiziert.
**Ursache:** `hat_gutachten_pos` prüfte nur Gutachten-Positionen (`rep_gutachten_netto`, `wbw`, `rw`, `wm`). SV-Rechnungen haben `position_key = "sv_kosten"` / `"sv_kosten_netto"` – diese wurden nicht geprüft.
**Fix:** Separates `hat_sv_rechnung_pos` Flag + eigener Dispatch-Branch:
```python
hat_sv_rechnung_pos = any(
    t.get("position_key") in ("sv_kosten", "sv_kosten_netto")
    and (t.get("konfidenz") or 0) >= 0.85
    for t in treffer_liste
)
if (hat_gutachten_pos or hat_sv_rechnung_pos) and eakte_base_path:
    ...
    elif hat_sv_rechnung_pos and _klasse in ("rechnung", "sv_rechnung"):
        _pr = dispatch_res.get("parse_ergebnis") or {}
        eakte_cache[nr] = {"nettobetrag": _pr.get("nettobetrag"), "bruttobetrag": _pr.get("bruttobetrag")}
```
`eakte_cache[nr]` wird in-memory befüllt → Betrag-Lookup im selben API-Aufruf greift sofort.
**Lerneffekt:** Auto-Import-Logik bei neuen Dokumentklassen immer erweitern. `rechnung_parse_cache` (DB) wird NUR durch manuellen Parse-Endpunkt befüllt – Auto-Import muss `eakte_cache` direkt aktualisieren.

---

### [v46-04] Wertminderung = 0.0 statt 150.0 (Regex-Backtracking)
**Datei:** `backend/parsers/gutachten_parser.py`
**Symptom:** Gutachten mit "Wertminderung 150,00 €" lieferte `result.wertminderung = 0.0`.
**Ursache:** Regex `[^\n]{0,80}(?:0[,.]00\s*€?)` – der Wildcard-Teil `[^\n]{0,80}` fraß ` 15` aus `150,00 €`, danach matchte `0,00 €` die Restzeichenfolge. Backtracking-Fehlmatch.
```python
# FALSCH – Backtracking-Falle:
r"(?:Merkantile\s+Wertminderung|...)[^\n]{0,80}(?:0[,.]00\s*€?|\b0\s*€)"

# RICHTIG – Lookbehind verhindert Fehlmatch auf Ziffernteil:
r"(?:Merkantile\s+Wertminderung|...)[^\n]{0,80}(?:(?<!\d)0[,.]00\s*€?|\b0\s*€)"
```
**Zweites Problem:** Reihenfolge war falsch – `_wm_kein` (0-Check) lief vor `_find_betrag` (Betrag-Suche). Bei Gutachten die zuerst "Wertminderung" erwähnen und danach den Betrag nennen: `_wm_kein` matche zuerst und setzte 0.0.
**Fix:** 3-Pass-Ansatz:
1. `_find_betrag(text, LABELS_WERTMINDERUNG)` – spezifische Labels
2. Fallback-Regex für `\bWertminderung\b` mit positivem Betrag (gleiche Zeile, kein keine/entfällt davor)
3. Erst wenn kein positiver Betrag → `_wm_kein` mit `(?<!\d)0[,.]00`
**Lerneffekt:** Bei Regex die `[^\n]{0,N}` gefolgt von `0,00` haben: immer `(?<!\d)` Lookbehind einsetzen. Reihenfolge: erst positiven Wert suchen, dann Null/keine prüfen.

---

### [v46-05] Dokument-Kacheln nach Auto-Import nicht aktualisiert
**Datei:** `frontend/src/sections/DokumenteSection.jsx`
**Symptom:** Nach Auto-Parsing wurden neue Dokumente in der DB gespeichert, aber die Kacheln im Dokumente-Reiter zeigten die neuen Einträge nicht.
**Ursache:** `ladeBelegeKandidaten` rief `ladeDokumenteListe()` nicht auf. Der Store kannte die neuen `dokumente`-Einträge nicht.
**Fix:** Response enthält `auto_importiert` (Zähler). Wenn > 0: `ladeDokumenteListe()` aufrufen. `handleBatchParser` ruft es immer auf.
```javascript
if (res?.auto_importiert > 0) await ladeDokumenteListe();
```
**Lerneffekt:** Wenn Backend-Operationen neue Rows in `dokumente` erstellen, muss das Frontend danach `dokumente/liste` neu fetchen. `auto_importiert` im Response dient als Signal.
