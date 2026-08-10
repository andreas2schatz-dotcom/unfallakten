# Changelog – Unfallakten-Verwaltungssystem

> Archiv der Umsetzungs-Protokolle (was wurde wann gebaut, Branch/Commits, Besonderheiten).
> **Keine Pflichtlektüre** — nur bei Bedarf nachschlagen.
> Aktuelle Arbeit: `docs/TODO.md` · Entscheidungen mit Begründung: `docs/DECISIONS.md` · Deploy/Betrieb: `docs/STATE.md`.
> Neueste Einträge oben.

---

## 2026-08-10 — Übersicht-Redesign A+B: Summen-SSOT, 3 Akkordeons, Onboarding-Fächer, Aktions-Pills (Branch `abschlussbericht`)

Umsetzung der Redesign-Mockups A+B (`handover/2026-08-10-uebersicht-redesign-mockups.md`, von RA Schatz freigegeben), SDD-Plan mit 11 Tasks im Anschluss an die Review-Session vom selben Tag (Befund-Katalog: `handover/2026-08-10-uebersicht-review-befunde.md`, löst B3 sowie die dort unter „Bewusst offen" vermerkten Doppel-Requests/-Logiken). Frontend-Vollsuite 491/491 grün.

- **Task 1 (`ddcccc82`):** Summen-Helfer extrahiert, `PositionsDashboard` bekommt eine `daten`-Prop statt eigenem Fetch — Vorbereitung für die gemeinsame Summen-Quelle.
- **Task 2 (`837ac355`, Befund B3):** Header-KPI rechnet jetzt aus den Ereignismodell-Summen (`/akten/<az>/positionen/status`); die Alt-Berechnung (`liveBrutto × HQ`) läuft nur noch als Fallback für Bestandsakten ohne Ereignisse. Siehe DECISIONS.md.
- **Task 3 (`68a8bed9`):** Redesign A umgesetzt — FinanzBand, RegulierungsTabelle und Forderungshistorie aus der Übersicht entfernt, durch 3 Akkordeons ersetzt, Phasenberechnung liest dieselben SSOT-Summen; `PositionsDashboard`-Titel zu „Positionen" vereinfacht.
- **Task 4 (`11e417c6`):** Forderungshistorie in den Regulierung-Tab verschoben (neue Komponente `components/ForderungshistorieKarte.jsx`).
- **Task 5 (`bae596fd`, Fix `723d51a4`):** Check-Pills mit Aktions-Popover, `mandantAktionen.js` als wiederverwendbare Helfer; Review-Fix hebt `AktionsPill` auf Modulebene, damit der Popover-State Re-Renders übersteht.
- **Task 6 (`4029846a`):** Onboarding-Checks als pure Funktion (`onboardingChecks.js`) — Vorbereitung für die Fächer-Darstellung.
- **Task 7 (`8d65f540`):** Redesign B umgesetzt — Onboarding-Fächer im PhasenStrip ersetzen den bisherigen Hub-Banner, `OnboardingHub` komplett entfernt.
- **Task 8 (`4703fb03`):** RA-Micro-Akkordeon zeigt nur noch Beteiligte, Kachel-Checks raus, `mandant-checks` nur noch 1 Request pro Akte statt 3.
- **Task 9 (`a326ab08`):** Tab-Leiste mit Farbpunkten/Badges statt Status-Emojis, 💰-Icon für den Gebühren-Tab, Button-Einrückung gefixt.
- **Task 10 (`7d4c3487`):** `dringlichkeit()`-Ampel zu `todoDringlichkeit()` dedupliziert (vorher 3× kopierte Logik).
- **Task 11 (dieser Eintrag):** Doku-Abschluss — DECISIONS.md (Summen-SSOT-Entscheidung), CHANGELOG.md, TODO.md.
- **Offen (Human-Gate):** Browser-Abnahme durch RA Schatz (Fächer, Pill-Popover, KPI-Zahlen an echter Akte, Bestandsakten-Fallback) — siehe TODO. Merge-Strategie `abschlussbericht` → `main` weiterhin ungeklärt (Branch stapelt auf Intake-Branch). Mockup C (Cockpit) nur bei Bedarf.

---

## 2026-08-10 — Übersicht-Review: 7 Befunde gefixt + toter Code entfernt (Branch `abschlussbericht`)

Review der ÜbersichtSection/AkteDetailView vom selben Tag (Befund-Protokoll: `handover/2026-08-10-uebersicht-review-befunde.md`, Redesign-Mockups separat). Alle Fixes TDD (11 neue Tests RED→GREEN), Frontend-Vollsuite 476/476 grün.

- **B1 (Crash):** `RegulierungsTabelle` referenzierte `effRep`/`ist130`, die dort nie definiert waren (unvollständig aus `constants.js` kopiert) — ReferenceError, sobald keine Abrechnungsart gesetzt und WBW > 0. Definitionen ergänzt (identisch zu `positionenVorlage`).
- **B2 (OnboardingHub):** prüfte Phantomfelder (`schaden.positionen`, `schaden.unfalldatum`, `a.typ`, kleingeschriebene Rollen, `d.klasse`) → 4 Kacheln konnten nie grün werden, Hub erschien wegen `!mandant.iban` quasi immer. Jetzt echte Quellen (`akte.unfalldatum`/`unfallort`, `gesamt_brutto`, `dokumentenklasse`, Rollen case-insensitive inkl. GHV/GBEV); Sichtbarkeit hängt an der eigenen Checkliste (verschwindet, sobald alle Pflichtbereiche ✓); Zähler dynamisch statt hartem „von 6".
- **B4:** „+ Todo" im Akten-Header öffnet jetzt wirklich das Inline-Formular (vorher nur Navigation zur Übersicht).
- **B6:** Akten-Chronik sortierte über formatierte Datums-Strings (innerhalb eines Jahres nach Uhrzeit statt Monat); jetzt ISO-`sortKey` vor der Formatierung.
- **B7:** §3a-Frist-Pill matchte `frist_typ === "gerichtlich"`, das To-Do-Formular vergibt aber `gericht` — beide Werte akzeptiert.
- **B8:** RSV-Kachel zeigte das Aktenzeichen doppelt (`zeigeBetreff` + `zeigeAktenzeichen`); dazu Doppel-Chevron `⌄⌄` korrigiert.
- **B5 (toter Code):** `AkteActionBoardHeader`, `TodoKachelKompakt`, `InfoZeile`, `InfoRow` + verwaiste Berechnungen (`regGrad`, `klageSumme`, brutto/netto-Block, `mandantName`) entfernt (~10,5 kB); `StaDialog` in `AkteDetailView` direkt importiert statt über den UebersichtSection-Re-Export; ungenutzte Importe bereinigt. Für Tests neu exportiert: `AktenTimeline`, `StatusBand`, `RechtsschutzKlappkachel`, `TodoInlineForm`.
- **Bewusst offen (Redesign-Session, `handover/2026-08-10-uebersicht-redesign-mockups.md`):** B3 — Header-KPI (mit HQ) und FinanzBand (ohne HQ) rechnen Summen unterschiedlich; Design-Entscheidung „eine Summen-SSOT" nötig. Ebenso: 3× `mandant-checks`-Request pro Aktenöffnung, 3× kopierte `dringlichkeit()`-Logik, 2× posMap-Aggregation.

---

## 2026-08-07 — Referenzwerkstatt editierbar in der ReviewQueue (Befund RA Schatz, Branch `abschlussbericht`, `a0d38d13`)

Befund bei der Browser-Abnahme: Das Feld `referenzwerkstatt` im Prüfbericht-Review erschien nur als JSON-Box, nicht korrigierbar — obwohl die Extraktion danebenliegen kann (Dok 555/Akte 332/26: Name „Postanschrift:", Ort „14329 Berlin\nFirmensitz"). Falsche Werkstatt-Adressen hätten die Entfernungsprüfung mit Müll gefüttert; Heilung ging nur über „Erneut parsen".

- **Neuer `ObjektFelderEditor`** in `ReviewQueueView.jsx`, analog zur Positions-Tabelle vom selben Tag: Werkstatt-Daten (name, adresse, plz_ort, telefon, km_genannt) als editierbare Zeilen, numerische Felder parsen auf Blur als Zahl (`parseBetragDe`, deutsches Format).
- **Maschinelle Prüfwerte bleiben schreibgeschützt** (`MASCHINELLE_OBJEKT_FELDER`: quelle, km_echt, minuten, abweichung_km, bewertung, geprueft_am, geprueft_gegen_akte) — sie kommen aus der Entfernungsprüfung bzw. der Extraktions-Herkunft und werden nur angezeigt.
- Verschachtelte Unterobjekte (z. B. `stundensaetze`) und nicht-flache Arrays bleiben JSON-Anzeige (`JsonBox` extrahiert).
- **Speicherweg unverändert bestätigt:** `PATCH /intake/dokument/<id>/felder` aktualisiert nur geänderte Felder, loggt ins `korrektur_log`, lässt übrige Felder unangetastet — Werte werden korrekt persistiert.
- **Tests (TDD, RED→GREEN):** 6 neue in `ReviewQueueView.objektfelder.test.jsx`; 2 Alt-Tests vom Vortag (Objekt = read-only-JSON) auf das neue Verhalten umgestellt. Frontend-Vollsuite 465/465 grün.

---

## 2026-08-07 — Firmen-Beteiligte: „Firma" statt echtem Namen (Befund 1280/25, Branch `abschlussbericht`, `6801be75`)

Befund RA Schatz: Die Beteiligten-Section der Akte 1280/25 zeigte einen Eintrag „Firma" mit leeren Feldern statt des echten Gegners „RCR GmbH". Ursache: RA-MICRO speichert den Namen (auch Firmennamen) IMMER in `sNachname`; `sErsteAdresszeile` ist nur die Anredeform des Adressfelds („Herrn", „Frau", „Firma", „Anwaltskanzlei", „c/o …") — per Datenanalyse bestätigt (12.559× „Herrn", 6.990× „Frau", 3.327× „Firma", nie ein echter Name). Unsere Heuristik „kein Vorname → `sErsteAdresszeile` ist Firmenname" verwarf dadurch bei Firmen den echten Namen; der Code-Kommentar „sErsteAdresszeile = offizieller Firmenname" war falsch.

- **Neue Helferfunktion `name_aus_ramicro_adresse(nachname, erste_adresszeile)`** (`word_service.py`, modulweit): Nachname zuerst, erste Adresszeile nur Fallback wenn Nachname leer. In Brief-Adressblöcken bleibt `sErsteAdresszeile` als eigene Zeile ÜBER dem Namen unverändert korrekt.
- **7 Fundstellen umgestellt:** `_beteiligter_dict` in `_lade_beteiligte_aus_ramicro` (Beteiligten-Section — der gemeldete Fall) und `_lade_gegner_adresse_aus_ramicro` (Forderungsschreiben-Gegneradresse; bevorzugte `erste` sogar bedingungslos) in `word_service.py`; `belege_routes.py` (Beleg-Kandidaten); `klage_routes.py` (Gerichts-Ermittlung); `wiedervorlage_routes.py` (Empfänger im Aktivitätslog, 2×); `personenschaden_routes.py` + `ramicro_akte_routes.py` (2×) (Adressanzeige/Adresssuche/Mandantenname — Muster `firma if firma else …` gedreht).
- **Anrede-Code „4" = Firma** ins Mapping aufgenommen (`ANREDE_CODES`, vorher wurde „4" roh angezeigt).
- **Tests (TDD, RED→GREEN):** 5 neue in `test_ramicro_firmen_name.py` (Helper-Units + nachgebautes 1280/25-Szenario über `_lade_beteiligte_aus_ramicro` mit Fake-Cursor). Gegenprobe per Stash: die 5 `test_modul8`-Fehlschläge im Kombi-Lauf sind vorbestehend (Testreihenfolge), nicht durch diesen Fix.
- **Live verifiziert (1280/25):** Mandantin „Anita Petrovic", Gegner „RCR GmbH" (Anrede: Firma), VHV als GHPV, SV Ninnivaggi.
- Bekannter Rest (bewusst nicht angefasst): Alt-Heuristik setzt bei Gegnern ohne Vorname `versicherung = name` — die RCR GmbH zeigt daher „RCR GmbH" auch im Versicherung-Feld.
- Memory: `feedback_ramicro_erste_adresszeile`.

---

## 2026-08-07 — Abrechnungs-Positionen: fehlender Hauptbetrag + editierbare Positions-Tabelle (Befund 1280/25, Branch `abschlussbericht`)

