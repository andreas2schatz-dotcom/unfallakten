# Unfallakten-System — Projektkontext für Claude

Koch, Schatz & Kollegen · Rechtsanwaltskanzlei Offenbach

## Pflichtlektüre zu Session-Beginn

Lies diese Dateien zu Beginn jeder Session, bevor du antwortest:

- `docs/ARCHITECTURE.md` — Stack, Dienste, Verzeichnisstruktur, Blueprints
- `docs/STATE.md` — aktueller Projektstatus, bekannte Probleme, offene Fragen
- `docs/TODO.md` — Backlog, Prioritäten, erledigte PRDs
- `docs/DATAMODEL.md` — Datenbankschema, Views, WDM-Mapping, Fallstricke
- `docs/DECISIONS.md` — Architekturentscheidungen und ihre Begründungen

## Wichtigste Regeln

- **RA-MICRO ist read-only** — niemals in die RA-MICRO SQL Server DB schreiben, nur in SQLite
- **Zielsprache Deutsch** — Benutzer ist Rechtsanwalt, nicht technisch, kommuniziert auf Deutsch
- **Keine unnötigen Abstraktionen** — nur umsetzen was explizit angefragt wird
- **Keine Kommentare** im Code außer bei nicht-offensichtlichem Verhalten
