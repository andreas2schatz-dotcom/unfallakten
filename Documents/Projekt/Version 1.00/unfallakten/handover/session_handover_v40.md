# Session-Übergabe – Kanzlei Koch, Schatz & Kollegen
# Unfallakten-Verwaltungssystem
> Stand: Session v40 – 2. April 2026
> Erledigt diese Session: PRD-23b vollständig geplant + PRD-Dokument erstellt
> Nächste Session: PRD-23b Session 1 – Registry-Erweiterung + GET /belege/kandidaten

---

## ⚠️ ERINNERUNG: WSL-Mount vor jedem Docker-Start!

```powershell
wsl --user root
mount -t cifs //192.168.10.100/ServerSQL/ra /mnt/eakte -o username=admin,password=passwort,ro
exit
docker compose up -d
```

---

## ⛔ ABSOLUTE REGELN

1. **Kein Schreibzugriff auf raEloakte** – NUR SELECT. Alle eigenen Daten in lokaler SQLite.

2. **Vor jedem Deploy: Code-Review gegen Learnings und bekannte Fehler:**
   - Routen-URLs: api.js ↔ Flask-Blueprint (`loesche` nicht `loeschen`!)
   - `_dok_dict()`: Beide Funktionen (upload_service + akten_routes) bei neuen Spalten
   - `d.typ` Fallback: `d.dokumentenklasse === "x" || d.typ === "x"`
   - React-Hook-Imports, Kommentar-Balance, **Python 3.9** (keine Union-Types `X | Y`, kein Walrus `:=`)
   - PRAGMA foreign_keys = OFF bei dok_id-Tabellen (B-06)
   - Reducer-Actions existieren? `confirm()` vor Löschaktionen
   - **B-08:** Bei durchgereichten Dicts IMMER prüfen ob alle Felder in JEDEM Zwischenschritt weitergegeben werden
   - **B-09:** Wenn Schadentabelle und Gegenstandswert unterschiedliche Quellen → beide prüfen
   - **PRD-24:** Override-Dict vollständig durchreichen: Wizard → API → klage_service
   - **WDM Key-Mismatch:** `sonstiges_wdm_X` ≠ `extra_wdm_ssX` → immer remap prüfen bei posMap-Aufbau

3. **Stimme nicht einfach zu.** Verbesserungsvorschläge und kritische Fragen stellen.

---

## Aktueller Systemstand

| Komponente | Details |
|---|---|
| DB-Schema-Version | **28** |
| Frontend | **27 Dateien** |
| Backend | Flask/Python 3.9, SQLite PK `az TEXT` |
| RA-Micro | SQL Server (read-only), WDM + E-Akte aktiv |
| E-Akte | Phase 1+2+3a live |

---

## Diese Session erledigt

### Planung PRD-23b (keine Code-Änderungen)

Vollständiges PRD-Dokument erstellt:
`handover/PRD-23b_Rechnungs_Parser.md`

Geklärte Architektur-Entscheidungen:
- Zwei Quellen: lokal importierte Dokumente (Prio 1) + E-Akte (Prio 2)
- `ist_firma()`: Port aus KlageSection.jsx:209 (bewährt)
- `position_aus_firmenname()`: Port des Musters aus handelsregister_service.py
- SV-Rolle: immer explizit erfasst (`sachverstaendiger`), kein Keyword-Lookup
- SV-Kosten: position_key abhängig von `mandant.vorsteuer`
- `handleBatchParser`-Stub in DokumenteSection.jsx bereits vorhanden (labeled PRD-23b)
- `schadenposition_belege`-Tabelle + `belegMap` + Preview via Blob-URL bereits live (PRD-23a)
- RA-MICRO: Firmennamen in `name`-Feld (kein `vorname`), `anrede = "Firma"`

### Datenfehler behoben
- Akte **1/80**: `betrag_gefordert` netto-Problem durch Re-Import behoben ✅

---

## Nächste Session: PRD-23b Session 1

### Was zu tun ist (in dieser Reihenfolge)

#### 1. Registry erweitern (`backend/config/registry.json`)

Neue generische Marker für Klasse `"rechnung"` hinzufügen:
```json
"Rechnungsnummer":       { "klasse": "rechnung", "marker_typ": "text" },
"Re.-Nr.":               { "klasse": "rechnung", "marker_typ": "text" },
"Rg.-Nr.":               { "klasse": "rechnung", "marker_typ": "text" },
"Zahlungsziel":          { "klasse": "rechnung", "marker_typ": "text" },
"Bitte überweisen Sie":  { "klasse": "rechnung", "marker_typ": "text" },
"Unsere Bankverbindung": { "klasse": "rechnung", "marker_typ": "text" },
"zzgl. 19% MwSt":        { "klasse": "rechnung", "marker_typ": "text" },
"zzgl. 19 % MwSt":       { "klasse": "rechnung", "marker_typ": "text" },
"Nettobetrag":           { "klasse": "rechnung", "marker_typ": "text" },
"Gesamtbetrag inkl":     { "klasse": "rechnung", "marker_typ": "text" },
"Zu zahlen bis":         { "klasse": "rechnung", "marker_typ": "text" },
"Fällig bis":            { "klasse": "rechnung", "marker_typ": "text" }
```

