# Session-Übergabe – Kanzlei Koch, Schatz & Kollegen
# Unfallakten-Verwaltungssystem
> Stand: Session v56 – 2. Mai 2026

---

## Aktueller Systemstand

| Komponente | Details |
|---|---|
| DB-Schema-Version | **37** (unverändert) |
| Frontend | React + Vite, aufgeteilt in Section-Dateien |
| Backend | Flask/Python 3.9, SQLite PK az TEXT |
| RA-Micro | Optional (RAMICRO_AKTIV=true), read-only, MS SQL Server via pymssql |
| E-Akte | EAKTE_BASE_PATH konfiguriert → Auto-Import aktiv |
| LLM | Qwen via LM Studio lokal (Shadow-Mode) |

---

## Erledigte Arbeiten v56

### Schwerpunkt: Action Board Global + Onboarding Hub

Vollständige Neuimplementierung des Dashboard-Bereichs. `DashboardView` entfernt und durch `ActionBoardView` ersetzt. Zusätzlich neuer `OnboardingHub` in der Aktenübersicht.

---

### Neue Dateien

| Datei | Zweck |
|---|---|
| `frontend/src/views/ActionBoardView.jsx` | Globales 3-Spalten-Sprungbrett (ersetzt DashboardView) |
| `frontend/src/sections/OnboardingHub.jsx` | Hub & Spoke Onboarding-Kacheln in UebersichtSection |
| `backend/tests/test_dashboard_uebersicht.py` | 6 Tests für neue Dashboard-Endpoints |
| `docs/superpowers/specs/2026-05-01-action-board-global-onboarding-design.md` | Design-Spec |
| `docs/superpowers/plans/2026-05-01-action-board-global-onboarding.md` | Implementierungsplan |

### Geänderte Dateien

| Datei | Änderung |
|---|---|
| `backend/routers/dashboard_routes.py` | +3 neue Endpoints + RA-MICRO Import |
| `frontend/src/api.js` | +3 neue apiDashboard-Funktionen |
| `frontend/src/App.jsx` | DashboardView → ActionBoardView (lazy import) |
| `frontend/src/sections/UebersichtSection.jsx` | OnboardingHub als erstes Kind eingebunden |
| `backend/db/schema_manager.py` | Migration-28-Guard (unfalldetails-Tabelle) |

### Gelöschte Dateien

- `frontend/src/views/DashboardView.jsx` — obsolet, durch ActionBoardView ersetzt

---

### Commits dieser Session

```
03ebe40 chore(ui): DashboardView entfernt (ersetzt durch ActionBoardView)
c920b15 test(dashboard): Tests für /ramicro-fristen hinzugefügt (6 Tests gesamt)
9061843 fix(ui): WV-Response korrekt entpacken (value.wiedervorlagen, nicht value)
d7e144a feat(ui): OnboardingHub — Hub & Spoke Onboarding in UebersichtSection
3c670ce fix(ui): ActionBoardView Import-Namen korrigiert (wiedervorlage/akten)
5e6870e feat(ui): ActionBoardView ersetzt DashboardView in App.jsx
47dd241 feat(ui): ActionBoardView — globales Sprungbrett mit Fristen/WV/Nachrichten
8d4e9c7 feat(api): apiDashboard.onboardingOffen/nachrichtenNeu/ramicroFristen
782d9f9 fix(dashboard): _RAMICRO_GRUENDE als Modulkonstante (nicht in Schleife)
1bf72bf feat(dashboard): /ramicro-fristen Endpoint (RA-MICRO read-only)
acfb103 fix(dashboard): ORDER BY erstellt_am statt az, redundante WHERE-Klausel
b45d970 feat(dashboard): /onboarding-offen + /nachrichten-neu Endpoints
```

---

## Action Board — Architektur

### Layout

```
┌─ Action Board ─────────── Freitag, 2. Mai 2026 ────── [+ Neue Akte] ──┐
│ Fristen (RA-MICRO)  │ Handlung erforderlich    │ Nachrichten           │
│ 220px (fix)         │ 1fr                      │ 2fr                   │
│                     │                          │                       │
│ Heute + letzte 7    │ ● WV fällig (heute)      │ [📧 E-Mail] [👤] [🔬] │
│ Tage aus RA-MICRO   │ ● Onboarding unvollst.   │                       │
│ Amber=heute         │                          │ E-Mails aus           │
│ Rot=vergangen       │ Klick → Akte öffnen      │ email_import_log      │
└─────────────────────┴──────────────────────────┴───────────────────────┘
```

### Backend-Endpoints

