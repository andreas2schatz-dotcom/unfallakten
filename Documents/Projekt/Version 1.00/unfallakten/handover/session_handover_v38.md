# Session-Übergabe – Kanzlei Koch, Schatz & Kollegen
# Unfallakten-Verwaltungssystem
> Stand: Session v37 – 1. April 2026
> Erledigt diese Session: PRD-24 Sessions A + B + C vollständig implementiert
> Nächste Session: PRD-24 Session D (Integrationstest + Deploy + Abschluss)
> Ab jetzt: Claude Code (CLI) im Projektverzeichnis

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
   - **B-08:** Vor einem Fix erst `PRAGMA table_info` prüfen, nicht raten
   - **B-09:** Wenn Schadentabelle und Gegenstandswert unterschiedliche Quellen → beide prüfen
   - **PRD-24:** Override-Dict vollständig durchreichen: Wizard → API → klage_service

3. **Stimme nicht einfach zu.** Verbesserungsvorschläge und kritische Fragen stellen.

---

## Aktueller Systemstand

| Komponente | Details |
|---|---|
| DB-Schema-Version | **28** (aktivlegitimation in unfalldetails) |
| Frontend | **27 Dateien** (neu: KlageWizard.jsx) |
| Backend | Flask/Python, SQLite PK `az TEXT` |
| RA-Micro | SQL Server (read-only), WDM + E-Akte aktiv |
| E-Akte | Phase 1+2+3a live |
| Dispatcher | 3-stufige Kaskade + Konflikt-Erkennung |

---

## Erledigte PRDs + Bugs

| PRD/Bug | Feature | Session |
|---|---|---|
| PRD-14 | Single Source of Truth: Abrechnungsart | v19 |
| PRD-01 | To-Do-System + Header-Widget | v20/v21 |
| PRD-02 | Kürzungsarten: Textbaustein-Feld | v20 |
| PRD-16 | Reiter-Reihenfolge + Status-Dots | v21 |
| PRD-04 | Dokumentenklassen + Dispatcher + Registry | v23 |
| PRD-04b | Feedback-Loop: Korrektur + Trainingsdata | v24 |
| PRD-20 | App.jsx Refactoring (26 Dateien) | v25 |
| PRD-15 | WDM Auto-Load | v26 ✅ |
| PRD-21 Ph1-3a | E-Akte komplett | v28-29 |
| PRD-22a | Gutachten im Schaden-Reiter | v30 |
| PRD-22b | Regulierung: Abrechnungen + Löschfunktion | v31 |
| PRD-23a | Schadenposition-Belege + Schadenbelege-Card | v32 |
| B-08 | Netto/Brutto bei Vorsteuer | v33 ✅ |
| B-09 | Gegenstandswert + fehlende Positionen | v34 ✅ |
| PRD-03 | Klageschrift K-02–K-15 | v35-36 |

---

## Offene Bugs

| # | Problem | Status |
|---|---|---|
| B-03 | Klagegenerator Blöcke | 🟡 Großteils gefixt |
| B-06 | PRAGMA bei dok_id-Tabellen | Checkliste |

---

## PRD-03: Klageschrift Formatierung (13/15)

| # | Änderung | Status |
|---|---|---|
| K-01 | Datum/AZ unter Textfeld verrutscht | ✅ Gefixt in Session A |
| K-02–K-15 | Alle weiteren Formatierungen | ✅ Erledigt |

### Deploy-Files (bereit):
```
backend/word/klage_service.py
backend/word/forderungsschreiben_wv.py
backend/routers/klage_routes.py
```

---

## PRD-24: Aktivlegitimation + Klage-Wizard

> Vollständige Planungsdokumentation: `prd24_planung.md`

### Status Sessions

| Session | Inhalt | Status |
|---|---|---|
| **A** | K-01 Fix + Template + Kachel 3 → 4 | ✅ Code fertig |
| **B** | Backend: Migration 28, Endpoints, get_aktivlegitimation_text() | ✅ Code fertig |
| **C** | Frontend: KlageWizard.jsx, KlageSection, api.js | ✅ Code fertig |
| **D** | **Integrationstest + Deploy + Bugfixes** | 🔴 Nächste Session |

### Deploy-Status

⚠️ **Noch nicht deployed!** Alle drei Sessions müssen deployed werden:

**Session A – Frontend + Backend:**
```powershell
docker cp src/sections/KlageSection.jsx unfallakten-frontend-dev:/app/src/sections/KlageSection.jsx
docker cp backend/word/klage_service.py unfallakten-backend-dev:/app/backend/word/klage_service.py
docker cp backend/word/klagevorlage.docx unfallakten-backend-dev:/app/backend/word/klagevorlage.docx
```

**Session B – Backend:**
```powershell
docker cp backend/routers/klage_routes.py unfallakten-backend-dev:/app/backend/routers/klage_routes.py
docker cp backend/db/schema_manager.py unfallakten-backend-dev:/app/backend/db/schema_manager.py
docker restart unfallakten-backend-dev
# Schema prüfen – muss 28 zeigen:
docker exec unfallakten-backend-dev python3 -c "import sqlite3; c=sqlite3.connect('/app/data/unfallakten.db'); print('Schema:', c.execute('SELECT MAX(version) FROM schema_version').fetchone()[0])"
```

