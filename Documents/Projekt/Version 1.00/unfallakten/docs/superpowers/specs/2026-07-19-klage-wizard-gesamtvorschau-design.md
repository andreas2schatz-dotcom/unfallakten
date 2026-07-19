# Design: Klage-Wizard — Gesamtvorschau vor dem Download

> Stand: 2026-07-19 · Freigegeben von RA Schatz (Brainstorming-Session)
> Paket 3 von 4 der Klage-Wizard-Verbesserungsrunde (1: Entwurf speichern, 2: UI-Führung, 4: Standardtexte pflegbar)
> Scope-Session: nur Design, keine Umsetzung in dieser Session.

## Problem

Es gibt nur den DOCX-Download (`apiKlage.generieren` lädt den Blob und triggert sofort den Download, `api.js:315/334`). Die „Vorschau"-Kästen in den Steps (`buildVorschauText`, `buildRwVorschau`) sind clientseitige Nachbildungen einzelner Abschnitte; der Gleichlauf mit dem Backend wird nur durch die Golden-File-Matrix (V10) abgesichert, nicht in der UI. Fehler findet man erst nach dem Zyklus generieren → Word öffnen → zurück in den Wizard.

## Anforderung (RA Schatz, 2026-07-19)

Die Gesamtvorschau dient der **Kontrolle** und soll **schnelle Änderungen direkt eintippen** lassen. Druckgenauigkeit ist **nicht** notwendig.

Verworfen: PDF-Vorschau via LibreOffice (druckgenau, aber read-only — Korrekturen erzwingen Rücksprung in die Schritte; schwerer Container, Sekunden Wartezeit) und reiner Browser-Zusammenbau (Nachbildung, Drift-Risiko).

## Lösung: Wortgenaue Server-Text-Vorschau, abschnittsweise bearbeitbar

### Backend

Neuer Vorschau-Modus im `klage_service`: derselbe Aufbauweg wie `generiere_klageschrift` (identisches `cfg`), aber statt DOCX-Rendering eine **strukturierte JSON-Antwort** mit den Dokument-Abschnitten in Dokumentreihenfolge:

```
{ abschnitte: [ { key, titel, text, editierbar, override_feld|null, schritt_nr|null } ] }
```

- `editierbar=true` + `override_feld` für alles, was heute ein `*_override` ist (Sachverhalt, Unfalltext, Anträge, Würdigung, Verzug, Gebühren).
- `editierbar=false` + `schritt_nr`/Hinweis für Daten-Abschnitte (Rubrum aus Parteien, Streitwert-Zeile etc.).
- Kernpunkt: **eine Quelle** — die Texte entstehen im selben Code wie das DOCX; die Vorschau kann inhaltlich nicht driften. Umsetzungsweg bei der Planung entscheiden: Textaufbau aus dem Renderer herausziehen (bevorzugt, zahlt auf V11/Paket 4 ein) statt Parallel-Pfad.
- Endpoint: `POST /klage/vorschau/<akte>` mit demselben `cfg`-Body wie das Generieren (kein Persistenz-Seiteneffekt).

### Frontend (Schritt 11)

- Knopf **„Vorschau erzeugen"** lädt die aktuelle Fassung (explizit, kein Auto-Load); danach durchscrollbare Gesamtansicht der Klageschrift.
- **Abschnittsweises Bearbeiten:** Hover zeigt „✎ Bearbeiten" → Abschnitt wird inline zum Textfeld. Speichern der Änderung schreibt in den zugehörigen Wizard-State (`override_feld`) und setzt das jeweilige **Manuell-Flag** — exakt derselbe Mechanismus wie in den Schritten; Entwurf-Speichern (Paket 1) sichert die Änderung mit, `TextVeraltetBadge`/Diff (Paket 2) funktionieren unverändert.
- Nach einer Abschnitts-Änderung wird die Vorschau aktualisiert (erneuter Vorschau-Aufruf).
- Nicht-editierbare Abschnitte: dezente Kennzeichnung + Hinweis „Änderbar über Schritt N / Karte X".
- Download-Knopf bleibt daneben: erst prüfen, dann herunterladen.

## Kopplungen

- **Paket 1:** Vorschau-Edits sind gewöhnliche ungespeicherte Änderungen (Dirty-Status, Schließen-Guard, Speichern-Knopf).
- **Paket 2:** Schrittnummern nach dem 11-Schritte-Umbau; `schritt_nr`-Hinweise entsprechend.
- **Paket 4 (V11):** Wenn der Textaufbau für die Vorschau ohnehin aus dem f-String-Monolithen herausgelöst wird, ist das die Vorarbeit für Template-/Textbaustein-Fähigkeit — Reihenfolge in der Planung berücksichtigen.

## Tests (bei Umsetzung)

- Paritätstest: Abschnittstexte der Vorschau == Textinhalt des erzeugten DOCX für dieselbe `cfg` (Erweiterung der V10-Golden-Matrix).
- Endpoint: editierbar-Markierung, Reihenfolge, kein DB-Write.
- Vitest: Vorschau-Laden, Inline-Edit setzt Override + Manuell-Flag, Aktualisierung, nicht-editierbar-Hinweis.

## Bewusst nicht im Scope

- Keine Druckbild-Simulation (Seitenumbrüche, Schriftbild — dafür Word), kein PDF/LibreOffice, kein Bearbeiten nicht-überschreibbarer Abschnitte, keine Autosaves aus der Vorschau heraus.
