# Design: Regulierung-Status-Kachel in RegulierungSection

**Datum:** 2026-06-22  
**Scope:** Kleines Feature — 1 neue DB-Spalte, 1 Migration, 1 API-Erweiterung, 1 Frontend-Kachel

---

## Ziel

In der RegulierungSection eine kompakte Kachel „Regulierung abgelehnt?" anzeigen, die den Gesamt-Status der Regulierung auf Akten-Ebene festhält. Dieser Status ist relevant für eine spätere Klage (z.B. Klagebegründung, Streitwert, Haftungsgrundlage).

---

## Datenmodell

### Neue Spalte in `unfallakte`

```sql
regulierung_status TEXT NOT NULL DEFAULT 'offen'
    CHECK(regulierung_status IN ('offen', 'abgelehnt', 'teilhaftung'))
```

**Bedeutung der Werte:**
- `offen` — Regulierung noch nicht abgeschlossen oder vollständig (Standard)
- `abgelehnt` — Versicherung hat Regulierung vollständig abgelehnt → `haftungsquote` wird auf `0` gesetzt
- `teilhaftung` — Versicherung reguliert nur anteilig → `haftungsquote` enthält den Prozentsatz (0–99)

Die bestehende Spalte `unfallakte.haftungsquote` (REAL, 0–100) wird für den Teilhaftungs-Prozentsatz mitgenutzt. Keine neue Spalte nötig.

### Schema-Migration

Neue Migration mit nächster Versionsnummer (aktuell 44 → neu: 45):
```sql
ALTER TABLE unfallakte ADD COLUMN regulierung_status TEXT NOT NULL DEFAULT 'offen'
    CHECK(regulierung_status IN ('offen', 'abgelehnt', 'teilhaftung'));
```

---

## Backend

### Endpoint-Erweiterung

Der bestehende Akte-Update-Endpoint (PATCH `/akten/<az>`) wird um `regulierung_status` erweitert:

- Akzeptiert `regulierung_status` im Request-Body (`'offen'` | `'abgelehnt'` | `'teilhaftung'`)
- Validierung: nur die drei erlaubten Werte
- Bei `abgelehnt`: `haftungsquote` wird automatisch auf `0` gesetzt
- Bei `offen`: `haftungsquote` wird auf `100` gesetzt (Vollhaftung als Default)
- Bei `teilhaftung`: `haftungsquote` wird aus dem Request-Body übernommen (Pflichtfeld, 1–99)
- Gibt aktualisierte Felder `regulierung_status` und `haftungsquote` zurück

### API-Response

```json
{
  "regulierung_status": "teilhaftung",
  "haftungsquote": 70.0
}
```

---

## Frontend

### Komponente: RegulierungStatusKachel

Kleine, in sich geschlossene Kachel, eingebettet oben in `RegulierungSection.jsx` (vor den Abrechnungen).

**Aufbau:**
```
┌─────────────────────────────────────────┐
│ Regulierung abgelehnt?                  │
│                                         │
│  ○ Nein   ○ Ja   ○ Teilhaftung         │
│                                         │
│  [nur bei Teilhaftung sichtbar:]        │
│  Versicherung reguliert: [70] %         │
└─────────────────────────────────────────┘
```

**Verhalten:**
- Radio-Buttons: Nein / Ja / Teilhaftung
- Beim Klick auf Nein oder Ja: sofortiger Auto-Save (kein Speichern-Button)
- Bei Teilhaftung: Prozent-Eingabefeld erscheint inline (1–99), Speichern per Enter oder Blur
- Ladezustand während Save: Button/Radio kurz disabled + Spinner
- Nach erfolgreichem Save: kurze grüne Bestätigung (Toast oder Inline-Check)

**State:**
- `regulierungStatus` (`'offen'` | `'abgelehnt'` | `'teilhaftung'`) — aus Akte-Daten
- `teilhaftungProzent` (number 1–99) — aus `hq`-Prop
- `saving` (boolean)

**Props-Anbindung:**
- Liest `hq` und (neues) `regulierungStatus` aus den Akte-Daten
- Schreibt via `dispatch` nach erfolgreichem Save (aktualisiert `hq` und `regulierungStatus` im globalen State)

**Darstellung im Klage-Wizard:**
- Kein Änderungsbedarf: `hq`-Prop wird bereits korrekt an den Klage-Wizard übergeben
- `regulierung_status = 'abgelehnt'` kann im Wizard als Hinweistext genutzt werden (optional, nicht Teil dieses Specs)

---

## Nicht im Scope

- Änderungen am Klage-Wizard (folgt separat bei Bedarf)
- Anzeige des Status im Action Board oder Dashboard
- Historisierung von Status-Änderungen

---

## Implementierungsschritte (Übersicht)

1. Schema-Migration 45: `ALTER TABLE unfallakte ADD COLUMN regulierung_status`
2. Backend: Endpoint PATCH `/akten/<az>` um `regulierung_status` + automatisches `haftungsquote`-Setzen erweitern
3. Backend: `regulierung_status` in GET `/akten/<az>` Response aufnehmen
4. Frontend: `RegulierungStatusKachel`-Komponente in `RegulierungSection.jsx` einbauen
5. Frontend: `api.js` um `regulierungStatusSpeichern()` erweitern (oder bestehenden Akte-Update nutzen)
