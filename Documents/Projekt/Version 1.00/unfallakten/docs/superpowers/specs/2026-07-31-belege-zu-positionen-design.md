# Design: Belege → Positionen (Vorbefüllen mit Bestätigung) — Baustelle 3

**Datum:** 2026-07-31 · **Status:** Design von RA Schatz freigegeben. Umsetzung nach Merge-Gate.
**Herkunft:** UX-Review 2026-07-31 (`handover/2026-07-31_UX-Review_Roadmap.md`, B7).
**Mockup:** https://claude.ai/code/artifact/14ac0f02-2a09-457c-8ff0-f52d7c9bd26d — Schaden-Ansicht: amber vorbefüllte Positionen (unbestätigt) mit Herkunfts-Chip + inline ✓/✗, Sammelleiste „Alle bestätigen", Konflikt-Zeile (rot, „Beleg weicht ab"), bestätigte Zeile (grün), „Zu prüfen"-Block mit Positions-Dropdown, Referenzdokumente (Abrechnungsschreiben bleibt Referenz). Standard hell. Quelle: Scratchpad `belege.template.html`.
**Nächster Schritt:** `superpowers:writing-plans` nach Merge-Gate.

---

## 1. Ziel

Geparste Gutachten/Rechnungen sollen ihre Beträge in die Schadenpositionen **vorbefüllen**, statt dass RA Schatz sie abtippt — sicher, weil die Beträge am Ende Forderung/Klage werden. Prinzip: **Vorbefüllen + eine Bestätigung**; nichts wird ohne Blick verbindlich.

## 2. Ist-Zustand (verifiziert, Explore-Kartierung 2026-07-31)

- **Schadenpositionen** = eine Zeile je Akte in Tabelle `schadenpositionen`, **Spalte pro Position** (`backend/models/schaden.py:147-207`; „sonstige Schäden" als JSON in `wdm_extras_json`). Speichern: `PUT /akten/<id>/schaden` (`backend/routers/schaden_routes.py:185-230`). Belege-n:m: `schadenposition_belege`.
- **Parser vorhanden:** Gutachten-Parser liefert einen fertig gemappten Block `schadenpositionen` mit DB-Keys (`backend/routers/pdf_parse_routes.py:295-309`, `backend/parsers/gutachten_parser.py`). Rechnungs-Parser liefert nur Gesamtbeträge (`backend/parsers/rechnung_parser.py:16-24`). Output in `dokumente.parse_json` bzw. `rechnung_parse_cache`.
- **Mapping Beleg → Position vorhanden**, aber verstreut: `_KLASSE_POSITION_MAP`/`_FIRMA_POSITION_MAP` (`belege_routes.py:122-152`), Gutachten→4 Positionen (`belege_routes.py:585-617`), Registry `rechnungstyp_mapping.yaml`.
- **Kandidaten-Erzeugung vorhanden:** `GET /belege/kandidaten` (`belege_routes.py:492-959`) liefert Position + Betrag + Konfidenz. „🤖 Auto-Zuordnung" (`DokumenteSection.jsx`) erzeugt nur Vorschläge im Frontend-Store, **schreibt nichts**.
- **„📄 Aus Gutachten"** (`SchadenSection.jsx:323-368`): füllt Formular-State vor, speichert **nicht** (Extra-Klick nötig). „🔍 RA-Micro WDM" füllt und speichert direkt.
- **Persistenz heute nur manuell:** „Alle übernehmen" (`SchadenSection.jsx:486-511`, `DokumenteSection.jsx:523-560`) schreibt via `apiBelege.zuordnen` + `apiSchaden.speichern`, **nur bei Konfidenz ≥ 0.80**.
- **„Referenz-Dokumente (ohne Positionszuweisung)"** (`SchadenSection.jsx:1184-1218`): Kandidaten mit `position_key === null` — Abrechnungsschreiben (betreffen mehrere Positionen, bewusst `null`) + unklassifizierte Rechnungen.

**Die Lücke:** Parsen + Mapping + Vorschlag existieren. Was fehlt/manuell ist: der **Schreibschritt Kandidat → `schadenpositionen.<key>`** ohne Klick, plus eine saubere Trennung sicher/unsicher.

## 3. Getroffene Entscheidungen (RA Schatz, 2026-07-31)

1. **Automatik-Grad:** Vorbefüllen + **eine Bestätigung** (nicht voll automatisch).
2. **Unsichere:** nur **sichere** Treffer vorbefüllen; unsichere in getrennte „Zu prüfen"-Liste.
3. **Scope:** nur die Formular-Befüllung (`schadenpositionen`). Zwei-Modelle-Konsolidierung ausdrücklich **nicht** hier (§9, TODO-Eintrag angelegt).

## 4. Vorbefüll-Zustand („aus Beleg – unbestätigt")

- Sichere Kandidaten (Konfidenz ≥ Schwelle, eindeutiger `position_key`) erscheinen als **Wert im Positionsfeld**, sichtbar markiert: eigener Rahmen/Farbe + Herkunfts-Chip (z. B. „aus Gutachten" / „aus Rechnung: Brass" + %).
- Der Wert zählt **noch nicht** zur Forderung, solange unbestätigt.
- **Architektur:** Der Vorbefüll-Wert ist eine **Überlagerung aus den vorhandenen Kandidaten** (aus `parse_json` reproduzierbar), **kein** persistierter Halbzustand in `schadenpositionen`. Erst Bestätigung schreibt in die Tabelle → nichts Unbestätigtes in der bindenden Quelle, überlebt Reload (Kandidaten sind neu ableitbar).

## 5. Bestätigungs-Schritt

- **Pro Feld:** „✓ übernehmen".
- **Sammel:** Leiste „N Positionen aus Belegen · Alle bestätigen".
- Bestätigung schreibt via bestehende `apiSchaden.speichern` (`schadenpositionen`) + `apiBelege.zuordnen` (`schadenposition_belege`), Markierung verschwindet.
- **Konflikt-Schutz:** Hat ein Feld bereits einen bestätigten/handeingetragenen Wert und ein Beleg schlägt einen anderen vor → **kein Überschreiben**; Hinweis „Beleg sagt X, Feld hat Y" zum Auflösen.

## 6. „Zu prüfen"-Liste (unsichere)

- Belege mit Betrag, aber unklarer Position → getrennter Block „Zu prüfen (N)": Betrag + Auswahl der Zielposition (oder „als Referenz behalten"). Füllen **nichts** automatisch ins Formular.
- **Abrechnungsschreiben** (`position_key === null`, mehrere Positionen) bleiben **Referenzdokument** (wie heute), nicht „zu prüfen".

