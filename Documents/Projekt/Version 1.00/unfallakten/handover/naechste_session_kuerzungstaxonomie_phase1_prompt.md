# Prompt für die nächste Session — Kürzungstaxonomie Phase 1 (Planung)

> Zum Einfügen als Start-Prompt. Stand: 2026-07-23 nach Abschluss Phase 0 (Handtest).

---

Wir planen Phase 1 der Kürzungstaxonomie. Heutige Session = **Planung mit `superpowers:writing-plans`** auf Basis von Konzept-Abschnitt 12.6 — kein Umsetzungscode, bevor der Plan steht und freigegeben ist.

Pflichtlektüre in dieser Reihenfolge:
1. `docs/TODO.md` — Eintrag „Kürzungstaxonomie" (Phase-0-Befunde).
2. `handover/KONZEPT-Kuerzungstaxonomie-Vorgangsautomat.md` — Abschnitt 12 (verbindlich, besonders 12.5 + 12.6); Abschnitte 2 und 10 nur bei Bedarf.
3. `docs/DECISIONS.md` — die 5 Einträge vom 2026-07-23, besonders die beiden neuen: **Entscheidungs-Tor** (Option (b), getrennte Faltungen) und **Phase-0-Abschluss** (Zielwerte, Matching-Architektur, A–F-Zuordnung).
4. `handover/phase0-handtest-stichproben.md` — nur Abschnitt „Ergebnis der Tiefenprüfung" (Kennzahlen + Kernerkenntnisse).

Verbindliche Vorgaben aus Phase 0 (nicht neu diskutieren):
- **Kürzung = Ereignis-Attribut** (Option b): Tripel (Position × Typ × Betrag) lebt in `ereignis_positionen`; keine neue Tabelle; `regulierung_positionen` bleibt Erfassungsweg (Doppelschreibmuster).
- **Zwei getrennte Faltungen:** Vorgangsautomat = eigene Faltung über denselben Ereignisstrom, liest Positionszustand, schreibt nie hinein.
- **Kürzungs-Erkennung = Differenz Forderung (Soll) vs. Zahlung (Ist)** — nie aus dem Abrechnungsschreiben allein. Keyword-Matching liefert nur den TYP, nur auf Begründungsdokumenten (Prüfberichte, Erläuterungen); Zahlmitteilungen werden auf Positionen/Beträge geparst.
- **Matching-Architektur:** regelbasiert als Erstvorschlag, LLM nur Fallback. Zielwerte nach ~4 Wochen: Abdeckung ≥ 90 %, Trefferquote Typ ≥ 75 %, Positionszuordnung ≥ 90 %.
- **Registry-Migration 19 → ~30 A–F-Typen** nach der Zuordnungstabelle im DECISIONS-Eintrag (inkl. neue Typen A07 Neu-für-alt, A11 Abrechnungszeitpunkt, C01b Wertminderung-Steuer; 4 Quelldateien sind KEIN Kürzungstyp). Alt-IDs stabil halten, `verifiziert_am` = „handgeprüft RA Schatz, Juli 2026" stempeln.
- **Editor-Komponente entsteht in Phase 1**, V11 erbt sie (DECISIONS 2026-07-23).

Der Plan muss mindestens abdecken (aus 12.6 + 10.5):
1. Registry-Migration `kuerzungsarten` → A–F-Taxonomie (+ Import der zugeordneten Quelldateien aus `tools/textbausteine/`, inkl. Platzhalter-Parametrisierung).
2. `pruefdienstleister`-Stammtabelle + FK am Abrechnungsschreiben; `begruendung_roh` als Pflichtfeld je geflaggter Kürzung (mit Betrag als Pflichtangabe).
3. Typ-Zuordnung im ReguWizard/Review-UI schärfen (gleicher Bildschirm für RA und ReFa; Baustein-Vorauswahl wirkt in Stellungnahme UND Klage-Wizard).
4. Runde-1↔Runde-2-Vergleich auf dem Ereignisstrom (Nachzahlung = Differenz der `gekuerzt`-Beträge je position_key × Typ; Praxisbeleg: Stichprobe 20, Kostenpauschale 25 € → +5 €).
5. Dokument-Verkettung Abrechnungsschreiben ↔ Prüfbericht derselben Abrechnungsrunde (Stichprobe 25: Zahlung und Begründung in getrennten Dokumenten).
6. Stichwort-Fixes ins Matching: Wortgrenzen (Kleinteilepauschale ≠ Unkostenpauschale), „Kennzeichen" auf Schilderkosten/Erneuerung verengen, ControlExpert-Tabellen strukturiert parsen; Positions-Synonymik je Versicherer-Template („Differenzbetrag" = Fahrzeugschaden usw.).
7. Editor-Komponente (Platzhalter-Hilfe, Live-Vorschau, Registry+Override) — wiederverwendbar für V11.

Kleine Vorab-Restposten (können vor der Planung in 10 Minuten erledigt werden):
- `tools/textbausteine/ghpfstverort.DOC` in Word öffnen → A04-Zuordnung bestätigen.
- 3 Datenqualitäts-Funde aus der TODO: Dokument 41478 gehört zu 852/25 (liegt unter 971/25), Dokument 43429 referenziert 418/28 (liegt unter 980/25), Dokument 2562 ist ein SV-Gutachten (als „abrechnungsschreiben" klassifiziert, Akte 562/26).

Regeln: RA-MICRO strikt read-only · aktive DB ist das Docker-Volume `/app/data/unfallakten.db` im Container `unfallakten-backend-dev`, NICHT `backend/data/` · Migrationen atomar in EINEM Edit (Flask-Reloader-Falle!) · TDD bei der Umsetzung · Zielsprache Deutsch, ich bin Anwalt, nicht Techniker · Befunde sofort in TODO/DECISIONS statt nur in Berichten.
