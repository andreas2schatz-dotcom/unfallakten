# Action Board Global + Onboarding Hub — Design Spec
**Datum:** 2026-05-01  
**Status:** Freigegeben  
**PRD:** PRD-NEW (Action Board Global) + PRD-NEW (Onboarding Hub)

---

## Zusammenfassung

Zwei zusammenhängende Features in einer PRD:

1. **Action Board Global** — ersetzt `DashboardView` vollständig. Kanzleiweites Sprungbrett: RA-MICRO Fristen, Akten mit Handlungsbedarf, neue Nachrichten.
2. **Onboarding Hub** — neue Komponente oben in `UebersichtSection`. Hub & Spoke mit 7 Kacheln, erscheint bei neu angelegten / unvollständigen Akten.

Der Link zwischen beiden: Im Action Board erscheinen Akten mit "Onboarding unvollständig" → Klick öffnet Akte → UebersichtSection zeigt den Hub.

---

## Design System

Identisch mit bestehendem System (`theme.js`, `.impeccable.md`):

- **Fonts:** Bricolage Grotesque (Labels, AZ, Abschnittstitel) · Figtree (Body, Beträge)
- **Primär:** Navy `#1B2A4A`
- **Akzent:** Terrakotta `#A06B4A` / Pale `#F3EAE2`
- **Hintergrund:** Pergament-Weiß `#F6F4EF` · Surface `#FAFAF8`
- **Borders:** `#E2DDD3`
- **Fristen-Farben:** Rot ≤ 14 Tage · Amber ≤ 30 Tage · Grün > 30 Tage

---

## Teil 1: Action Board Global

### Betroffene Dateien

| Datei | Änderung |
|---|---|
| `frontend/src/views/ActionBoardView.jsx` | NEU — ersetzt DashboardView |
| `frontend/src/App.jsx` | `active === "dashboard"` → `<ActionBoardView>` |
| `backend/routers/dashboard_routes.py` | NEU — `/api/dashboard` Endpoint |
| `backend/routers/ramicro_routes.py` | NEU oder erweitern — `/api/ramicro/fristen` |
| `backend/main.py` | Neue Router registrieren |

### Layout

3-Spalten-Grid, kein Scrollen, volle Viewport-Höhe:

```
┌──────────────────────────────────────────────────────────────┐
│ Action Board                    Donnerstag, 1. Mai 2026  [+ Neue Akte] │
├─────────────────┬───────────────────────┬────────────────────┤
│ Fristen         │ Handlung erforderlich │ Nachrichten        │
│ (RA-MICRO)      │                       │                    │
│                 │ ● WV fällig           │ [Email] [Portal] [SV] │
│ rot / amber /   │ ● Onboarding offen    │                    │
│ grün je Dauer   │                       │ Liste je Tab       │
│                 │ [Klick → Akte öffnen] │                    │
└─────────────────┴───────────────────────┴────────────────────┘
```

**Grid:** `grid-template-columns: 220px 1fr 320px` · Höhe: `calc(100vh - header)`

**Kopfzeile:** Datum (Bricolage Grotesque, Navy) + "Neue Akte"-Button (Terrakotta) rechtsbündig. Klick öffnet vorhandenes `NeueAkteModal` aus `AktensucheView` (Modal-Logik extrahieren oder duplizieren).

### Spalte 1: Fristen (RA-MICRO)

- Überschrift: "Fristen" (Bricolage Grotesque, klein, Navy)
- Jede Frist als Karte: `az` + Mandantenname + Fristbezeichnung + Datum + Tage-Countdown
- Farb-Codierung per `tage_bis`: ≤ 14 → `redBg/redText`, ≤ 30 → `amberBg/amberText`, > 30 → `greenBg/greenText`
- Fallback wenn RA-MICRO nicht erreichbar: Textzeile "RA-MICRO nicht verbunden" (kein Fehler)
- Klick auf Frist-Karte: öffnet Akte-Tab via `openAkte(az)`

### Spalte 2: Handlung erforderlich

Zwei Gruppen, jeweils eigene Abschnittsüberschrift:

