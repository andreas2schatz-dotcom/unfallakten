# Design: Klage-Wizard — Standardtexte in den Einstellungen pflegbar

> Stand: 2026-07-19 · Freigegeben von RA Schatz (Brainstorming-Session)
> Paket 4 von 4 der Klage-Wizard-Verbesserungsrunde (1: Entwurf speichern, 2: UI-Führung, 3: Gesamtvorschau)
> Scope-Session: nur Design, keine Umsetzung in dieser Session. Entspricht der vorgemerkten Struktur-Verbesserung **V11** (docs/BUGFIX_KLAGE_WIZARD.md).

## Problem

~56 juristische Standardtexte der Klageschrift stehen fest im Code (`backend/word/klage_service.py`, `sg_text_builder.py`, Frontend-Generatoren in `KlageWizard.jsx`). Jede Formulierungsänderung braucht einen Programmierer. Inventar (Explore 2026-07-19):

- **Kategorie A — statisch** (~12, 21 %): u. a. Auslandsunfall-Absatz (EuGH C 463/06 + BGH VI ZR 200/05; existiert nur im Frontend, `buildSachverhaltText`), Versäumnisurteil-Block, RVG-Begründung Abs. 2+3, Schluss-Hinweissatz.
- **Kategorie B — Platzhalter, grammatikneutral** (~20, 36 %): Fall-B-Klemm-/Differenz-Sätze, RVG-Tabellenzeilen, SG-Behandlung/Dauerfolgen, Verzugssatz mit Datum, Grundhaftungssatz.
- **Kategorie C — grammatik-abhängig** (~24, 43 %): alle Anträge, Sachverhalt-Kernsätze, Aktivlegitimation, Einwände-Rahmensätze (Kopfsatz, 5 Einleitungs-Varianten, Schlusssatz), SG-Kernsatz, Alleinhaftungssatz. Beugung kommt aus den zentralen V3-Partei-Grammatik-Helfern (`_beklagten_grammatik`, `_get_kl_genus_vars` u. a., Backend/Frontend wortgleich).

**Abgrenzung:** Die Textbausteine je Kürzungsart sind seit PRD-02 in der DB pflegbar und bleiben unberührt. Pflegbar werden die festen Rahmen- und Kernsätze.

**Nebenbefund (mitzubeheben in Stufe 1):** Fall-B-/Differenz-/Teilregulierungssätze im Backend hartcodieren „Die Beklagte" (Sg. fem.) und nutzen die Beklagten-Grammatik-Helfer nicht — inkonsistent bei mehreren/männlichen Beklagten.

## Entscheidung (RA Schatz, 2026-07-19)

**Stufenmodell** (verworfen: alles auf einmal; Varianten je Grammatikfall — vierfacher Pflegeaufwand):

- **Stufe 1:** Kategorien A+B (~32 Bausteine) pflegbar — nur Wert-Platzhalter, kein Grammatik-Risiko.
- **Stufe 2:** Kategorie C (~24 Bausteine) pflegbar über **vorflektierte Platzhalter**.

Zusatzanforderung RA Schatz: Die Einstellungen brauchen eine **Einfügehilfe für Grammatik-Platzhalter** (siehe UI).

## Architektur

**Baustein-Verzeichnis (Registry):** je Baustein Kennung, Standardtext, erlaubte Platzhalter (mit Pflicht-Markierung), Dokumentabschnitt, Beschreibung. Muster: YAML-Registry, fail-loud beim App-Start (wie `klasse_ereignistyp.yaml` / `rausch_absender.yaml`). Die **Standardtexte bleiben im Programm** (Registry); die DB speichert **nur Abweichungen** (neue Tabelle `standardtext_override`: baustein_key UNIQUE, text, geaendert_am — Migration nach den bekannten Regeln). „Auf Standard zurücksetzen" = Override löschen; nichts ist kaputt-löschbar.

