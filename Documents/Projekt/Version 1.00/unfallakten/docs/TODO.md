# TODO – Unfallakten-Verwaltungssystem

> Schlanke Arbeitsliste — nur Zukunftsgerichtetes. Zuletzt gestrafft: 2026-08-12 (nach dem großen Merge).
> Erledigtes mit Protokoll → `docs/CHANGELOG.md` · Entscheidungen mit Begründung → `docs/DECISIONS.md` · Deploy/Betrieb → `docs/STATE.md`.

---

## 🔄 In Arbeit

### Belegkette Fundament (R1+R2) — ✅ umgesetzt (2026-09-08, Branch `belegkette-fundament`), Abnahme offen
Migration 75 gibt `dokumente` die Spalte `dokument_datum` (Datum des Schreibens statt
Eingang), abgeleitet aus `bezeichnung_felder.datum` der Klassen-Registry, im Freigabe-
Dialog korrigierbar. Die Review-Freigabe trägt ihre Belege jetzt selbst in
`schadenposition_belege` ein (`backend/services/beleg_zuordnung.py`, einziger Schreibweg).
Spec `docs/superpowers/specs/2026-09-07-belegkette-beweisantritt-design.md`, Protokoll →
CHANGELOG. **Offen:**
- **Abnahme im Betrieb** (siehe Spec-Anhang): Gutachten freigeben → Datumsfeld vorbelegt,
  Positionen zeigen das Gutachten als Beleg ohne manuelles Zuordnen; Mietwagenrechnung
  freigeben → sofort Beleg an der Position; altes Forderungsschreiben mit Datum von damals
  freigeben → steht im Klage-Wizard an der richtigen Stelle in der Verzugsliste.
