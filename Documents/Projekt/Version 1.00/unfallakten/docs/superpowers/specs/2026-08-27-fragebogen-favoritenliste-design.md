# Priorisierte Fragebogen-Liste in der Review-Queue — Design

Stand: 2026-08-27 · Brainstorming mit RA Schatz · Branch-Vorschlag `fragebogen-favoritenliste`

## Problem

Unfallfragebögen von der Kanzlei-Website kommen als standardisierte E-Mail mit
JSON-Anhang herein und landen in der Review-Queue — dort aber als Klasse
`sonstiges`, optisch ununterscheidbar von Spam und Rundschreiben. Sie gehen
unter.

Bestandsaufnahme in der Produktivdatenbank am 2026-08-27:

| Intake | Betreff | AZ im Bogen | Bester Treffer heute |
|---|---|---|---|
| 474 | Tim Englert – 2026-07-02 | – | 675/26 (Kennzeichen, 0,7) |
| 475 | Mack Gideon – 2026-07-22 | – | keiner |
| 476 | Perisa Petrovic (Az. 641/26) | 641/26 | 641/26 (1,0) |
| 527 | Paul Golovin – 2026-08-03 | – | keiner |
| 613 | Sandra Hartmann – 2026-07-31 | – | keiner |
| 672 | Bernd Rügner – 2026-08-06 | – | keiner |
| 727 | Bernharda Darowski – 2026-04-09 | – | keiner |
| 834 | Ingelor Reinhard – 2026-07-30 | – | keiner |

Acht Bögen lagen unbearbeitet seit dem 4. bis 15. August. Nachprüfung gegen
RA-MICRO ergab: **alle acht gehören zu bestehenden Akten**, kein einziges
Neumandat. Sechs davon wurden über die Mandantenadresse aus dem Bogen
eindeutig gefunden (742/26, 760/26, 768/26, 710/26, 751/26, 749/26).

## Bestand — was es schon gibt

- **Erkennung:** `import_service._ist_fragebogen_email` (Betreffmuster
  `Unfallbogen: …` oder Anhang `unfallbogen_*.json`) und
  `email_import/fragebogen_parser.parse_fragebogen_anhang` (prüft
  `meta.formular == "unfallbogen"`, Schema 2.0/2.1).
- **Ablage:** `import_service._fragebogen_in_intake_queue` legt den Bogen
  verlustfrei als Text-Intake-Dokument ab, Signal `dokument_art: "fragebogen"`,
  bei angegebenem Aktenzeichen zusätzlich `az`.
- **Feld-Übernahme bei der Freigabe:** `services/fragebogen_uebernahme.py` +
  `FragebogenUebernahme` in `ReviewQueueView.jsx:904` — vollständig gebaut,
  bleibt unverändert.
- **Aktenanlage aus der Queue:** `AktenanlageDialog` + OMA-XML-Export, live
  abgenommen 2026-08-03.
- **Akten-Matching:** `intake/akten_matching.finde_kandidaten` mit Aktenzeichen,
  Kennzeichen, E-Mail, Name+Datum, Name; RA-MICRO-Brücke über
  `ramicro/email_matching.suche_akte_in_ramicro`.
- **Schadentag-Suche gegen RA-MICRO:** `routers/aktensuche_routes.py:116` fragt
  `varU-TAG` bereits ab, samt ISO→`TT.MM.JJ`-Konverter.

## Befunde — warum die Bestandsprüfung heute versagt

1. **Falsche E-Mail-Adresse.** `akten_matching.py:339` übergibt `mails[0]`, also
   den Mail-Absender. Bei einer Formularmail ist das `unfall@anwalt-offenbach.de`
   — das eigene Postfach. Die Mandantenadresse steht in `mandant.email` und wird
   nie benutzt. Ursache aller sechs Fehlschläge.
2. **Kennzeichen-Regex verfehlt reale Eingaben.** `akten_matching.py:48`
   verlangt `OF-BR 1612`. Tatsächlich eingetippt wurde: `WÜ PG 777`, `OF A-418`,
   `OFGM891`, `OF CJ 828`, `k.A. Fußgänger`, `siehe Akte`. Von sechs Bögen war
   einer im erwarteten Format. Bei einem strukturierten Feld ist Regex-Extraktion
   ohnehin der falsche Weg.
