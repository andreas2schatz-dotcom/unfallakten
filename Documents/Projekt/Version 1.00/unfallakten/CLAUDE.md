# Unfallakten-System — Projektkontext für Claude

Koch, Schatz & Kollegen · Rechtsanwaltskanzlei Offenbach

## Pflichtlektüre zu Session-Beginn

Immer lesen:
- `docs/TODO.md` — **nur** die schlanke Arbeitsliste (In Arbeit, Backlog, Unklar). Bewusst kurz gehalten, damit der Kontext nicht vollläuft.

Bei Bedarf lesen (nur wenn die Aufgabe es erfordert):
- `docs/CHANGELOG.md` — Umsetzungs-Historie (was wurde wann gebaut, Commits, Besonderheiten). NICHT bei jedem Start laden.
- `docs/DATAMODEL.md` — bei DB-Änderungen, Schema-Migrationen, SQL-Abfragen
- `docs/ARCHITECTURE.md` — bei neuen Features, Routing, Dienst-Struktur
- `docs/DECISIONS.md` — bei Architektur-Fragen oder wenn Begründungen für bestehende Lösungen gefragt sind
- `docs/STATE.md` — bei Statusabfragen/Sprint-Planung; Abschnitt 0 enthält aktuelle **Deploy-/Betriebswarnungen**

## Wichtigste Regeln

- **RA-MICRO ist read-only** — niemals in die RA-MICRO SQL Server DB schreiben, nur in SQLite
- **Zielsprache Deutsch** — Benutzer ist Rechtsanwalt, nicht technisch, kommuniziert auf Deutsch
- **Keine unnötigen Abstraktionen** — nur umsetzen was explizit angefragt wird
- **Keine Kommentare** im Code außer bei nicht-offensichtlichem Verhalten