## 7. Nachvollziehbarkeit

Jede vorbefüllte/bestätigte Position zeigt ihre **Herkunft** (Dokument); Klick → Beleg öffnen. Jede Zahl bis zum PDF rückverfolgbar.

## 8. Datenfluss (neu)

```
parse_json/cache ─► GET /belege/kandidaten (Position+Betrag+Konfidenz)
   ├─ sicher (≥ Schwelle, key≠null) ─► Vorbefüll-Overlay im Positionsfeld (unbestätigt)
   │        └─[Bestätigen]─► apiSchaden.speichern + apiBelege.zuordnen ─► schadenpositionen
   ├─ unsicher (Betrag, key unklar) ─► Block „Zu prüfen" (manuelle Zuordnung)
   └─ key=null / Abrechnungsschreiben ─► Referenzdokumente (unverändert)
```
Neu ist **kein** Parser/Mapping, sondern: der Vorbefüll-Overlay-Zustand, die Sicher/Unsicher-Trennung an der Schwelle, die Bestätigungs-UX (inline + Sammel) und der Konflikt-Schutz.

## 9. Nicht-Ziele

- **Zwei-Positions-Modelle-Konsolidierung** (Formular `schadenpositionen` vs. Ereignis-Modell `ereignis_positionen`) — eigene Baustelle, in `docs/TODO.md` unter „Unklar/zu klären" erfasst.
- Kein Aufbrechen von Rechnungen in Einzelpositionen (Parser liefert Gesamtbetrag).
- Keine Änderung an RA-Micro-WDM-Direktübernahme.

## 10. Offene Punkte (writing-plans)

- Konkrete **Sicher-Schwelle** (heute 0.80) — bestätigen/justieren.
- Genaue visuelle Markierung des Vorbefüll-Zustands (Farbe/Rahmen/Chip) — im Mockup vorschlagen.
- Verhalten bei mehreren Belegen für dieselbe Position (jüngster gewinnt? beide zeigen?).
- Ob „Alle bestätigen" pro Beleg oder pro Position gruppiert.

## 11. Tests

- Sicherer Kandidat erscheint als unbestätigter Vorbefüll-Wert, zählt erst nach Bestätigung zur Forderung.
- Unsicherer Kandidat landet in „Zu prüfen", nie im Feld.
- Konflikt: vorhandener Wert wird nie überschrieben.
- Bestätigung schreibt `schadenpositionen` + `schadenposition_belege` und setzt Herkunft.
- Reload: unbestätigte Vorbefüllung wird aus Kandidaten neu abgeleitet, nicht als Forderung gezählt.
