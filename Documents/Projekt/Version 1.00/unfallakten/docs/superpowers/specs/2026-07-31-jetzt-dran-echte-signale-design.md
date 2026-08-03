# Design: Fristen-Kachel weg · „Jetzt dran" auf echte Signale (Baustelle 1b → verschmilzt mit 2)

**Datum:** 2026-07-31 · **Status:** Design von RA Schatz freigegeben. Umsetzung **in bzw. direkt nach `dashboard-hell`** (Merge-Gate, s. u.).
**Herkunft:** UX-Review 2026-07-31 (`handover/2026-07-31_UX-Review_Roadmap.md`, B3). Ursprünglich „Fristen-Triage" — durch DB-Forensik verworfen, s. §2.
**Mockup:** https://claude.ai/code/artifact/5673d08a-e973-4f09-8d30-51fd53da9e5f — Dashboard ohne Fristen-Kachel, „Jetzt dran" mit Typ-Tags (Verjährung/§3a PflVG/Regulierung/Wiedervorlage) + Farbcodierung, Kacheln Termine/Gerichtstermine/Regulierung/Wiedervorlagen, Hinweis „gerichtliche Fristen → RA-MICRO". Standard hell. Quelle: Scratchpad `dash.template.html`.
**Nächster Schritt:** `superpowers:writing-plans` nach Merge-Gate.

---

## 1. Ziel

Die Dashboard-„Fristen" sind irreführend: Sie zeigen keine echten Fristen, sondern eine als „Fristen" etikettierte Auswahl von **Wiedervorlagen** — Quelle der erdrückenden „50 überfällig". Ziel: die falsche Kachel entfernen und die daran hängende **„Jetzt dran"-Leiste** aus *ehrlichen* Signalen speisen. Kein RA-MICRO-Wiedervorlage-Eintrag wird je wieder als „Frist" ausgegeben.

## 2. Vorgeschichte / Warum keine „Fristen-Triage" (verifiziert)

