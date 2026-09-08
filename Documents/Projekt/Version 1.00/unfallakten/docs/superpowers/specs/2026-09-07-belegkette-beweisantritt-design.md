# Belegkette und Beweisantritt — Entwurf

Stand: 2026-09-07 · Grundlage: Sparring-Gespräch mit RA Schatz
Status: **Entwurf zur Durchsicht — nicht umgesetzt, keine Zeile Code geändert**

---

## 1. Worum es geht

Die Schadenposition ist in der Aktenarbeit kein Summand, sondern ein
**Beweismittel-Anker**: Anspruch + Betrag + Beleg + Beweisangebot in einem.
Aus dieser Sicht folgen drei Wünsche, die heute alle an derselben Stelle
scheitern:

1. Der Klagetext soll Daten aus der Akte ziehen statt sie abzufragen
   („Gutachten vom …", „Verzug seit …").
2. Zu jeder Schadenposition soll sofort sichtbar sein, welcher Beleg sie
   trägt — und daraus soll in der Klage automatisch das Beweisangebot
   entstehen („BEWEIS: … Anlage K 1").
3. Maßgeblich ist immer das **Datum des Schreibens**, nie das Datum der
   Erfassung.

Der praktische Befund von RA Schatz: Ein Dokument wird in die Review-Queue
gegeben, freigegeben, geparst, ein Ereignis wird zugeordnet — und es taucht
in der Belegliste der Schadenpositionen trotzdem nicht auf. Die Arbeit wird
in der DokumenteSection und in der Schadenbelegliste zweimal gemacht, und
für den Klage-Wizard verpufft sie ganz.

Dieser Befund ist wörtlich zutreffend, nicht gefühlt. Abschnitt 3 belegt ihn.

---

## 2. Die fünf Regeln

Im Gespräch festgelegt. Sie sind die eigentliche Substanz dieses Entwurfs.

### R1 — Das Dokumentdatum gehört an das Dokument

Das Datum, das auf dem Schreiben steht, ist eine Eigenschaft des Dokuments:
unveränderlich, ohne Betrag, ohne Wirkung, ohne Versionierung. Es gehört als
Spalte an `dokumente` — nicht in ein Ereignis, nicht in eine Anzeigezeile.

Es ist die gemeinsame Basis von Klagetext, Verzugsermittlung, Ereignis-
Chronik und Beweisantritt. Ohne diese Spalte ist keiner der drei Wünsche
lösbar.

### R2 — Beleg und Vorgang sind zwei verschiedene Wahrheiten

* **`schadenposition_belege` sagt, *womit* eine Position bewiesen wird.**
  Ein Zustand. Dafür ist die Tabelle gebaut (Migration 27, PRD-23a), samt
  `UNIQUE(akte_az, position_key, dokument_id)`.
* **Das Ereignis sagt, *wann* etwas hereinkam.** Ein Vorgang. Es speist
  Chronik, Checkliste, Eskalationsstufe.

Die Klage zieht ihre Beweisangebote aus der Beleg-Tabelle. Chronik und
Checkliste lesen die Ereignisse. Die Review-Freigabe schreibt in **beide** —
genau wie der manuelle Zuordnungsweg es heute schon tut.

Damit ist auch die im Gespräch aufgeworfene Frage beantwortet, ob es
überhaupt Ereignisse sein müssen: für die Klage nein. Dafür braucht es
Beleg + Datum. Die Ereignisse behalten ihren eigenen, kleineren Job.

### R3 — Die Anlagennummer hängt am Dokument, nicht an der Position

Ein Dokument = eine Anlagennummer = ein Beweisantritt, unabhängig davon, wie
viele Positionen es trägt. Die aus dem Gutachten abgeleiteten Positionen
(Wiederbeschaffungswert, Restwert, fiktive Reparaturkosten, Reparaturdauer)
werden im Beleg zusammengezogen; das Gutachten wird **einmal** referenziert.

### R4 — Die Nummer folgt der Zitierreihenfolge im Schriftsatz

Kein festes „K 1" für das Gutachten. Die Nummer bedeutet „das wievielte
Dokument wird im Schriftsatz zitiert". Bei finanziertem Fahrzeug steht die
Freigabeerklärung vorher, das Gutachten rutscht dann auf K 2 — so verhält
sich der bestehende Code bereits (siehe 3.4).

### R5 — Wiederholtes Zitat: „Anlage K n, b.b."

Erstes Zitat eines Dokuments: volle Beweiszeile mit Bezeichnung, Datum und
Anlagennummer. Jedes weitere Zitat: nur noch „Anlage K n, b.b."
(*bereits bekannt*). Die Nummer bleibt stabil, die Form ändert sich.

Anwendungsfall aus dem Gespräch: Der Nutzungsausfall wird nach der
Schadentabelle erklärt — dort wird das Gutachten erneut zitiert, aber
verkürzt.

---

## 3. Befund im Code

Alle Angaben am 2026-09-07 im Arbeitsbaum geprüft.

### 3.1 Das Dokumentdatum existiert nicht als Datum

`backend/db/schema.py:210–228` — die Tabelle `dokumente` hat `hochgeladen_am`
und sonst kein Datumsfeld. Das Datum des Schreibens ist nirgends abfragbar.

Bemerkenswert: **Das System ermittelt dieses Datum bereits, klassenweise.**
22 der 23 Klassen-Registries deklarieren unter `bezeichnung_felder` eine
`datum`-Rolle, die auf das jeweils richtige geparste Feld zeigt:

| Klasse | Datumsfeld | | Klasse | Datumsfeld |
|---|---|---|---|---|
| gutachten | `besichtigungsdatum` | | abrechnungsschreiben | `schreibdatum` |
| reparaturrechnung | `rechnungsdatum` | | mietwagenrechnung | `rechnungsdatum` |
| abschlepprechnung | `rechnungsdatum` | | standkostenrechnung | `rechnungsdatum` |
| sv_rechnung | `rechnungsdatum` | | rechnung | `rechnungsdatum` |
| forderungsschreiben | `datum` | | mahnschreiben | `datum` |
| klagedrohung | `datum` | | sachstandsanfrage | `datum` |
| fragebogen | `unfalltag` | | übrige | `datum` |

**Ausnahme:** `pruefbericht.yaml:81` deklariert nur `aussteller`, keine
`datum`-Rolle. Einziger Ausreißer der 23.

`backend/services/dokument_bezeichnung.py` (`baue_bezeichnung`) liest diese
Rolle aus und baut daraus einen Satz:

> „Gutachten Müller & Partner vom 14.03.2024 (4.820,00 €)"

Dieser Satz landet in `dokumente.bezeichnung` (Spalte aus
`schema_manager.py:1014`) — als **Prosa**. Das Datum wird also korrekt
ermittelt und anschließend als strukturierte Information weggeworfen.

### 3.2 Die Freigabe schreibt keinen Beleg

`backend/services/eingehende_ereignisse.py:577–650` (`erzeuge_aus_freigabe`)
schreibt bei der Review-Freigabe ein Ereignis mit `position_key` — und ruft
`schreibe_ereignis()` auf, sonst nichts. In `schadenposition_belege` landet
nichts.

Der umgekehrte Weg ist besser verdrahtet: `backend/routers/belege_routes.py:416–435`
schreibt bei manueller Zuordnung erst in `schadenposition_belege` und legt
danach zusätzlich das Ereignis an, kommentiert mit „Alt-Tabelle
`schadenposition_belege` laeuft weiter".

Die Belegliste `GET /akten/<az>/belege` (`belege_routes.py:338–377`) liest
ausschließlich `schadenposition_belege`. **Deshalb** fehlt die über die
Review-Queue freigegebene, sauber geparste Rechnung in der Belegliste. Die
Automatik ist an dieser Stelle schlechter als die Handarbeit.

Reichweite der Automatik ohnehin begrenzt: Positionen werden bei der
Freigabe nur für `gutachten` und die fünf in
`backend/registry/rechnungstyp_mapping.yaml` gemappten Rechnungsklassen
abgeleitet — **6 von 23 Klassen**. Der Rest ist Handarbeit.

### 3.3 Der Klage-Wizard kennt Belege nicht

`grep -c belege frontend/src/sections/KlageWizard.jsx` → **0**.

Es existiert kein Codepfad, über den die Beleg-Zuordnung in der Klage
ankommen könnte. Die Arbeit verpufft nicht metaphorisch.

### 3.4 Die Anlagen-Mechanik existiert bereits

* `backend/word/klage_service.py:312` — `AnlagenZaehler` vergibt fortlaufende
  K-Nummern in Dokumentreihenfolge (aus KW-12).
* `klage_service.py:303–310` — `_ANLAGE_RE` / `_max_anlagen_nr` respektieren
  Nummern, die in Override-Texten bereits von Hand vergeben wurden.
* `backend/registry/klage_standardtexte.yaml:14` — Platzhalter `ANLAGE_NR`
  („Laufende Anlagen-Nummer", Beispiel „K 2") existiert im Textregister.
* `backend/tests/test_klage_service_docx.py:869–870` hält R4 bereits fest:
  bei finanziertem Fahrzeug Freigabeerklärung = K 1, Schadengutachten = K 2.

Der Zähler zählt heute allerdings **drei fest verdrahtete Textbausteine** ab
(Freigabeerklärung, Schadengutachten, Atteste) — die tatsächlichen Belege der
Akte sieht er nie. Und er zählt pro Aufruf hoch: über Positionen iteriert
bekäme dasselbe Gutachten mehrere Nummern (Verstoß gegen R3).

Der Abschnitt `schaden` im Textregister enthält neun Bausteine, darunter
genau einen `schaden_beweis_gutachten` — R3 ist dort also im Ansatz schon
abgebildet. Ein Baustein für den Nutzungsausfall-Absatz nach der
Schadentabelle fehlt.

Das Kürzel „b.b." kommt im gesamten Projekt kein einziges Mal vor.

### 3.5 Das Verzugsdatum kommt aus einer Ersatzquelle

`backend/routers/klage_routes.py:667–698`:

* `verzug_datum` = `MAX(datum)` aus `forderung_positionen` — die
  Forderungshistorie, die nur der Generierungsweg mitschreibt.
* Die Auswahlliste der Verzugsdokumente kommt aus
  `dokumente.dokumentenklasse IN ('mahnschreiben','verzugsschreiben','forderungsschreiben')`,
  sortiert nach `hochgeladen_am` — also nach dem Scan-Datum.

Ein eingescanntes altes Forderungsschreiben erscheint damit in der Liste,
aber ohne Datum; `verzug_datum` fällt auf den RA-MICRO-WDM-Wert
`varSCHREIBENVERZUG` zurück. Im Wizard steht deshalb das Handeingabefeld
„Datum des Schreibens (für BEWEIS-Zeile)"
(`frontend/src/sections/KlageWizard.jsx:1626`).

**Nebenbefund:** Die Abfrage sucht nach der Klasse `verzugsschreiben`, die es
in `backend/registry/klassen/` nicht gibt — toter Zweig.

### 3.6 Die Verzugskette ist modelliert, aber nicht verdrahtet

* `backend/registry/ereignistypen.yaml:91` kennt `fristsetzung_generiert`.
* `backend/services/fristablauf_service.py:43–45` führt genau diesen Typ als
  fristauslösend.
* Der Scheduler erzeugt daraus ein `fristablauf`-Ereignis mit Datum.

Es fehlen Anfang und Ende: **niemand schreibt jemals `fristsetzung_generiert`**
(kein Aufrufer im Produktivcode), und der Klage-Wizard liest von dieser Kette
kein Feld.

### 3.7 Ereignisse aus der Review-Queue tragen das falsche Datum

Für die Nacherfassung alter Vorgänge relevant:

* `eingehende_ereignisse.py:600` — `_heute_wenn_leer(datum)`; `intake_routes`
  übergibt nie ein Datum. Jedes Freigabe-Ereignis bekommt **heute**.
* Ausgehende Typen sind im Freigabe-Dialog dreifach gesperrt:
  `frontend/src/views/ReviewQueueView.jsx:1156` (Filter),
  `backend/routers/intake_routes.py:1085` (Serverfilter),
  `backend/services/positionsmodell_registry.py:251` (die Registry
  `klasse_ereignistyp.yaml` darf keinen ausgehenden Typ enthalten).
* `backend/services/positionsstatus_service.py:279` (`berechne_historie_hinweis`,
  N-07) blendet für Bestandsakten bereits einen Hinweis ein, dass die
  Ereignishistorie unvollständig ist — die Lücke ist im Code als
  Dauerzustand dokumentiert, nicht als Aufgabe.

---

## 4. Die Kette

> **Schadenposition → Beleg (Dokument) → Dokumentdatum → Beweiszeile + Anlage K n**

Jedes Glied existiert im Code. Es fehlen zwei Kanten und eine Spalte:

| # | Fehlt | Betrifft |
|---|---|---|
| 1 | `dokumente` bekommt eine Datumsspalte, gefüllt aus der bestehenden `bezeichnung_felder.datum`-Regel, bei der Freigabe korrigierbar | R1 |
| 2 | Die Review-Freigabe schreibt zusätzlich nach `schadenposition_belege` | R2 |
| 3 | Der Klage-Wizard liest die Belegliste und übergibt sie dem `AnlagenZaehler`, der zum Register mit Zitierzustand wird | R3–R5 |

---

## 5. Der Kontrollschritt im Wizard

Ein Wizard-Schritt „Beweismittel" vor dem Schreiben: alle Positionen mit
ihrem Beleg, durchnummeriert, zum Durchgehen.

Er prüft **beide Richtungen desselben Joins**:

* **Position ohne Beleg** — Beweisangebot fehlt.
* **Beleg ohne Position** — der teurere Fehler: eine Abschlepprechnung liegt
  geparst in der Akte, aber die Position wurde nie erfasst; es wird zu wenig
  eingeklagt.

---

## 6. Offene Punkte

1. **Woher kommt das Datum bei Dokumenten ohne Parser?**
   `forderungsschreiben.yaml` hat weder `parser` noch `regex_felder`. Bei
   Altpapier muss das Datum bei der Freigabe von Hand erfasst werden. Soll
   das Feld Pflicht sein oder darf es leer bleiben?
2. **`pruefbericht` hat keine `datum`-Rolle.** Welches geparste Feld ist das
   Datum eines Prüfberichts?
3. **Migration des Bestands.** Für bereits freigegebene Dokumente lässt sich
   das Datum aus `parse_json` nachziehen. Für Dokumente ohne Parse-Ergebnis
   bleibt es leer — akzeptabel?
4. **Reihenfolge der Zitate.** R4 macht die Reihenfolge der Positionsgruppen
   im Schriftsatz zur Nummerierungsreihenfolge. Diese Reihenfolge muss
   irgendwo festgeschrieben werden.
5. **Verzugskette.** Soll `fristsetzung_generiert` einen Schreiber bekommen
   und der Wizard das Verzugsdatum aus der Kette lesen? Eigenes Vorhaben,
   setzt R1 voraus.
6. **Toter Zweig `verzugsschreiben`** in `klage_routes.py:688` — Klasse
   anlegen oder Abfrage bereinigen?
7. **Ereignis-Nacherfassung für Altakten** (Abschnitt 3.7) — eigenes
   Vorhaben. Ohne R1 erzeugt sie falsche Chronologie und wäre schlechter als
   der heutige ehrliche N-07-Hinweis.

---

## 7. Ausdrücklich nicht Gegenstand

* **Kein Umbau des Ereignismodells.** Der Geld-SSOT-Beschluss
  (`docs/DECISIONS.md:339`, 2026-08-26) bleibt unberührt: Schadenpositionen
  und Abrechnungsart sind aktenwahr, das Ereignismodell rechnet nicht.
  Nacherfasste Beträge in Ereignissen wären Chronik-Dekoration ohne Wirkung
  auf Summen, Klageanträge oder KPI.
* **Keine Zusammenlegung der beiden Tabellen.** R2 trennt sie bewusst nach
  Bedeutung statt sie zu verschmelzen.
* **Keine neue Positionsart für die Reparaturdauer.** Sie steckt als
  `nutzungsausfall_tage` / `nutzungsausfall_tagessatz` im Gutachten-Schema;
  die Position heißt `nutzungsausfall` und trägt in
  `backend/registry/positionsarten.yaml:101` bereits
  `checkliste: [gutachten_eingegangen]`. Die Gruppe aus R3 ist damit
  vollständig abbildbar.