**Session C – Frontend:**
```powershell
docker cp src/sections/KlageWizard.jsx unfallakten-frontend-dev:/app/src/sections/KlageWizard.jsx
docker cp src/sections/KlageSection.jsx unfallakten-frontend-dev:/app/src/sections/KlageSection.jsx
docker cp src/api.js unfallakten-frontend-dev:/app/src/api.js
docker restart unfallakten-frontend-dev
```

**Reihenfolge: B zuerst (Migration!), dann A, dann C.**

### Was wurde geändert

**Session A:**
- `klage_service.py`: `_p_rechts()` neu (K-01 Fix), `_vertretungs_hinweis()` wiederhergestellt, `{{AKTIVLEGITIMATION}}` in ooxml_blocks (leer)
- `klagevorlage.docx`: Tippfehler `{{AKTIVLEGITIMATION}` → `{{AKTIVLEGITIMATION}}` gefixt
- `KlageSection.jsx`: Kachel 3 (Schadenpositionen) und Kachel 4 (Regulierung) zusammengeführt zu einer Kachel. Oberteil: Checkbox-Liste aus `positionen`-State. Unterteil: `RegulierungsTabelle` read-only als Kontext. Kachelnummern: 1 Gericht, 2 Rubrum, 3 Schaden+Regulierung, 4 Personenschaden, 5 Zinsen, 6 RVG.

**Session B:**
- `schema_manager.py`: Migration 28 – drei neue Spalten in `unfalldetails`:
  - `aktivlegitimation_typ TEXT NOT NULL DEFAULT 'eigentum'`
  - `aktivlegitimation_freigabe TEXT NOT NULL DEFAULT 'freigabe'`
  - `aktivlegitimation_datum TEXT`