**Gruppe A — Wiedervorlage fällig:**
- Akten mit `wv_datum ≤ heute` (nicht abgeschlossene Akten)
- Anzeige: AZ + Mandantenname + WV-Notiz + wie viele Tage überfällig
- Sortierung: ältestes WV-Datum zuerst

**Gruppe B — Onboarding unvollständig:**
- Akten ohne Beteiligter `rolle='mandant'` ODER ohne IBAN-Feld gesetzt
- Anzeige: AZ + Mandantenname (oder "–") + was fehlt (z.B. "IBAN fehlt", "Mandant fehlt")
- Sortierung: Erstellungsdatum, neueste zuerst

Jeder Eintrag: Klick → `openAkte(az)`. Keine Inline-Aktionen in dieser Spalte.

### Spalte 3: Nachrichten

Tab-Leiste mit drei Tabs:

| Tab | Inhalt | Status |
|---|---|---|
| 📧 E-Mail (n) | Ungelesene Emails aus `email_log`, neueste zuerst | Aktiv |
| 👤 Mandantenportal | — | Placeholder "demnächst" |
| 🔬 SV-Portal | — | Placeholder "demnächst" |

Jeder E-Mail-Eintrag: AZ (verlinkt) + Absender + Betreff-Vorschau + Datum. Klick → `openAkte(az)`.

### Backend: `/api/dashboard`

```
GET /api/dashboard
Response:
{
  "wiedervorlage_faellig": [
    { "az": str, "mandant": str, "wv_datum": str, "wv_notiz": str, "tage_ueberfaellig": int }
  ],
  "onboarding_offen": [
    { "az": str, "mandant": str|null, "fehlt": ["mandant"|"iban", ...] }
  ],
  "nachrichten_neu": [
    { "az": str, "absender": str, "betreff": str, "datum": str, "kanal": "email" }
  ]
}
```

**WV-Abfrage:** JOIN `akten` + bestehende WV-Tabelle, Filter `wv_datum <= today AND status != 'abgeschlossen'`.

**Onboarding-Abfrage:** Akten ohne Beteiligter `rolle='mandant'` (LEFT JOIN auf `beteiligte`) ODER Beteiligter vorhanden aber `iban IS NULL OR iban = ''`. Nur nicht abgeschlossene Akten.

**Nachrichten-Abfrage:** Aus `email_log` oder äquivalenter Tabelle — ungelesene Emails, neueste zuerst, max. 20 Einträge. Implementierer klärt genaue Tabelle beim Bauen.

### Backend: `/api/ramicro/fristen`

```
GET /api/ramicro/fristen
Response:
[
  { "az": str, "mandant": str, "frist_art": str, "frist_datum": str (ISO), "tage_bis": int }
]
```

- RA-MICRO DB read-only öffnen (wie in `word_service.py`)
- Genaue Tabellen- und Spaltennamen beim Bauen ermitteln (RA-MICRO Schema ist nicht im Repo dokumentiert)
- Filter: `frist_datum BETWEEN heute AND heute+60 Tage`, nur offene Fristen
- Sortierung: `frist_datum ASC`
- Fehlerbehandlung: Exception → leere Liste `[]`, kein HTTP-Fehler
- Nur aktiv wenn `RAMICRO_AKTIV=true`

---

## Teil 2: Onboarding Hub

### Betroffene Dateien

| Datei | Änderung |
|---|---|
| `frontend/src/sections/OnboardingHub.jsx` | NEU — Hub & Spoke Komponente |
| `frontend/src/sections/UebersichtSection.jsx` | Import + Render `<OnboardingHub>` ganz oben |

### Wann erscheint der Hub

`UebersichtSection` rendert `<OnboardingHub az={az}>` als erstes Element wenn:
- `beteiligte` enthält keinen Eintrag mit `rolle='mandant'` **ODER** Mandant-Beteiligter hat kein IBAN-Feld gesetzt
- **UND** `localStorage.getItem('onboarding_hub_versteckt_' + az) !== 'true'`

Der Status wird live aus dem Redux-State `st.beteiligte` abgeleitet — kein eigener API-Call.

