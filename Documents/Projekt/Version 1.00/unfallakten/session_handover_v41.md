# Session-Übergabe – Kanzlei Koch, Schatz & Kollegen
# Unfallakten-Verwaltungssystem
> Stand: Session v41 – 4. April 2026
> Erledigt diese Session: Backend & Datenbank Code-Review (11 Fixes)
> Nächste Session: Frontend Code-Review (dann zurück zu → session_handover_v40.md)

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
| DB-Schema-Version | **33** |
| Frontend | **35 JSX-Dateien** + api.js |
| Backend | Flask/Python 3.9, SQLite PK `az TEXT` |
| RA-Micro | SQL Server (read-only), WDM + E-Akte aktiv |

---

## Diese Session erledigt

### Backend & Datenbank Code-Review – 11 Fixes

Alle Fixes dokumentiert in `handover/bugs_and_fixes.md` (CR-01 bis CR-11).

| Fix | Datei | Art |
|---|---|---|
| CR-01 | `routers/todos_routes.py` | `PRAGMA foreign_keys = OFF` entfernt (Migration 32 hat Root Cause behoben) |
| CR-02 | `app.py` | Hardcoded Passwort → `ADMIN_PASSWORT_2` Env-Variable |
| CR-03 | `db/schema_manager.py` | Doppelter Migration-Key 3 entfernt |
| CR-04 | `routers/dashboard_routes.py` | LEFT JOIN beteiligte → korrelierte Subquery (kein Duplikat-Risiko) |
| CR-05 | `routers/akten_routes.py` | Doppelte Query (limit=10000) → `len(akten)` |
| CR-06 | `routers/dashboard_routes.py` | 4 DB-Connections → 1 gemeinsame Connection |
| CR-07 | `models/schaden.py` | `PRAGMA table_info` gecacht statt bei jedem Write |
| CR-08 | `auth/middleware.py` | Code-Duplikation → `_authentifiziere()` Hilfsfunktion |
| CR-09 | `db/schema_manager.py` | Migration 7 an korrekte Position verschoben |
| CR-10 | `app.py` | `SECRET_KEY` ohne Fallback – wirft RuntimeError wenn nicht gesetzt |
| CR-11 | `app.py` | Alle Blueprint-Imports nach oben, alphabetisch sortiert |

---

## Nächste Session: Frontend Code-Review

### ➡️ PROMPT FÜR NEUE SESSION:

```
Wir machen ein systematisches Code-Review des Frontends des Unfallakten-Systems.
Lies zuerst session_handover_v41.md für den Kontext.

Du bist Senior Frontend Engineer und untersuchst den Code auf:
- Performance-Issues (unnötige Re-Renders, fehlende useMemo/useCallback, doppelte Fetches)
- Bugs (fehlerhafte API-Calls, fehlende Error-States, Race Conditions)
- Sicherheit (sensitive Daten in State/LocalStorage, XSS)
- Doppelten Code und verbesserungswürdige Patterns

Wir gehen systematisch vor:
1. Zuerst Struktur & Überblick (Komponentenbaum, State-Management)
2. Dann api.js und Fehlerbehandlung
3. Dann die großen Komponenten: AkteDetailView, DashboardView, KlageSection
4. Dann Views und kleinere Komponenten

Frontend-Dateien (35 JSX + api.js):
- src/api.js, src/App.jsx, src/main.jsx
- src/components/: AkteDetailView, LoginPage, StaDialog, common, layout
- src/sections/: BeteiligteSection, DokumenteSection, KlageSection, KlageWizard,
  RaMicroSachstandsCard, RegulierungSection, SchadenSection, UebersichtSection,
  UnfalldetailsSection, WordSection
- src/views/: AktensucheView, DashboardView, EinstellungenView, EmailImportView,
  KuerzungskatalogView, StatistikenView, WiedervorlageView
- src/views/email_import/: BussgeldEmailView, TerminEmailView, UnfallEmailView
- src/views/email_import/components/: AktionBadge, AnhangZeile, EmailKarte,
  FragebogenErstkontaktKarte, ImapKonfigDialog, InAkteButton, RegulierungBestaetigenButton

Erstelle zunächst eine Übersicht der gefundenen Issues, priorisiert nach Schweregrad.
Wir gehen dann Issue für Issue durch und fixen was sinnvoll ist – analog zum Backend-Review.

Nach Abschluss des Frontend-Reviews: session_handover_v40.md für die offenen Feature-Tasks lesen.
```

---

## Offene Feature-Tasks (pausiert während Code-Review)

Alle offenen Tasks stehen in **session_handover_v40.md**. Nach dem Frontend-Review dort weitermachen.

Wichtigste offene Tasks:
- **PRD-23b Session 1** – Registry-Erweiterung + `GET /akten/<az>/belege/kandidaten`
- **PRD-22c Session 5** – Tests Fragebogen-Backend
- **Klage-Wizard** – „Kürzungen"-Button in Step 5
- **PRD-25c/25d** – Mandantenkommunikation + Intelligente STA
- **Bußgeld-Feature** – Deployment (bussgeld@ bei Strato + .env)
