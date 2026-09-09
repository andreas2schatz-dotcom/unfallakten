# Warum landen so viele Dokumente in `sonstiges`? — Befunde

Stand: 2026-09-09 · Auftrag: `handover/naechste_session_sonstiges_klassifikation_prompt.md`

## Kurzfassung

Die Ausgangszahl war falsch, und es gibt **nicht eine** Ursache, sondern drei — mit
klarem Schwerpunkt bei **fehlenden Klassen**, nicht bei einem kaputten Klassifikator.
Der Klassifikator liegt in den nachgesehenen Fällen richtig: die Dokumente sind
tatsächlich keine der 23 Klassen.

---

## Befund 0 — die Ausgangszahl zählte den Papierkorb mit

Der Papierkorb ist **nicht** über `queue_status` abgebildet, sondern über
`verworfen_grund`: ein aussortiertes Dokument behält `queue_status='bereit_zur_review'`
und bekommt zusätzlich einen Grund. Die Auswertung vom 2026-09-08 filterte nur auf
`queue_status` und zählte damit 1.590 bereits weggeräumte Dokumente mit.

| Kennzahl | Handover 2026-09-08 | tatsächlich |
|---|---|---|
| Dokumente in der Queue | 1.915 | **345** |
| davon `sonstiges` | 1.647 (86 %) | **271 (79 %)** |
| davon aus `placetel.de` | 629 | **8** |

Der Anteil bleibt hoch, die Menge ist ein Zehntel der angenommenen. Für künftige
Auswertungen gilt: `WHERE queue_status='bereit_zur_review' AND verworfen_grund IS NULL`.

## Befund 1 — die Placetel-Regel arbeitete bereits richtig

627 Anrufbenachrichtigungen waren automatisch aussortiert, keine einzige stand in der
Queue. Was übrig blieb, waren die **Anhänge — der Faxeingang der Kanzlei**: darunter ein
Gutachten (1510), ein Fragebogen (1721) und zwei Rechnungen (1761, 2329). `nur_body` war
Absicht und richtig.

**Entscheidung RA Schatz 2026-09-09:** Faxe bleiben, die Bodies werden künftig gar nicht
mehr gespeichert (Policy `nur_anhaenge`, siehe DECISIONS + CHANGELOG).

## Befund 2 — die 271 `sonstiges` im Überblick

Rund gerechnet (Dokument × Zustellung, deshalb Randunschärfe von ~5 %):

### Anhänge — 117 echte Dokumente ohne passende Klasse

| Anzahl | Was es ist |
|---|---|
| **38** | **Lichtbilder / Unfallfotos** (`IMG_0195.jpeg`, `IMG-20260830-WA0001.jpg`) |
| **31** | allgemeine Versicherer-Briefe (`Anschreiben.pdf`, `Geschäftsbrief.pdf`, `Reproduktion.pdf`, `LVMBRIEF_*.pdf`) |
| 32 | nicht über den Dateinamen zuzuordnen (`Anforderung_Kfz-Versicherung_*.pdf`, `DE_PaymentLetter.PDF`, `072305.pdf`) |
| 5 | generische Schadendokumente (`Schadendokument_2026*.pdf`) |
| 4 | Faxe der Telefonanlage |
| 2 / 2 / 2 / 1 | Bewerbungen · Deckungszusagen RSV · Vollmachten · Ausweis/Führerschein |

Alle haben Text (63× OCR, 54× Textebene) — es fehlt also nicht die Texterkennung,
sondern die Klasse.

### Bodies — rund 154

