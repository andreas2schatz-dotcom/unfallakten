# Nächste Session: Warum sind 86 % der Review-Queue „sonstiges"?

Stand: 2026-09-08 · Aufgenommen am Rande der Belegketten-Arbeit, bewusst nicht dort mitbehandelt.

## Auftrag

In der Review-Queue liegen 1.915 Dokumente, davon 1.647 in der Auffangklasse `sonstiges`
— 86 %. Finde heraus, warum, und schlag RA Schatz vor, was dagegen zu tun ist.

**Die Aufgabe ist zuerst eine Diagnose, keine Umsetzung.** Es gibt mindestens drei
plausible Ursachen mit völlig verschiedenen Konsequenzen (siehe unten). Welche zutrifft,
ist noch nicht entschieden — und bevor das nicht geklärt ist, wäre jede Änderung geraten.

## Warum das zählt

Die Auffangklasse hat keinen Parser. Ein Dokument in `sonstiges` liefert deshalb keine
Felder, kein Datum, keine Positionen und keinen Beleg — es ist für jede Automatik
unsichtbar und muss vollständig von Hand erfasst werden. Aufgefallen ist das, weil das
neue Feld „Datum des Schreibens" im Freigabe-Dialog praktisch immer leer blieb: die
Vorbelegung greift nur, wenn eine Klasse ein Datumsfeld hat und der Parser es füllt.

## Gemessener Stand (2026-09-08, Entwicklungsdatenbank im Docker-Volume `dev-data`)

Alle Zahlen aus `intake_dokumente` mit `queue_status='bereit_zur_review'`.

| Kennzahl | Wert |
|---|---|
| Dokumente in der Queue | 1.915 |
| Zeitraum | 2026-07-09 bis 2026-09-08 (zwei Monate Rückstau) |
| davon `sonstiges` | **1.647 (86 %)** |
| davon mit Konfidenz **≥ 0,85** | **1.641** |
| davon mit Konfidenz 0,50–0,70 | 6 |
| `klasse_quelle` | durchweg `auto` (keine Handkorrektur) |
| `sonstiges` als E-Mail | 1.297 |
| `sonstiges` als Datei (Scan/PDF) | 349 |

Klassenverteilung der übrigen: `rechnung` 81, `gutachten` 67, `sachstandsanfrage` 39,
`forderungsschreiben` 14, `fragebogen` 13, `pruefbericht` 12, `abschlepprechnung` 9,
`reparaturrechnung` 7, `klagedrohung` 5, `mahnschreiben` 4, `abrechnungsschreiben` 4,
`klage` 3, `kaufvertrag` 3, `mietwagenrechnung` 2, `attest` 2, `arztbericht` 2,
`nachbesichtigung` 1.

### Der auffälligste Einzelbefund

Top-Absenderdomains der `sonstiges`-E-Mails:

| Domain | Anzahl |
|---|---|
| **placetel.de** | **629** |
| gmail.com | 104 |
| allianz.de | 68 |
| huk-coburg.de | 60 |
| anwalt-offenbach.de (eigene Kanzlei) | 75 (in zwei Schreibweisen) |
| outlook.com | 32 |
| kravag.de | 21 |
| anwaltverein.de | 21 |
| generali.com, eiden-seminare.com | je 20 |
| axa.de | 20 |

`placetel.de` ist die Telefonanlage — 38 % aller `sonstiges`-Dokumente stammen von dort.
Die Domain steht bereits in `backend/registry/rausch_absender.yaml`, aber mit
`policy: nur_body` statt `komplett`. Ob das Absicht war (Anrufbenachrichtigungen mit
Anhang? Rufnummer im Betreff?) ist **nicht geklärt** und die erste Frage an RA Schatz.

75 Dokumente stammen von der **eigenen Kanzleidomain** — vermutlich ausgehende Post, die
zurück in die Queue läuft.

## Drei Ursachen, die auseinanderzuhalten sind

1. **Rauschen, das gar nicht in die Queue gehört.** Telefonanlage, Newsletter, eigene
   ausgehende Post. Dann ist es kein Klassifikationsproblem, sondern ein Filterproblem,
   und die Lösung liegt in `rausch_absender.yaml` — nicht im Klassifikator.
2. **Echte Post, die keine der 23 Klassen trifft.** Allgemeine Korrespondenz von
   Versicherern, Mandantenanfragen. Dann fehlt eine Klasse (oder mehrere), und die
   Lösung ist ein Registry-Eintrag plus Parser.
3. **Echte Post, die eine Klasse träfe, aber falsch einsortiert wird.** Dann ist der
   Klassifikator das Problem.

Die Konfidenzzahlen sprechen gegen einen Schwellenwertfehler: der Klassifikator ist sich
in 1.641 von 1.647 Fällen **sicher**. Entweder liegt er sicher richtig (Fall 1 und 2)
oder sicher falsch (Fall 3) — und das unterscheidet nur ein Blick in die Dokumente
selbst.

**Erster Schritt:** eine Stichprobe von 20–30 `sonstiges`-Dokumenten durchsehen (Betreff
und erste Zeilen) und in die drei Kategorien einsortieren. Das beantwortet die Frage
schneller als jede Codeanalyse.