Befund RA Schatz: Im VHV-Abrechnungsschreiben (Dok 517, Akte 1280/25) fehlte „Abrechnung nach Prüfbericht 5.448,62 EUR" in `felder.positionen` — die LLM-Extraktion las die Zeile als `abrechnungsart`, die Summen-Validierung meldete korrekt die 5.448,62-Differenz, korrigieren ließ es sich aber nicht, weil `positionen`/`zahlungen` im Review nur als rohes JSON angezeigt wurden.

**Backend (`abrechnungsschreiben_parser.py`, `intake/extraktion.py`):**
- Neues Positions-Pattern „Abrechnung nach Prüfbericht" → `reparatur_netto` (VHV-Layout für regulierte Reparaturkosten).
- `sv_kosten`-Suchfenster endet jetzt an Summen-/Zahlungszeilen (`_SUMMENZEILEN_RE`) — die Maximum-Heuristik griff sonst den Auszahlungsbetrag der Folgezeile (VHV: 7.751,54 statt 1.316,62).
- Sicherungsnetz `_ergaenze_abrechnungspositionen` (nur Klasse `abrechnungsschreiben`, nach der LLM-Extraktion): Regex-Positionen als deterministische Kandidaten. Leere LLM-Liste → Kandidaten komplett übernehmen; sonst wird nur ergänzt, was die Differenz zum Gesamtbetrag **exakt** erklärt (einzelner Kandidat oder Summe aller fehlenden; Toleranz 1 Cent wie `validierung.py`; Abzugs-Arten `mwst_abzug`/`pruefbericht_abzug`/`restwert` nie). Erklärt nichts die Differenz, bleibt die ehrliche Validierungswarnung stehen — kein Raten.

