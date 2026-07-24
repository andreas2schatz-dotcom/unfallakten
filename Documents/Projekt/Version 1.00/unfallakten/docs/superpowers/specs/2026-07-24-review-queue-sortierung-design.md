# Design: Review-Queue — Sortier-Toggle Eingangsdatum

> Stand: 2026-07-24 · Freigegeben von RA Schatz (Brainstorming-Session)
> Scope-Session: nur Design, keine Umsetzung in dieser Session.

## Problem

Die Review-Queue (`frontend/src/views/ReviewQueueView.jsx`) zeigt Dokumente in fester Server-Reihenfolge: `ORDER BY erstellt_am ASC, konfidenz DESC, id ASC` (`backend/routers/intake_routes.py:163`, bewusste Grundpriorisierung aus `freigabe.md` Stufe 1: älteste Dokumente zuerst, damit nichts vergessen wird). Wenn RA Schatz ein Dokument manuell importiert, landet es je nach Alter irgendwo in dieser Liste — es gibt keine Möglichkeit, gezielt nach den zuletzt eingegangenen Dokumenten zu schauen, um den manuellen Import wiederzufinden.

## Entscheidungen (RA Schatz, 2026-07-24)

1. **Nur ein Sortier-Toggle** für das Eingangsdatum (aufsteigend/absteigend) — keine weiteren Filter (Klasse, Status, Fristprio) in diesem Zug.
2. **Client-seitig, kein Backend-Eingriff:** Die Server-Reihenfolge (inkl. Konfidenz-Tiebreak) bleibt die Datenquelle. „Absteigend" ist schlicht die umgedrehte Liste, kein zweiter Sortier-Algorithmus.
3. **Gruppen-Ebene:** E-Mail-Anhänge (Kind-Dokumente über `parent_zustellung_id`, gruppiert via `gruppiereQueue()`) bleiben unter ihrem Eltern-Dokument eingerückt; sortiert wird die Gruppen-Liste anhand des Eltern-Eintrags, nicht einzelne Kinder verstreut.
4. **Persistenz:** Gewählte Richtung wird in `localStorage` gespeichert und bleibt über Sessions hinweg bestehen.
5. **Sichtbarkeit:** Toggle nur in der Queue-Ansicht (nicht im Papierkorb-Tab).

## UI

Kleiner Toggle-Button im Queue-Header, unterhalb der Zeile „X bereit · Y fehlerhaft" (`ReviewQueueView.jsx` um Zeile 1364), sichtbar nur wenn `ansicht === "queue"`:

- Zustand aufsteigend (Standard): Label „🕓 Älteste zuerst"
- Zustand absteigend: Label „🕓 Neueste zuerst"
- Klick kehrt die Richtung um.

## Implementierung (Umriss)

- Neuer State `sortAbsteigend` (boolean), initialisiert aus `localStorage.getItem("reviewQueueSortAbsteigend") === "true"`.
- Beim Umschalten: State togglen + `localStorage.setItem(...)`.
- Rendering: `const gruppen = useMemo(() => { const g = gruppiereQueue(queue); return sortAbsteigend ? [...g].reverse() : g; }, [queue, sortAbsteigend]);` — ersetzt den bisherigen Inline-Aufruf `gruppiereQueue(queue).map(...)` an Zeile 1396.
- Keine Änderung an `intake_routes.py` / Backend-Query.

## Tests

- Unit-Test für die Sortier-/Umkehr-Logik (z. B. `gruppen`-Reihenfolge bei `sortAbsteigend=true/false`), analog zu bestehenden `ReviewQueueView.*.test.jsx`-Dateien.
- Manueller Browser-Nachtest: Toggle klicken, Reihenfolge visuell prüfen, Reload → Richtung bleibt erhalten (localStorage).

## Nicht im Scope

- Weitere Filter (Klasse, Status, Fristprio) — potenzielle Folge-Iteration, falls sich Bedarf zeigt.
- Änderung der Server-seitigen Standard-Priorisierung.
- Sortierung im Papierkorb-Tab.