| Anzahl | Was es ist |
|---|---|
| **21** | **Begleitmails ohne eigenen Inhalt** („Bitte beachten Sie den Anhang") von DEVK, Dialog, Generali, Barmenia, LVM, Haftpflichtkasse |
| 24 | von der **eigenen Kanzleidomain** — davon 5 Unfallbögen, 5 Terminanfragen, 1 Kontaktanfrage, 8 `WG:`-Weiterleitungen echter Mandantenpost, 3 Test-/Monitoring-Mails |
| 11 | Werbung und Dienstleister-Automatik (Seminare, Druckerzählerstände, Buchhandlung) |
| ~98 | echte Korrespondenz: Gegner, Zeugen, Dolmetscher, Polizei, Mandanten |

**Wichtig:** Die eigene Kanzleidomain ist **kein** Rauschen. Dort laufen die
Unfallbögen des Webformulars und die Weiterleitungen der Mitarbeiter ein. Eine
Domain-Sperre auf `anwalt-offenbach.de` würde echten Posteingang zerstören.

## Befund 3 — kein Klassifikationsfehler im engeren Sinn

Ursache 3 aus dem Auftrag („träfe eine Klasse, wird aber falsch einsortiert") ließ sich
in der Stichprobe von 30 Dokumenten **nicht** belegen. Die hohe Konfidenz ist kein
Widerspruch: `sonstiges` ist die Auffangklasse ohne Marker, sie „gewinnt" nicht gegen
eine andere Klasse, sondern bleibt übrig.

---

## Empfehlungen, nach Hebelwirkung

| # | Maßnahme | wirkt auf | Aufwand |
|---|---|---|---|
| 1 | **Klasse `lichtbild`** — an Dateiendung/MIME erkannt, kein Parser nötig, Datum = Zustelldatum | ~38 | klein |
| 2 | **Begleitmail-Unterdrückung** — Body ohne eigenen Inhalt + vorhandener Anhang → Body verwerfen. Muss eine **Inhaltsregel** sein, keine Domainregel: die Absender sind Versicherer, von denen echte Post kommt | ~21 | mittel |
| 3 | **Klasse für allgemeine Versicherungskorrespondenz** mit Datumsfeld | ~31 | mittel |
| 4 | Terminanfragen des eigenen Buchungssystems aus der Queue nehmen (haben einen eigenen Reiter) | ~5 | klein |
| 5 | Test-/Monitoring-Mails der eigenen Domain nicht in die Queue | ~3 | klein |
| 6 | Reparse der 5 Unfallbögen (474, 475, 476, 727, 834) — bereits als eigener TODO-Punkt geführt | 5 | erledigt sich |

Zusammen decken 1–6 rund **100 der 271** ab. Der Rest ist echte, vielgestaltige
Korrespondenz — dafür ist `sonstiges` die richtige Antwort, und der Aufwand einer
eigenen Klasse lohnt nicht.

## Offene Fragen an RA Schatz

1. **Lichtbilder:** eigene Klasse, oder sollen Unfallfotos weiter von Hand einsortiert
   werden?
2. **Allgemeine Versicherungskorrespondenz:** eigene Klasse mit Datum, oder bewusst
   Handarbeit?
3. **Bewerbungen** (2 Stück, `Lebenslauf.pdf`, `Bewerbung Dossier.pdf`): gehören die
   überhaupt in dieses System, oder sollen sie an `info@` verbleiben?
4. **Papierkorb-Altbestand:** 628 Placetel-Bodies liegen weiter im Papierkorb. Löschen?

## Fallen, die beim Nacharbeiten gelten

- **Papierkorb-Filter nicht vergessen** (siehe Befund 0) — sonst misst man wieder falsch.
- **`zustellungen.absender` ist der rohe From-Header** (`"Name" <mail@domain>`); Domains
  nur über einen echten Parse ziehen, sonst entstehen Werte wie `kravag.de" <schaden@…>`.
- **Der Text von Datei-Dokumenten steht nicht in `structured_payload`** — diese Spalte
  ist nur für `payload_typ='text'` gefüllt. Bei Anhängen sagt `textquelle`
  (`ocr`/`textebene`), dass Text da war; er wird nur nicht in der Zeile aufbewahrt.
  Aus einer leeren Spalte auf fehlende Texterkennung zu schließen wäre falsch.
- **Aktive Entwicklungsdatenbank liegt im Docker-Volume**, nicht unter `backend/data/`.