## Wo der Code steht

- `backend/intake/klassifikator.py` — `klassifiziere_stufe1()` (Zeile 67, Marker aus der
  Registry) und `klassifiziere_stufe2()` (Zeile 141, LLM). Zweistufige Kaskade.
- `backend/registry/klassen/*.yaml` — 23 Klassen, je mit `marker`, `regex_felder`,
  `schema`. `sonstiges.yaml` hat **bewusst keine Marker** („sonst würde alles hier
  landen") — es ist die Auffangklasse.
- `backend/registry/rausch_absender.yaml` — Domain-Regeln mit `policy: komplett` oder
  `nur_body`.
- `backend/services/dokument_bezeichnung.py` — `dokument_datum_aus_feldern()`; zeigt, was
  eine Klasse ohne Parser an Automatik verliert.

## Bindende Regeln, die dabei gelten

- **RA-MICRO ist read-only.** Nur SQLite beschreiben.
- **Rausch-Regeln nur domainweit.** Versicherer- und Freemailer-Domains dürfen **nie**
  eingetragen werden — von dort kommt echte Post. Auch `anwaltverein.de` und `iww.de`
  schicken echte Post neben Werbung. (Festlegung RA Schatz, siehe Projektgedächtnis.)
- **Eine neue Dokumentklasse** = eine YAML in `backend/registry/klassen/` plus
  `py tools/gen_dokumentenklassen.py` (auf dem **Host** ausführen, nicht im Container).
- **`INTAKE_REVIEW_PFLICHT`**: die Review-Freigabe ist der einzige Schreibweg in die Akte.
  Nichts an dieser Aufgabe darf daran rütteln.
- Python 3.9-kompatibel; keine Kommentare im Code außer bei nicht-offensichtlichem
  Verhalten; Zielsprache Deutsch.

## Was bereits ausgeschlossen ist

- **Kein Schwellenwertproblem.** 1.641 von 1.647 liegen bei Konfidenz ≥ 0,85.
- **Keine Handkorrekturen im Spiel.** `klasse_quelle` ist durchweg `auto`.
- **Kein Altbestand-Artefakt.** 879 Altdokumente wurden am 2026-08-28 archiviert; die
  1.915 hier sind der Zufluss seit 2026-07-09.
- **Der Rückstau ist real.** Bei ~40–80 echten Poststücken pro Tag erklären zwei Monate
  nicht 1.915 Dokumente — es sei denn, ein großer Teil ist Rauschen (siehe Placetel).

## Fallen

- **`zustellungen.absender` enthält den rohen From-Header** (`"Name" <mail@domain>`).
  Eine naive Domain-Zerlegung liefert Werte wie `kravag.de" <schaden@kravag.de>` oder
  Domains mit angehängtem `>`. Jede Domain-Auswertung muss den Header sauber parsen —
  auch die Zahlen oben tragen diesen Fehler noch in sich und sind als Größenordnung zu
  lesen, nicht als exakte Werte.
- **Die aktive Entwicklungsdatenbank liegt im Docker-Volume**, nicht unter
  `backend/data/`. Abfragen über `docker exec unfallakten-backend-dev python -c ...`.
  Die Datei auf dem Host steht auf einem älteren Schemastand.
- **HMR ist unter Windows kaputt.** Nach Frontend-Änderungen den Container neu starten
  (`docker restart unfallakten-frontend-dev`) und im Browser hart neu laden.

## Fragen an RA Schatz

1. **Placetel:** Sollen Benachrichtigungen der Telefonanlage komplett aus der Queue
   verschwinden (`policy: komplett`), oder steckt in Betreff oder Anhang etwas, das
   gebraucht wird? Das allein sind 38 % der Auffangklasse.
2. **Eigene ausgehende Post:** 75 Dokumente kommen von `anwalt-offenbach.de`. Sollen die
   in die Queue?
3. **Fehlt eine Klasse?** Wenn die Stichprobe zeigt, dass viel allgemeine
   Versicherungskorrespondenz dabei ist: soll es dafür eine eigene Klasse geben, oder
   bleibt das bewusst Handarbeit?

## Zusammenhang mit laufender Arbeit

Branch `belegkette-fundament` (20 Commits, noch nicht gemergt) führt das Feld „Datum des
Schreibens" ein und lässt die Review-Freigabe ihre Belege selbst schreiben. Für
`sonstiges`-Dokumente greift beides mangels Parser kaum — bei E-Mails immerhin das
Zustelldatum als Vorbelegung (Commit `c03bc0f0`). Der Rückstau in der Queue ist der
Grund, warum das überhaupt auffiel. Die Belegketten-Arbeit selbst ist von dieser Frage
unabhängig und muss nicht abgewartet werden.

Kontext: `docs/superpowers/specs/2026-09-07-belegkette-beweisantritt-design.md`,
`docs/TODO.md` (Abschnitt „Belegkette Fundament"), `docs/DECISIONS.md` (zwei Einträge vom
2026-09-08).
