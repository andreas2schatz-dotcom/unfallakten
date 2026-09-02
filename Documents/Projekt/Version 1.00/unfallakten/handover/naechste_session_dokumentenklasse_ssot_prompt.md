# Startprompt: Dokumentenklasse-SSOT umsetzen

Diesen Text in einer **frischen Sitzung** als erste Nachricht einfügen.

---

Führe den Plan `docs/superpowers/plans/2026-09-02-dokumentenklasse-ssot.md` aus.

Lies zuerst den Plan und die dort im Kopf verlinkte Spec
`docs/superpowers/specs/2026-09-02-dokumentenklasse-ssot-design.md`. Beide
sind vollständig — du brauchst keinen Kontext aus früheren Sitzungen.

Arbeite die neun Tasks der Reihe nach ab, testgetrieben, mit einem Commit
je Task. Halte nach Task 4 und nach Task 8 an und berichte, bevor du
weitermachst: das sind die beiden Migrationen, Task 8 ist destruktiv.

---

## Worum es geht

Die in der Review-Queue vergebene Dokumentklasse überlebt die Freigabe
nicht — in der DokumenteSection erscheint fast alles als „Sonstiges".
Ursache ist eine zweite, gröbere Klassenquelle (`dokumente.typ`, sechs
Werte) neben der Registry (23 Klassen). Die Spalte entfällt.

## Ausgangslage (geprüft 2026-09-02)

- Branch: `fragebogen-favoritenliste`
- `schema_version` = 72, nächste Migrationen sind 73 und 74
- Vollsuite grün: 2207 bestanden, 69 übersprungen, ~11,5 Minuten
- Die Entwicklungsdatenbank liegt im Docker-Volume
  (`/app/data/unfallakten.db` im Container `unfallakten-backend-dev`),
  **nicht** unter `backend/data/`

## Drei Fallen, die im Plan stehen und leicht übersehen werden

1. **Reloader-Falle.** Migrationen atomar in *einem* Schreibvorgang in
   `schema_manager.py` — Dict-Eintrag, Dispatch-Zweig und Funktion
   zusammen. Bei getrennten Edits stempelt der Flask-Reloader die Version
   über den generischen else-Zweig, ohne die Migration auszuführen.
   Betraf bereits die Migrationen 54, 55, 58, 60, 71.

2. **Zwei FK-Verletzungen bestehen bereits** (`klassifikation_training` →
   `dokumente`, `aktivitaeten` → `unfallakte`). Die Nachkontrolle nach
   Migration 74 muss auf **genau zwei** prüfen. **Null wäre verdächtig**,
   nicht beruhigend — dann stimmt die Prüfung nicht.

3. **„typ" ist im Projekt ein Allerweltswort** — `dateityp`,
   `ereignistyp`, `payload_typ`, `fahrzeug_typ`, und in
   `klage_routes.py:1920` heißt `typ` der Gerichtstyp (`amts`/`land`).
   Nie ungefiltert danach suchen. Beim Durchsuchen zusätzlich
   `frontend/dist` ausschließen, sonst verrauscht der Build-Bundle jede
   Suche.

## Nach der Umsetzung offen

- **Stakeholder-Portal.** Der Sync-Payload liefert danach `klasse` +
  `klasse_label` statt `typ`. Das Portal ist **nicht live**, ein
  abgestimmter Doppel-Deploy ist also nicht nötig. Die acht anzupassenden
  Portal-Dateien stehen in Spec Abschnitt 6.3; das Repo liegt unter
  `Projekt/Version 1.00/stakeholder-portal`. RA Schatz zieht das separat
  nach — **nicht** ungefragt mitmachen.
- **Betriebsabnahme** (Task 9): Die Belege-Ansicht zeigt danach Beträge,
  die vorher unsichtbar waren. Beabsichtigt, aber mit RA Schatz an einer
  bekannten Akte gegenprüfen.
