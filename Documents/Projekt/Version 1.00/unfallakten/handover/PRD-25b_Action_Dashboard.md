# PRD-25b – Action-Dashboard
> Erstellt: 2026-04-03  
> Status: Bereit zur Implementierung  
> Abhängigkeiten: PRD-25a (Fristen-Todos) ✅ empfohlen vorher, email_import_log ✅, regulierung ✅  
> Design: ui-ux-pro-max Skill verwenden  

---

## Ziel

Das bestehende `DashboardView.jsx` (Akten-Liste mit Status-Zählern) wird durch ein
**priorisiertes Arbeitsboard** ersetzt. Der Sachbearbeiter sieht beim Öffnen sofort:
was ist heute fällig, was braucht jetzt Aufmerksamkeit.

Vier Bereiche, von oben nach unten nach Dringlichkeit.

---

## Layout-Entwurf

```
┌─────────────────────────────────────────────────────────────────────┐
│  Guten Morgen · Freitag, 3. April 2026                              │
│  3 Punkte brauchen heute deine Aufmerksamkeit                       │
├──────────────────────────────┬──────────────────────────────────────┤
│                              │                                      │
│  ⚠  FRISTEN (2)              │  ✉  NEUE EINGÄNGE (5)               │
│  ─────────────────────────── │  ─────────────────────────────────── │
│  Verjährung in 18 Tagen      │  3 E-Mails nicht zugeordnet         │
│  AZ 1087/24  31.12.2026      │  2 Fragebogen-Erstkontakte neu      │
│                              │                                      │
│  Antwort ausstehend 15 Tage  │                                      │
│  AZ 0934/23  Forderungsschr. │                                      │
│                              │                                      │
├──────────────────────────────┴──────────────────────────────────────┤
│                                                                     │
│  📋  REGULIERUNG ZU PRÜFEN (3)                                      │
│  ─────────────────────────────────────────────────────────────────  │
│  AZ 1102/24  Regulierungsschr. eingeg.  vor 12 Tagen  2.840 €      │
│  AZ 0887/23  Teilreg. offen             Differenz     1.200 €      │
│  AZ 0762/23  §3a PflVG-Frist            in 4 Tagen                 │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  💤  AKTEN OHNE BEWEGUNG (4)                                        │
│  ─────────────────────────────────────────────────────────────────  │
│  AZ 0554/23  Letzte Aktivität vor 28 Tagen  →  Sachstandsanfrage?  │
│  AZ 1203/24  Letzte Aktivität vor 21 Tagen  →  Sachstandsanfrage?  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Datenquellen (bestehend, kein neues Schema)

| Block | Quelle | Bedingung |
|---|---|---|
| Fristen | `todos` WHERE `quelle='system'` AND `erledigt=0` | `faellig_am` ≤ heute + 30 Tage |
| Neue Eingänge E-Mail | `email_import_log` | `status='nicht_zugeordnet'` AND `email_typ != 'fragebogen'` |
| Neue Eingänge Fragebogen | `fragebogen_erstkontakt` | `status='neu'` |
| Regulierung zu prüfen | `regulierung` | `status='ausstehend'` OR (`status='teilreguliert'` AND kein Erledigt-Datum) |
| §3a PflVG | `todos` | `frist_typ='pflvg_3a'` AND `erledigt=0` AND `faellig_am` ≤ heute + 7 Tage |
| Akten ohne Bewegung | `aktivitaeten` | MAX(zeitstempel) < heute − 14 Tage AND `status != 'abgeschlossen'` |

---

## Backend: Neuer Endpunkt

```
GET /dashboard/action-items
```

Response-Struktur:
```json
{
  "fristen": [
    {
      "akte_az": "1087/24",
      "text": "Verjährung in 18 Tagen",
      "faellig_am": "2026-04-21",
      "frist_typ": "verjährung_2m",
      "tage_bis_faellig": 18
    }
  ],
  "eingaenge": {
    "emails_nicht_zugeordnet": 3,
    "fragebogen_neu": 2
  },
  "regulierung_offen": [
    {
      "akte_az": "1102/24",
      "mandant_name": "Riccio",
      "tage_seit_eingang": 12,
      "betrag_differenz": 2840.0,
      "regulierung_status": "ausstehend"
    }
  ],
  "akten_ohne_bewegung": [
    {
      "akte_az": "0554/23",
      "mandant_name": "Müller",
      "tage_ohne_bewegung": 28,
      "vorschlag": "sachstandsanfrage"
    }
  ]
}
```

**Neue Datei:** `backend/routers/dashboard_routes.py`  
**Blueprint:** `dashboard_bp`, Prefix: `/dashboard`  
In `app.py` registrieren.

---

## Vorschlag-Logik (Akten ohne Bewegung)

```python
def _berechne_vorschlag(akte_az, tage):
    # Prüft zuletzt generierte Dokumente
    # < 14 Tage: kein Vorschlag
    # 14-21 Tage: "Sachstandsanfrage?"
    # > 21 Tage ohne STA: "Dringende Sachstandsanfrage"
    # > 21 Tage + bereits 2 STAs: "Klage prüfen?"
```

---

## Frontend: DashboardView.jsx (Ersatz)

### Komponenten-Struktur

```
DashboardView.jsx
  ActionHeader.jsx        ← Begrüßung + Zusammenfassung
  FristenBlock.jsx        ← Frist-Karten, sortiert nach faellig_am
  EingaengeBlock.jsx      ← E-Mail + Fragebogen Zähler mit Direktlinks
  RegulierungBlock.jsx    ← Regulierung zu prüfen
  OhneBewegungBlock.jsx   ← Akten ohne Bewegung + Vorschlag-Chips
```

Alle Blöcke werden via `GET /dashboard/action-items` befüllt.
Bestehende Akten-Liste (gefiltert + sortierbar) bleibt als **zweites Tab**
„Alle Akten" erhalten — sie verschwindet nicht.

### Design-Vorgaben (ui-ux-pro-max)

- **Farbcodierung**: rot = heute/überfällig, amber = ≤7 Tage, blau = ≤30 Tage
- **Kompakte Zeilen-Karten**: kein Accordion-Aufklappen im Dashboard
- **Direktlink** auf jeder Karte → öffnet die Akte direkt
- **Vorschlag-Chip** (z.B. `→ Sachstandsanfrage?`) ist klickbar und öffnet
  direkt den Sachstandsanfrage-Dialog der Akte (PRD-25d)
- **Leer-Zustände** wenn kein Eintrag: kurze grüne Bestätigung „Alles erledigt ✓"
- Loading-Skeleton für den initialen Datenabruf

---

## Session-Plan

| Session | Inhalt |
|---|---|
| 1 | `dashboard_routes.py` + Endpunkt `/dashboard/action-items` + alle Queries |
| 2 | `DashboardView.jsx` Umbau: ActionHeader + Tab-Wechsel Akten-Liste |
| 3 | FristenBlock + EingaengeBlock |
| 4 | RegulierungBlock + OhneBewegungBlock + Vorschlag-Chips |
| 5 | Design-Review (ui-ux-pro-max) + Abnahme |

---

## Abgrenzung

- **Kein Echtzeit-Refresh** (kein WebSocket) — Laden beim Tab-Wechsel reicht
- **Kein persönlicher Filter** (benutzer_id) in Phase 1 — alle Einträge für alle Nutzer
- **Kein RA-MICRO-Abgleich** in Phase 1 — nur lokale SQLite-Daten