Dispatcher-Konflikt-Schutz ist bereits eingebaut – kein Sonderbedarf.

#### 2. Neuer Endpunkt `GET /akten/<az>/belege/kandidaten`

**Datei:** `backend/routers/belege_routes.py`

Zweistufige Logik:
- Stufe 0: `SELECT` aus lokalen `dokumente` WHERE `dokumentenklasse LIKE 'rechnung%'`
- Stufe 1: E-Akte Metadaten + Beteiligten-Abgleich (nur wenn `RAMICRO_AKTIV`)

Hilfsfunktionen (alle Python 3.9 kompatibel):
```python
def ist_firma(b):          # Port aus KlageSection.jsx:209
def position_aus_firmenname(name):  # Port des handelsregister-Musters
def _domain_aus_email(email):
def klassifiziere_eakte_dok(dok, beteiligte, vorsteuer):
```

Response-Format: siehe PRD-23b_Rechnungs_Parser.md

#### 3. Wichtige Details

- `sachverstaendiger`-Rolle: direkt → `sv_kosten_netto` (vorsteuer=J) oder `sv_kosten` (N)
- `sonstiger`-Rolle: erst Domain-Match, dann `position_aus_firmenname(b.name)`
- E-Akte-Fallback: nur aktivieren wenn `RAMICRO_AKTIV=true` UND `EAKTE_BASE_PATH` gesetzt
- Graceful degradation: Mount-Fehler → leere `eakte_kandidaten`-Liste, kein 500er
- `ist_firma()` exakt nach KlageSection-Logik: `anrede=="firma" OR (not vorname AND rolle!="mandant")`

---

## Offene Features (Backlog)

| Priorität | PRD | Beschreibung |
|---|---|---|
| **Läuft** | **PRD-23b** | Rechnungs-Parser (Session 1 von 4) |
| Danach | **PRD-03** | Klagegenerator Abschlusstest |
| Groß | **PRD-22c** | Mandanten-Fragebogen (5–7 Sessions) |

### PRD-23b Sessions 2–4 (nach Session 1)
- Session 2: `rechnung_parser.py` + `POST parse-pdf/eakte/<nr>` + Schema-Migration 29
- Session 3: Frontend Inline-Symbol + Split-View + handleBatchParser
- Session 4: Tests + Abnahme

### Künftige Wizard-Erweiterungen (niedrige Priorität)
- EinwandePanel: neue Kategorien → `KATEGORIE_ORDER`/`KATEGORIE_LABELS` in KlageWizard.jsx
- Step 5 RW: § 7 StVG / § 823 BGB / § 115 VVG Textbausteine
- PRD-24b+: Vollständiger Wizard mit Unfallhergang-Details

---

## Kritische Regeln

- `unfallakte` PK = `az TEXT`
- ⛔ raEloakte: NUR SELECT
- ⛔ Python 3.9: keine Union-Types `X | Y`, kein Walrus `:=`
- ⛔ Vor Deploy: Code-Review (Routen, _dok_dict, d.typ Fallback, Hooks, Netto/Brutto, Dict-Mapping)
- ⛔ Override-Dict vollständig durchreichen (B-08 Analog)
- § 203 StGB: Keine Mandantendaten extern
- ⚠️ WSL-Mount vor jedem Docker-Start!

---

## Docker-Befehle

```powershell
# ⚠️ WSL-Mount (JEDES MAL vor Docker-Start!)
wsl --user root
mount -t cifs //192.168.10.100/ServerSQL/ra /mnt/eakte -o username=admin,password=passwort,ro
exit

docker compose up -d

# Schema prüfen (soll 28 zeigen)
docker exec unfallakten-backend-dev python3 -c "import sqlite3; c=sqlite3.connect('/app/data/unfallakten.db'); print('Schema:', c.execute('SELECT MAX(version) FROM schema_version').fetchone()[0])"

# Deploy Backend
docker cp backend/routers/belege_routes.py  unfallakten-backend-dev:/app/backend/routers/belege_routes.py
docker cp backend/config/registry.json      unfallakten-backend-dev:/app/backend/config/registry.json
docker restart unfallakten-backend-dev
```