- `klage_routes.py`:
  - Neue Funktion `_mandant_ist_fahrer()` (vergleicht fahrer_mandant/varM-FAHRER gegen Mandantenname, erkennt „siehe oben")
  - `speichere_unfalldetails`: drei neue Felder in TEXT_FELDER
  - `hole_klage_daten`: `aktivlegitimation`-Block in Response
  - `generiere_klage`: `overrides`-Dict + `_override()`-Helper, alle neuen Felder in `unfalldetails` durchgereicht
- `klage_service.py`:
  - `_get_kl_genus_vars()` – Eigentümer/in, ihn/sie
  - `get_aktivlegitimation_text()` – alle 6 Fälle A–G
  - `_build_aktivlegitimation_xml()` – OOXML-Wrapper mit BEWEIS-Block
  - `{{AKTIVLEGITIMATION}}` jetzt live befüllt

**Session C:**
- `api.js`: `apiKlage.generieren(az, klagenConfig, overrides = null)` – overrides-Parameter
- `KlageSection.jsx`: Import KlageWizard, 8 neue States, `oeffneWizard()`, `wizardGenerieren()`, `<KlageWizard>` Einbindung, „🧙 Wizard"-Button
- `KlageWizard.jsx`: Neue Datei – 3-Step-Modal-Wizard:
  - Step 1: Zweispaltig – Aktivlegitimations-Auswahl + Live-Vorschau (DokumentCard)
  - Step 2: Schadenpositionen-Checkboxen (aus wizardPos-Kopie) + Personenschaden
  - Step 3: Zusammenfassung + gebündelte Warnungen + Generieren-Button

### Aktivlegitimation: Textbausteine (Referenz)

| Fall | Bedingung | Verhalten |
|---|---|---|
| A | Eigentum + selbst gefahren | Text + § 1006 BGB |
| B | Eigentum + nicht gefahren | Nur Eigentumstext |
| C | Finanziert + Freigabe | Text + BEWEIS: Freigabeerklärung, Anlage K1 |
| D | Finanziert + Bedingungen | Text + BEWEIS: Finanzierungsbedingungen, Anlage K1 |
| E | Geleast + Freigabe | Wie C, Leasinggeberin |
| F | Geleast + Bedingungen | Wie D, Leasingbedingungen |
| G | Ungeklärt | Leer + UI-Warnung ⚠, Generierung nicht gesperrt |

### Fahrer-Ermittlung (§ 1006 BGB, Fall A)

```python
# _mandant_ist_fahrer(ud, mandant, wdm_fahrer_raw)
# Mandant ist Fahrer WENN:
#   fahrer_mandant (SQLite) oder varM-FAHRER (WDM)
#   == Mandantenname (lowercase) ODER == "siehe oben"
```

### Bekannte Learnings aus PRD-24-Implementierung

- **B-08 Analog:** Override-Dict muss von Wizard → `apiKlage.generieren` → Flask-Body → `akte_daten["unfalldetails"]` → `klage_service` vollständig durchgereicht werden. In Session B explizit mit `_override()`-Helper gelöst.
- **Python 3.9:** Keine Union-Types `dict | None` in Signaturen, kein Walrus-Operator `:=` (beide in Session C-Bugs gefunden und gefixt).
- **Props-Vollständigkeit:** Alle Props die KlageSection an KlageWizard sendet müssen in der Signatur empfangen werden, und alle empfangenen Props müssen auch genutzt werden (zinsenAb/verzug-Bug in Session C gefunden).

---

## Session D: Integrationstest-Checkliste

```
□ Migration 28 läuft durch (Schema 28 nach Restart)
□ unfalldetails.aktivlegitimation_* Spalten vorhanden (PRAGMA table_info)
□ /klage/daten Response enthält "aktivlegitimation"-Key
□ Wizard-Button erscheint im Klage-Tab
□ Wizard öffnet sich (Modal sichtbar)
□ Step 1: Radios wechseln + Vorschau aktualisiert sich
□ Step 1: Datum-Picker bei Freigabe-Option
□ Step 1: Warnung-Card bei "Ungeklärt"
□ Step 2: Checkboxen funktionieren, Klagebetrag aktualisiert sich
□ Step 3: Zusammenfassung korrekt, Zinsen-Zeile sichtbar
□ Generieren aus Wizard: Word-Download funktioniert
□ Generieren aus Wizard: Aktivlegitimation-Text im Word korrekt
□ K-01: Datum/AZ korrekt positioniert (nicht verschoben)
□ One-Click-Generieren (alter Button) weiterhin funktionsfähig
□ Kachel 3 zeigt Checkboxen + Regulierungstabelle darunter
```

---

## Produktplanung

```
── ERLEDIGT ───────────────────────────────────────────────────
PRD-14 ✅  PRD-01 ✅  PRD-02 ✅  PRD-16 ✅  PRD-04 ✅
PRD-04b ✅  PRD-20 ✅  PRD-15 ✅  B-08 ✅  B-09 ✅
PRD-21 Phase 1+2+3a ✅  PRD-22a ✅  PRD-22b ✅  PRD-23a ✅
PRD-03 K-01-K-15 ✅

── IN PROGRESS ────────────────────────────────────────────────
PRD-24    Klage-Wizard + Aktivlegitimation (Session D: Test + Deploy)

── NÄCHSTE ────────────────────────────────────────────────────
PRD-24    Session D (Integrationstest, Bugfixes)
PRD-23b   Rechnungs-Parser + Auto-Zuordnung
PRD-03    Klagegenerator Abschlusstest
PRD-22c   Mandanten-Fragebogen (5-7 Sessions)

── OFFEN ──────────────────────────────────────────────────────
PRD-24b   Vollständiger 5-Step-Wizard (Unfallhergang, Haftungsbegründung)
PRD-21 Phase 3b  Batch-Klassifikation
PRD-21 Phase 3c  Filter nach Dokumentenklasse
PRD-17  Tagesstart-Dashboard
PRD-04c TF-IDF Classifier
PRD-06  Parser Reparaturrechnung
WEBSITE Kanzlei-Website Redesign (separates Projekt)
```

---

## Kritische Regeln

- `unfallakte` PK = `az TEXT`
- ⛔ raEloakte: NUR SELECT
- ⛔ Python 3.9: keine Union-Types `X | Y`, kein Walrus `:=`
- ⛔ Vor Deploy: Code-Review (Routen, _dok_dict, d.typ Fallback, Hooks, Netto/Brutto, Dict-Mapping)
- ⛔ Stimme nicht einfach zu – Verbesserungsvorschläge stellen
- ⛔ Override-Dict vollständig durchreichen (B-08 Analog)
- § 203 StGB: Keine Mandantendaten extern
- Dispatcher = Single Entry Point für alle PDFs
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

# PRAGMA table_info unfalldetails (Aktivlegitimation-Spalten prüfen)
docker exec unfallakten-backend-dev python3 -c "
import sqlite3
c = sqlite3.connect('/app/data/unfallakten.db')
cols = [r[1] for r in c.execute('PRAGMA table_info(unfalldetails)').fetchall()]
for col in cols:
    if 'aktiv' in col: print('✓', col)
"

# Frontend-Dateipfade im Container
# /app/src/sections/KlageSection.jsx
# /app/src/sections/KlageWizard.jsx   ← neu
# /app/src/api.js
```

---

## Hinweis für Claude Code

Du arbeitest direkt im Projektverzeichnis. Die geänderten Dateien liegen unter:
- `backend/word/klage_service.py`
- `backend/word/klagevorlage.docx`
- `backend/routers/klage_routes.py`
- `backend/db/schema_manager.py`
- `src/sections/KlageSection.jsx`
- `src/sections/KlageWizard.jsx` ← neue Datei, muss angelegt werden
- `src/api.js`

Falls die Dateien noch nicht im Projektverzeichnis liegen (nur in den Deploy-ZIPs aus claude.ai), müssen sie zuerst aus den ZIPs extrahiert werden:
- `session_a_deploy.zip`
- `session_b_deploy.zip`
- `session_c_deploy.zip`

Diese ZIPs wurden in der vorherigen claude.ai-Session erstellt und sollten im Download-Ordner liegen.