DB-Forensik über alle 8 RA-MICRO-Datenbanken (read-only, 2026-07-31, Details → Memory `feedback_ramicro_fristen_quelle`):
- RA-MICROs **echte Fristen** (eigenes Objekt mit „Erledigt am + grüner Haken": Felder Fristablauf, Aktenkurzbezeichnung, Aktenzeichen Gericht, Bemerkung, Erledigt, von SB, Notiz, Datenpool) sind in **keiner lesbaren SQL-Tabelle** auffindbar. Testfall Akte 1129/24 „Vorfrist Schriftsatzschluss" (SB PK): nirgends in SQL.
- Beweis der Trennung: `tblAktenWiedervorlagen` hat **keine** Erledigt-Spalte (WVs kann man nur schieben) — Fristen haben eine. Fristen liegen also nur im RA-MICRO-Programm, nicht im SQL-Mirror.
- Folge: Eine Fristen-Triage auf Fristen-Daten ist technisch **nicht möglich**. Kanzlei nutzt für echte Fristen weiterhin die **RA-MICRO-Tagesübersicht** (dort funktionierend, mit grünem Haken).

## 3. Ist-Zustand (verifiziert)

- `frontend/src/views/ActionBoardView.jsx`: ruft `apiDashboard.fristen()` → `GET /dashboard/fristen`. Speist **beide**: `FristenKachel` (`daten.fristen.eintraege`) **und** `JetztDranLeiste` (Props `fristenStatus` + `fristen`).
- `GET /dashboard/fristen` → `_lade_ramicro_fristen_hart()` (`backend/routers/dashboard_routes.py`): `tblAktenWiedervorlagen`, `iWiedervorlageGrund IN (21,22,31,46,51,55,75)`, −365..+14 Tage. = mislabelte Wiedervorlagen.
- Ehrliche Quellen existieren bereits:
  - `GET /dashboard/action-items` → `_lade_fristen` (lokale `todos`, `quelle='system'`: **Verjährung §199 BGB, §3a PflVG**, antwort_2w) — echte, systemeigene Fristen. Plus `_lade_regulierung_offen` (Differenz > 0, PflVG-Nähe).
  - `GET /dashboard/wiedervorlagen` → überfällige WVs.

## 4. Entscheidung

1. **Fristen-Kachel entfernen** (`FristenKachel` aus `ActionBoardView` raus).
2. **`/dashboard/fristen` + `_lade_ramicro_fristen_hart()` stilllegen** (nicht mehr aufrufen; Code entfernen oder als deprecated markieren). E2E-Test, der `/dashboard/fristen` abbricht, entsprechend anpassen.
3. **„Jetzt dran" auf echte Signale umstellen** (§5).

## 5. „Jetzt dran" — echte Datenquellen & Priorisierung

Zusammengeführte Top-N-Liste (N ≈ 3–5) aus drei ehrlichen Quellen, priorisiert:

| Prio | Quelle | Inhalt | Typ-Tag |
|---|---|---|---|
| 1 | `todos` (system), frist_typ `verjährung` / `pflvg_3a` | echte gesetzliche Fristen, nach Ablauf-Nähe | „Verjährung" / „§3a PflVG" |
| 2 | `_lade_regulierung_offen` | offene Regulierungen (Differenz > 0), PflVG-Nähe hebt Prio | „Regulierung" |
| 3 | `/dashboard/wiedervorlagen` (WV überfällig) | dringendste überfällige WVs, Verkehrsunfall-Scope (Referat 04) soweit ermittelbar | „Wiedervorlage" |

- Sortierung: Prio-1 immer zuerst (nach Restttagen aufsteigend), dann Prio 2/3 nach Überfälligkeit.
- `antwort_2w`-Todos sind weicher (Nachhak-Erinnerung) → nur nachrangig oder ausgeschlossen (offen, §11).
- Jeder Eintrag: Typ-Tag, Akte-Az, Mandant, Fälligkeit/Restttage, Klick → Akte öffnen.
- SB-Filter (bestehende Dashboard-Chips) wirkt weiter.

### 5a. Länge der Leiste (Kern — sonst verliert sie ihren Zweck)

Drei Regeln statt einer festen Zahl:

1. **Aufnahme per Schwelle, nicht per Ranking.** Ein Vorgang erscheint nur, wenn er wirklich dringend ist: harte Frist im Vorfrist-Fenster; §3a-PflVG ≤ 7 Tage; Regulierung überfällig über Schwelle; WV überfällig. Nicht-Dringendes bleibt in den Kacheln darunter. Dadurch bleibt die Leiste von sich aus kurz. Qualifiziert nichts → ehrlicher Leerzustand „Nichts Dringendes — guter Tag", **nicht** mit Weniger-Dringendem auffüllen.
2. **Weiche Obergrenze 5 (Ziel 3–4) für die Anzeige.** Mehr als 5 gleichzeitig sichtbar zerstört den „zuerst"-Charakter.
3. **Harte gesetzliche Fristen (Verjährung / §3a PflVG) werden von der Obergrenze NIE verdrängt.** Sind sie fällig, stehen sie immer drin; die weichen Slots (Regulierung/WV) weichen. So kann die Kürzung nie eine echte Frist verstecken.

**Überlauf:** Qualifizieren mehr als die Obergrenze, dezenter Hinweis „+ N weitere dringende" (aufklappen bzw. Sprung in die passende Kachel) — nie stilles Abschneiden.

**Umsetzungsweg (Vorschlag):** `JetztDranLeiste` aus den **bereits vorhandenen** Endpunkten `action-items` (fristen + regulierung_offen) + `wiedervorlagen` speisen — kein RA-MICRO-Fristen-Zugriff nötig. Alternativ ein neuer komponierender Endpoint `GET /dashboard/jetzt-dran` (in writing-plans entscheiden).

## 6. Ehrlichkeits-Hinweis

Für **gerichtliche Fristen** bleibt die RA-MICRO-Tagesübersicht die Quelle. Optional dezenter Dashboard-Hinweis „Gerichtliche Fristen: in RA-MICRO" (statt einer Fake-Liste). Nicht-Ziel: RA-MICRO-Fristen selbst anzeigen (technisch nicht lesbar).

## 7. Layout-Konsequenz (dashboard-hell)

`dashboard-hell` hat „Fristen links oben (3:2)" prominent platziert. Ohne Fristen-Kachel wird die Fläche frei:
- „Jetzt dran" wird prominenter (rückt nach oben).
- Freie Fläche → Termine / Regulierung / Wiedervorlagen.
- Genaues Layout im Zuge von `dashboard-hell` (dort ist der Dashboard-Umbau ohnehin offen).

## 8. Einordnung & Reihenfolge

- **Merge-Gate:** erst `aktenanlage` → `main`, dann `dashboard-hell` → `main`. Diese Änderung revidiert dashboard-hell-Layout → am besten **in dashboard-hell einarbeiten** oder unmittelbar danach.
- **Verschmilzt mit Baustelle 2 (Alarm → Aktion):** „Jetzt dran = echte Dringlichkeit" ist inhaltlich der Kern von Baustelle 2 → 1b-Rest und 2 werden zusammen geplant. Damit entfällt „Volumen zähmen / Fristen-Triage" als eigene Baustelle.

## 9. Nicht-Ziele

- Keine echten RA-MICRO-Fristen anzeigen (nicht SQL-lesbar).
- Keine Änderung an der eigenständigen Wiedervorlage-Ansicht (Menü) — nur die Dashboard-Kachel/-Leiste.
- Kein Schlummern/Erledigt-Overlay mehr nötig (war für die verworfene Fristen-Triage gedacht).

## 10. Tests

- `JetztDranLeiste` rendert aus den echten Quellen; Prio-1-Fristen (Verjährung/PflVG) erscheinen zuoberst.
- Kein Aufruf von `/dashboard/fristen` mehr; alter E2E-Abbruchtest angepasst/entfernt.
- SB-Filter wirkt auf die neue Leiste.
- Leerzustand (keine dringenden Signale) zeigt sauberen „nichts dringend"-Zustand statt falscher Entwarnung.

## 11. Offene Punkte (writing-plans)

- `antwort_2w`-Todos in „Jetzt dran" aufnehmen oder nicht?
- Neuer Endpoint `/dashboard/jetzt-dran` vs. Frontend-Komposition aus vorhandenen Endpunkten.
- Konkrete Schwellenwerte (§5a Regel 1): Vorfrist-Fenster Verjährung, PflVG-Tage, Regulierung-Überfälligkeit in Tagen. Obergrenze 5 (§5a) — bei Bedarf justieren.
- Misch-Sortierung Prio 2 vs. 3.
- Verkehrsunfall-Scope (Referat 04) auf die WV-Quelle anwenden (analog `REFERAT_VERKEHRSUNFALL = {4}` in `wiedervorlage_routes.py`).
- Platzierung/Text des optionalen „Gerichtliche Fristen: in RA-MICRO"-Hinweises.