### "Zur normalen Ansicht"-Button

Setzt `localStorage.setItem('onboarding_hub_versteckt_' + az, 'true')` → Hub ausgeblendet für diese Akte. Erscheint automatisch wieder wenn sich Onboarding-Zustand ändert (z.B. IBAN später gelöscht → Hub wieder sichtbar, localStorage-Flag wird ignoriert wenn Status sich verschlechtert).

Konkret: Hub erscheint IMMER wenn Onboarding-Bedingung erfüllt ist, außer wenn Flag gesetzt UND Bedingung seit Flag-Setzen nicht schlechter geworden.

Einfachere Umsetzung: localStorage-Flag gilt absolut — Hub bleibt versteckt bis Akte manuell über Action Board erneut geöffnet wird. Implementierer entscheidet nach Aufwand.

### 7 Kacheln (Hub & Spoke)

Kacheln in 2-Spalten-Grid (4+3), alle gleichwertig, alle optional:

| # | Kachel | ✓ Bedingung | Klick-Ziel |
|---|---|---|---|
| 1 | Mandant | `beteiligte` hat `rolle='mandant'` | Tab "Beteiligte" |
| 2 | Gegner / Schädiger | `beteiligte` hat `rolle='gegner'` | Tab "Beteiligte" |
| 3 | GHPV (Versicherung) | `beteiligte` hat `rolle='ghpv'` oder `'versicherung'` | Tab "Beteiligte" |
| 4 | Unfalldetails | `schaden.unfalldatum` + `schaden.unfallort` gesetzt | Tab "Unfalldetails" |
| 5 | Schadenspositionen | `st.schaden.positionen` ≥ 1 Eintrag | Tab "Schaden" |
| 6 | Vollmacht & Dokumente | `dokumente` enthält Eintrag mit `klasse='Vollmacht'` | Tab "Dokumente" |
| 7 | Erstforderung *(optional)* | Aktivitäten-Log enthält `typ='forderungsschreiben'` | Tab "Word" |

**Visuell:**
- Erledigt: Grüner Hintergrund (`greenBg`), Häkchen-Icon, `greenText`
- Offen: Amber-Hintergrund (`amberBg`), Kreis-Icon, `amberText`
- Kachel 7 (Erstforderung): Lila-Akzent (`#7c3aed`), Schrift "optional" in kleiner Subzeile
- Fortschrittszeile oben: "3 von 6 Bereichen vollständig" (Erstforderung wird in Zähler nicht einbezogen)

**Klick-Verhalten:** `setActiveTab(tabname)` — nutzt vorhandene Tab-Navigation in `AkteDetailView`.

### Keine neuen DB-Felder

Alle 7 Status-Checks werden aus vorhandenem Redux-State abgeleitet (`st.beteiligte`, `st.schaden`, `st.dokumente`, `st.aktivitaeten`). Kein neuer Backend-Endpoint für den Hub.

---

## Nicht im Scope

- Mandantenportal-Nachrichten (eigene PRD: PRD-25c)
- SV-Portal-Nachrichten (eigene PRD)
- Frist-Eingabe oder -Bearbeitung im Action Board (RA-MICRO read-only)
- Mobile-Ansicht
- Onboarding-Hub-Schritte als Inline-Formulare (Kachel-Klick navigiert nur zum Tab)
- Neue Felder in `beteiligte`-Tabelle

---

## Offene Fragen (beim Implementieren klären)

1. **RA-MICRO Fristen-Tabelle:** Genaue Tabellen- und Spaltennamen beim ersten Bauen ermitteln.
2. **E-Mail-Tabelle für Nachrichten:** Welche Tabelle / welche Spalte markiert eine Email als "ungelesen"? Ggf. vereinfacht: alle Emails der letzten 7 Tage anzeigen.
3. **WV-Tabelle:** Bestehende WV-Abfrage aus `WiedervorlageView` als Referenz nutzen.
4. **"Neue Akte"-Button:** `NeueAkteModal` aus `AktensucheView` extrahieren oder Logik duplizieren — Implementierer entscheidet nach Aufwand.
