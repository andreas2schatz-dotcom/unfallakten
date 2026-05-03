# Unfallakten-System — Projektkontext für Claude

Koch, Schatz & Kollegen · Rechtsanwaltskanzlei Offenbach

## Pflichtlektüre zu Session-Beginn

Immer lesen:
- `docs/TODO.md` — Backlog, Prioritäten, erledigte PRDs

Bei Bedarf lesen (nur wenn die Aufgabe es erfordert):
- `docs/DATAMODEL.md` — bei DB-Änderungen, Schema-Migrationen, SQL-Abfragen
- `docs/ARCHITECTURE.md` — bei neuen Features, Routing, Dienst-Struktur
- `docs/DECISIONS.md` — bei Architektur-Fragen oder wenn Begründungen für bestehende Lösungen gefragt sind
- `docs/STATE.md` — bei expliziten Statusabfragen oder Sprint-Planung

## Wichtigste Regeln

- **RA-MICRO ist read-only** — niemals in die RA-MICRO SQL Server DB schreiben, nur in SQLite
- **Zielsprache Deutsch** — Benutzer ist Rechtsanwalt, nicht technisch, kommuniziert auf Deutsch
- **Keine unnötigen Abstraktionen** — nur umsetzen was explizit angefragt wird
- **Keine Kommentare** im Code außer bei nicht-offensichtlichem Verhalten