3. **Kennzeichen ohne Rollentrennung.** `_suche_kfz_in_sqlite`
   (`akten_matching.py:155`) sucht in `beteiligte.kfz_kennzeichen` ohne
   `rolle`-Filter — ein Gegner-Kennzeichen kann eine fremde Mandantenakte
   treffen.
4. **Unfalltag wird nie geprüft.** Der Bogen liefert ISO (`2026-03-28`), das
   Muster `akten_matching.py:52` erwartet `28.03.2026`. Der Kombi-Match
   „Name + Unfalltag" fällt bei jedem Bogen still aus.
5. **Die Queue-Liste kennt keine Fragebögen.** `GET /intake/queue`
   (`intake_routes.py:134`) liest aus `signale_json` nur `absender_kategorie`,
   nicht `dokument_art`. Erst `hole_detail` liefert `ist_fragebogen`.
6. **Aktenanlage-Vorschlag greift nicht.** `zeigeAktenanlageVorschlag`
   (`ReviewQueueView.jsx:77`) feuert nur bei Gutachten von Gutachtern.
7. **Doppelweg.** `_fragebogen_neuer_mandant_stub` (`import_service.py:1095`)
   ist die einzige Fragebogen-Funktion **ohne** `review_pflicht_aktiv()`-Guard.
   Bögen ohne Aktenzeichen werden zusätzlich nach `fragebogen_erstkontakt`
   geschrieben und erscheinen als Karte im `unfall@`-Reiter. Die Tabelle ist
   leer (0 Zeilen); elf von zwölf Versuchen scheiterten historisch mit
   `no such table` (Migration 30 fehlte auf dieser Datenbank).

## RA-MICRO — verfügbare Merkmale (nur lesend geprüft)

WDM-Variablen in `_tbl0WDMDaten` (Schlüssel-Wert je `AktenNr`):

- `varU-TAG` — Unfalltag, Format `TT.MM.JJ`
- `varM-KZ` — Kennzeichen des Mandanten
- `varG-KZ` — Kennzeichen des Gegners
- `varU-ORT` — Unfallort

Abgleich an den Fällen:

| Akte | `varM-KZ` | Bogen-Kennzeichen | `varU-TAG` | Bogen-Unfalltag |
|---|---|---|---|---|
| 742/26 Golovin | `WÜ PG 777` | `WÜ PG 777` | 03.08.26 | 2026-08-03 |
| 710/26 Gideon | `OF-GM 891` | `OFGM891` | 22.07.26 | 2026-07-22 |
| 768/26 Reinhard | *(leer)* | *(Fußgängerin)* | 30.07.26 | 2026-07-30 |
| 675/26 | `MZ AF 65` | — | 02.07.26 | 2026-07-02 |
| 751/26, 760/26, 749/26 | *(leer)* | | *(leer)* | |

Die Merkmale ergänzen sich: Mandantenadresse traf 6 von 6, `varM-KZ` ist bei 3
von 7 gepflegt, `varU-TAG` bei 4 von 7. Wo WDM leer ist, rettet die Adresse den
Treffer.