| Endpoint | Quelle | Filter |
|---|---|---|
| `GET /dashboard/action-items` | SQLite | Bestehendes PRD-25b Dashboard (unverändert) |
| `GET /dashboard/onboarding-offen` | SQLite | Akten ohne Mandant-Beteiligter ODER ohne IBAN, max 20 |
| `GET /dashboard/nachrichten-neu` | SQLite (email_import_log) | JOIN mit unfallakte, letzte 20 |
| `GET /dashboard/ramicro-fristen` | RA-MICRO (tblAktenWiedervorlagen) | -7 Tage bis heute, DESC |

### Datenpfad WV-Spalte

`apiWV.liste({ nurHeute: false })` → `/wiedervorlage/` → liefert `{ anzahl, wiedervorlagen: [...] }`.
In ActionBoardView: `wv.value?.wiedervorlagen || []` → filter `datum <= heuteISO()`.

### RA-MICRO Fristen-Tabelle

Tabelle: `tblAktenWiedervorlagen`, JOIN: `tblAkten a ON a.GUIDAkte = w.GUIDAkte`
Relevante Spalten: `dtWiedervorlage`, `sWiedervorlagegrund`, `iWiedervorlageGrund`, `a.sAktenNummer`, `a.sAktenSachbearbeiter`, `a.sMandant`
Filter: `dtAblage IS NULL OR dtAblage = '1899-12-30'` (aktive Akten)
Grunde-Mapping: `_RAMICRO_GRUENDE` dict in `dashboard_routes.py` (Modulkonstante)

---

## OnboardingHub — Architektur

**Trigger:** Rendert in `UebersichtSection` wenn `!mandant || !mandant.iban`
**Ausblenden:** `localStorage.setItem('onboarding_hub_versteckt_${az}', 'true')`
**Props:** `az`, `beteiligte`, `schaden`, `dokumente`, `aktivitaeten`, `onTabWechsel`
**Tab-Navigation:** `onTabWechsel` → `onNavigate` → `setSec` in AkteDetailView

### 7 Kacheln

| # | Label | Bedingung | Tab |
|---|---|---|---|
| 1 | Mandant | beteiligte rolle='mandant' vorhanden | beteiligte |
| 2 | Gegner / Schädiger | beteiligte rolle='gegner' | beteiligte |
| 3 | GHPV (Versicherung) | rolle ghpv/versicherung/ghpv_versicherung | beteiligte |
| 4 | Unfalldetails | schaden.unfalldatum + unfallort | unfalldetails |
| 5 | Schadenspositionen | schaden.positionen.length >= 1 | schaden |
| 6 | Vollmacht & Dokumente | dokumente mit klasse 'vollmacht' | dokumente |
| 7 | Erstforderung (optional, lila) | aktivitaeten typ='forderungsschreiben' | word |

Zähler: nur 1–6 (Erstforderung nicht als Pflicht)

---

## Wichtige Patterns & Fallstricke

### api.js Export-Namen
Die tatsächlichen Export-Namen in `api.js` weichen von intuitiven Namen ab:
- `wiedervorlage` (NICHT `apiWV`)
- `akten` (NICHT `apiAkten`)
- `apiDashboard` ✓
- `apiKlage` ✓

In `ActionBoardView.jsx` daher: `import { apiDashboard, wiedervorlage as apiWV, akten as apiAkten } from "../api";`

### WV-Response-Wrapper
`wiedervorlage.liste()` gibt `{ anzahl: N, wiedervorlagen: [...] }` zurück — KEIN plain array!
Immer `.wiedervorlagen` entpacken: `wv.value?.wiedervorlagen || []`

### RA-MICRO Exception-Handling
Bei nicht verbundenem RA-MICRO: `RaMicroNichtAktiv` oder `RaMicroVerbindungsFehler` → immer `[]` zurückgeben, nie werfen.

---

## Offene Punkte / Nächste Session

- **PRD-29 DKz-Filter**: E-Akte Whitelist via DKz-Feld — Implementierungsplan vorhanden (`handover/PRD-32_...`), noch nicht gestartet
- **PRD-22c Mandanten-Fragebogen**: Session 4–5 noch ausstehend
- **Fristen-Spalte**: Zeigt aktuell nur RA-MICRO Wiedervorlagen (nicht "harte" Rechtsmittelfristen). Falls RA-MICRO andere Fristen-Tabelle hat, ggf. Schritt 1 aus Task 2 des Plans erneut ausführen.
- **Nachrichten-Spalte**: Mandantenportal + SV-Portal als Placeholder — eigene PRDs (PRD-25c)

---

## Tests

```bash
cd backend
python -m pytest tests/test_dashboard_uebersicht.py -v
# 6 Tests: onboarding-offen (200+401), nachrichten-neu (200+401), ramicro-fristen (200+401)
```

---

## Git-Status

Branch: `main` (alle Commits lokal, noch nicht gepusht)
Letzter Commit: `03ebe40` — DashboardView entfernt