- **R3–R5 stehen aus** (Anlagennummern, „b.b.", Beweismittel-Schritt im Klage-Wizard).
- **Entscheidung RA Schatz (2026-09-08):** Ein Gutachten belegt Wertminderung, Restwert,
  die fiktiven Reparaturkosten (`rep_gutachten_netto`) und den Wiederbeschaffungswert
  (`wiederbeschaffung`) — jeweils mit dem Betrag, der wörtlich im Gutachten steht.
  Wertminderung und Restwert können 0 sein, das ist eine gültige Belegzeile.
  Gutachterkosten belegt NICHT das Gutachten, sondern die SV-Rechnung. Umgesetzt in
  `_gutachten_belegpositionen` (`backend/services/beleg_zuordnung.py`).
- **Offen: Doppelbedeutung des Positionsschlüssels `wiederbeschaffung`.** Im Buchungsmodell
  (`waehle_fahrzeugschaden` in `backend/services/eingehende_ereignisse.py`) steht
  `wiederbeschaffung` für den Wiederbeschaffungs**aufwand** (WBW abzüglich Restwert); im
  Schadenformular (`frontend/src/config/constants.js`, Label „Wiederbeschaffungswert
  (WBW)") und in der Beleganzeige (`SchadenSection.jsx`) steht derselbe Schlüssel für den
  vollen Wiederbeschaffungswert, mit dem Restwert als eigener Abzugszeile. Der neue
  Gutachten-Beleg auf `wiederbeschaffung` (siehe oben) folgt bewusst der
  Formular-Bedeutung, weil dort die Beleganzeige nachschlägt — die Doppelbedeutung selbst
  ist damit nicht aufgelöst, nur bewusst in Kauf genommen.
- **Offen: fiktive Mehrwertsteuer.** Der Gutachten-Parser extrahiert keinen ausgewiesenen
  Steuerbetrag (`backend/registry/klassen/gutachten.yaml` kennt nur `reparaturkosten_netto`
  und `reparaturkosten_brutto`) und es fehlt ein passender Positionsschlüssel — `mwst_abzug`
  ist ein Abzugsposten (Nebenkosten), kein ausgewiesener Steuerbetrag. Nicht aus
  brutto minus netto ableiten (Geld-SSOT). Parserfeld + Positionsschlüssel fehlen noch.
- **`pruefbericht`** ist als einzige Klasse ohne `datum`-Rolle geblieben — braucht erst ein
  Parserfeld.
- **Toter Zweig `klage_routes.py`:** fragt nach der Klasse `verzugsschreiben`, die es in der
  Registry nicht gibt.

### Termine der Akte bei den To-Dos — ✅ umgesetzt (2026-09-07, Branch `fragebogen-favoritenliste`), Abnahme offen
Block „Termine" in der Akten-Übersicht, über den Fristen. Zeile aufklappbar (Ort, SB,
Notiz) statt eigener Terminseite. Quelle `raKalender.dbo.Events` über den neuen Dienst
`backend/services/termine_ramicro.py`, den sich Dashboard-Kachel und Akte teilen.
Anders als im Dashboard: ohne Datumsfenster und ohne Kalenderfilter. Protokoll → CHANGELOG.
**Offen:**
- **Aktenblock ansehen:** Akte mit Gerichtstermin öffnen — stehen Art, Datum, Uhrzeit und
  Gericht richtig da, und stimmt der Inhalt beim Aufklappen mit RA-MICRO überein?
- **Dashboard-Weg prüfen:** In der Termine-Kachel auf einen Termin klicken — die Akte muss
  aufgehen und den Termin oben im Block zeigen.
- **Ausfall prüfen:** RA-MICRO-Dienst aus → der Block muss „RA-MICRO nicht erreichbar"
  mit „Erneut laden" zeigen, nicht „keine Termine".
- **Menge beobachten:** Alte Akten führen womöglich viele vergangene Termine. Falls der
  Block zu lang wird, wären die vergangenen der nächste Aufklapper.

### Fristen aus dem RA-MICRO-Kalenderbaum — ✅ umgesetzt (2026-09-07, Branch `fragebogen-favoritenliste`), Abnahme offen
Echte Fristen aus `Z:\RA\Kalender\GT`, Fenster 14 Tage zurück bis 3 Werktage voraus.
Erledigte werden am Schlussfeld-Vermerk erkannt und ausgefiltert, Vorfristen gekennzeichnet.
Leser `backend/services/fristen_gt.py`, Protokoll → CHANGELOG.
Dazu ein Block in der Akten-Übersicht bei den To-Dos: dort **alle** unerledigten Fristen
der Akte (51 Akten, 154 Fristen, bis zu 14 je Akte), laufende zuerst, read-only.
**Kachel im Betrieb bestätigt** (RA Schatz, 07.09.2026: „funktioniert genau richtig").
**Offen:**
- **Testfrist löschen:** `ZZTESTFRIST0907` in Akte 274/25 (Beginn 31.12.2029, Ende 10.01.2030).
  Danach verschwindet sie automatisch aus dem Bestand — sie liegt ohnehin außerhalb des Fensters.
- **Kachel gegenlesen:** Die 5 echten Fristen und 15 Vorfristen mit RA-MICRO vergleichen.
  Stimmen Grund, Datum und Sachbearbeiter?
- **Mount-Ausfall prüfen:** `wsl -d docker-desktop -- umount /mnt/eakte` und die Übersicht
  neu laden — Kachel **und** Aktenblock müssen „Fristenkalender nicht erreichbar
  (E-Akte-Mount)" zeigen, nicht „keine Fristen". Danach `tools/eakte_mount.ps1`.
- **Aktenblock ansehen:** z.B. Akte 70/24 (10 Fristen) oder 603/25 (9). Viele davon sind
  seit über einem Jahr offen und vermutlich nur nie abgehakt worden — falls das stört,
  wäre der Aufklapper für Ältere die nächste Stufe.
- **Entscheidung offen:** Überfällige **Vorfristen** machen aktuell 13 der 20 Einträge aus
  (älteste −14 Tage). Eine Vorfrist, deren echte Frist schon vorbei oder in Sicht ist, hat
  ihren Zweck erfüllt. Falls die Kachel zu voll wirkt: Vorfristen nur in der Vorschau
  zeigen, nicht in der Rückschau.

### Wiedervorlagegründe aus der RA-MICRO-Maske — ✅ umgesetzt (2026-09-07, Branch `fragebogen-favoritenliste`), Abnahme offen
Die geratenen Bezeichnungen sind durch `Z:\RA\Mas\TextWV.msk` ersetzt (99 Gründe, alle
verifiziert; von 41 verwendeten Codes war vorher genau einer richtig). Erzeugt per
`py tools/gen_wiedervorlage_codes.py`. Protokoll → CHANGELOG, Begründung → DECISIONS.
**Offen — Sichtkontrolle im Betrieb:**
- **Wiedervorlagen-Kachel ansehen:** Statt „Zahlung Gegner"/„Vollstreckung"/„Sachstand"
  muss dort jetzt „Mandant gemeldet?", „Ermittlungsakte da?", „Entscheidung/Gericht?"
  stehen. RA Schatz prüft, ob die Gründe zu den Akten passen.
- **Fristen-Kachel** speist sich nicht mehr aus Wiedervorlagen, sondern aus dem
  RA-MICRO-Kalenderbaum — eigener Eintrag oben.
- **Stellungnahme-Filter:** `hole_faellige_wiedervorlagen(nur_stellungnahme=True)` filtert
  jetzt auf 11/16/99 statt 5/6/11/16. Prüfen, ob die Liste vollständig wirkt.

### Dokumentklasse als SSOT — ✅ umgesetzt (2026-09-04, Branch `fragebogen-favoritenliste`), Abnahme offen
`dokumente.typ` ist entfallen, `dokumentenklasse` ist alleinige Wahrheit. Spec + Plan unter
`docs/superpowers/`, Protokoll → CHANGELOG, Begründungen → DECISIONS, Deploy → STATE Abschnitt 0.
Commits `2c6e8f82`..`22e184d8`,
Backend 2222 grün (69 skipped), Frontend 634 grün. **Offen — Abnahme im Betrieb:**
- **Freigabe durchspielen:** Dokument in der Review-Queue öffnen, Klasse auf `sv_rechnung`
  setzen, an eine Akte freigeben. In der DokumenteSection muss **SV-/Gutachterrechnung**
  stehen, nicht „Sonstiges".
- **Klassenlisten vergleichen:** Dropdown in der Review-Queue und in der DokumenteSection
  nebeneinander — dieselben 23 Einträge, dieselben Bezeichnungen.
- **Belege-Ansicht gegenprüfen:** An einer bekannten Akte mit freigegebenen Rechnungen.
  Dort erscheinen jetzt Kandidaten und Beträge, die vorher unsichtbar waren — beabsichtigt
  (das Parse-Ergebnis wandert seit Task 3 mit), verändert aber sichtbar das Bild.
  Gemeinsam mit RA Schatz prüfen, dass die Beträge stimmen.
- **Stakeholder-Portal nachziehen:** Der Sync-Payload liefert jetzt `klasse` +
  `klasse_label` statt `typ`. Die acht anzupassenden Dateien stehen in Spec Abschnitt 6.3;
  Repo unter `Projekt/Version 1.00/stakeholder-portal`. Portal ist **nicht live**, kein
  Doppel-Deploy nötig.
- **Sicherung aufräumen:** `/app/data/bak_vor_migration_74.db` im Dev-Volume löschen,
  sobald die Abnahme durch ist.

### Priorisierte Fragebogen-Liste in der Review-Queue — ✅ codeseitig komplett (2026-08-28, Branch `fragebogen-favoritenliste`), Abnahme offen
Spec + Plan unter `docs/superpowers/`, Protokoll → CHANGELOG. Alle 8 Aufgaben committet (`60e28ef4`..`b15bcd24`), Backend 1994 grün (38 skipped), Frontend 594 grün. **Offen — Abnahme im Betrieb:**
- **Reparse der acht Altbögen:** In der Review-Queue je Bogen (474, 475, 476, 527, 613, 672, 727, 834) den Reparse-Knopf drücken, rund zehn Sekunden warten. Sie tragen noch `sonstiges`; die Signale entstehen erst beim Pipeline-Lauf neu.
- **Sektion prüfen:** Liste zeigt oben „⭐ Unfallfragebögen (8)", darunter „Übrige Dokumente".
- **Ampeln prüfen:** 476 → 641/26 (Aktenzeichen); die sechs über die Mandantenadresse geprüften Fälle grün auf 742/26, 760/26, 768/26, 710/26, 751/26, 749/26; 474 weiterhin 675/26 (Kennzeichen). Bogen 672 gehört zur **abgelegten** Akte 749/26 — muss den Zustand „abgelegt" mit Ablagedatum zeigen und **keinen** Anlage-Knopf.
- **Eine Freigabe durchspielen:** grünen Bogen öffnen, Akte bestätigen, Feld-Übernahme prüfen (Mandant/Gegner/Unfall/Personenschaden), freigeben. Der Eintrag verschwindet aus der Sektion, das Dokument erscheint in der Akte als „Unfallfragebogen vom …".
- **Blauen Fall prüfen:** Ist kein Bogen blau, ersatzweise an einem Testbogen ohne bekannte Merkmale — der Anlage-Dialog muss mit Name, Anschrift, Telefon, E-Mail, Kennzeichen und Unfalltag vorbefüllt öffnen.
- **`unfall@`-Reiter prüfen:** Die Karte „Fragebogen-Erstkontakt" ist verschwunden, der Reiter im Übrigen unverändert. Der Erstkontakt-Weg ist stillgelegt, die Tabelle `fragebogen_erstkontakt` bleibt leer bestehen.
- **Merken für Tests:** 18 Tests laufen absichtlich echt gegen RA-MICRO und werden normal übersprungen — Aufruf mit `RAMICRO_INTEGRATION=1 pytest -m ramicro_integration backend/tests/`.

### Beteiligten-Kürzel-Verzeichnis — ✅ umgesetzt (2026-08-31, Branch `fragebogen-favoritenliste`), Abnahme offen
Zeugen standen als Gegner in der Beteiligtenliste und waren im Klage-Wizard als Beklagte vorausgewählt. Fünf getrennte Kürzel-Auslegungen sind auf `backend/registry/beteiligten_kuerzel.yaml` vereinheitlicht. Protokoll → CHANGELOG, Begründungen → DECISIONS. Backend 2105 grün, Frontend 603 grün. **Offen — Abnahme im Browser:**
- **Akte 13/26:** Müller und Bukh müssen als „Zeuge/Zeugin" erscheinen (violett), nicht als Gegner. Danach den Klage-Wizard derselben Akte öffnen: nur die VHV darf angehakt sein.
- **Akte 108/26:** Rechtsschutzversicherung, Schadenabwickler, Landgericht, Staatsanwaltschaft und Polizei müssen einzeln benannt sein — vorher hießen alle fünf „Sonstige Beteiligte".
- **Fragezeichen-Fälle sichten:** Drei Beteiligte im Bestand tragen ein Kürzel ohne Eintrag (`KOAN`, `OA`, `UB`). Sie zeigen ein „?" mit Erklärung beim Überfahren. Wenn Sie die Bedeutung kennen: in die YAML nachtragen.
- **Entscheidung RA Schatz — `HV`/`VS`:** Beide sind als `offen: true` markiert, weil das Kürzel die Sparte nennt (Haftpflicht/Versicherung), nicht die Seite. In den Unfallakten kommt derzeit keines vor.
- **Merken:** Nach Änderungen an der YAML ist ein `docker restart unfallakten-backend-dev` nötig (Reloader reagiert nur auf `.py`, die Registry cached).

### Review-Queue im Testbetrieb sauber halten (seit 2026-08-28)
879 Altdokumente archiviert (reversibel, Papierkorb-Reiter), acht Werbedomains in die Rausch-Regel. Protokoll → CHANGELOG. **Offen:**
- **Regelmäßig aufräumen, solange das System nicht live ist** — Zufluss 40–80 Dokumente/Tag, der Rauschfilter fängt davon nur ~7 %. Kommando: `MSYS_NO_PATHCONV=1 docker exec unfallakten-backend-dev python /app/tools/queue_altbestand_archivieren.py --dry-run` (ohne `--dry-run` räumt es auf).
- **Entscheidung RA Schatz:** automatischen Archivierungslauf einrichten? Falls ja, muss er **vor dem Live-Gang wieder abgeschaltet werden**, sonst verschwindet ungesehene Post.
- **Beim Live-Gang prüfen:** Die acht neuen Rausch-Domains und die bewussten Ausnahmen (`anwaltverein.de`, `iww.de` — verschicken auch echte Post) noch einmal gegenlesen.

### Geld-SSOT + Abrechnungs-Vorschlag (2026-08-26, Branch `geld-ssot-abrechnungsvorschlag`)
Grundsatzentscheidung RA Schatz in `docs/DECISIONS.md` („Geld-SSOT", hebt den Beschluss vom 2026-08-10 auf). Protokoll → CHANGELOG. **Offen:**
- **Browser-Abnahme an 589/26:** Beleg-Dropdown zeigt Bezeichnungen statt Hashes; Hinweisleiste „ausgelesene Abrechnungsschreiben" in der Regulierung + Übernahme-Dialog; Kopfzahl der Übersicht = 6.256,57 € und deckungsgleich mit dem Abschlussbericht; neue Zeile „Kosten der Nachbesichtigung (brutto)" im Schaden-Tab.
- **Regulierungs-Tabelle + Forderungshistorie auf `/akten/<az>/positionen/status` umstellen** — letzter Rest Doppelberechnung (gleiche Zahlen, eigener Frontend-Code).
- **Haftungsquote in der Kopfzahl:** wird nicht mehr aufmultipliziert (Gleichstand mit dem Abschlussbericht). Falls quotiert gewünscht, muss der Bericht mitziehen — Entscheidung RA Schatz.
- **Auffangklasse `rechnung`:** Freigabe bucht keine Position; ein späteres Reparse verfeinert die Klasse, zieht das Ereignis aber nicht nach (589/26: beide SV-Rechnungen). Eigenes Vorhaben.
- Toter Code in `RegulierungSection.jsx`: `AbrechnungFormular` + `ManuelleAbrechnungFormular` (~340 Zeilen) werden nirgends gerendert.

### Abschlussbericht auf dem Kanzleibriefbogen + USt der RA-Gebühren (2026-08-27, Branch `geld-ssot-abrechnungsvorschlag`)
Protokoll → CHANGELOG, Begründungen → DECISIONS („Abschlussbericht und Klageschrift", 2026-08-27). Backend 1923 / Frontend 571 grün, **noch nicht committet**. **Offen:**
- **Sichtprüfung im Betrieb:** einen Abschlussbericht und einen Sachstandsbericht erzeugen und gegenlesen — Briefbogen mit Sozietätsleiste, Betreffblock (Kurzbezeichnung / Aktenlangbezeichnung / „Abschlussbericht"), Arial 12 durchgehend, Tabellenausrichtung, Grußformel mit der Unterschrift des Aktensachbearbeiters, Bewertungslink klickbar.
- **Vorsteuer-Fall am lebenden Objekt:** Der Absatz „Ihre Anwaltskosten" ist bisher nur an einem konstruierten Fall geprüft (589/26 ist nicht vorsteuerabzugsberechtigt). Bei der nächsten Firmen-/Unternehmerakte gegenlesen — auch die Klageschrift (Antrag 2 netto, Gebührentabelle ohne USt-Zeile).
- **Datenlage Vorsteuer-Kennzeichen:** Die Regel greift nur bei gepflegtem Kennzeichen (RA-MICRO bzw. WDM `varSSTF`); fehlt es, gilt brutto. Auszählen, bei wie vielen laufenden Akten das Feld leer ist — dann entscheiden, ob eine Warnung im Brief-Dialog nötig ist.
- **Entscheidung RA Schatz — Druckdateinummer:** Die IF-Felder in der Fußzeile aller vier Vorlagen vergleichen ein fest eingetipptes `"AS"` gegen die Kürzel (`if "AS"="AS" "D90" ""`), deshalb trägt jeder Brief den Präfix D90 statt D2/D1/D6. Soll der Renderer das Kürzel einsetzen? Betrifft die Nummerierung aller vier Dokumente.
- **Aktenkonto (Zukunftsthema, RA Schatz):** Ein echter Zahlungsverlauf ist heute nicht abbildbar — es gibt kein Aktenkonto, Auszahlungen an Mandant und Dritte sind nirgends erfasst. Der Bericht spricht deshalb nur noch vom „Regulierungsverlauf". Eigenes Vorhaben, falls gewünscht.
- Zwei Nachbesserungen aus der PDF-Sichtprüfung sind bewusst so geblieben: die Spalte im Regulierungsverlauf heißt „Abrechnung" statt „Abrechnung vom" (passt bei Arial 12 nicht auf eine Zeile), und die Spalte „Anmerkung" steht rechtsbündig, weil die Regel „erste Spalte links, alle weiteren rechts" so vorgegeben war.

### Produktiv-Nachtests nach dem großen Merge (seit 2026-08-11, RA Schatz)
Alles ist in `main` gemergt+gepusht (`cf7dd74d`); Entscheidung RA Schatz: Abnahmen erfolgen im laufenden Betrieb („die Randfälle kriege ich nur so mit"). Beim Arbeiten gezielt sichten, Auffälligkeiten melden:
- **Abschluss-/Sachstandsbericht:** DOCX in beiden Modi generieren und gegenlesen.
- **Entfernungsprüfung:** „📍 Entfernung prüfen"-Popup an 1280/25; dabei Positions-Tabelle im Review-Detail von Dok 517 sichten.
- **Intake-Pending-Badge:** Import in Testakte → „Review ausstehend" in der Dokumentenkachel → Link öffnet Dok in der ReviewQueue → Zeile verschwindet nach Freigabe.
- **SSOT-Klassen-Dropdown** in der ReviewQueue (22 Klassen) kurz sichten.
- **Sachbearbeiter-Verwaltung:** Reiter „Sachbearbeiter" öffnen (elf Zeilen, JH grau als „ausgeschieden", Aktenzahlen aus RA-MICRO, Hinweis auf ME/EM/EY); danach Tagesübersicht öffnen (Chips zeigen beim Überfahren die Klarnamen, CS ist neu dabei, JH nicht).
- **Übersicht-Redesign:** Sichtkontrolle; bewusste Eigenheiten: kurzes KPI-Umspringen beim Öffnen (Alt-Zahlen → Ereignismodell), HQ=0-Semantik (Header 0 € gefordert, Backend-DOCX rechnet bei HQ=0 mit 100 % — bekannte Inkonsistenz).
Zurückgestellte Minors je Modul: `bugfixes.md` + CHANGELOG-Einträge 2026-08-07/-11 (opportunistisch bei nächster Anfassung).

### SV-Portal Ninnivaggi — ✅ umgesetzt (Branch `sv-portal-laufende-akten`, 2026-08-21), Abnahme offen
Spec + Plan unter `docs/superpowers/`, Protokoll → CHANGELOG. Endstand deckungsgleich mit RA-MICRO: 578 Akten, 109 laufend, 469 abgeschlossen. **Offen:**
- **Sichtprüfung im Browser** (datenseitig bereits geprüft, aber nicht am Bildschirm): Portal auf `localhost:3002` starten, im Admin auf Ninnivaggi impersonieren — Startseite meldet „Meine Akten — 578 Fälle", die Liste zeigt beim Öffnen 109, der Chip „Abgeschlossen" klappt 469 auf.
- **Zwei Szenarien am lebenden Objekt:** eine Akte in RA-MICRO reaktivieren (muss nach dem Nachtlauf zurück zu „Laufend", mit wiederhergestelltem Aktenstand); eine Akte in den Einstellungen sperren (muss aus seiner Liste verschwinden).
- **Veröffentlichung des Portals** — eigenes Vorhaben: Domain (`portal.anwalt-offenbach.de` löst derzeit nicht auf), SSL, E-Mail-Versand der Zugangslinks, Auftragsverarbeitung und Datenschutzerklärung für den SV-Zugang. Erst danach kann Ninnivaggi überhaupt zugreifen.
- **Zweiter Sachverständiger (Cassese):** Der Mechanismus trägt ihn; Freischaltung war nicht Teil dieser Abnahme.
- Nacharbeitsliste (geringe Befunde aus den Prüfungen) → `bugfixes.md`.

### Offene Entscheidungen RA Schatz
- **Schriftsatz-Zählung fürs RVG (`gebuehren_service._zaehle_schriftsaetze`):** Die Abfrage zählte bisher alles außer Gutachten und Sachstandsanfragen — weil `sonstiges` alle Feinklassen einsammelte, liefen SV-Rechnungen, Mietwagen- und Abschlepprechnungen als „Schriftsatz“ mit. Beim Wegfall von `typ` verhaltensgleich übersetzt (Ausschlussliste). Fachlich wäre vertretbar, Rechnungen künftig **nicht** mehr als Schriftsatz zu zählen — das senkt die Umfangsbewertung. Entscheidung RA Schatz.
- **I-10 Haftungsquote (Forderungsschreiben):** Brief behauptet bei erfasster Teilhaftung weiterhin Alleinschuld und fordert ungekürzt; FE-Banner quotiert daneben. Braucht juristische Formulierung für den Teilhaftungs-Baustein (+ HQ=0-Konvention, vgl. Inkonsistenz Übersicht/DOCX).
- **Fehlablage (Kürzungstaxonomie Phase 0):** Dok 41478 + 43429 aus Akten 971/25 / 980/25 löschen? (FEHLABLAGE-Vermerk gesetzt; 852/25 nur in RA-MICRO, 418/28 existiert nirgends.)

### Aktenanlage aus der ReviewQueue (PRD-NEW) — ✅ gemergt + gepusht (2026-08-03, `main`=`81e33206`), Nachlauf offen
Feature live abgenommen: Prefill Mandant, OMA-XML **strukturgleich** zum echten RA-MICRO-Export, **Dateiname muss mit `Oma_` beginnen** (Watcher-Filter, case-sensitiv), Import wird erkannt. Behoben: stale-auftraggeber-Prefill + Anrede-Normalisierung, Migration-66-Reloader-Falle, OMA-Pfad (`Z:\RA\M-Plattform`) + Dateiname + XML-Struktur (keine leere `<Gegnerliste>`, `<tvm/>`). Prod-Compose nachgezogen. Detail → Memory `project_unfallakten_aktenanlage`.
**Offen (opportunistisch, kein Blocker):**
- Echter End-to-End-Create-Test beim **nächsten echten Neu-Mandanten**: Adress-Dublette Mandant (Punkt 4), Geschwister-Szenario (Punkt 5), `dtAnlage`-Prüfung. Mit Bestands-/Altakten nicht testbar (RA-MICRO-Test-Akten nicht löschbar).
- Beteiligten-Dublettencheck (DEKRA/Versicherung) — erst am echten Import verifizieren, ob RA-MICROs eigene OMA-Dublettenprüfung reicht.
- `beispieloma.xml` als **bereinigte** Test-Fixture committen (sonst skippt der Struktur-Guard-Test in CI); NICHT die echte Kundendatei (PII).
- Prod-Rollout: `oma-share`-Volume steht in `docker-compose.prod.yml`; bei non-root Gunicorn ggf. `uid`/`gid` anpassen.

### Dashboard-Hell — ✅ gemergt (2026-08-03), Feinschliff ✅ (2026-08-12)
Nacharbeit abgeschlossen: doppelte React-Keys, A11y (`aria-pressed`/`role=alert`/`aria-hidden`), `type=button` + Retry-Disable + `tageBadgeText`-Konsolidierung, toter `pendingEmailId`/`nachrichtenNeu`-Code raus, Sidebar-Emoji → SVG-Icons. Protokoll → CHANGELOG 2026-08-12. **Offen war nur:** SB-Klarnamen-Tooltips → jetzt Teil der Sachbearbeiter-Verwaltung (oben).

### Kürzungstaxonomie — Phase 0 ✅ · Phase 1 ✅ · in `main` (2026-07-24)
**Offen:**
- **Messung Zielwerte (~2026-08-20, nach ~4 Wochen Betrieb):** `docker exec unfallakten-backend-dev python /app/tools/kuerzungsmatching_report.py` — Zielwerte: Abdeckung ≥ 90 %, Trefferquote ≥ 75 %, Positionszuordnung ≥ 90 % (DECISIONS 2026-07-23). Baseline siehe CHANGELOG.
- **Runden-Kachel im echten Betrieb** sichten, sobald die erste Akte 2 Abrechnungsrunden hat (Test-Abdeckung vorhanden, echter Fall noch nicht).
- Fehlablage-Entscheidung → oben bei „Offene Entscheidungen RA Schatz".
Phase 2 (vorgemerkt): Trigger-Umkehr Stellungnahme (PRD-39), Zahlungs-Kaskade, Vorgangsautomat — Konzept `handover/KONZEPT-Kuerzungstaxonomie-Vorgangsautomat.md` Abschnitt 12.

---

## 📋 Backlog (nach Priorität)

### Kritisch / Bald
- **PRD-25c – Automatische Mandantenkommunikation:** `MandantenEmailDialog` nach Generierung von Forderungs-/Regulierungsschreiben; 3 Textbausteine je Trigger, neue Tabelle `mandanten_emails`. PRD: `handover/PRD-25c_Mandantenkommunikation.md`.

### Mittel
- **PRD-39 – Stellungnahme zum Abrechnungsschreiben (DOCX): bereits durch PRD-27 abgedeckt** (verifiziert 2026-07-23: 4 aktive Routen in `stellungnahme_routes.py`, voller DOCX-Generator, Tabelle `stellungnahme_texte`/Mig 40). Offen ist NUR die Trigger-Umkehr (Queue liefert fertigen Entwurf statt manuellem Wizard-Aufruf) — Teil von Phase 2 der Kürzungstaxonomie, kein eigenes Vorhaben.
- **Dokumentenklasse „Klagedrohung" mit `frist_datum` → Verzugs-Automatik im Klage-Wizard:** Fristsetzungs-Schreiben bekommen eigene Klasse + strukturiertes Fristdatum; Verzugseintritt-Vorbelegung = Tag nach Fristablauf. Zwei Befüllungswege (selbst erzeugte Schreiben stempeln die Frist exakt; importierte via Parser). `verzug_dokumente` um `frist_datum` erweitern; optional Kopplung an Fristen-System (PRD-25a). Berührt Intake + Generator — eigenes Vorhaben.
- **Kennzeichen-Erkennung im Akten-Matching zu streng:** `_KFZ_MUSTER` (`backend/intake/akten_matching.py:48`) verlangt zwingend die Schreibweise mit Bindestrich (`OF-BR 1612`). Reale Schreibweisen wie `WÜ PG 777`, `OF A-418`, `OFGM891`, `OF CJ 828` werden nicht erkannt — bei einer Stichprobe von sechs Unfallfragebögen (2026-08-27) traf genau einer das Muster. Für Fragebögen ist das seit dem 2026-08-28 gelöst — dort kommen die Merkmale aus den strukturierten Bogenfeldern statt aus dem Volltext (CHANGELOG 2026-08-28); bei gescannten Gutachten, Rechnungen und Schreiben bleibt die Lücke, dort steht das Kennzeichen nur im Volltext. Zu klären: Muster auf freie Schreibweisen erweitern (Trennzeichen optional) und gegen Fehltreffer absichern. Eigenes Vorhaben, klein.
- **PRD-32 Phase 2 – Rechnungstypen Beleg-Mapping:** erkannte Typen automatisch der Schadenposition zuordnen (Standkosten→Standgeld usw.). Plan: `handover/PRD-32_Rechnungstypen_Parser.md`.
- **PRD-05 – Betrag-Abgleich nach Upload:** hochgeladene Rechnung gegen Schadenposition abgleichen.

### Später
- **PRD-01 – To-Do-System Vollausbau** (Aufgabenzuweisung, Fälligkeiten, Filterung).
- **PRD-06 – Parser Reparaturrechnung via LLM** (für nicht-Regex-parsbare Rechnungen).
- **PRD-07 – Workflow-Regeln + automatische To-Dos** (Regelmaschine bei Ereignissen).
- **PRD-21 Phase 3b/3c** – Batch-Klassifikation + Filter nach Dokumentenklasse (E-Akte).
- **PRD-04c – TF-IDF Classifier** (Ergänzung zum Regex-Dispatcher).
- **PRD-24b – Vollständiger 5-Step-Wizard** (Unfallhergang + Haftungsbegründung als eigene Steps).
- **PRD-25d – Intelligente Sachstandsanfrage.** Alter Plan (`handover/PRD-25d_Intelligente_Sachstandsanfrage.md`) basiert auf `aktenchronik_service.py` (Neubau) — veraltet, seit Pipeline-v7 gibt es das Ereignis-Modell (`ereignis_service.py`, Tabelle `ereignisse`/`ereignis_positionen`) als SSOT für den Aktenverlauf. Aktenchronik-Konzept wird nicht mehr verwendet. Vor Umsetzung: Plan auf Ereignis-Modell umstellen (eigenes Brainstorming). **Dazu gehören die offenen STA-Review-Kernbefunde 2026-08-11** (K-1 Eskalation ignoriert eingegangene Antworten, K-2 RA-MICRO-Vorlagen-Weg für die Stufenlogik unsichtbar, K-3 keine Rundenlogik, M-3–M-6, G-4–G-6) — Befund-Katalog + Empfehlung: `handover/2026-08-11-sachstandsanfrage-review-befunde.md` Abschnitt 6.
- **Stakeholder-Portal (separates Projekt):** PORTAL-A1/B1/B2/B3 — je Plan in `handover/PORTAL-*.md`.

### UserStories (externes Review, offen)
- **PRD-US03 – SV-Portal Upload-Empfang (Kanzlei-Seite):** `POST /sv-portal/upload`, Audit-Tabelle `sv_portal_uploads`. **Braucht US04** (Gegenstelle).
- **PRD-US04 – SV-Portal-Server (Gegenstelle):** eigenständige Web-App, **nicht** im Unfallakten-Repo umsetzbar. Entspricht `handover/PORTAL-B2_SV_Cockpit.md`.

### Action-Board-Restposten (Verfeinerung)
- Fristen-Spalte zeigt nur RA-MICRO-Wiedervorlagen, keine „harten" Rechtsmittelfristen (falls RA-MICRO eine Fristen-Tabelle führt, Schritt 1 wiederholen).
- Nachrichten-Spalte: Mandantenportal-/SV-Portal-Nachrichten sind Placeholder; echte Integration hängt an PRD-25c.

---

## ⏸️ Zurückgestellt (bewusst, kein Handlungsbedarf)
- **Prod-Rollout intake-stufe1** (Nutzer 2026-07-15) → Runbook + Deploy-Reihenfolge in `docs/STATE.md`.
- **N-05** (Yielding/Teilergebnisse) und **P1.8** (Backfill, forward-only) → Begründung in `docs/DECISIONS.md`.
- **Betragsvalidierung Intake** (2026-08-05): größtenteils redundant — Regex↔LLM-Konsens-Check (`llm_konflikt`, > 1 €) existiert bereits in `gutachten_parser.py:685` + `abrechnungsschreiben_parser.py:599`, Temperatur 0 gesetzt. Nicht neu bauen; einziger Rest-Hebel = Beträge als String ins JSON-Schema. Detail: `PROJEKTERWEITERUNG_betragsvalidierung.md` + Memory `project_unfallakten_betragsvalidierung_redundant`.
- **PRD-38** (Dokumentenbezeichnung per LLM) → Begründung in `docs/DECISIONS.md`.
- **V11 Stufe 2 — Kategorie C über vorflektierte Platzhalter** (RA Schatz, 2026-07-24): Aufwand/Ertrag passt aktuell nicht — die betroffenen ~24 Kategorie-C-Bausteine (Anträge, Aktivlegitimation, Sachverhalt-Kernsätze) sind grammatikalisch bereits korrekt hartcodiert (Genus/Numerus/Konjugation via `_get_kl_genus_vars`/`_beklagten_grammatik` in `klage_service.py`), unklar ob echter Änderungsbedarf besteht. Erst Live-Feedback aus dem Betrieb von Stufe 1 abwarten; bei konkretem Bedarf ggf. nur einzelne Bausteine gezielt freigeben statt volle Editor-Infrastruktur.
  Beim eventuellen Kickoff mitzunehmen (Abschluss-Review Stufe 1):
  - Verwaiste Overrides sichtbar machen (Startup-Warnung oder „verwaist"-Anzeige in GET /klage-standardtexte, Lösch-Option) — bei Key-Umbenennungen fällt Kanzlei-Text sonst stumm auf Standard zurück
  - Golden-Test: fehlende Golden-Datei muss FAILen statt still regenerieren (KLAGE_GOLDEN_UPDATE=1 als einziger Schreibweg)
  - Sync-Test Frontend-Fixture (standardtexteFixture.js) ↔ YAML-Registry (wortgleich, byte-genau)
  - Standardtexte-Refresh in offener KlageSection nach Override-Änderung in den Einstellungen (aktuell fetch-once pro Mount)

---

## 🚫 Verworfen (nicht durchführbar)
- **PRD-29 – Schmerzensgeld-Ermittlungstool** (RA Schatz, 2026-07-24): Als nicht durchführbar eingestuft — die Schmerzensgeld-Datenbank ist nicht per API ansprechbar. Plan lag unter `handover/PRD-29_Schmerzensgeld_Tool.md` (Recherche-Ansatz teils über Claude web_search, teils manueller Link zu schmerzensgeld.online ohne API).

---

## ❓ Unklar / zu klären
- **Echte RA-MICRO-Fristen** — liegen nicht im SQL Server (alle acht Datenbanken geprüft, `raKalender.dbo.Deadlist` existiert und ist leer). Offen: In welchem RA-MICRO-Modul werden sie geführt, und lässt sich die Synchronisation nach `Deadlist` einschalten?
- **Freitext-Wiedervorlagen mit Fristcharakter** — 652 Einträge, darunter „Anspruchsbegründung fertigen! DRINGEND!". Landen in der Wiedervorlagen-Kachel. Erkennung offen.
- **Wiedervorlagegrund-Bezeichnungen unverifiziert** — Alle 46 eingebauten RA-MICRO-Codes in `backend/registry/wiedervorlage_codes.yaml` tragen `verifiziert: false`; die Texte stammen aus einer früheren Session und wurden nie gegen RA-MICROs eigene Auswahlliste geprüft. Sechs Codes (25, 61, 63, 78, 93, 98) haben noch gar keine Bezeichnung (`offen: true`) und erscheinen als „Unbekannter Grund (<code>)". Klärt sich durch einen Screenshot der RA-MICRO-Dropdownliste „Wiedervorlagegrund" oder durch Stichprobe der fünf Codes aus der Fristen-Kachel gegen die jeweilige Akte: 55 → 158/25CO, 21 → 157/23AS, 51 → 361/25PK, 75 → 403/26AH, 31 → 808/26AS. Eilt: 537 Wiedervorlagen zeigen inzwischen eine dieser unverifizierten Bezeichnungen, wo vorher nur das pauschale Wort „Wiedervorlage" stand.
- **PRD-29 DKz-Filter — erledigt oder offen?** Handover sagt „implementiert" (via Schlagwort `E-Brief`, da DKz-Feld in DB fehlt), v56 sagt „nicht gestartet". Ist das ursprüngliche Ziel als erfüllt zu betrachten?
- **Zwei getrennte Positions-Modelle abgleichen (aus UX-Review 2026-07-31, Baustelle 3):** Das alte Schaden-Formular (`schadenpositionen`-Tabelle, füttert Forderung/Klage) und das neuere Ereignis-Modell (`ereignisse`/`ereignis_positionen`/`position_ereignis_cache`, füttert `PositionsDashboard`) laufen parallel und gleichen sich **nicht** automatisch ab; die `position_key`-Namensräume differieren (alt hat `_netto`-Varianten, Registry `positionsarten.yaml` nicht — im Code als „bis P1.7" vertagt, `belege_routes.py:135-152`). Zu klären: konsolidieren (eine SSOT) oder bewusst getrennt lassen? Kontext: `docs/superpowers/specs/2026-07-31-belege-zu-positionen-design.md` §9.

---

## ✅ Erledigt
> Kompakter Index. Vollständige Umsetzungs-Protokolle mit Commits/Tests: **`docs/CHANGELOG.md`**.

| Datum | Feature |
|---|---|
| 2026-08-28 | **Priorisierte Fragebogen-Liste in der Review-Queue** (Modul `fragebogen_signale`, Klasse `fragebogen` + Migration 71/72, Akten-Matching aus Bogenfeldern statt Regex, RA-MICRO-Kandidatensuche über `varM-KZ`/`varG-KZ`/`varU-TAG`/Nachname, Vier-Zustands-Ampel inkl. „abgelegt“, Queue-Endpunkt, ⭐-Sektion im Frontend, Aktenanlage aus Bogendaten, Erstkontakt-Doppelweg stillgelegt) — Branch `fragebogen-favoritenliste`, Protokoll → CHANGELOG. Abnahme im Betrieb offen, siehe „In Arbeit“ |
| 2026-08-12 | **Sachbearbeiter-Verwaltung in den Einstellungen** (Migration 68, Tabelle `sachbearbeiter` mit 11 Startzeilen ersetzt vier hartcodierte Listen; CRUD-Reiter + RA-MICRO-Abgleich; Tagesübersicht-Chips mit Klarnamen-Tooltips) — Spec `docs/superpowers/specs/2026-08-12-sachbearbeiter-verwaltung-design.md`, Plan `docs/superpowers/plans/2026-08-12-sachbearbeiter-verwaltung.md`, Protokoll → CHANGELOG. Browser-Sichtprüfung offen, siehe „In Arbeit" |
| 2026-08-11 | **Großer Merge nach `main` + Push** (`40c9143e..cf7dd74d`, FF): kompletter Stapel `intake-review-sichtbarkeit` + `abschlussbericht` — SSOT-Dokumentenklassen (22), Intake-Review-Sichtbarkeit, Abschluss-/Sachstandsbericht, Referenzwerkstatt+Entfernungsprüfung, Übersicht-Redesign A+B, Forderungsschreiben-Fixes (C-1, I-1–I-9), STA-Sofort-Fixes, E-Mail-Hotfixes, Testsanierungen (modul6/7 + Vollsuite). Entscheidung RA Schatz: Abnahmen produktiv statt vorab |
| 2026-08-11 | **Backend-Vollsuite-Testsanierung: 123 → 0 Failures** (1735/1735 grün): modul1–4 + Nachbarn auf heutige API portiert; 3 echte Befunde gefixt (Frisch-DB-FK `unfallakte(id)`→`az` in Migration 3, `todos` ON DELETE CASCADE, „Rechnung (Auffang)" raus aus der Dokumentbezeichnung via `bezeichnung_label`); 2 Isolationsprobleme (sv_portal-Fixture ohne eigenes DB_PATH, akten_matching gegen echtes RA-MICRO). Protokoll → CHANGELOG |
| 2026-08-11 | **Sachstandsanfrage: Review + Sofort-Fixes** (M-1 AZ-Format Dialog-Einstiege, M-2 Genus/Kasus `{SchreibenDativ}`, G-1 PII-Log, G-2 Fristanzeige, G-3, G-7 Stufenlogik-Tests) — Befund-Katalog `handover/2026-08-11-sachstandsanfrage-review-befunde.md`; Kernbefunde K-1–K-3 → Backlog PRD-25d |
| 2026-08-11 | **Forderungsschreiben: Review-Fixes** C-1 (berechne_positionen = SSOT Brief+Historie, Restwert negativ) + I-1–I-9 + Aufräumen — `bugfixes.md`; offen nur I-10 (Entscheidung RA Schatz) |
| 2026-08-10 | **Übersicht-Redesign A+B** (Summen-SSOT aus Ereignismodell, 3 Akkordeons, Onboarding-Fächer, Aktions-Pills) + Playwright-Abnahme 19/19 an echten Akten |
| 2026-08-07 | **Abschluss-/Sachstandsbericht** (Migration 67, `abschluss_uebersicht.py`, DOCX, Kurationsdialog; Gebühren-Streitwert-Folgefund gefixt) — DOCX-Sichtprüfung → Produktiv-Nachtests |
| 2026-08-04 | **Intake-Review-Sichtbarkeit** (`GET /akten/<az>/intake-pending`, `IntakePendingListe`, ReviewQueue-Direktsprung) + **Dokumentenklassen-SSOT** (22 Klassen, Registry-YAML + `tools/gen_dokumentenklassen.py`) + Scheduler-Fix Dev |
| 2026-08-10 | **Übersicht-Review-Fixes** (`f6fd2f3d`, Branch `abschlussbericht`): 7 Befunde behoben — Crash RegulierungsTabelle (effRep/ist130), OnboardingHub-Phantomfelder + Auto-Ausblenden bei vollständiger Checkliste, „+ Todo"-Formular im Header, Chronik-Sortierung (ISO-sortKey), §3a-Fristtyp-Pill, RSV-Doppelanzeige, ~10,5 kB toter Code raus; TDD 11 neue Tests, Vollsuite 476/476. Befund-Katalog: `handover/2026-08-10-uebersicht-review-befunde.md` · offen: B3/Redesign → Backlog „Mittel" |
| 2026-08-07 | **Firmen-Beteiligte-Fix** (`6801be75`): RA-MICRO-Name immer aus `sNachname`, `sErsteAdresszeile` nur Anredeform — „Firma"-Geistereintrag statt „RCR GmbH" in 1280/25 behoben, 7 Fundstellen + Anrede-Code 4, 5 Tests, live verifiziert |
| 2026-08-07 | **Referenzwerkstatt-Extraktion (VHV-Blockformat) + Entfernungsprüfung ReviewQueue (Button+Popup+Persistierung) + Intake-Restbefunde a/c** (Marker-Wortgrenzen, Datums-Scheinkonflikt) + **RA-MICRO-read-only-Fallback Mandanten-Adresse** — Branch `abschlussbericht`, an Dok 516/517 + Akte 1280/25 E2E-verifiziert; Browser-Abnahme offen, siehe „In Arbeit" |
| 2026-08-06 | **E-Mail-Import Endlos-Poll-Loop gefixt** (`34342daa`: On-demand-Aktenanlage repariert + FK-Guard) und **Dubletten bereinigt** (Freigabe RA Schatz): `dokumente` 53.216→789 Zeilen, 106.266 Dateien / ~222 GB aus `/app/uploads` entfernt, VACUUM 50→4 MB. Backup: `/app/data/unfallakten.db.bak_pre_dubletten_cleanup_20260806_155109`. Außerdem `8e9b50ea`: Prüfbericht-Schema (fiktive/konkrete Erstattung) + Validierungsregeln aktiv (ReviewQueue-Warnung bei Positionssummen-Abweichung, Akte 1280/25) |
| 2026-08-03 | **Aktenanlage + Dashboard-Hell in `main` gemergt (FF) + gepusht** (`81e33206`); OMA-Live-Abnahme: Prefill-Fix (stale auftraggeber + Anrede-Normalisierung), Migration-66-Reloader-Reparatur, OMA-Pfad→`Z:\RA\M-Plattform`, Dateiname-Präfix `Oma_`, XML strukturgleich zum echten Export; Prod-Compose `oma-share` nachgezogen |
| 2026-07-24 | Klage-Wizard-Verbesserungsrunde Pakete 1–4 komplett (Entwurf speichern, UI-Führung, Gesamtvorschau, Standardtexte V11 Stufe 1) — in `main`, gepusht |
| 2026-07-30 | Dashboard-Hell-Umbau: Tagesübersicht hell (Pergament-Tokens), Jetzt-dran-Leiste, Fristen zuerst (3:2), Posteingang-Kachel entfernt, Zustände je Kachel, Tastatur, SB-Filter-Persistenz — Branch `dashboard-hell`, Browser-Abnahme offen, siehe „In Arbeit" |
| 2026-07-30 | Aktenanlage aus der ReviewQueue (PRD-NEW): Migration 66, OMA-XML-Generator, RA-MICRO-Erkennung read-only, `/aktenanlage`-Blueprint, Freigabe-Hook, `AktenanlageDialog` (ersetzt `NeueAkteModal`), ReviewQueue-Banner/Chip/Leiste, OMA-Export-Ordner in Compose/.env — Abnahme am echten System offen, siehe „In Arbeit" |
| 2026-07-29 | UI-Kleinkram-Runde (6 Punkte, gemeldet 2026-07-23): Systemstatus-Kachel-Bug war Caching-Problem (Nutzer bestätigt behoben); Navigationsleiste Icon-Ausrichtung + Hover-Effekt verstärkt; E-Mail-Identifier Versicherer/Gutachter zu einem Reiter mit Subreitern zusammengeführt (Muster Personenschaden/Sachschaden); Bestandsaufnahme Gutachter-Identifier (2: Ninnivaggi, Cassese); GLM-OCR-Karte im KI-Assistent-Reiter (Modellauswahl + Verbindungstest, analog Lokales-LLM-Switcher) |
| 2026-07-28 | Review-Queue: Sortier-Toggle Eingangsdatum (auf/ab, localStorage-Persistenz) — in `main`, Browser-Nachtest 11/11 bestanden |
| 2026-07-23 | Kürzungstaxonomie **Phase 1 komplett** (12 Tasks: Mig 64, YAML-Registry A–F, Matching+LLM, Verkettung, Typ-UI, Runden-Vergleich, TextbausteinEditor, ZITAT, Messanker) — Branch `kuerzungstaxonomie-phase1` |
| 2026-07-23 | Kürzungstaxonomie-Konzept verifiziert + Prozess revidiert (Papier Abschnitt 12, 3 DECISIONS-Einträge); Klage-Wizard-Fix [FEHLT]-Marker; Browser-Nachtests Paket 2+3 bestanden; main gepusht (58 Commits) |
| 2026-07-21 | Klage-Wizard Paket 3: Gesamtvorschau (Server-Text-Vorschau + Inline-Edit, Single-Source; lokal main, Browser-E2E offen) |
| 2026-07-21 | Globaler Firmen-Vertreter-Speicher (Tabelle `firmen_vertreter`, aktenübergreifende Vertreter-Zuordnung) |
| 2026-07-20 | Klage-Wizard Paket 2: UI-Führung (umgesetzt, noch nicht gemergt) |
| 2026-07-19 | Klage-Wizard Paket 1: Entwurf speichern (in main) |
| 2026-07-19 | PRD-33 Klage-Wizard Feintuning KOMPLETT (40 Bugs KW-01–40, S1–6) |
| 2026-07-16 | Rausch-Absender auto-aussortieren + Papierkorb |
| 2026-07-16 | Bugfix AZ-Normalisierung + Personenschaden-Schema-Drift (Mig 60) |
| 2026-07-15 | PRD-37 Dokumentenbezeichnung (Mig 59); PDF-Splitting Review (Mig 58); Prod-Rollout Git-Teil |
| 2026-07-14 | Fragebogen-Feld-Übernahme; N-03 Retry-Differenzierung (Mig 57); N-04 Seiten-Triage |
| 2026-07-13 | Bugfix-Reihe BUG-01–30 (Intake v7); N-01/N-02 (Mig 56)/N-06; N-09/N-10; Druckbutton |
| 2026-07-12 | P1.5e Review-Freigabe schreibt Ereignisse für alle Klassen |
| 2026-07-10 | P1.7 UI-Positionsmodell; Text-Pfad Intake (Mig 54); N-08 (Mig 55)/N-07 |
| 2026-07-09 | Intake-Refactoring S1.9 + Positionsmodell P1.1–P1.6 (Mig 49/51/52) |
| 2026-07-08 | Bugfixing-Session (Testsuite-Sanierung, Mig 50 unfalldetails) |
| bis 2026-07 | Ältere PRDs (PRD-01…PRD-36, US01/02/05/06, B-08/09 …) — Index in CHANGELOG.md |