**Frontend (`ReviewQueueView.jsx`):**
- `FelderEditor`: Listen flacher Objekte (`positionen`, `zahlungen`) werden als editierbare Tabelle gerendert (Spalten = Key-Union, Zeile hinzufügen/entfernen) statt als JSON-Box. Betragsspalten (Regex `betrag|summe|mwst` oder numerischer Wert) zeigen deutsches Format; Parse auf Blur via `parseBetragDe` („5.448,62" → 5448.62 als **Zahl** — Strings würden von der Summen-Validierung still ignoriert). Verschachtelte Objekte (`referenzwerkstatt`) bleiben bewusst schreibgeschützte JSON-Anzeige.

**Tests (TDD, RED→GREEN):** 8 neue BE-Tests (`test_abrechnung_positionen_sicherungsnetz.py`: Parser-Pattern, SV-Fenster, Ergänzen einzeln/mehrfach, Kein-Junk, LLM-Ausfall-Fallback, Abzugs-Sperre), 8 neue FE-Tests (`ReviewQueueView.positionen.test.jsx`). Frontend-Vollsuite 459/459 grün. Backend: modulnahe Suiten grün (extraktion/validierung/entfernung/s18 + neu); Vollsuite-Fehlschläge (auth-/env-lastig: modul4-Routen, sv_portal, s19-Whitelist-Zeilendrift `email_import`) vorbestehend — Stash-Gegenprobe ohne diese Änderung liefert identische Fehlschläge.

**Live verifiziert:** echter Worker-Reparse Dok 517 (LLM aktiv) → 5 Positionen inkl. „Abrechnung nach Prüfbericht 5.448,62", Validierungswarnung weg, keine Degradation.

---

## 2026-08-07 — Referenzwerkstatt-Extraktion + Entfernungsprüfung ReviewQueue + Restbefunde a/c (auf Branch `abschlussbericht`)

Fortsetzung des Befunds Akte 1280/25 (3 Arbeitspakete laut Handover, Entscheidungen RA Schatz vom 2026-08-07: deterministischer Regex-Weg statt LLM-Fenster-Erweiterung; Entfernungsprüfung nur manuell per Button, da die Mandanten-Adresse an den externen Dienst OpenRouteService geht). Alle Pakete SDD-umgesetzt (TDD, Task-Reviews + Whole-Branch-Final-Reviews inkl. Fix-Wellen, alle Approved/Ready). 10 Commits `19e9467e..1aa59f79`.

**Paket 1 — Referenzwerkstatt-Extraktion VHV-Blockformat (`19e9467e`, `b9bb7dc8`, `284970b3`, `b3ae0680`):**
- `werkstatt_service.extrahiere_verweisbetrieb`: neue Stufe 1b für das VHV-Blockformat („Für die Korrekturberechnung haben wir den Reparaturbetrieb …"); Suchfenster endet bei „berücksichtigt." → es wird der VERWENDETE Betrieb gezogen, nicht die danach gelisteten Alternativbetriebe. Neuer `quelle`-Wert `vhv_block`.
- **Verhaltensänderung Bestand:** Stufe 3 (Trigger-Kontext) liefert nur noch Treffer mit PLZ-Zeile — der Floskel-Satz „Wird eine Referenzwerkstatt benannt, …" erzeugte vorher Scheintreffer. Betrifft auch den Alt-Endpoint `/distanz/prüfen-aus-dokument` (alte RegulierungSection): km-only-Treffer ohne Adresse melden jetzt „Kein Verweisbetrieb gefunden" statt „Adresse unvollständig" — gewollt, diese Treffer waren nie geocodierbar.
- Intake-Fallback in `extraktion.py` (Muster Prüfdienstleister-Fallback): füllt `felder.referenzwerkstatt` nur bei Klasse `pruefbericht` und nur wenn das LLM nichts liefert. Kanonische Keys `{name, adresse, plz_ort, telefon, km_genannt, quelle}`.
- Review-Fix `b3ae0680`: LLM-gelieferte `referenzwerkstatt`-Dicts werden per `setdefault` auf die kanonischen Keys normalisiert (`quelle: "llm"`), YAML-`beschreibung` in `pruefbericht.yaml` nennt die Keys explizit. **Deploy-Hinweis: YAML-Änderung → Backend-Restart in der Zielumgebung nötig.**
- Verifiziert am echten Dok 516 (Reparse): Möser Arno – Karosseriefachbetrieb, Philipp-Reis-Straße 9, 63128 Dietzenbach, 16,0 km, `quelle: vhv_block`.

**Paket 2 — Entfernungsprüfung in der ReviewQueue (`665a5bf4`, `c331545c`, `dd073e74`):**
- Neuer Endpoint `POST /intake/dokument/<id>/entfernung` (Body `{akte_az}`): Werkstatt aus `felder.referenzwerkstatt`, Mandanten-Adresse via `_mandant_adresse` (distanz_routes) aus dem übergebenen Akten-Kandidaten, `pruefe_entfernung` (ORS Geocoding+Routing). Bei Erfolg werden `{km_echt, minuten, abweichung_km, bewertung, textbaustein, geprueft_am, geprueft_gegen_akte}` ins Feld persistiert (bleibt in `intake_dokumente.parse_json`, via `freigaben`-Join zur Akte auflösbar — Datenbasis für den späteren Stellungnahme-Workflow). `textbaustein` nur bei `unzumutbar` (> 15 km), sonst wäre die Rüge inhaltlich falsch. Bei ORS-Fehler keine Persistierung.
- Frontend: Button „📍 Entfernung prüfen" im Review-Detail (nur Klasse `pruefbericht`; ohne gewählten Akten-Kandidaten deaktiviert mit Hinweis — Auswahl liefert die Mandanten-Adresse) + `EntfernungDialog`-Popup (genannte vs. echte km, Fahrzeit, Bewertung, Textbaustein mit Kopieren-Button). Fehler (404/422) erscheinen im Popup statt als Panel-Fehler.
- Review-Fix `dd073e74`: `FelderEditor` rendert Objekt-Werte (z. B. `referenzwerkstatt`) schreibgeschützt als JSON statt als editierbares `[object Object]`-Input — schützt die geprüften Werte vor versehentlichem Überschreiben. Plus Docstring-Präzisierungen.
- ORS-Smoke am echten Werkstatt-Standort ok (Offenbach→Dietzenbach: 16,9 km, 22 Min.). **Befund:** Akte 1280/25 hat lokal keine `beteiligte`-Zeilen → Button zeigt dort den (gewollten) Fehler „Mandanten-Adresse nicht gefunden". Laut Final-Review Regelfall bei frischen RA-MICRO-Akten → Backlog: RA-MICRO-read-only-Fallback in `_mandant_adresse` (Muster `_lade_beteiligte_aus_ramicro`, `word_service.py`).

**Paket 3 — Restbefunde a+c (`80120bb2`, `1aa59f79`):**
- (a) Marker-Matching in `klassifikator.py` von Substring auf Wortgrenzen umgestellt (`_marker_im_text`, Lookarounds `(?<!\w)…(?!\w)` statt `\b` wegen Sonderzeichen-Markern wie „Control€xpert"). „Rechnung" trifft nicht mehr „**Ab**rechnung". Golden-/E2E-Gates grün. Konvention: Bindestrich zählt als Wortgrenze („Reparaturkosten-Rechnung" trifft Marker „Rechnung" — gewollt, vgl. Marker „Reparatur-Rechnung"); Flexionsformen bei Bedarf als eigene YAML-Marker nachpflegen.
- (c) `llm_konflikt`-Vergleich normalisiert Datumswerte (nur DD.MM.YYYY ↔ YYYY-MM-DD, beidseitig) vor dem Vergleich — der Scheinkonflikt „2026-04-28" vs. „28.04.2026" entfällt, echte Datums-Konflikte bleiben.
- Verifiziert am echten Dok 517 (Reparse): `llm_konflikt` leer, Klasse korrekt `abrechnungsschreiben`.

**Tests:** 31 neue Backend-Tests (RED→GREEN, TDD) über `test_werkstatt_verweisbetrieb.py` (neu), `test_intake_entfernung.py` (neu), `test_intake_extraktion.py`, `test_intake_klassifikator.py`; 5 neue Frontend-Tests (`ReviewQueueView.entfernung.test.jsx`, neu). Frontend-Vollsuite 451/451 + Build grün. Vorbestehend unverändert: 2× `test_intake_routes` „Rechnung (Auffang)", `test_modul7`.

**Nachtrag (gleicher Tag, Freigabe RA Schatz):** RA-MICRO-read-only-Fallback für die Mandanten-Adresse (`1b74f938` + Fehlerpfad-Tests): `_mandant_adresse` (distanz_routes.py) fällt bei lokal fehlendem/adresslosem Mandanten auf `_lade_beteiligte_aus_ramicro` (word_service.py, nur SELECTs — read-only-Regel gewahrt) zurück; lokaler Treffer verhindert den RA-MICRO-Zugriff. Live verifiziert: 1280/25 löst jetzt die echte Mandanten-Adresse aus RA-MICRO auf. Bewusste Nebenwirkung: Auch der Alt-Endpoint `/distanz/prüfen-aus-dokument` profitiert; bei lokal fehlendem Mandanten kommt dessen 404 nun erst nach einem zusätzlichen RA-MICRO-Roundtrip (vorher sofort) — gewollt, konsistentes Verhalten.

**Offen (Human-Gates):** Browser-Abnahme des Entfernungs-Popups durch RA Schatz (jetzt direkt an 1280/25 möglich); Merge-Strategie unverändert (Branch stapelt, siehe TODO „In Arbeit").

---

## 2026-08-06 — Prüfbericht-Extraktion Akte 1280/25, Runde 2 (auf Branch `abschlussbericht`)

Anlass: RA Schatz meldete, das Prüfbericht-Parsing (Dok 516, VHV-Drei-Spalten-Format) sei trotz Schema-Erweiterung vom Vormittag weiter fehlerhaft. Befund: Die Altfelder des ControlExpert-Schemas passen nicht auf das VHV-Format — das LLM erfand `abzug_gesamt` (1.585,89 = selbst errechnete Differenz Gefordert−Fiktiv), belegte `reparaturkosten_brutto` mit dem Brutto NACH Prüfung und mischte Konkret-/Fiktiv-Spalte; `pruefdienstleister` (Pflichtfeld) und `auftraggeber` blieben leer bzw. wurden mit der Anspruchstellerin befüllt; die Schadennummer-Regex brach am Leerzeichen ab.

- **Schema-Feldbeschreibungen (neu):** Registry-`schema`-Werte dürfen jetzt statt reiner Typangabe ein Mapping `{typ, beschreibung}` sein (`registry_loader`-Validierung fail-loud, `llm_service` gibt die Beschreibung im Prompt als `- feld (typ): beschreibung` aus). `pruefbericht.yaml` nutzt das für alle Betragsfelder („niemals selbst errechnen", Spaltenzuordnung konkret/fiktiv, Brutto = VOR Prüfung) + `auftraggeber` (nicht der Anspruchsteller). Extraktor-Systemprompt generell verschärft: „Errechne keine Werte selbst".
- **2 neue Validierungsregeln** in `intake/validierung.py`: `netto_nach_abzug_konsistent` (vor − Abzug = nach) und `nach_pruefung_gleich_konkreter_erstattung` (Spaltenvermischung konkret/fiktiv wird als amber Warnung sichtbar); beide in `pruefbericht.yaml` registriert.
- **Prüfdienstleister-Fallback** in `intake/extraktion.py`: fehlt der LLM-Wert, wird der Dokumentkopf (erste 1.500 Zeichen) auf ControlExpert/DEKRA und ersatzweise `VERSICHERER_PATTERNS` geprüft. Nur der Kopf zählt — „Dekra-Zertifizierung" in der Werkstatt-Merkmalliste (Seite 3) erzeugte sonst ein falsches „DEKRA". Dok 516 bleibt korrekt leer (VHV nennt sich im Bericht selbst nicht).
- **Schadennummer-Regex mit Leerzeichen:** `abrechnungsschreiben.yaml` fängt jetzt „SD0 0003 2129 28 T01" komplett (Token-Muster `[^\S\n]`-getrennt, bricht an Zeilenende); `pruefbericht.yaml` bekam zusätzlich ein `Schaden-Nr.`-Muster für `vorgangsnummer`. Der `llm_konflikt` „SD0" bei Dok 517 ist damit weg.
- **Verifiziert am echten Dokument** (Container-Restart + Reparse): Dok 516 liefert jetzt konsistent 7.034,51 (gefordert) / 6.506,29 (nach Prüfung = konkret) / 5.448,62 (fiktiv), keine erfundenen Werte mehr; Dok 517 volle Schadennummer + Positionssummen-Warnung unverändert aktiv.
- **Tests:** 18 neue (RED→GREEN, TDD): `test_intake_validierung.py` (2 Regeln), `test_llm_service_s16b.py` (Beschreibungen im Prompt, Systemprompt), `test_intake_extraktion.py` (Fallback inkl. DEKRA-Fehltreffer), `test_registry_felder.py` (Regexe + Schema-Form), `test_registry_loader.py` (Schema-Mapping-Validierung). Betroffene Suiten grün (84 + 61 E2E); vorbestehend unverändert: 2× `test_intake_routes` „Rechnung (Auffang)".
- **Offen:** `referenzwerkstatt` bleibt leer (Werkstatt-Block liegt außerhalb des N-06-LLM-Seitenfensters) → TODO-Backlog (d); Marker-Wortgrenze (a) + Datums-Scheinkonflikt (c) weiter offen.

---

## 2026-08-06 — E-Mail-Import Endlos-Poll-Loop gefixt · Intake-Fixes Akte 1280/25 · Dubletten-Bereinigung (auf Branch `abschlussbericht`)

Anlass: RA Schatz meldete unbefriedigendes Parsing zweier VHV-Dokumente (Akte 1280/25) und 353 Dokumente voller Dubletten in Akte 543/26. Die Dubletten-Analyse deckte einen seit Ende Juni wiederkehrenden Endlos-Loop im E-Mail-Import auf.

**Endlos-Poll-Loop (`34342daa`):** Ursachenkette: RA-MICRO-Match auf lokal fehlende Akte → On-demand-Anlage tot (verweistes Modul `backend.ramicro.ramicro_liste`, ImportError still verschluckt) → `email_import_log`-INSERT verletzt FK auf `unfallakte(az)` → Mail weder geloggt noch als gelesen markiert → jeder Poll (1-Min-Takt) verarbeitete sie erneut. Zwei Wellen: 2026-06-28..07-14 (Alt-Pfad schrieb `dokumente`-Zeilen + Anhangs-Dateien) und ab 2026-08-04 (nach Scheduler-Reaktivierung; nur noch `.eml`-Kopien). Fix doppelt: `_stelle_sqlite_akte_sicher` nutzt `erstelle_oder_hole_akte` (+ Stammdaten best-effort aus RA-MICRO) und neuer FK-Guard in `_verarbeite_eine` degradiert lokal nicht anlegbare Akten zu `nicht_zugeordnet` statt Crash. 3 Tests `test_email_import_fk_guard.py` (RED→GREEN). Live verifiziert: die 5 festhängenden Mails wurden zugeordnet (Akten 431/22, 1043/25, 241/22, 732/26, 288/26 on-demand angelegt), Folgeläufe 0 Fehler.

**Intake-Fixes Akte 1280/25 (`8e9b50ea`):**
- `pruefbericht.yaml`: Schema um `erstattung_konkrete_reparatur_netto` + `erstattung_fiktive_abrechnung_netto` erweitert — die VHV-Drei-Spalten-Tabelle (gefordert/konkret/fiktiv) hatte kein Zielfeld, der regulierungsentscheidende Fiktiv-Wert (5.448,62 €) ging verloren. Reparse Dok 516 verifiziert. Achtung: Registry-YAMLs werden beim Backend-Start geladen; der Flask-Reloader reagiert nicht auf YAML-Änderungen → Container-Restart nötig.
- Neu `backend/intake/validierung.py`: die YAML-`validierungsregeln` (`summe_positionen_gleich_gesamt`, `abzug_gesamt_summe`) werden erstmals ausgeführt (waren reine Doku). Warnungen landen in `parse_json.validierung_warnungen`, Detail-Route reicht durch, ReviewQueue zeigt amber Hinweis. Reparse Dok 517 (VHV-Abrechnungsschreiben): Warnung nennt exakt die vom LLM ausgelassene Hauptposition (Differenz 5.448,62 €). 11 Tests `test_intake_validierung.py` (RED→GREEN).

**Dubletten-Bereinigung (Freigabe RA Schatz, „aufräumen"):** Backup `/app/data/unfallakten.db.bak_pre_dubletten_cleanup_20260806_155109` (SQLite `.backup`-API). `dokumente` 53.216 → 789 Zeilen — behalten: älteste Zeile je (akte_id, dateiname, dateigröße) plus alle aus 9 Referenz-Tabellen (`pruefberichte`, `forderung_positionen`, `abrechnungsschreiben`, `schadenposition_belege`, `freigaben`, `ereignisse`, `position_ereignis_cache`, `klassifikation_training`, `todos`) und `email_import_log.importierte_dok`-JSON referenzierten IDs. Danach Verwaisten-Sweep in `/app/uploads` (nur Top-Level-Dateien, Unterordner unangetastet; behalten wurde alles, was eine der 6 Pfad-Spalten referenziert). Ergebnis: 106.266 Dateien gelöscht, ~222 GB frei, VACUUM 50 → 4 MB. 543/26: 353 → 6 Dokumente.

**Tests/Regressionen:** Fokussierte Suiten grün (Intake-Pipeline/Extraktion/Routen/Review-E2E 72 passed, E-Mail-Import-Suiten 22+3, Registry 21). Frontend-Vollsuite 446/446. Vorbestehend (per stash-Gegenlauf verifiziert, nicht durch diese Arbeit): `test_modul7` importiert gelöschtes Modul `email_import.parser` (48 F), 2× `test_intake_routes` Bezeichnungs-Label „Rechnung (Auffang)".

**Offen:** Marker-Wortgrenze „Rechnung" trifft „**Ab**rechnung" (Auto-Klassifikation schlug abrechnungsschreiben→rechnung vor); Schadennummer-Regex bricht an Leerzeichen ab („SD0"); Datums-Scheinkonflikt im LLM/Regex-Konsens-Check (ISO vs. deutsch) → TODO Backlog.

---

## 2026-08-05 — Abschluss-/Sachstandsbericht (Branch `abschlussbericht`, basiert auf `intake-review-sichtbarkeit`)

Design-Spec `docs/superpowers/specs/2026-08-05-abschlussbericht-design.md` · Plan `docs/superpowers/plans/2026-08-05-abschlussbericht.md`. Neuer Dokumenttyp `abschlussbericht`: ein kuratiertes Schlussfeld (`abschluss_status.schluss_typ`) schaltet zwischen Abschluss- und Sachstandsbericht um — derselbe DB-freie Übersichts-Service liefert Positionen, Zahlungsverlauf, Empfänger-Split und Anwaltskosten-CTA sowohl an den DOCX-Renderer als auch an einen internen Vorschau-Endpoint. Die alte automatische Auto-Summary (`abschluss_summary.py`) entfällt ersatzlos zugunsten des kuratierten Wegs.

- `228ecc0b` Migration 67 — Tabelle `abschluss_status` (+ `test_migration_67.py`, 4 Tests).
- `bb1857bd` pos_map mit Zahlungsverlauf + RA-Gebühren-Filter (`services/abschluss_uebersicht.py`).
- `3a7f3b0d` Übersichts-Objekt: Positionen, Empfänger-Split, Summen, Modus.
- `df73fd80` Anwaltskosten, Bewertungs-CTA, Plausi-Kontrolle (`test_abschluss_uebersicht.py`, insgesamt 19 Tests).
- `73532e03` DOCX-Renderer `word/abschlussbericht.py` im Hausstil (+ `test_abschlussbericht_docx.py`).
- `cbc24d74` Fix: Verjährungs-Hinweis unabhängig vom Schlusstext rendern (Review-Fund, 4 DOCX-Tests).
- `7a5d5e60` Typ-Verdrahtung word_service + Datenlader (`abschluss_status`, `gebuehren_kontext`).
- `23ea6792` Fix: Streitwert-Fallback — toter `COALESCE(rep_rechnung_brutto, rep_gutachten_netto, 0)` durch >0-Vorrang ersetzt (Review-Fund; + `test_gebuehren_kontext_loader.py`, 2 Tests).
- `64aa203b` Routen `GET /akten/<az>/abschluss-uebersicht` + `PUT /akten/<az>/abschluss-status` (+ `test_abschluss_routes.py`).
- `cac4d939` Rückbau alte Auto-Summary (`abschluss_summary.py` gelöscht, Guard-Test; insgesamt 5 Route-Tests).
- `6a0a9ad7` Frontend: Kurationsdialog + WordSection-Kachel + API-Client (+ `AbschlussberichtDialog.test.jsx`, 3 Vitest; Vollsuite 446, Build grün).
- `4d343077` Fix: Amber-Rohwerte durch `theme.js`-Tokens ersetzt (Review-Fund).
- `b4d7f289` Fix: „für Sie kostenfrei"-Aussage nur noch bei Vollhaftung (Spec §15; Fund des Whole-Branch-Final-Reviews) — `getragen_von = "gegner"` nur wenn keine Abrechnung `haftungsquote < 100`; sonst neutraler „Kostentragung … gesondert"-Satz im Schreiben. +2 Tests. **Revidiert am 2026-08-06 (s. u.).**
- **2026-08-06 — Folgefund Gebührenassistent gefixt (Freigabe RA Schatz):** derselbe tote `COALESCE(rep_rechnung_brutto, rep_gutachten_netto, 0)` im Streitwert-Fallback existierte auch in `gebuehren_routes.py` (Anzeige) und `gebuehren_word.py` (Kostennote-DOCX, „Gegenstandswert") — bei fiktiver Abrechnung ohne Forderungsschreiben fehlte der Fahrzeugschaden. Beide Stellen auf `>0`-Vorrang-CASE umgestellt; 3 Regressionstests (`test_gebuehren_streitwert_fallback.py`, inkl. DOCX-Inhaltsprüfung, RED→GREEN).
- **2026-08-06 — Klarstellung RA Schatz (revidiert `b4d7f289`):** „kostenfrei" gilt auch bei Teilhaftung — die Kanzlei rechnet die Geschäftsgebühr aus dem **regulierten** Streitwert ab, der Versicherer trägt sie vollständig. `getragen_von` wieder immer `"gegner"`; RVG-Fallback-Betrag wird jetzt aus `summen.gezahlt` (reguliert) statt aus der Forderung berechnet, DOCX-Satz nennt die Basis („berechnet aus dem regulierten Betrag"). Spec §15 entsprechend präzisiert. Tests umgedreht + neuer Basis-Pin-Test (`test_rvg_basis_ist_regulierter_betrag`).
- **Endabnahme (2026-08-05):** voller fokussierter Testlauf im Container — `test_migration_67.py`(4) + `test_abschluss_uebersicht.py`(20) + `test_abschlussbericht_docx.py`(5) + `test_abschluss_routes.py`(5) + `test_word_gueltige_typen.py`(3) + `test_gebuehren_kontext_loader.py`(2) = **39/39 passed**. Frontend: 3 neue Vitest, Vollsuite **446/446** grün, Build grün. Whole-Branch-Final-Review: Ready to merge (nach `b4d7f289`), keine offenen Critical/Important.
- **Offen:** Browser-Abnahme RA Schatz (DOCX-Sichtprüfung beide Modi), Merge nach Klärung der Branch-Reihenfolge (stapelt auf `intake-review-sichtbarkeit`), Portal-Auslieferung als eigenes Stakeholder-Portal-Teilprojekt. Siehe TODO.md.
- **Folgefund (Review, außerhalb dieser Runde):** `gebuehren_routes.py` (Streitwert-Fallback) enthält denselben toten COALESCE-Bug wie der in `23ea6792` gefixte — bei fiktiver Abrechnung ohne Forderungsrunde zeigt der Gebührenassistent den Fahrzeugschaden-Anteil als 0. Separater Fix nötig (Bestandsfeature, Entscheidung RA Schatz aussteht).

---

## 2026-07-30 — Dashboard-Hell-Umbau (Branch `dashboard-hell`, basiert auf `aktenanlage`)

Design-Spec + Mockup `docs/superpowers/specs/2026-07-30-dashboard-hell-*` (von RA Schatz freigegeben, danach Umsetzung). Anlass: UI-Review des Dashboards (Nielsen-Score 14/40). P0-Befunde: komplett dunkler Viewport (~100 % statt Soll ~18 %) sowie stille API-Fehler, die eine grüne Entwarnung bei Fristen vortäuschten; automatischer Detektor fand 4× `borderLeft`-3px-Streifen als Farbcode-Krücke; 5 WCAG-Kontrast-Fails, schlimmster Wert 1,9:1. 8 Commits `5449beae..36e4581d`, Subagent-Driven Development.

- **Task 1** `5449beae` Design-Spec + Mockup (Freigabe RA Schatz).
- **Task 2** `49ce39e6` gemeinsame `boardUi`-Bausteine (`Kachel`/`KachelInhalt`/`Zeile`) als echte Buttons/Badges statt Divs mit Klick-Handler — Grundlage für die spätere Tastaturbedienung.
- **Task 3** `c909f3e8` `FristenKachel` auf Pergament-Tokens (`tokens.css`) umgestellt, dadurch ohne Zusatzaufwand auch im clio-Scheme lesbar; Positionierung links oben im 3:2-Raster.
- **Task 4** `09e493b8` `WiedervorlagenKachel`: gleiche Token-Umstellung, Liste ohne WV-Eintrag auf 5 gedeckelt + Sprung zur Vollansicht.
- **Task 5** `2d7f6d41` `TermineKachel` auf Pergament-Tokens umgestellt.
- **Task 6** `adaa7ed5` `JetztDranLeiste`: 3 dringendste Einträge aus Fristen + Wiedervorlagen, reine Client-seitige Ableitung ohne eigenen Endpoint.
- **Task 7** `8e62bd08` `ActionBoardView`+`App.jsx`: Posteingang-Kachel ersatzlos entfernt (E-Mail-Arbeit läuft über E-Mail-Import/Review-Queue), Lade-/Fehler-/Leer-Zustand je Kachel (Fehlerzustand: roter Hinweisblock mit „Erneut laden" ersetzt den Kachelinhalt; die zuletzt geladenen Daten bleiben im State erhalten und erscheinen nach erfolgreichem Neuladen sofort wieder), eine einzige Farbachse (Rot nur überfällig, Gelb heute), SB-Filter jetzt persistiert in `localStorage` (`dashboard.aktiveSB`) — leere Auswahl zeigt einen Hinweis statt der bisherigen Invertierungslogik.
- **Task 8** `36e4581d` Aufräumen: verwaistes `openEmail` entfernt.
- **Tests:** 28 neue Frontend-Tests (`boardUi` 5, `FristenKachel` 5, `WiedervorlagenKachel` 4, `TermineKachel` 3, `JetztDranLeiste` 5, `ActionBoardView` 6 — je vorher RED verifiziert), Vollsuite **434/434 grün**, Lint ohne neue Befunde.
- **Review:** jeder Task einzeln subagent-reviewed (Spec + Qualität) — alle Approved.
- **Offen:** Browser-Abnahme durch RA Schatz gegen das Mockup (siehe TODO.md). **Merge-Reihenfolge: erst `aktenanlage` → `main`, dann `dashboard-hell`.**
- **Fixwelle (Whole-Branch-Review):** SB-Filter lässt Einträge ohne oder mit unbekanntem SB-Kürzel jetzt immer durch (`ActionBoardView`), `badgeText`-Guard in `FristenKachel` korrigiert (positive Tage zeigen „+N T" statt fälschlich „−N T"), CHANGELOG-Korrektur zum Fehlerzustand. Vollsuite **435/435 grün**.
- **Playwright-Browsertest gegen die laufende Dev-App (2026-07-30): 20/20 bestanden.** Geprüft im echten Chromium: Pergament-Hintergrund + Bricolage-Titel, alle Kacheln inkl. Jetzt-dran, kein Posteingang, keine 3px-Streifen, Einträge als Buttons, SB-Persistenz über Reload, Fehlerblock bei abgebrochenem `/dashboard/fristen`-Request (kein falscher Leertext, Jetzt-dran ausgeblendet, Erholung per „Erneut laden"), Klick auf Eintrag öffnet Akte 97/25AS. Beobachtung (Bestand, nicht Teil des Umbaus): Die App verlangt nach jedem Browser-Reload einen erneuten Login (Benutzer nur im React-State).

---

## 2026-07-30 — Aktenanlage aus der ReviewQueue (PRD-NEW, Branch `aktenanlage`)

Design-Spec `docs/superpowers/specs/2026-07-30-aktenanlage-design.md` · Plan `docs/superpowers/plans/2026-07-30-aktenanlage.md`. Anlass: Kommt ein Gutachten per E-Mail herein und existieren Mandant/Unfall noch nicht im Bestand (Absender per Gutachter-Identifier bestätigt, keine Akten-Kandidaten), gab es bislang keinen Weg weiter — Freigabe blieb ohne `akte_az` gesperrt (422), die Akte musste manuell in RA-MICRO angelegt werden. 12 Tasks, Subagent-Driven Development, 20 Commits `b15c6669..ee486332` + Task 12 (diese Session).

- **Task 1** `b15c6669` Migration 66: Tabelle `aktenanlage_vorgaenge` (`status` CHECK `laeuft|akte_erkannt|abgeschlossen|abgebrochen`, `formular_json`, `xml_pfad`, `mandant_*`, `erkanntes_az`, `angelegt_am/von`, `erkannt_am`).
- **Task 2** `a8388b94`+`98c2eaa9`+`b96bf5af` OMA-XML-Generator `backend/ramicro/oma_xml.py` (`erzeuge_oma_xml`/`schreibe_oma_xml`) nach dem Muster `beispieloma.xml` — atomares Schreiben (Temp-Datei + `os.replace`), Mikrosekunden-genaue Dateinamen gegen Kollision, `short_empty_elements=False` für referenztreue Leerfeld-Serialisierung, Options-Labels `HERR`/`FRAU`/`FIRMA`, ISO-Datumsformat.
- **Task 3** `e8e0d1f1`+`31afa74b` RA-MICRO-Helfer (strikt read-only): `adress_service.hole_adresse_details`/`akten_zu_adresse`, neues Modul `akten_erkennung.finde_neue_akten` (Read-Only-Abfrage auf `tblAkten`↔`tblAktenBeteiligte`↔`tblAdressen`, Adressnummer hat Vorrang vor Nachname-Suche).
- **Task 4** `76173b0d`+`e688a4f7`+`20565355` Service `aktenanlage_service.py` + Blueprint `/aktenanlage` (`POST /aktenanlage`, `GET /aktenanlage/offen` inkl. lazy Erkennung im 30-s-Poll, `POST /aktenanlage/<id>/abbrechen`, `.../abschliessen`); 409-Guard gegen doppelten laufenden Vorgang pro Intake-Dokument (transaktional), Schattenakte wird beim leeren Einstieg **vor** dem Statuswechsel angelegt (Reihenfolge-Bugfix).
- **Task 5** `2e193685`+`1994158b` `GET /aktenanlage/adressen?q=` (Dubletten-Check) + Gutachter-Vorlage aus dem Identifier-Treffer; Adressnr als Int, 422-Präzisierung.
- **Task 6** `4659beaa` Freigabe-Hook in `post_freigabe`: schließt Aktenanlage-Vorgänge der E-Mail-Gruppe, übernimmt Unfalldatum/-ort aus `formular_json` in die Schattenakte, Response-Feld `aktenanlage`.
- **Task 7** `1d5e5b42` Review-Queue liefert `absender_kategorie` aus `zustellungen.signale_json` (Banner-Voraussetzung: Klasse `gutachten` + `absender_kategorie=gutachter` + keine Akten-Kandidaten).
- **Task 8** `2cc98de4` `gutachten.yaml`-Registry um Auftraggeber-Felder erweitert (Vorbefüllung des Dialogs aus dem Gutachten-Parse).
- **Task 9** `d94f8929`+`015cfb35` `apiAktenanlage` (Frontend-API-Client) + neue Komponente `AktenanlageDialog.jsx` mit debouncter Dubletten-Suche gegen `tblAdressen`; Stale-Response-Guard per Generationszähler (schnelles Tippen wirft keine veralteten Treffer mehr an).
- **Task 10** `6fe9bbbb`+`086ae420` ReviewQueue-Integration: Hinweis-Banner „Vermutlich neue Akte", Button „➕ Neue Akte anlegen" im Zuordnen-Abschnitt, Status-Chip (`⏳ läuft`/`✅ Akte … angelegt`), schmale Status-Leiste über der Queue-Liste; Null-Guard gegen Klicks auf durch den Poll bereits entfernte Einträge.
- **Task 11** `91a3a054`+`ee486332` Aktensuche nutzt denselben `AktenanlageDialog` (leerer Einstieg ohne Vorbefüllung); die bisherige inline `NeueAkteModal`-Komponente in `AktensucheView.jsx` entfällt, toter `apiAkten`-Import entfernt.
- **Task 12** (diese Session) Infrastruktur: `OMA_EXPORT_PFAD` (Container-Pfad `/app/oma_export`) in `docker-compose.yml`+`docker-compose.prod.yml` als Env+Volume ergänzt, Host-Pfad über `OMA_EXPORT_HOST_PFAD` (Default `./oma_export`) in `.env.example` dokumentiert.
- **Kern-Invarianten:** RA-MICRO bleibt strikt read-only (geschrieben wird nur die XML-Datei + SQLite); Review-Freigabe bleibt der einzige Schreibweg für Dokumente (INTAKE_REVIEW_PFLICHT unangetastet); kein eigener Navigationspunkt.
- **Endabnahme:** Backend voller Lauf (docker exec, force-recreate nach Compose-Änderung) **230 failed/1308 passed/15 skipped** — Failure-Set deckungsgleich mit dem seit Monaten bekannten lokalen Alt-Cluster (test_modul1-7/dashboard/sv_portal/prd27/migration_46, u. a. verursacht durch `_ensure_admin_exists`-Bootstrap-Kollision mit `/auth/register/erster` in den jeweiligen `setUp()`s, sowie — neu identifiziert — `test_modul6`-Konfigurationsdatei-Checks, die im Dev-Container strukturell nicht auflösbar sind, weil `docker-compose.yml`/`Dockerfile`/`nginx/`/`Makefile`/`.gitignore` dort nie gemountet werden; siehe DECISIONS/STATE bei Bedarf); **die 49 aktenanlage-spezifischen Tests (`test_aktenanlage_routes.py`, `test_oma_xml.py`, `test_ramicro_aktenanlage.py`) sind alle grün**, keine neue Datei im Failure-Set. Frontend **404/404** grün (61 Dateien, inkl. `AktenanlageDialog.test.jsx`, `ReviewQueueView.aktenanlage.test.jsx`).
- **Offen (RA Schatz, außerhalb dieser Session):** manueller Abnahmetest am echten System — die drei Verifikationspunkte aus Spec Abschnitt 9 (Adressnummer-Referenz „Bekannt=Ja", konkreter `OMA_EXPORT_HOST_PFAD`, Options-Labels/ISO-Datum + `dtAnlage`-Spalte beim ersten echten Import). Siehe TODO.md.
- **Final-Review-Fixwelle** (diese Session): Gruppen-Schließregel korrigiert (Vorgang schließt erst beim letzten offenen Geschwister-Dokument der E-Mail-Gruppe, Unfalldaten-Übernahme bleibt sofortig, Spec 5.4 angepasst); AZ-Übernahme aus dem Dubletten-Check wirkt jetzt tatsächlich im Zuordnen-Abschnitt der ReviewQueue; Offline-Hinweis für die RA-MICRO-Adresssuche im Dialog (`suche_adressen_status`, Response-Feld `verfuegbar`); Namens-Warnung beim leeren Einstieg (zweiter Klick legt trotzdem an); AZ-Feld bleibt nach Vorbelegung leerbar (Einmal-Vorbelegung per Ref); 409-Pfad in `lege_vorgang_an` löscht die XML jetzt fehlertolerant (`OSError` abgefangen, kein 500 auf Windows-Share-Sperren).

---

## 2026-07-28 — Review-Queue: Sortier-Toggle Eingangsdatum (Branch `review-queue-sortierung`, in `main`)

Design-Spec `docs/superpowers/specs/2026-07-24-review-queue-sortierung-design.md`, Plan `docs/superpowers/plans/2026-07-24-review-queue-sortierung.md`. Anlass: manuell importierte Dokumente waren in der Review-Queue (fest sortiert nach `erstellt_am ASC`) schwer wiederzufinden.

- **Task 1** `23d0f8bc` reiner Helfer `sortiereGruppen(gruppen, absteigend)` in `ReviewQueueView.jsx` (kehrt die von `gruppiereQueue()` gelieferten Gruppen-Blöcke um, keine Backend-Änderung), 3 Unit-Tests.
- **Task 2** `edb4f763` State/Toggle-Button „🕓 Älteste zuerst" ↔ „🕓 Neueste zuerst" im Queue-Header (nur in der Queue-Ansicht, nicht im Papierkorb), Persistenz über `localStorage` (`reviewQueueSortAbsteigend`).
- Subagent-Driven Development: 2 Tasks je Implementierung+Review (Spec ✅/Approved), Abschluss-Review „Ready to merge" — keine Critical/Important-Funde.
- **Browser-Nachtest (Playwright, gegen echte Dev-DB, 111 aktive Queue-Einträge, rein lesend)** 11/11 PASS. Wichtig: Umkehrung wirkt auf **Gruppen-Ebene** (E-Mail-Anhang-Blöcke bleiben zusammen, nur ihre Reihenfolge untereinander dreht sich um), nicht als flache Element-Umkehr — mit den 20 Mehrfach-Dokument-Gruppen der Live-Queue verifiziert.
- Fast-Forward-Merge nach `main` (`cc415175..edb4f763`), Branch gelöscht. `main` nicht gepusht.

---

## 2026-07-24 — Klage-Wizard Paket 4: Standardtexte pflegbar, V11 Stufe 1 (Branch `standardtexte-v11`)

Plan `docs/superpowers/plans/2026-07-24-klage-wizard-standardtexte-v11-stufe1.md` (Design-Spec: `docs/superpowers/specs/2026-07-19-klage-wizard-standardtexte-design.md`; Stufe 1 = 44 Bausteine Kategorie A+B; Kategorie C/vorflektierte Platzhalter bewusst als Stufe 2 vertagt, siehe TODO.md). Baut auf der `TextbausteinEditor`-Komponente der Kürzungstaxonomie Phase 1 auf.

- **Task 1** `497d9caf` Golden-Paritäts-Matrix (16 Szenarien, `test_klage_standardtexte_golden.py` + `backend/tests/golden/klage_standardtexte/*.txt`) als Regressionsschutz **vor** dem Registry-Umbau; Aktualisierung der Golden-Files über `KLAGE_GOLDEN_UPDATE=1`.
- **Task 2** `ff9aa8f3`+`2013df3b` Nebenbefund-Fix Beklagten-Grammatik: bei mehreren Beklagten heißt es jetzt einheitlich „Die Beklagten haben …" (`nom_gross`/`hat`) statt „Die Beklagte zu 2) hat …" — das „zu N)"-Suffix entfällt in genau diesen zwei Sätzen (Fall-B-/Regulierungssatz), BE (`klage_service.py`) und FE-Spiegel (`buildRwVorschau`) wortgleich nachgezogen.
- **Task 3** `adc811b1` YAML-Registry `backend/registry/klage_standardtexte.yaml` (44 Bausteine, 23 Platzhalter) + fail-loud Loader `backend/services/standardtext_registry.py` (App-Start bricht bei defektem YAML, wie bei der Kürzungstyp-Registry).
- **Task 4** `513aa47b` Migration 65: Tabelle `standardtext_override` + Model, kanzleiweit je Baustein überschreibbar (ein Override pro Baustein, gilt kanzleiweit — nicht je Akte).
- **Task 5** `29701bec` `klage_service.py`/`sg_text_builder.py` beziehen 36 Call-Sites aus der Registry statt aus eingebranntem Text — golden-paritätisch, **null YAML-Korrekturen nötig** (Matrix aus Task 1 blieb durchgehend grün).
- **Task 6** `59bc7751` REST `/klage-standardtexte` (5 Routen: Liste, Override, Reset, Vorschau, `/aufgeloest`), 422/409-Validierung für unbekannte Bausteine/Platzhalter.
- **Task 7** `a140d203`+`6e3cdfaf` Einstellungen-Tab „📄 Standardtexte" (`StandardtexteTab.jsx`, Wiederverwendung des `TextbausteinEditor`), Vite-Proxy ergänzt; Fehlerbehandlung Zurücksetzen + toter Import nachgezogen.
- **Task 8+9** `a21439b1`+`81f7284a` Klage-Wizard bezieht die 8 Stufe-1-Texte live über `/klage-standardtexte/aufgeloest` (Fetch aus `KlageWizard` in `KlageSection` geliftet, Seed-Race-Fix, sichtbarer Fehlerzustand statt stillem Fallback).
- **Wichtige Befunde:**
  1. Der Teilregulierungssatz ist im Backend strukturell unerreichbar (`klage_service.py`, KW-04-Altlast) — im Golden-Test (`teilregulierung.txt`) dokumentiert, kein neuer Bug, nicht in dieser Runde behoben.
  2. `sg_text_builder` wirkt auch im Forderungsschreiben mit — Overrides der Schmerzensgeld-Bausteine ändern **beide** Dokumente (bewusst, freigegeben: einheitliche Formulierungen).
- Endabnahme: Backend voller Lauf **204f/1277p/18s + 88 Subtests** (Alt-Cluster identisch verteilt: `test_modul3/4/7` 151, `test_modul2` 16, `test_modul5` 15, `test_dashboard_uebersicht` 9, `test_modul1` 6, `test_sv_portal` 4, `test_prd27`/`test_modul6`/`test_migration_46` je 1 — exakt wie Bestand, keine neue Datei im Failure-Set); Frontend **382/382** grün.
- **Browser-E2E per Playwright BESTANDEN (2026-07-24, 24/24 Checks):** Einstellungen-Tab komplett (Gruppen, Suche, Chip-Einfügung, Live-Vorschau mit Beispielwerten, Speichern-Sperre bei unbekanntem Platzhalter, Override + „geändert"-Badge, Reset), Wizard an Akte 285/26 (Schritt 9 Verzug-Text aus Registry, Gesamtvorschau Schritt 11 zeigt Override im Schlusssatz), Test-Override danach entfernt (System unverändert). Nach dem Merge-Checkout zusätzlich CRLF-Falle gefixt: `.gitattributes eol=lf` für die Golden-Fixtures (core.autocrlf hätte sie bei jedem frischen Checkout mit CRLF materialisiert und den Byte-Vergleich gebrochen). Sichtabnahme RA Schatz im Betrieb weiterhin sinnvoll, aber kein Blocker mehr.

---

## 2026-07-23 — Phase-1-Nachtrag: Genus-Platzhalter (Weg 2, Freigabe RA Schatz)

18 Genus-Platzhalter für die Mandantschaft (`<PRON>`, `<POSS_EM>`, `<ANREDE_DEKL>`, `<MANDANT_NOM>`, `<UNSERES>` …), gespeist aus RA-MICRO `sAnrede` (Erkennung wiederverwendet: `bestimme_geschlecht` aus `forderungsschreiben_wv._grammatik_vars` extrahiert, verhaltensgleich). Stellungnahme-Kontext löst sie akten-genau auf (ohne Anrede-Daten bewusst maskulin = Bestandsverhalten); Klage-Einwände lösen sie über den neuen wortgleichen FE-Helfer `platzhalterLogik.js` (`weiblich`-Flag des Wizards) auf, Unauflösbares wird sichtbarer `[FEHLT: <X>]`-Marker.
**Kernfund:** 5 Bausteine (1, 16, 21, 24, 32) enthielten noch **rohe RA-MICRO-Grammatikcodes** (`<@a2A> Mandant<@S2A>`, `<@PP1A>` …) — beim RTF-Import nie übersetzt, standen wörtlich in Briefen. `tools/genus_umstellung_bausteine.py` (Dry-Run/--write, JSON-Backup im Datenverzeichnis) hat 7 Bausteine umgestellt; danach 0 @-Codes. Dabei 3 Alt-Textfehler behoben (id 16 fehlendes Subjekt, id 24 fehlendes „ist", `$WZ`-Währungsmarker global entfernt). Die maskulinen Pronomen der übrigen Bausteine beziehen sich auf Gerichte/SV/BGH-Zitate — bewusst unangetastet. Offen sichtbar bleiben `<V-KRVON>/<V-KRBIS>` (id 32, Krankschreibung — Kontextwerte erst Phase 2). Tests: +12 Backend (`test_genus_platzhalter.py`), +11 Vitest (`platzhalterLogik.test.js`, `KlageWizard.einwaende-genus.test.jsx`), Vitest gesamt 362 grün.

---

## 2026-07-23 — Kürzungstaxonomie Phase 1 KOMPLETT (12 Tasks, Branch `kuerzungstaxonomie-phase1`)

Plan `docs/superpowers/plans/2026-07-23-kuerzungstaxonomie-phase1.md` (freigegeben inkl. der 3 Detail-Entscheidungen A05a–c/Varianten-Suffix/A09). Umsetzung über mehrere Sessions; eine Session brach mittendrin ab (Task 8 lag fertig, aber uncommittet vor — nach Prüfung ohne Verlust committet).

- **Task 1** `a8248f67` Migration 64: `kuerzungsarten.typ_code`+`verifiziert_am` (UNIQUE-Partial-Index) + 13 neue Seeds (→ 32), Stammtabelle `pruefdienstleister` (+FK-Spalten auf pruefberichte/abrechnungsschreiben), `ereignis_positionen.begruendung_roh`, `regulierung_positionen.typ_quelle`.
- **Task 2** `1257c157`+`0f97084a` YAML-Registry `backend/registry/kuerzungstypen/` (32 A–F-Typen) + fail-louder Loader (`kuerzungstyp_registry.py`, App-Start bricht bei defektem YAML).
- **Task 3** `3c2a6d74`+`99369b07` Baustein-Import 19→32 (ghpfansprort.doc→RTF konvertiert, Masken-Zeilen/&&-Artefakte gestrippt).
- **Task 4** `7c9d795f`+`6cf32afb` `textbaustein` REST-fähig, `GET /kuerzungsarten/platzhalter`, `POST /kuerzungsarten/vorschau`.
- **Task 5** `e35a2002`+`b11b2e68` Regel-Matching (`kuerzungstyp_matching.py`): Wortgrenzen, Briefkopf-Filter, Kontext-Pflicht-Keywords — Phase-0-Fehlerfälle als Fixtures.
- **Task 6** `114372af` LLM-Fallback (closed-label, nur wenn Regeln leer) + Positions-Synonymik je Versicherer-Template (`positions_synonyme.yaml`).
- **Task 7** `ba38f4f2` Verkettung Abrechnungsschreiben↔Prüfbericht (Auto-Kandidat ±90 Tage/Schadennummer, PATCH, `pruefdienstleister_id`-Befüllung, Frontend-Dropdown).
- **Task 8** `3e1a626b` Typ-Zuordnung im Regulierungs-UI: Vorschlag-Chips aus verkettetem Prüfbericht, **Pflicht-Begründung** (PATCH ohne Begründung → 400), `typ_quelle`, `begruendung_roh` bis ins Ereignis. Vitest `RegulierungSection.typvorschlag.test.jsx`.
- **Task 9** `90f74758` Runde-1↔Runde-2-Vergleich: `abrechnungsrunden_service.py` (reine Lese-Faltung, `ersetzt_durch`-Filter kollabiert ReguWizard-Ersetzungen), `GET …/abrechnungen/runden`, `RundenVergleichKachel` (grün=Nachzahlung, grau=aufrechterhalten, rot=neu/erhöht). 9 Tests.
- **Task 10** `03b2018c` `TextbausteinEditor.jsx` (Chips mit Cursor-Insert, 400-ms-Debounce-Vorschau, `pruefePlatzhalter` blockiert Speichern) + `KuerzungskatalogView` auf A–F-Gruppierung, typ_code-Badge, verifiziert_am. Nebenbefund behoben: CardHead-Prop `titel`→`title` an der Runden-Kachel.
- **Task 11** `cbe8a77f` Baustein-Fallback vereinheitlicht: Positions-JOIN liefert jetzt `ka.textbaustein` (Kette gespeichert→textbaustein→standard_gegenargument greift erstmals wirklich); `begruendung_roh` je Gruppe in Vorschau+DOCX; neuer Platzhalter `<ZITAT>` (Versicherer-Wortlaut); ReguWizard zeigt Zitat kursiv überm Textarea.
- **Task 12** Messanker `tools/kuerzungsmatching_report.py` (3 Zielwert-Kennzahlen, via docker exec), Doku nachgeführt (DATAMODEL Mig 64, ARCHITECTURE Taxonomie-Pfad, TODO). **Baseline 2026-07-23** (aktive DB, Schema 64, vor Betrieb): Abdeckung 17,4 % (4/23) · Trefferquote 0 % (0/4, alle 4 Alt-Zuordnungen manuell) · Betragszuordnung n/a (0 Ereignisse seit Stichtag) — naturgemäß niedrig, Messung ~2026-08-20.
- **Bekannte Alt-Failures** der lokalen Windows-Testumgebung (ModuleNotFound-Cluster) unverändert; alle taxonomie-relevanten Suites grün, Vitest komplett grün.
- **Offen zur Abnahme RA Schatz:** Browser-Kurztest Katalog-Editor (Task 10 Step 4) + Typ-Chips/Runden-Kachel im echten Betrieb; Messung der Zielwerte nach ~4 Wochen (TODO-Eintrag).

---

## 2026-07-23 — Kürzungstaxonomie: Konzept-Verifikation + Klage-Wizard-Fix „[FEHLT]-Marker"

Konzeptionelle Session (Kritik + Codebasis-Verifikation des Papiers `handover/KONZEPT-Kuerzungstaxonomie-Vorgangsautomat.md`), direkt in `main`.

- **Papier Abschnitt 12** neu: zwei 11.4-Befunde korrigiert (Textbausteine: 14/19 in aktiver Dev-DB befüllt, nicht 0/19 — Prüfung war gegen falsche DB; Fallback-Kritik gilt nur für Klage-Pfad), Migrations-Delta 56–63 als unkritisch verifiziert, RA-MICRO-Aktenkonto per Katalogabfrage negativ geprüft (keine Zahlungsdaten auf dem SQL Server), Differenz-Mathematik in `eingehende_ereignisse._regulierungs_wirkungen()` als bereits vorhanden identifiziert (stützt Option b aus 10.3.1).
- **3 DECISIONS-Einträge** (2026-07-23): Phase 1 vor V11 (Editor-Komponente entsteht in Phase 1) · Urteilscheck für Bestand entfällt (handverifiziert) · kommentarlose Zahlungen als Kaskade Betrags-Matching → Versicherer-Anfrage → protokollierte Not-Zuordnung.
- **Bugfix (TDD):** `EinwaendeAuswahl.uebernehmen()` erzeugte bei Kürzungsart ohne `textbaustein`/`standard_gegenargument` eine Überschrift ohne Argumentation. Jetzt sichtbarer `[FEHLT: Kein Textbaustein zur Kürzungsart „…" hinterlegt]`-Marker; neue Tests `KlageWizard.einwaende-fehlt.test.jsx` (3). Frontend-Suite **342/342** grün.
- TODO.md: PRD-39 als „durch PRD-27 abgedeckt" umgeschrieben; Kürzungstaxonomie Phase 0 (Handtest) als nächstes Vorhaben eingetragen; V11 wartet bewusst.
- **Browser-Nachtests RA Schatz (gleiche Session): Paket 2 (UI-Führung: Status-Symbole, Schließen-Dialog, Vertreter-Lookup) und Paket 3 (Gesamtvorschau-E2E inkl. DOCX-Kontrolle) BESTANDEN** — inkl. Sichtprüfung des neuen [FEHLT]-Markers. Klage-Wizard-Runde damit abgeschlossen bis auf V11 (wartet auf Phase 1).
- `main` erstmals seit Wochen gepusht (58 Commits, bis `80e2f044`).

---

## 2026-07-20 — Klage-Wizard Paket 2: UI-Führung

Branch `klage-wizard-ui-fuehrung`, 14 Commits `65f657bc..22ae53a3`, **noch NICHT in `main` gemergt**.
Spec `docs/superpowers/specs/2026-07-19-klage-wizard-ui-fuehrung-design.md` · Plan `docs/superpowers/plans/2026-07-19-klage-wizard-ui-fuehrung.md`. Subagent-Driven (9 Tasks + Fix-Welle + Test-Nachzug), Whole-Branch-Review (Opus): Ready to merge, keine Critical/Important.

- Status-Symbole (✓/⚠/●) im Fortschrittsbalken; Einwände als eigener Schritt (10→11 Schritte, Schnell-Durchlauf ohne Kürzungen möglich); Inline-Wort-Diff „Änderungen anzeigen".
- Neu: reine Logik `frontend/src/sections/wizardFuehrungLogik.js` (`wortDiff` LCS, `schrittStatus`/`schrittWarnung`/`firmenOhneVertreter`); Komponenten `DiffAnsicht`/`EditorMitDiff`/`StepEinwaende`/`EinwaendeAuswahl`.
- `ENTWURF_FORMAT_VERSION` 1→2 (Alt-Entwürfe → „Neu beginnen").
- Endabnahme: Frontend-Suite **314/314** (45 Dateien) + Build grün.

**Browser-Nachtest RA Schatz 2026-07-20 → 3 Punkte, auf demselben Branch behoben:**
(a) Schließen-Dialog als klare Messagebox „Verwerfen & schließen" / „Speichern & schließen" / „Zurück".
(b+c) Vertreter-Lookup direkt im Wizard (Knopf an Firmen ohne Vertreter in Schritt 2 + Schritt 11, öffnet das bestehende Modal über dem Wizard) statt „schließen → Lookup → neu öffnen" (`00e3f820`); stille Vertreter-Speicherfehler jetzt als Toast (`5e5b438b`).
**Root-Cause-Fund dabei:** `beteiligte.vertreter_name`/`vertreter_funktion` (Migration 23) fehlten auf der Dev-DB trotz `schema_version=61` → Dev-DB per ALTER nachgezogen (Backup `…bak_20260720_vertreter_drift`). Deploy-Konsequenz siehe STATE.md.

**Offen** (→ nächster Schritt in TODO.md): Für Akten **ohne** SQLite-Beteiligte (z. B. 828/24 — Versicherung als synthetischer § 115-VVG-Beklagter `id -1`) kann der Vertreter nicht per `UPDATE beteiligte WHERE id=?` persistiert werden → globaler Firmen-Vertreter-Speicher nötig.

---

## 2026-07-19 — Klage-Wizard Paket 1: Entwurf speichern

**Umgesetzt + in `main` gemergt.** Expliziter Speichern-Knopf, Schließen-Guard, Fortsetzen-Dialog, Positions-Abgleich mit Hinweis; Tabelle `klage_entwurf` (JSON + `format_version`, Migration 61), Endpoints `GET/PUT/DELETE /klage/entwurf`.
Subagent-Driven (9 Tasks) + Final-Review (READY): 2 Review-Fixes (`suche_gerichte`-Splice `4b9b4bc8`; frischer Wizard nicht „ungespeichert" `22654940`). FF-Merge `715126d2..22654940` (11 Commits, Branch gelöscht).
Endabnahme: Backend voller Lauf **204f/1098p/18s + 24 Subtests** (Alt-Cluster, null neue), neue Tests `test_migration_61.py` (4) + `test_klage_entwurf.py` (8) grün; Frontend **251** Vitest + Build grün.
Spec `docs/superpowers/specs/2026-07-19-klage-wizard-entwurf-speichern-design.md` · Plan `docs/superpowers/plans/2026-07-19-klage-wizard-entwurf-speichern.md`.

**Nachtest-Bugfixes (Akte 828/24 — vier ALT-Bugs seit April, nicht vom Entwurf-Feature; Branch `klage-beklagte-dubletten-fix`, 4 Commits, TDD):**
1. `fd9b7af3` Versicherung doppelt als Beklagte — synthetischer GHPV-Eintrag trotz echtem GHPV-Beteiligten (WDM-Kurzname „ADAC" ≠ „ADAC Autoversicherung AG"); jetzt `_ghpv_bereits_vorhanden` (Kürzel GHPV/GH/GHV zählt immer, sonst Namens-Containment).
2. `bf1c3a35` Wizard-Rubrum zeigte den Fahrer als Versicherung + pauschal „vertreten durch den Vorstand"; Parteien-Karte verlor Lookup-Button/Vertreter-Warnung → neues Modul `parteiLogik.js` für `StepRubrum` + Karte.
3. `d36c61a1` Vertreter-Lookup: HTML-Entities wurden gelöscht statt dekodiert (Umlaute weg), GF-Treffer bei AGs → `_extrahiere_vertreter` pure + Rechtsform-Widerspruchs-Filter.
4. `07cb5bbf` Lookup übernahm Organe fremder/Sammel-Impressen → `_seite_passt_zur_firma` + blockbezogene Extraktion. Live-Probe „ADAC Autoversicherung AG" → korrekt „Vorstand: Stefan Daehne".
5. `9384184c` Expliziter Lookup-Klick zeigte dauerhaft den still vorgefetchten Sitzungs-Cache → Klick sucht jetzt immer frisch, Cache nur für den stillen Vorab-Lookup.
Tests: 8 GHPV + 22 Parser + 12 parteiLogik/Rubrum-Vitest; 178 firmen+klage-Backend grün, Frontend 267 + Build grün.

---

## 2026-07-19 — PRD-33: Klage-Wizard Feintuning KOMPLETT (40 Bugs KW-01–KW-40, Sessions 1–6)

Ist-Analyse (2026-07-17): Multi-Agent-Code-Research → 40 Bugs KW-01–KW-40 + 11 Verbesserungen V1–V11, Tracking `docs/BUGFIX_KLAGE_WIZARD.md`. DOCX-Direkttest-Muster `test_klage_service_docx.py`. Grundsatzentscheidungen → DECISIONS.md.

- **Session 1** (2026-07-17, Branch `klage-wizard-fixes`, in main `578c93e0`): KW-23 Platzhalter-Guard Step 10 (`a6711c2d`) vor KW-01; KW-01 Merge-Lücke (`antraege_override`/`mit_feststellung_sg`/`mit_feststellung_sach` erreichen `klage_cfg`, `e668f50f`+`f239a1fe`); KW-02 RVG-Faktor nicht ins Euro-Override-Feld (`b1c1fbfb`); KW-14 `klage_generiert`-Ereignis trägt Positionen (`d42f09eb`). Backend 204f/965p, Frontend 97/97.
- **Session 2** (2026-07-17, Branch `klage-wizard-fixes-s2`): KW-03 Quote-Fälle A/B (BE+FE), KW-04 eine Rechenquelle + DOCX-Direkttest, KW-05 Eigentum/§1006, KW-07 SG-Ausschluss, KW-11 Unkostenpauschale, KW-39 vorgezogen. Backend 204f/1000p null neue, Frontend 122 + Build.
- **Session 3** (2026-07-18, Branch `klage-wizard-fixes-s3`, in main `d856a8d4`): KW-06 + KW-15–21 als V3-Partei-Grammatik-Cluster (BE-Helfer `_anrede_norm`/`_ist_maennliche_privatperson`/`_beklagten_grammatik`/`_beklagten_rolle`/`_vertreter_suffix`/`_rechtsform_klasse` + FE `kanonischeBeklagte`/`beklagtenGrammatik`/`versichererSuffix`). Backend 204f/1044p, Frontend 141 + Build.
- **Session 4** (2026-07-18, Branch `klage-wizard-fixes-s4`, 9 Commits `36ca8ec6..2076e83e`, in main `ec53900b`): KW-09/10/12/13/08 + KW-35. **V5** Datumsvertrag (`_fmt_datum`/FE-Port `fmtDatumDe`), **KW-10** Verzugseintritt ≠ Schreibdatum (cfg `verzug_schreiben_datum`; Eintritt-Default Schreibdatum+14 Tage), **KW-08** Legacy-Generieren-Button entfernt, **KW-35** RVG-Fallback `_rvg_anlagedatum`, **V6/KW-13** „RVG gerichtlich"-Duplikat entfernt, **V4/KW-12** `AnlagenZaehler` (fortlaufende K-Nummern). Backend 204f/1056p, Frontend 159 + Build.
- **Session 5** (2026-07-18, Branch `klage-wizard-fixes-s5`, 8 Commits `6752215e..e3c1ab68`, in main `c003e962`): KW-22/24–29 als **V7**. Manuell-Flags (`wizardSachverhaltManuell`/`wizardGebuehrenManuell`/`wizardAntraegeManuell`), `antraegeBasis`-Fingerprint + `AntraegeSync` + `TextVeraltetBadge`, `komponiereAntraege` statt Einbrennen, `kannSpringen` kumulativ, Gericht-Persistenz, Verzugsdok-Datum aus `forderung_positionen`, stiller Vertreter-Lookup. Plan `docs/superpowers/plans/2026-07-18-prd33-s5-wizard-state-ux.md`. Backend 204f/1059p, Frontend 198 + Build.
- **Session 6** (2026-07-19, Branch `klage-wizard-fixes-s6`, 15 Commits `c003e962..81706b67`, in main `68ba3e49`): KW-30–34/36–38/40 + **V10**. Bedingte Segmente `unfall_seg`/`ereignis_seg`, zeilenweiser Sachverhalt-Parser, laufender Abschnittszähler `_abschnitt_kopf` (nummerierter Verzug), RVG-0-Suppression + Fall-B-Klemmsatz, `_round2_half_up` (FE half-up vs. BE banker's angeglichen), zentrale Registry `frontend/src/config/klagePositionKeys.js` + Contract-Tests, 10 tote Symbole raus, `<w:tab/>`-Runs, GHPV/Label-Fixes. **V10 Golden-File-Matrix** (`TestV10RenderSmoke` + `TestV10Matrix` 24 Kombinationen) als Regressionsschutz. Backend 204f/1086p + 24 Subtests, Frontend 223 + Build.

**PRD-33 KOMPLETT:** alle 40 KW-Bugs behoben oder mit Begründung als entfallen dokumentiert. FF-Merges nach Freigabe RA Schatz 2026-07-19.

---

## 2026-07-16 — Rausch-Absender automatisch aussortieren + Papierkorb

Aus Topic „Filterregeln für die Review-Queue", im Brainstorming zugespitzt: wertloses Rauschen auf `info@` gar nicht erst in die Queue lassen.
Spec `docs/superpowers/specs/2026-07-16-rausch-absender-auto-aussortieren-design.md` · Plan `…/plans/2026-07-16-rausch-absender-auto-aussortieren.md`. 7 Commits `f0ca50ac..49f53f1e` (Subagent-Driven, TDD, Opus-Whole-Branch-Review + Fix-Wave + Re-Review), per FF in `main` (`49f53f1e`).

- YAML-Registry `backend/registry/rausch_absender.yaml` (fail-loud, eager beim App-Start) mappt Absender-Domain→Policy; reine Funktion `backend/intake/rausch_regel.py::policy_fuer_domain`. Placetel→`nur_body` (Fax-PDF bleibt), beA→`komplett`.
- `adapter_imap.verarbeite_email` ruft `backend/intake/verwerfen.py::auto_verwerfen` (Soft-Delete, `verworfen_von=NULL`, `grund='rauschen'`); `_VERWERFBARE_STATUS` enthält `laeuft` (Worker-Race-Fix).
- Papierkorb: `GET /intake/papierkorb` + `POST …/wiederherstellen`, Queue⇄Papierkorb-Toggle in `ReviewQueueView`. Keine Migration.
- Backend 204f/961p, Frontend 91 + Build. **DEV-Smoke ✅** (verify-Skill, rückstandsfrei).

---

## 2026-07-16 — Bugfix: AZ-Normalisierung + Personenschaden-Schema-Drift

Commit `991095e1` auf `main`. systematic-debugging + TDD. Fund: Unfallbogen freigegeben, Reiter Unfalldetails leer.
- (a) `AktenLiveSuche` nahm die RA-MICRO-Anzeigeform mit SB-Kürzel (`670/26AS`) als Speicherschlüssel → Phantom-Akte. Fix: `t.az_roh`; `post_freigabe` normalisiert `akte_az` via `_basis_az`. Daten `670/26AS`→`670/26` repariert.
- (b) `personenschaden.krankenhaus_aufenthalt` fehlte in Bestands-DBs (Schema-Drift) → stiller Datenverlust via Best-Effort-Swallow. **Migration 60** (additiv/idempotent). Deploy-Konsequenz siehe STATE.md.

---

## 2026-07-15 — PRD-37: Dokumentenbezeichnung vorschlagen + Feld

Regelbasiert vorgeschlagene, editierbare Dokumentenbezeichnung im Review + in der E-Akte.
Spec `docs/superpowers/specs/2026-07-15-dokumentenbezeichnung-design.md` · Plan `…/plans/2026-07-15-dokumentenbezeichnung.md`. 13 Commits `12b31f14..b19decb8` (Subagent-Driven, TDD, Opus-Final-Review READY), per FF in `main` (`b19decb8`).
- Reine Funktion `backend/services/dokument_bezeichnung.py::baue_bezeichnung` → `«Label» «Aussteller» vom «Datum» («Betrag»)`; Sonderfall `sonstiges` = „Schreiben"/„E-Mail".
- Je Klassen-YAML `label` + `bezeichnung_felder`; `hole_detail` liefert `bezeichnung`+`bezeichnung_vorschlag`; `PATCH /intake/dokument/<id>/bezeichnung`; Freigabe schreibt nach `dokumente.bezeichnung`; E-Akte nachträglich editierbar.
- **Migration 59** (additiv/nullable/idempotent). Deploy-Konsequenz siehe STATE.md. Frontend 88 + Build, Backend zero neue Failures.

---

## 2026-07-15 — PDF-Splitting im Review-UI (Option C)

Mehrseitige Sammel-PDFs im Review-Dialog entlang Seitengrenzen auftrennen, bevor freigegeben wird.
Spec `docs/superpowers/specs/2026-07-15-pdf-splitting-review-design.md` · Plan `…/plans/2026-07-15-pdf-splitting-review.md`. 7 Commits `f7b5191b..e3492e9d` (Subagent-Driven, TDD), in `main` `c093ad70`/gepusht.
- **Ansatz A:** Teile = neue Intake-Dokumente (`queue_status='neu'` → Worker klassifiziert), Original soft-deleted + verlinkt via `aufgeteilt_aus_id`; Zustellungs-Signale vererbt.
- **Migration 58** (`intake_dokumente.aufgeteilt_aus_id`), `backend/intake/split_service.py` (PyMuPDF), Endpoints `/split`+`/seiten`+`/thumbnail`+Guard, Frontend `splitLogik.js`+`SplitDialog.jsx`.
- Abschluss-Review (Opus) READY TO MERGE. **DEV-E2E-Smoke ✅** (Reloader-Trap Mig 58 auf DEV gefunden+gefixt).

---

## 2026-07-15 — Prod-Rollout intake-stufe1 (Git-Teil)

`intake-stufe1` → `main` per Fast-Forward gemergt (`a06aaae5`, 201 Commits) + beide Branches nach origin gepusht; Backup-Tag `pre-rollout-main-20260715` (alter main `e8313486`, lokal+remote); Home-Repo-Guardrail angelegt.
**Prod-Deployment bewusst vertagt** (Nutzer 2026-07-15) — Details/Runbook siehe STATE.md.

---

## 2026-07-14 — Fragebogen-Feld-Übernahme bei Freigabe (Folge aus BUG-01)

Branch `intake-stufe1`, Commits `362a0895..367f44de` (10 Commits). Subagent-Driven (7 Tasks, TDD), Abschluss-Review Opus READY WITH FOLLOW-UPS.
Spec `docs/superpowers/specs/2026-07-14-fragebogen-feld-uebernahme-design.md` · Plan `…/plans/2026-07-14-fragebogen-feld-uebernahme.md`.
- Freigabe-Dialog zeigt geparste Felder als editierbare Vorschau; nur leere Aktenfelder werden übernommen, abweichende überschreibbar. Abschnitts-Checkboxen + Auto-Collapse.
- Service `backend/services/fragebogen_uebernahme.py` (eigene Transaktion je Abschnitt); `GET /intake/dokument/<id>/fragebogen-vorschau`, Übernahme in `post_freigabe` (Best-Effort). Frontend `FragebogenUebernahme`.
- Voraussetzung mitgefixt: Text-Dokument-Freigabe (ohne Arbeitskopie) via `_sichere_text_arbeitskopie`. Keine Migration.
- Guards `test_s19_intake_write_guard.py` + `test_s19d_e2e_no_intake_writes.py` bleiben grün; `uebernehme` in die Guard-Whitelist verboten aufgenommen (nur `post_freigabe` erlaubt, Commit `29285840`).
- **Smoke-Test in DEV ✅** (13 Felder geschrieben, rückstandsfrei). Nebenbefund: Reloader-Migrations-Trap `llm_degradiert` fehlte → per ALTER nachgezogen.

---

## 2026-07-14 — Pipeline-Qualität N-03 + N-04

- **N-03 Retry-Differenzierung + Degradations-Hinweis** (Commits `7142b73b..ad7fcfe9`, Subagent-Driven, Whole-Branch-Review READY). Spec/Plan `…2026-07-14-n03-retry-differenzierung*`. `klassifiziere_fehler(meldung)` → timeout (Backoff) / ressourcendruck (+900s, kein Zähler) / reproduzierbar (sofort `pipeline_fehler`). `extrahiere_felder` liefert `llm_status`; **Migration 57** `intake_dokumente.llm_degradiert`; Frontend `DegradationBadge` „nur Regex". „Arbeitskopie fehlt" ist jetzt reproduzierbar → kein Retry. Backend 204f/846p, Frontend 60.
- **N-04 Seiten-Triage vor OCR** (Commits `e806c281..e8d3fca1`, Subagent-Driven, READY nach 1 Fix). Spec/Plan `…2026-07-14-n04-seiten-triage*`. Triage über **Textabdeckung** (Flächenanteil Wort-Boxen) statt Wortzahl → robust gegen Fotoseiten. `_ocr_seite` Tesseract-zuerst → `text_abdeckung`/`ist_bildseite` → GLM nur auf Textseiten. Migrationsfrei (`SeitenText.ist_bildseite`, `parse_json.bildseiten_anzahl`). Frontend `BildseitenBadge`. Backend 204f/857p, Frontend 62. **SDD-Lehre:** nach Signaturänderung volle Suite, nicht nur Golden-Subset (Critical `TestBug12OcrLinear` gebrochen → Fix `e8d3fca1`).

---

## 2026-07-13 — Bugfix-Reihe BUG-01–30 (Intake-Pipeline v7) + N-01/N-02/N-06 + N-09/N-10 + Druckbutton

Code-Review 2026-07-12 fand 30 Bugs (Multi-Agent, `docs/BUGFIX_INTAKE_V7.md`). Alle behoben (TDD), Branch `intake-stufe1`, nicht gepusht.
- **P0 (BUG-01–04)** `6c858aa1` — stiller Datenverlust unter `INTAKE_REVIEW_PFLICHT` geschlossen (Fragebogen→Queue, Anhang-Fehler, Upload-Ziel-Akte, Alt-Mail-Fallback).
- **P1 (BUG-05–07)** `b6826d91` — Betrags-Korrektheit (`_feld_zu_zahl` nutzt `parse_betrag`, kein 100×-Fehler), Freigabe-Guards (409), `_anker_dokument_id` filtert per `akte_az`.
- **P2 (BUG-08–13)** `7b95be7a` — RA-MICRO-only-Akte on-demand in SQLite, Fristablauf-Job ohne Write-Lock, Scheduler-Loopback-Lease (`scheduler_lease.py`), Upload-Validierung 422, OCR pro Seite via `first_page`/`last_page`, Migration 50 ohne executescript.
- **P3 (BUG-14–19)** `88271a6a` — Signal-Vererbung an Anhänge, E-Akte-Key `az`, KFZ-Umlaut-Muster, Kurz-Body-Schwelle weg, Queue-Sortierung.
- **P4 (BUG-20–30)** `8bac957f`/`1f469367`/`f175fe2c`/`b9254e09`/`b822cfa8` — `hole_queue` per `json_extract`+JOIN, AZ-Norm-Helper, IMAP-Config-Dedup, Poll-Abbruch bei Unmount u. a. Frontend 48 grün.
- **N-01 + N-06** `c5a46c13` — N-01 Wörterbuch-Check → OCR-Fallback bei korruptem Font-Encoding (`_WOERTERBUCH`/`woerterbuch_quote`); N-06 Seitenauswahl (Seite 1 + letzte + Regex- + Tabellen-Seiten) via `llm_text`-Param, Regex bleibt auf Volltext.
- **N-02** `34b50e63` (Mig `94c18ea1`) — OCR-Qualitätsmetriken (**Migration 56** `ocr_ratio_salat`+`ocr_quote_woerter`), `dokument_ocr_qualitaet` (Schlechteste-Seite auf Finaltext), Frontend `OcrBadge`.
- **N-09 + N-10 + Druckbutton** — N-09 `busy_timeout=30000`-PRAGMA (verify+harden, `timeout=30` setzte es ohnehin); N-10 Backup repariert (`scripts/backup.sh`, SQLite `.backup` statt `cp`, stündlich) — **Fund:** `.backup` läuft NICHT von `:ro`-Mount (WAL braucht `-shm`-Schreibzugriff) → `/data` auf read-write; Guard `TestBackupInfra`. Druckbutton `druckZiel(detail, pdfSrc)`, Frontend 52.

---

## 2026-07-12 — P1.5e: Review-Freigabe schreibt Ereignisse für alle Klassen

Branch `intake-stufe1`, Commits `6863f918..a0c50f6a`. Spec/Plan `…2026-07-11-p15e-freigabe-ereignisse*`. Subagent-Driven (5 Tasks, TDD). Grundsatzentscheidungen → DECISIONS.md.
- Registry `backend/registry/klasse_ereignistyp.yaml` (7 Klassen → eingehender Ereignistyp) + fail-loud Loader-Feld.
- Helper `eingehende_ereignisse.erzeuge_aus_freigabe()` — Positionen nur bei `gutachten_eingegangen`/`rechnung_eingegangen`, sonst Fakt-Ereignis; `herkunft='freigabe'`, Best-Effort, Doppelerfassungs-Guard.
- `post_freigabe` schleift über bestätigte `kandidaten_ereignisse`; Gutachten-Sonderfall entfernt; `_anker_dokument_id` liefert stabile dokument_id. Serverseitiger `eingehend`-Guard (Defence-in-depth).
- Frontend: `default_ereignistyp` belegt das Dropdown vor. Keine Migration. Backend 204f/732p, Frontend 41.
- **Follow-up** `74400131`: Polling-Tick überschrieb offene Dialog-Eingaben → `naechsterFormState(detail, {skipFormReset})`. Frontend 44.

---

## 2026-07-10 — P1.7 (UI Positionsmodell) + Text-Pfad + N-08/N-07

- **P1.7** (UI-Umsetzung Positionsmodell): `AbleitungBadge.jsx` (Wissensgrenze „nach Aktenlage, letztes Ereignis vom …", technisch erzwungen); Backend `has_unbestaetigt` + Registry-Metadaten; `PositionsDashboard` in `UebersichtSection.jsx` (Datenquelle ausschließlich `GET /akten/<az>/positionen/status`, Toggle getrennt/aggregiert, WDM-Kennzeichnung); Ereignisliste-Endpoint; `DokumentAktionsmenue.jsx` (Kebab je PDF-Zeile). Vitest-Setup (vitest+jsdom+testing-library) eingeführt. 36 Tests. (DetailPanel-State-Reset via `key={aktivId}`, `d4c9cda`.)
- **Text-Pfad für Intake-Pipeline** (6 Commits `e73ab003..e2b5815a`). Spec/Plan `…2026-07-10-text-pfad-intake*`. Text-Zweig in `verarbeite_dokument` (`_synth_seite`, `payload_typ='text'`, `textquelle='email_text'`); `hole_detail` liefert `payload_typ`+`eltern_email`; Frontend `TextVorschau`+`EmailKontextBox`+`gruppiereQueue`. **Migration 54** (`textquelle`-CHECK erlaubt `email_text`). Backfill 51 Text-Dokumente (`scripts/backfill_textpfad.py`).
- **N-08** Baseline „Sekunden pro Freigabe": **Migration 55** (`review_geoeffnet_am`), `sekunden_bis_freigabe` als `korrektur_log`-Zeile.
- **N-07** Bestandsakten-Hinweis (Ersatz für zurückgestelltes P1.8): `positionsstatus_service.berechne_historie_hinweis()` + `EREIGNISMODELL_EINGEFUEHRT_AM` (env, Default `2026-07-09` — beim Prod-Cutover setzen). Frontend-Hinweisbox in `PositionsDashboard.jsx`.

---

## 2026-07-09 — Intake-Refactoring: S1.9 + Positionsmodell P1.1–P1.6

**Großprojekt Pipeline v7 + Positionsmodell.** Maßgebliche Dokumente: `freigabe.md`, `PIPELINE-REFACTORING-PLAN.md`, `POSITIONSMODELL-PLAN.md` (Projekt-Root). Arbeitsbranch `intake-stufe1`.

- **S1.9a–d** — `INTAKE_REVIEW_PFLICHT` (Default True) macht die Review-Freigabe zum einzigen Schreibweg in Akten-Tabellen (Grundsatz → DECISIONS.md). **Migration 49** (`email_import_log.ausgeblendet`). Alt-Pfade (Anhang-Auto-Registrierung, Upload-Route, E-Akte-Import, `_ergaenze_*`) hinter dem Flag stillgelegt; Guard-Test `test_s19_intake_write_guard.py` als Rollback-Anker + `test_s19d_e2e_no_intake_writes.py`.
- **P1.1** — Registries `positionsarten.yaml`/`ereignistypen.yaml`/`aktionen.yaml` + fail-loud Loader `positionsmodell_registry.py` mit Konsistenzchecks.
- **P1.2** — **Migration 51** `ereignisse` / `ereignis_positionen` / `position_ereignis_cache` (K-M1 UNIQUE). `ereignis_service.schreibe_ereignis()` einziger Schreibpunkt; `rebuild_cache()`; AST-Guard-Test blockiert Fremd-Writes.
- **P1.3** — `positionsstatus_service.leite_positionsstatus_ab()` (liest nur `position_ereignis_cache.status='aktuell'`); Blueprint `positionen_routes.py` (`/positionen/status`, `/aktionen`).
- **P1.4** — `ausgehende_ereignisse.erzeuge()` an 5 Generierungs-Stellen (word_service, gebuehren_word, klage_routes, sta_routes, stellungnahme_routes).
- **P1.5a–d** — vier Bestätigungswege (`eingehende_ereignisse.py`): ReguWizard→`abrechnung_eingegangen`, Beleg→`rechnung_eingegangen`, Gutachten→`gutachten_eingegangen` (K-M2a positionsscharfe Ersetzung), WDM→`abrechnung_eingegangen` (unbestätigt, `herkunft='wdm'`). Registry `rechnungstyp_mapping.yaml`.
- **P1.6** — System-Ereignisse via APScheduler. **Migration 52** (`todos.fristablauf_ereignis_id`). `fristablauf_service.verarbeite_faellige_todos()`, cron-Job täglich 03:15, Endpoint `/system/fristablauf/manual`.

**P1.8 (Backfill) ZURÜCKGESTELLT** (Entscheidung RA Schatz 2026-07-13, forward-only) → siehe DECISIONS.md. Prompt archiviert: `handover/naechste_session_P1_8_prompt.md`.

---

## 2026-07-08 — Bugfixing-Session (Testsuite-Sanierung)

Branch `intake-stufe1`. Baseline 294f/385p/26e → **211f/524p/0e/18s** (−83 failures, −26 errors).
- `a6fb6f4` Test-Stub-Kontamination in `test_prd23b.py` entfernt (Modul-Ebenen-`sys.modules`-Stub kontaminierte Reihenfolge); Guard `test_prd23b_kontamination.py`.
- `12d78c5` `TestKlassifiziereEakteDok` an Listen-Signatur angepasst; SV-Domain-Tests korrigiert.
- `9ffcbe6` `conftest.py` setzt `FLASK_SECRET_KEY` vor Collection.
- `746f731` `test_modul6.py` `TestBackupScript` entfernt, Gitignore-Erwartungen aktualisiert.
- `70c77c4` **Migration 50** legt `unfalldetails`-Tabelle nachträglich an (Root-Cause: `CREATE TABLE unfalldetails` fehlte im Schema-Manager → Mig 28 SKIPPED → `POST /klage/generieren` crashte 500). Handover `handover/2026-07-08-datenmodell-bugs-unfalldetails-cleanup.md`.
- `d5916d3` `cleanup_abrechnungen.py` DB_PATH-Default gefixt.
- `6572abf` `test_portal_sync.py` Fixture um `gutachten_nr`.
- `e7bdad9` Auth-Bootstrap in `conftest.py` (`JWT_SECRET_KEY`+`ADMIN_*`).
- `9fcdcb5` nginx.conf Config-Bugs + self-signed Zertifikat lokal.

**Offen (Alt-Cluster, kein Blocker):** Testsuite-Modernisierung `test_modul3/4/7` (~150 Failures, kein 1-Zeilen-Fix, eigenes Ticket); `test_prd23b.py`/`test_modul8.py` Alt-Failures; kleinere `test_migration_46`/`test_sv_portal`/`test_modul1`.

---

## Ältere abgeschlossene PRDs (Kurz-Index)

Detail in den jeweiligen Session-Handovers (`handover/`, `session_handover_v38–v56.md`) und der Git-Historie.

| PRD / Feature | Beschreibung |
|---|---|
| PRD-01 (Basis) | To-Do-System + Header-Widget |
| PRD-02 | Textbaustein-Feld Kürzungsarten |
| PRD-03 K-01–K-15 | Klageschrift-Formatierung |
| PRD-04 / 04b | Dokumentenklassen + Dispatcher + Registry; Feedback-Loop |
| PRD-14 | SSOT Abrechnungsart |
| PRD-15 | WDM Auto-Load |
| PRD-16 | Tab-Reihenfolge als Workflow-Ablauf |
| PRD-18 | Phasen-Strip (UebersichtSection) |
| PRD-20 | App.jsx Refactoring (26 Dateien) |
| PRD-21 Ph. 1–3a | E-Akte Auto-Import |
| PRD-22a/b/c/d | Gutachten-Reiter; Regulierung+Löschen; Mandanten-Fragebogen; E-Mail-Import-UI |
| PRD-23a/b | Schadenposition-Belege; Rechnungs-Parser (59 Tests) |
| PRD-24 | Aktivlegitimation + Klage-Wizard A–D |
| PRD-25a/b | Automatische Fristen; Action-Dashboard |
| PRD-26 | Klage-Wizard 10-Step (Umbau) |
| PRD-27 | ReguWizard – Stellungnahme-Wizard |
| PRD-28 | Gebührenassistent Nr. 2300 VV RVG + Kostennote DOCX |
| PRD-29b | E-Akte E-Brief-Filter via Schlagwort |
| PRD-30 | OCR + SSE-Streaming (pytesseract, pdf2image) |
| PRD-31 (KI) | KI-Parsing Gutachten (Shadow-Mode, Konflikt-Dialog) |
| PRD-32 Ph. 1 | Rechnungstypen-Subklassen im Classifier |
| PRD-34 | Inbox-Pattern Dokumente-Kachel |
| PRD-35 | Klage-Wizard Bug-Fixes (5 Bugs) |
| PRD-36 (a–d) | Code-Konsolidierung (`_helpers.py`, `utils/datum.py`, `models/beteiligte.py`) |
| PRD-US01/02/05/06 | RA-Micro Heartbeat; IMAP Auto-Polling (Schema-43); E-Akte Hover-Vorschau; Health-Dashboard |
| PRD-US19 | RA-Micro DMS Integration (read-only) |
| B-08 / B-09 | Netto/Brutto bei Vorsteuer; Gegenstandswert |
| Regulierungs-Workflow Option B | 5 Phasen, Legacy deprecated, Delete-Bug v14c |
| KI-Parsing Regulierungsschreiben | Qwen Shadow-Mode, Modell-Switcher, Few-Shot |
| Action Board Global + OnboardingHub | ActionBoardView, OnboardingHub (7 Kacheln) |
| E-Mail-Workflow Redesign | EmailDetailView, UA-Ordner, Migration 42/44 |