**Klage-Service-Umbau (V11):** `generiere_klageschrift` und die Frontend-Generatoren beziehen jeden Baustein aus dem Verzeichnis (Override vor Standard) statt aus f-Strings. Frontend holt die aufgelösten Texte via API (kein dupliziertes Verzeichnis). Der Auslandsunfall-Absatz zieht vom Frontend ins zentrale Verzeichnis um. **Kopplung Paket 3:** die Gesamtvorschau speist sich aus demselben Aufbauweg — der Umbau ist gemeinsame Vorarbeit; Reihenfolge in der Planung abstimmen.

**Platzhalter-Auflösung:**

- Wert-Platzhalter (Stufe 1): `{{betrag}}`, `{{datum}}`, `{{quote}}`, `{{anlage_nr}}` … — eingesetzt wie heute.
- Vorflektierte Platzhalter (Stufe 2): `{{klaeger}}` → „Der Kläger/Die Klägerin/Die Kläger", `{{klaeger_dativ}}`, `{{klaeger_genitiv}}`, `{{beklagte_wird_verurteilt}}`, `{{beklagte_zu_n}}` …, plus Verb-Paare mit Partei-Bezug: `{{kl:hat/haben}}`, `{{bek:haftet/haften}}` — aufgelöst durch die bestehende Grammatik-Schicht. Am erzeugten Dokument ändert sich ohne Override nichts (Golden-Parität).

## Einstellungs-UI

Neue Karte **„Standardtexte Klageschrift"**:

- Bausteine gruppiert nach Dokumentabschnitt (Anträge, Sachverhalt, Aktivlegitimation, Würdigung/Einwände, Schmerzensgeld, Verzug, Gebühren, Schluss); geänderte Bausteine sichtbar markiert; Suche.
- **Editor je Baustein** mit:
  - **Platzhalter-Einfügehilfe (Pflichtbestandteil, RA Schatz):** neben dem Textfeld eine gruppierte Liste aller für diesen Baustein erlaubten Platzhalter (Gruppen: Kläger / Beklagte / Verb-Paare / Werte), jeder als anklickbarer Chip mit Klartext-Beschreibung und Beispielwert („{{klaeger_dativ}} — ‚dem Kläger' / ‚der Klägerin' / ‚den Klägern'"); Klick fügt den Platzhalter an der Cursor-Position ein. Kein Auswendiglernen von Codes.
  - **Live-Vorschau an einer Beispiel-Akte** (Klägerin + zwei Beklagte, damit Grammatikfälle sichtbar werden) — aktualisiert beim Tippen.
  - **Speicher-Prüfung:** unbekannter Platzhalter → Fehler (Speichern blockiert); fehlender Pflicht-Platzhalter (z. B. Betrag im Zahlungsantrag) → Warnung mit bewusstem Bestätigen.
  - „Auf Standard zurücksetzen" je Baustein (mit Anzeige des Standardtexts vor dem Zurücksetzen).

## Tests (bei Umsetzung)

- Registry: fail-loud (unbekannter Platzhalter im Standardtext, doppelte Kennung), Vollständigkeit gegen Inventar.
- Golden-Parität: ohne Overrides erzeugt der umgebaute Service byte-identische Texte zur V10-Golden-Matrix.
- Override-Auflösung, Reset, Speicher-Prüfung (Fehler/Warnung), Migrations-Guard.
- Grammatik-Platzhalter: Auflösung je Genus/Numerus/Partei gegen die bestehenden Helfer-Tests.
- Vitest: Einfügehilfe (Chip → Cursor-Einfügung), Live-Vorschau, Markierung geänderter Bausteine.
- Nebenbefund-Fix: Fall-B-Sätze mit mehreren/männlichen Beklagten.

## Bewusst nicht im Scope

- Kürzungsart-Textbausteine (bereits pflegbar), Rubrum/Tabellenaufbau (Daten, kein Freitext), Formatierungs-Optionen im Editor, Textbausteine anderer Dokumente (Forderungsschreiben etc. — ggf. spätere Runde nach demselben Muster).
