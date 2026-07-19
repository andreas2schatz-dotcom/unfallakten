# Design: Klage-Wizard — Entwurf speichern

> Stand: 2026-07-19 · Freigegeben von RA Schatz (Brainstorming-Session)
> Paket 1 von 4 der Klage-Wizard-Verbesserungsrunde (2: UI-Führung, 3: Gesamtvorschau, 4: Standardtexte pflegbar)
> Scope-Session: nur Design, keine Umsetzung in dieser Session.

## Problem

Der gesamte Wizard-Zustand lebt in React-`useState` in `KlageSection.jsx` (~128 useState-Stellen). Browser-Reload, Akten-Wechsel oder Schließen des Browsers verwirft alle manuellen Textänderungen und Einstellungen; nur das Gericht wird persistiert (`PUT /klage/gericht`). Eine Klageschrift entsteht selten in einer Sitzung — Datenverlust ist im Alltag real.

## Entscheidungen (RA Schatz, 2026-07-19)

1. **Expliziter Speichern-Knopf** — kein Auto-Save.
2. **Beim Öffnen nachfragen** — „Entwurf vom … fortsetzen oder neu beginnen?"
3. **Nach erfolgreichem Generieren bleibt der Entwurf erhalten** (kein Auto-Löschen).
4. **Akte geändert → Abgleichen + Hinweis** — Entwurf wird gegen den aktuellen Aktenstand abgeglichen, Abweichungen werden angezeigt.

Umsetzungsvariante: **A — Speicherung in SQLite** (verworfen: B localStorage — rechnergebunden, flüchtig; C E-Akte-Dokument — Arbeitsstand ist kein Aktendokument).

## Datenmodell

Neue Tabelle `klage_entwurf` (Migration 61, additiv):

| Spalte | Typ | Bemerkung |
|---|---|---|
| `akte_id` | wie Akten-Referenz in bestehenden Tabellen, UNIQUE | eine Zeile je Akte (Upsert); Typ bei Umsetzung an vorhandenes Muster angleichen |
| `entwurf_json` | TEXT | vollständiger Wizard-Zustand als JSON |
| `format_version` | INTEGER | Schema des JSON; bei künftigen Wizard-Umbauten hochzählen, alte Entwürfe erkennbar |
| `gespeichert_am` | TEXT (ISO) | Anzeige „Gespeichert 19.07., 14:32" |

Inhalt `entwurf_json` (alles, was `oeffneWizard()` heute initialisiert): `wizardStep`, `wizardMaxStep`, `aktLegTyp`/`aktLegFreigabe`/`aktLegDatum`, `auslandsunfall`, alle Textfelder (`wizardSachverhaltText`, `wizardUnfallText`, `wizardRwText`, `wizardVerzugText`, `wizardAntraegeText`, `wizardGebuehrenText`), alle Manuell-Flags (`wizardSachverhaltManuell`, `wizardAntraegeManuell`, `wizardVerzugManuell`, `wizardGebuehrenManuell`), Positionen (key + checked), `wizardMitSG`/`wizardSGMind`, `wizardHq`/`wizardHb`, `wizardMitFestSg`/`wizardMitFestSach`, `wizardRvgAussergOv`. **Nicht** im Entwurf: Gericht (bleibt in bestehender eigener Persistenz), berechnete Daten (`rvgData`, `wizardRvgAussergData` — werden beim Laden neu berechnet), Beträge der Positionen (kommen beim Laden frisch aus der Akte).

RA-MICRO wird nicht berührt (read-only-Regel).

## API

- `GET /klage/entwurf/<akte>` → Entwurf + `gespeichert_am` + `format_version`, 404 wenn keiner existiert.
- `PUT /klage/entwurf/<akte>` → Upsert (Speichern-Knopf, Aktualisierung beim Generieren).
- `DELETE /klage/entwurf/<akte>` → Löschen (siehe „Neu beginnen").

AZ-Normalisierung wie überall über den `_pruefe_akte`-Rückgabewert (bekannte Falle).

## UI-Verhalten

**Speichern-Knopf.** Im Wizard-Fuß auf jedem Schritt: „💾 Entwurf speichern" + Statusanzeige daneben: „Gespeichert 19.07., 14:32" bzw. „Ungespeicherte Änderungen" (Dirty-Erkennung über Vergleich mit zuletzt gespeichertem Zustand).

**Schließen-Guard.** Schließen des Wizards mit ungespeicherten Änderungen → Dialog „Ungespeicherte Änderungen — Speichern / Verwerfen / Zurück zum Wizard". Ohne diesen Guard scheitert der Zweck des expliziten Speicherns am Vergessen.

**Beim Öffnen.** Existiert ein Entwurf: Dialog „Entwurf vom 19.07., 14:32 (Schritt 7 von 10) — fortsetzen oder neu beginnen?". „Neu beginnen" startet den Wizard frisch; der gespeicherte Entwurf wird dabei **nicht sofort gelöscht**, sondern erst beim nächsten Speichern überschrieben (Schutz vor Fehlklick).

**Nach dem Generieren.** Entwurf bleibt erhalten; beim erfolgreichen Generieren wird der aktuelle Stand einmal automatisch gespeichert, damit Entwurf und erzeugtes DOCX übereinstimmen.

## Abgleich beim Fortsetzen (Positions-Reconcile)

Reine Funktion (testbar ohne UI): Entwurfs-Positionen (key + checked) × aktuelle Akten-Positionen →

- **Neue Position** in der Akte: erscheint zusätzlich, `checked=false`.
- **Weggefallene Position**: wird entfernt.
- **Geänderter Betrag**: aktueller Betrag wird übernommen (Beträge kommen grundsätzlich frisch aus der Akte).
- checked-Zustand, Texte und Manuell-Flags kommen aus dem Entwurf.

Ergebnis enthält eine Änderungsliste → gelbe Hinweis-Box „Seit dem Entwurf geändert: …" (nur wenn nicht leer). Veraltete Automatik-Texte meldet wie bisher der bestehende `AntraegeSync`/`TextVeraltetBadge`-Mechanismus (Basis-Fingerprint ändert sich durch die frischen Daten automatisch).

**Format-Version passt nicht** (alter Entwurf nach Wizard-Umbau): Dialog bietet nur „Neu beginnen" an, mit Hinweis „Entwurf stammt aus einer älteren Programmversion".

## Fehlerfälle

- Speichern schlägt fehl → Fehlermeldung im Wizard-Fuß, Zustand bleibt „Ungespeicherte Änderungen"; Wizard bleibt benutzbar.
- Entwurf-JSON nicht lesbar/korrupt → wie Format-Version-Mismatch behandeln (nur „Neu beginnen").

## Tests (bei Umsetzung)

- Backend: Migration 61 (Klon-Muster Mig 55/56, kein `executescript`, explizite Commits, atomar in einem Edit — Reloader-Falle), Endpoints GET/PUT/DELETE inkl. 404, Upsert, AZ-Normalisierung.
- Reconcile-Funktion: neue/weggefallene/geänderte Positionen, leere Änderungsliste, checked-Erhalt.
- Frontend (Vitest): Speichern-Knopf + Dirty-Status, Öffnen-Dialog (fortsetzen/neu), Schließen-Guard, Hinweis-Box, Format-Version-Mismatch.

## Bewusst nicht im Scope

- Kein Auto-Save, keine Entwurfs-Historie (nur ein Entwurf je Akte), kein Entwurf in der E-Akte, keine Mehrbenutzer-Konfliktbehandlung (letzter Schreiber gewinnt — Kanzlei-Realität: eine Person je Klage).