`tblAkten` liefert zusätzlich `sAktenKurzBezeichnung` („Hartmann/Guthier"),
`sAktenSachbearbeiter`, `dtAnlage` und `dtAblage`. Der bestehende Ablage-Filter
(`email_matching.py:209`, `dtAblage IS NULL OR = '1899-12-30'`) löst den
Zweifelsfall 613 von allein: von den zwei Hartmann-Akten ist 848/25 seit dem
15.12.2025 abgelegt, es bleibt 751/26.

## Getroffene Entscheidungen (RA Schatz, 2026-08-27)

1. **Die Review-Queue wird der einzige Arbeitsort** für Fragebögen. Der
   Erstkontakt-Weg wird stillgelegt.
2. **Darstellung: angepinnte Sektion** „⭐ Unfallfragebögen (n)" oben in der
   Queue-Liste, darunter unverändert die übrige Queue. Kein eigener Reiter,
   keine Doppelanzeige.
3. **Bestandsprüfung vor Aktenanlage.** Ein fehlendes Aktenzeichen bedeutet
   nicht automatisch Neumandat — der Mandant kann es schlicht vergessen haben.
   Geprüft wird gegen E-Mail-Adresse, Kennzeichen und Unfalltag.
4. **Drei Zustände statt zwei:** grün (Bestandsakte), gelb (prüfen), blau
   (neue Akte). Der Anlage-Knopf erscheint nur bei Blau.
5. **Eigene Dokumentenklasse `fragebogen`** in der Registry.
6. **Aktenanlage über den bestehenden Weg** (`AktenanlageDialog`, OMA-XML im
   Übergabeordner `Z:\RA\M-Plattform`), jetzt aus den Bogendaten vorbefüllt.

## Leitplanken

- **RA-MICRO ist read-only.** Gelesen werden `tblAkten`, `tblAdressen`,
  `tblAktenBeteiligte`, `_tbl0WDMDaten`. Geschrieben wird ausschließlich in die
  SQLite-Datenbank des Unfallakten-Systems.
- **Die menschliche Freigabe bleibt der einzige Schreibweg in die Akte**
  (`INTAKE_REVIEW_PFLICHT`). Keine automatische Zuordnung, keine automatische
  Freigabe.
- Testgetrieben, Deutsch, keine unnötigen Abstraktionen.

## Architektur

### 1. Signalbildung — neues Modul `backend/intake/fragebogen_signale.py`

Reine Lesefunktion ohne Datenbankzugriff, aus dem Bogen-JSON:

| Quelle im Bogen | Signal | Behandlung |
|---|---|---|
| `meta.aktenzeichen` | `az` | wie bisher |
| `mandant.email` | `mandant_email` | kleingeschrieben, getrimmt |
| `sachschaden.eigenes_fahrzeug.kennzeichen` | `kfz_mandant` | normalisiert + Plausibilitätsprüfung |
| `gegner.fahrzeug.kennzeichen` | `kfz_gegner` | normalisiert + Plausibilitätsprüfung |
| `mandant.name` | `nachname` | getrimmt |
| `unfall.datum` | `unfalltag` | ISO, unverändert |

**Kennzeichen-Normalisierung:** alle Zeichen außer `A-ZÄÖÜ0-9` entfernen,
großschreiben. Danach Plausibilitätsprüfung gegen
`^[A-ZÄÖÜ]{1,3}[A-Z]{1,2}\d{1,4}$`. Ergebnis an den echten Eingaben:

| Eingabe | Normalisiert | Gültig |
|---|---|---|
| `WÜ PG 777` | `WÜPG777` | ja |
| `OF A-418` | `OFA418` | ja |
| `OFGM891` | `OFGM891` | ja |
| `OF CJ 828` | `OFCJ828` | ja |
| `OF-BR 1612` | `OFBR1612` | ja |
| `k.A. Fußgänger` | `KAFUSSGÄNGER` | nein |
| `siehe Akte` | `SIEHEAKTE` | nein |

**Wo die Signale entstehen.** Nicht beim Einliefern, sondern **in der
Pipeline**, bei jedem Lauf neu aus dem gespeicherten Bogen-JSON. Für
Text-Dokumente hält die Pipeline den Payload ohnehin als `text_gesamt`
(`pipeline.py:171`); ein Fragebogen ist daran zweifelsfrei erkennbar, weil
`parse_fragebogen_anhang` gegen das Schema prüft. Die abgeleiteten Signale
werden der Liste aus `_lade_zustellungs_signale` hinzugefügt, bevor
`klassifiziere_stufe1` und `finde_kandidaten` sie sehen.

Das hat drei Vorteile gegenüber dem Schreiben in `signale_json`: die Ableitung
ist idempotent, es gibt nur eine Wahrheitsquelle (den Payload), und die acht
Altfälle heilen allein über den bereits vorhandenen Knopf
`POST /intake/dokument/<id>/reparse` — ohne Einmal-Skript und ohne Datenmigration.

Die Sammelfunktionen `_sammle_signale_mails` und `_sammle_signale_kfz`
(`akten_matching.py:84` und `:97`) müssen die neuen Schlüssel mitlesen; die
bisherigen Schlüssel (`absender`, `absender_email`, `kfz`, `kfz_kennzeichen`)
bleiben unangetastet, damit andere Dokumentarten unverändert laufen.

### 2. Suche — Erweiterungen in `akten_matching.py` und `ramicro/email_matching.py`

Neue beziehungsweise korrigierte Wege:

- **Mandantenadresse** statt Mail-Absender in die E-Mail-Suche (SQLite
  `beteiligte.email` und RA-MICRO `tblAdressen.sEMail`).
- **Kennzeichen rollenrichtig:** eigenes Kennzeichen gegen `varM-KZ`,
  Gegner-Kennzeichen gegen `varG-KZ`; in SQLite entsprechend mit `rolle`-Filter.
- **Unfalltag** gegen `varU-TAG` (Konverter aus `aktensuche_routes.py`
  wiederverwenden) und lokal gegen `unfallakte.unfalldatum`.
- **Nachname** gegen `tblAdressen.sNachname` als schwächstes Kriterium.

Der Ablage-Filter bleibt in allen Wegen erhalten.

**Gewichtung:**

| Merkmal | Score |
|---|---|
| Aktenzeichen | 1,0 |
| Mandanten-E-Mail | 0,8 |
| Eigenes Kennzeichen (`varM-KZ`) | 0,8 |
| Unfalltag **und** Nachname | 0,7 |
| Unfalltag allein | 0,5 |
| Gegner-Kennzeichen (`varG-KZ`) | 0,5 |
| Nachname allein | 0,4 |

Für Nicht-Fragebögen bleibt die bisherige Regex-Extraktion aus dem Volltext
unverändert.

### 3. Ampel

| Zustand | Bedingung | Anzeige |
|---|---|---|
| 🟢 grün | genau ein laufender Kandidat mit Score ≥ 0,7 | `→ 751/26 · Hartmann/Guthier` |
| 🟡 prüfen | mehrere laufende Kandidaten **oder** bester Score < 0,7 | `PRÜFEN · n Kandidaten` |
| 🔵 neue Akte | kein Kandidat | `NEUE AKTE` + Knopf „Akte anlegen" |

Jeder Eintrag nennt die Trefferbegründung im Klartext: „Mandanten-E-Mail",
„eigenes Kennzeichen", „Unfalltag + Name".

### 4. Dokumentenklasse `fragebogen`

Neue Registry-Datei `backend/registry/klassen/fragebogen.yaml`, leere
Markerliste, `bezeichnung_label: "Unfallfragebogen"`; danach
`py tools/gen_dokumentenklassen.py` auf dem Host.

Die Klasse wird **nicht** über den Textklassifikator gesetzt — ein Signal allein
erreicht nur `SIGNAL_KONFIDENZ = 0.55` (`klassifikator.py:29`) und bliebe unter
der Schwelle. Ein Fragebogen ist aber schema-validiert und damit keine
Vermutung. Die Pipeline stempelt die Klasse deshalb selbst, sobald sie den
Payload als Bogen erkennt, mit `klasse_quelle='fragebogen'` und Konfidenz 1,0.
Der Zweig für bindende Klassen (`pipeline.py:218`, bisher nur `manuell`) wird
um diesen Wert erweitert, damit ein manuell gesetzter Wert weiterhin Vorrang
behält und die Fragebogen-Klasse nicht vom Auto-Vorschlag überschrieben wird.

Ereignistyp-Zuordnung für die Freigabe über
`positionsmodell_registry.klasse_ereignistyp` ergänzen.

### 5. Queue-Endpunkt

`GET /intake/queue` liefert je Eintrag zusätzlich:

- `ist_fragebogen: bool`
- `bogen_kopf: {mandant_name, kennzeichen, unfalltag}`
- `zuordnung: {ampel, akte_az, kurzbezeichnung, begruendung, kandidaten_anzahl}`

Die Werte stammen aus `parse_json` und `signale_json`; die Abfrage liest sie nur
zusätzlich aus. Kein zweiter Endpunkt, kein Nachladen je Zeile.

### 6. Frontend `ReviewQueueView.jsx`

- Zwei Blöcke in der Liste: „⭐ Unfallfragebögen (n)" mit abgesetztem
  Hintergrund, darunter „Übrige Dokumente". Ein Fragebogen erscheint nur oben.
- Ist die Sektion leer, entfällt sie ganz — die gewohnte Ansicht bleibt
  unverändert.
- Sortierung innerhalb der Sektion nach Eingang; der bestehende
  Sortier-Umschalter wirkt auf beide Blöcke.
- Zeile: `📝 Fragebogen` · Ampel-Chip · Mandantenname · Kennzeichen ·
  Unfalltag · Trefferbegründung. Bei Blau zusätzlich „Akte anlegen".
- Bei Gelb zeigt das Detailpanel alle Kandidaten mit Aktenzeichen,
  Kurzbezeichnung, Sachbearbeiter und Anlagedatum zur Auswahl.
- Klick auf die Zeile öffnet das Detail; der Freigabeprozess mit der
  bestehenden Feld-Übernahme läuft unverändert weiter. Nach der Freigabe
  verschwindet der Eintrag aus der Sektion.
- `zeigeAktenanlageVorschlag` wird um den Fragebogen-Fall erweitert; der
  `AktenanlageDialog` wird aus den Bogendaten vorbefüllt (Name, Anschrift,
  Telefon, E-Mail, Kennzeichen, Unfalltag).

### 7. Stilllegung des Doppelwegs

- `_fragebogen_neuer_mandant_stub` (`import_service.py:1095`) erhält den
  fehlenden `review_pflicht_aktiv()`-Guard.
- Entfernt: `FragebogenErstkontaktKarte` und ihre Einbindung in
  `UnfallEmailView.jsx`, die API-Helfer `fragebogenErstkontakt` und
  `fragebogenErstkontaktStatus` (`api.js:432`), die zugehörigen Routen in
  `email_routes.py:949` und `:977`, sowie der Zähler `fragebogen_neu` in
  `dashboard_routes.py:133` (`gesamt` besteht danach nur noch aus
  `emails_nicht_zugeordnet`).
- Die Tabelle `fragebogen_erstkontakt` bleibt bestehen: leer, ohne Wirkung,
  eine Migration nur zum Löschen wäre unnötiges Risiko.

## Tests (TDD, vorab)

- **Signalbildung:** die sechs echten Kennzeichen-Schreibweisen ergeben den
  richtigen Schlüssel; `k.A. Fußgänger` und `siehe Akte` werden verworfen;
  fehlende Felder führen nicht zu leeren Signalen.
- **Ampel:** je Kandidatenlage der richtige Zustand, inklusive „mehrere
  laufende Kandidaten → gelb" und „abgelegte Akte zählt nicht".
- **Queue-Endpunkt:** liefert `ist_fragebogen`, `bogen_kopf`, `zuordnung`.
- **Frontend:** Sektion erscheint und verschwindet; Chips je Zustand;
  Anlage-Knopf nur bei Blau; Fragebogen nicht doppelt gelistet.
- **Regression:** Nicht-Fragebögen laufen unverändert über die
  Regex-Extraktion; die bestehende Feld-Übernahme bleibt unberührt.
- **Reparse:** heilt einen Altbogen (Klasse bleibt erhalten, Signale werden neu
  gebildet, Kandidat erscheint).
- RA-MICRO-Zugriffe in Tests gemockt (`_RAMICRO_VERFUEGBAR=False` beachten).

## Abnahme

Nach der Umsetzung an den acht liegenden Bögen im Betrieb: Reparse auslösen,
danach muss die Sektion acht Einträge zeigen, davon 476 → 641/26 (Aktenzeichen)
und die sechs geprüften Fälle grün auf 742/26, 760/26, 768/26, 710/26, 751/26,
749/26. Fall 474 muss weiterhin 675/26 zeigen (trifft schon heute über das
Kennzeichen).

## Nicht Teil dieses Vorhabens

- Automatische Zuordnung oder Freigabe.
- Dashboard-Kachel oder Benachrichtigung bei neuem Fragebogen.
- Änderungen an `fragebogen_uebernahme.py`.
- Löschen der Tabelle `fragebogen_erstkontakt`.
- Priorisierung anderer Dokumentarten (Fristen, Klagedrohungen) in derselben
  Sektion.
