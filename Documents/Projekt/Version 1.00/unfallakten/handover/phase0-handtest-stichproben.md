# Phase 0 Handtest — 30 Stichproben zur Tiefenprüfung

Datenstand: 2026-07-23, /app/data/unfallakten.db (Docker-Volume dev-data), Schema 63
Korpus: 11 einzigartige Prüfberichte (mit Datei), 59 einzigartige Abrechnungsschreiben mit Positionen (nach Hash-Deduplizierung; die 6.243 bzw. 672 DB-Zeilen sind Re-Import-Duplikate).

Prüffrage je Treffer: Ist der vorgeschlagene Kürzungstyp inhaltlich richtig — und würde der zugehörige Textbaustein als Erwiderung passen?

Stichproben: 7 Prüfberichte (alle mit Kürzungs-Indiz) + 23 Abrechnungsschreiben mit Typ-Treffern = 30

## Stichprobe 1 — Akte 558/26 (Prüfbericht)
Datei: `LVMBRIEF_30.278.811.1.pdf` (Dokument-ID 739)

- **K15 Unkostenpauschale (E06)**
  > …esem Betrag nicht bereits ausreichend abgegolten ist. F Sachverständigenkosten 703,05 € F Kostenpauschale 25,00 € - Erfahrungsgemäß deckt der eingesetzte Betrag die tatsächlich entstandenen Koste…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K17 SV-Kosten (E01/E02)**
  > …nrechnung, wenn der Schaden mit diesem Betrag nicht bereits ausreichend abgegolten ist. F Sachverständigenkosten 703,05 € F Kostenpauschale 25,00 € - Erfahrungsgemäß deckt der eingesetzte Betrag die tat…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-E03 Abschleppkosten**
  > …e LVM nutzt Dienstleister für die Erfüllung spezieller Aufgaben. Beispiele hier- für sind Abschleppunternehmen, Gutachter oder Unterstützungsleistungen im Schadenfall. Eine Auflistung der v…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 2 — Akte 526/26 (Prüfbericht)
Datei: `4_1420108155264_239015646_PB_FiktiveAbrechnung.pdf` (Dokument-ID 18632)

- **K01 Stundenverrechnungssaetze (A04)**
  > …g von Original-Ersatzteilen gewährleistet ist. Bei der hier im Prüfbericht ausgewiesenen Referenzwerkstatt handelt es sich um einen qualifizierten Kfz-Meisterfachbetrieb für Karosserie- und Lacki…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K03 UPE-Aufschlaege (A01)**
  > …55,30 € Abzug technische Prüfung (netto): -17,81 € Abzug weitere Prüfung (Stundenlohn, UPE, etc.) (netto): -70,97 € Abzug gesamt (netto): -88,78 € Reparaturkosten nach Prüfung…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K04 Verbringungskosten (A02)**
  > …330,00 € Abzug Werkstattalternative 0,00 € 0,00 € -52,80 € -52,80 € Arbeitslohn Verbringungskosten 0,00 € 0,00 € 0,00 € 0,00 € Verbringungskosten bei 0,00 € 0,00 € 126,00 €…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K10 Kleinteile (A06)**
  > …,00 € -233,21 € -233,21 € Lackierung Ersatzteile 890,44 € 0,00 € 0,00 € 890,44 € Kleinteile 17,81 € -17,81 € 0,00 € 0,00 € UPE Aufschlag bei Werkstattalternative 0,00 € 0,0…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K13 Kennzeichen (E05)**
  > …026 Vorgangs-Nr. 32038247 Auftraggeber HDI Fahrzeug Hersteller Typ Erstzulassung Kennzeichen VOLKSWAGEN SHARAN 22.11.2017 OF-BL 70 Fahrzeughalter Name Anschrift Herr Edib Hus…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K17 SV-Kosten (E01/E02)**
  > …0,00 € UPE Aufschlag bei Werkstattalternative 0,00 € 0,00 € 89,04 € 89,04 € (10%) Nebenkosten 0,00 € 0,00 € 0,00 € 0,00 € Ergebnis (netto v. NfA) Abzug NfA / Wertverbesserung…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 3 — Akte 194/26 (Prüfbericht)
Datei: `Nachdruck.pdf` (Dokument-ID 19779)

- **K01 Stundenverrechnungssaetze (A04)**
  > …(Kostenvoranschlag bzw. Gutachten) haben wir inhaltlich geprüft. Die darin ausgewiesenen Stundenverrechnungssätze sind bei fiktiver Abrechnung nicht erstattungsfähig. Die Reparatur kann gleichwertig…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K03 UPE-Aufschlaege (A01)**
  > …UG (-) ZUSCHLAG (+) Die Ersatzteilpreise wurden nach der unverbindlichen Preisempfehlung (UPE) des Herstellers/Importeurs berücksichtigt. 1 289,31 1 121,14 -168,17 Aufschläge auf Ersa…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K04 Verbringungskosten (A02)**
  > …chnungssatz der Vergleichswerkstatt in Höhe von 158,00 EUR angepasst. 200,20 205,40 +5,20 Verbringungskosten sind nur dann auszugleichen, wenn durch das Verbringen des Fahrzeugs vom Reparatur…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K05 Beilackierung (A03)**
  > …tt benannt, berücksichtigen wir die uns benannten Werte der Referenzwerkstatt. Kosten für Beilackierungsmaßnahmen sind bei Abrechnung nach Gutachten oder Kostenvoranschlag nur erstattungspflich…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K06 Kuerzung Reparaturrechnung (B01/B02)**
  > …raumkonservierungsmaterial pauschal mit 10,00 EUR. Erfolgt die Abrechnung auf Basis einer Reparaturrechnung, erstatten wir die geforderten Materialkosten für Hohlraumkonservierung, sofern der in Re…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K13 Kennzeichen (E05)**
  > …cht Schaden-Nr.: SD10003345598 Schadendatum: 06.02.2026 Beteiligter: Tanja Benkovic Amtl. Kennzeichen: F-MM 520 Dokument: Gutachten oder Kostenvoranschlag vom 23.02.2026 Datum der Prüfung: 24…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K17 SV-Kosten (E01/E02)**
  > …EUR 1 177,42 EUR Ersatzteile (inkl. Kleinmaterial) 1 289,31 EUR 1 289,31 EUR 1 289,31 EUR Nebenkosten 15,00 EUR 15,00 EUR 10,00 EUR Reparaturkosten 4 079,08 EUR 4 079,08 EUR 3 377,33 EUR Neu…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 4 — Akte 782/25 (Prüfbericht)
Datei: `Info_Kfz-Versicherung_AS2025-90776575_2026-06-24.pdf` (Dokument-ID 21506)

- **K06 Kuerzung Reparaturrechnung (B01/B02)**
  > …auch im Rahmen der kon­ kreten Reparatur geführt werden. Sie können uns auch gerne ältere Reparaturrechnungen (darin enthaltene personenbezogene Daten bitte schwärzen) zum Beleg senden. Die anderen…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 5 — Akte 375/26 (Prüfbericht)
Datei: `Reproduktion.pdf` (Dokument-ID 24804)

- **K01 Stundenverrechnungssaetze (A04)**
  > …für UPE-Aufschläge, Abzüge der Verbringungskosten und Benennung mit Gegenrechnung einer Referenzwerkstatt betrifft, unterliegen diese Punkte einer juristischen Beurteilung. Die in Rede stehende K…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K03 UPE-Aufschlaege (A01)**
  > …envoranschlags erfolgte im Rahmen der fiktiven Abrechnung. Sofern es die Korrekturen für UPE-Aufschläge, Abzüge der Verbringungskosten und Benennung mit Gegenrechnung einer Referenz…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K04 Verbringungskosten (A02)**
  > …Rahmen der fiktiven Abrechnung. Sofern es die Korrekturen für UPE-Aufschläge, Abzüge der Verbringungskosten und Benennung mit Gegenrechnung einer Referenzwerkstatt betrifft, unterliegen die…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K08 Batteriestuetzbetrieb**
  > …chnik und Lackierung e.V. Wir halten daher an unserer Korrektur fest. Dass die Position "Batteriestützbetrieb" erforderlich ist, sollte unstrittig sein, jedoch ist der von dem Sachverständige…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K09 Fehlerspeicher (A05-nah)**
  > …Punkte einer juristischen Beurteilung. Die in Rede stehende Korrektur der Arbeitsposition Fehlerspeicher auslesen haben wir unter Berücksichtigung der ergänzenden Ausführungen nochmals geprüft.…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 6 — Akte 298/26 (Prüfbericht)
Datei: `Anforderung_Kfz-Versicherung_AD2026-40467367_2026-06-30.pdf` (Dokument-ID 40579)

- **K01 Stundenverrechnungssaetze (A04)**
  > …Olga Sehr geehrte Damen und Herren, in dem von uns erstellten Prüfbericht haben wir eine Referenzwerkstatt gemäß den Vorgaben des Bundesge­ richtshofs (BGH) berücksichtigt. Diese Werkstatt ist für…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K10 Kleinteile (A06)**
  > …sem Grund bleibt der von uns vorgenommene Abzug bestehen. Die Berechnung einer pauschalen Kleinteilekostenpauschale von 2% wird von uns grundsätzlich nicht infrage gestellt. Diese Vorgehens…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K12 Zulassungsdienst (E05)**
  > …für Unterlagen, Stempelgebühren, die Beschaffung der Kennzeichen oder die Nutzung ei­ nes Zulassungsdienstes, haben wir im Prüfbericht darauf hingewiesen, dass diese Kosten nur im tatsächlichen Re…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K13 Kennzeichen (E05)**
  > …umutbar ist. Bezüglich der im Schadengutachten aufgeführten Kosten für die Erneuerung des Kennzeichens, einschließlich möglicher Ausgaben für Unterlagen, Stempelgebühren, die Beschaffung der…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K15 Unkostenpauschale (E06)**
  > …bleibt der von uns vorgenommene Abzug bestehen. Die Berechnung einer pauschalen Kleinteilekostenpauschale von 2% wird von uns grundsätzlich nicht infrage gestellt. Diese Vorgehensweise wird von a…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 7 — Akte 505/26 (Prüfbericht)
Datei: `2_8020101523265_239544681_PB_FiktiveAbrechnung.pdf` (Dokument-ID 51967)

- **K01 Stundenverrechnungssaetze (A04)**
  > …g von Original-Ersatzteilen gewährleistet ist. Bei der hier im Prüfbericht ausgewiesenen Referenzwerkstatt handelt es sich um einen qualifizierten Kfz-Meisterfachbetrieb für Karosserie- und Lacki…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K03 UPE-Aufschlaege (A01)**
  > …76,34 € Abzug technische Prüfung (netto): -17,15 € Abzug weitere Prüfung (Stundenlohn, UPE, etc.) (netto): -1.322,57 € Abzug gesamt (netto): -1.339,72 € Reparaturkosten nach Pr…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K04 Verbringungskosten (A02)**
  > …800,33 € Abzug Werkstattalternative 0,00 € 0,00 € -697,83 € -697,83 € Arbeitslohn Verbringungskosten 0,00 € 0,00 € 0,00 € 0,00 € Verbringungskosten bei 0,00 € 0,00 € 126,00 €…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K10 Kleinteile (A06)**
  > …,00 € -762,57 € -762,57 € Lackierung Ersatzteile 115,96 € 0,00 € 0,00 € 115,96 € Kleinteile 2,32 € 0,00 € 0,00 € 2,32 € UPE Aufschlag bei Werkstattalternative 0,00 € 0,00 €…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K13 Kennzeichen (E05)**
  > …026 Vorgangs-Nr. 32344045 Auftraggeber HDI Fahrzeug Hersteller Typ Erstzulassung Kennzeichen MERCEDES BENZ CLA SHOOTING BRAKE 03.09.2018 F-AX 990 Fahrzeughalter Name Anschrif…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K17 SV-Kosten (E01/E02)**
  > …2,32 € UPE Aufschlag bei Werkstattalternative 0,00 € 0,00 € 11,83 € 11,83 € (10%) Nebenkosten 14,01 € 0,00 € 0,00 € 14,01 € Ergebnis (netto v. NfA) Abzug NfA / Wertverbesserun…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-C03 Wiederbeschaffungswert**
  > …+49 2173 84984-99 | www.controlexpert.com | info@controlexpert.com 1 Controlexpert Wiederbeschaffungswert laut Unterlagen Korrektur nach Prüfung Wiederbeschaffungswert ohne MwSt. 12.292,68 €…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-C04 Wiederbeschaffungsdauer**
  > …t ohne MwSt. 12.292,68 € 0,00 € Wiederbeschaffungswert mit MwSt. 12.600,00 € 0,00 € Wiederbeschaffungsdauer: 0 Besteuerungsart: differenzbesteuert Ermittlungsart: - Ergebnis: Control€xpert G…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 8 — Akte 332/26 (Abrechnungsschreiben)
Datei: `Dokument-20260612083103.pdf` (Dokument-ID 233)

- **K02 Wertminderung (C01)**
  > …liche Leistungen (+) und Abzüge (-): Reparaturkosten gemäß Prüfbericht netto 4.447,57 € + Wertminderung 650,00 € + Sachverständigengebühren 1.298,53 € + Kostenpauschale 30,00 € Gesamt 6.426,10…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K13 Kennzeichen (E05)**
  > …m 12.06.2026 Schadennummer MT-26-1000645922-01 Schadentag 24.03.2026 Ihr Zeichen 332/26PK Kennzeichen OF-CO 7803 Ansprechpartner Frau A. Meifert Telefonnummer +49 3328 424 4125 Rechtsanwälte…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K15 Unkostenpauschale (E06)**
  > …bericht netto 4.447,57 € + Wertminderung 650,00 € + Sachverständigengebühren 1.298,53 € + Kostenpauschale 30,00 € Gesamt 6.426,10 € Entschädigungsanspruch 6.426,10 € + Anwaltskosten und Gebühren…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-E07 RA-Gebuehren**
  > ….298,53 € + Kostenpauschale 30,00 € Gesamt 6.426,10 € Entschädigungsanspruch 6.426,10 € + Anwaltskosten und Gebühren 756,30 € - bereits geleistet/Vorschuss 6.955,99 € Zahlbetrag 226,41 € Der Z…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 9 — Akte 263/26 (Abrechnungsschreiben)
Datei: `Dokument-20260706104118.pdf` (Dokument-ID 47112)

- **K12 Zulassungsdienst (E05)**
  > …ungen (+) und Abzüge (-): Wiederbeschaffungswert netto 8.829,27 € - Restwert 2.177,00 € + Ummeldekosten 3,30 € + Sachverständigengebühren 1.281,97 € + Kostenpauschale 30,00 € + Standgebühren 1…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K13 Kennzeichen (E05)**
  > …m 06.07.2026 Schadennummer MT-26-1000639715-01 Schadentag 14.03.2026 Ihr Zeichen 263/26PK Kennzeichen HG-OI 1979 Ansprechpartner Frau S. Rasch Telefonnummer +49 3328 424 4184 Rechtsanwälte K…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K15 Unkostenpauschale (E06)**
  > …27 € - Restwert 2.177,00 € + Ummeldekosten 3,30 € + Sachverständigengebühren 1.281,97 € + Kostenpauschale 30,00 € + Standgebühren 166,00 € Gesamt 8.133,54 € - Mithaftungsquote 30 % 2.440,06 € En…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-C02 Restwert**
  > …n Sie sämtliche Leistungen (+) und Abzüge (-): Wiederbeschaffungswert netto 8.829,27 € - Restwert 2.177,00 € + Ummeldekosten 3,30 € + Sachverständigengebühren 1.281,97 € + Kostenpauschale…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-C03 Wiederbeschaffungswert**
  > …lungen informieren. In der Übersicht finden Sie sämtliche Leistungen (+) und Abzüge (-): Wiederbeschaffungswert netto 8.829,27 € - Restwert 2.177,00 € + Ummeldekosten 3,30 € + Sachverständigengebühren…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-E07 RA-Gebuehren**
  > …0,06 € Entschädigungsanspruch 5.693,48 € - bereits an Sachverständigen gezahlt 897,38 € + Anwaltskosten und Gebühren 664,26 € Zahlbetrag 5.460,36 € Der Zahlbetrag wird auf Ihr Konto überwiesen…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 10 — Akte 31/26 (Abrechnungsschreiben)
Datei: `DE_PaymentLetter.PDF` (Dokument-ID 15570)

- **K16 Nutzungsausfall (D01-D03)**
  > …älte Koch, Schatz & Kollegen Zahlungsposition oder Abzug Wert Abzug Wert Zahlungsposition Nutzungsausfall 1298,00 EUR Ab- und Anmeldekosten 189,99 EUR Zahlungsbetrag 1487,99 EUR Die Anschlussgara…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 11 — Akte 1256/25 (Abrechnungsschreiben)
Datei: `Schadenzahlung_Kfz-Versicherung_AS2025-84620263_2026-07-03.pdf` (Dokument-ID 48172)

- **K15 Unkostenpauschale (E06)**
  > …Z / BIC PBNKDEF­ FXXX (Kontoinhaber: Rechtsanwälte Koch, Schatz und Kollegen) veranlasst. Kostenpauschale 30,00 EUR kalkulierte Reparaturkosten ohne Mehrwertsteuer 2.930,69 EUR Sachverständigenko…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K17 SV-Kosten (E01/E02)**
  > …t. Kostenpauschale 30,00 EUR kalkulierte Reparaturkosten ohne Mehrwertsteuer 2.930,69 EUR Sachverständigenkosten 1.083,38 EUR Zahlungsbetrag 4.044,07 EUR Wir haben das Sachverständigengutachten…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 12 — Akte 298/26 (Abrechnungsschreiben)
Datei: `Abrechnungsschreiben vom 08.04.26.pdf` (Dokument-ID 162)

- **K15 Unkostenpauschale (E06)**
  > …Z / BIC PBNKDEF­ FXXX (Kontoinhaber: Rechtsanwälte Koch, Schatz und Kollegen) veranlasst. Kostenpauschale 30,00 EUR kalkulierte Reparaturkosten ohne Mehrwertsteuer 2.103,36 EUR Rechtsanwaltsgebüh…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K17 SV-Kosten (E01/E02)**
  > …ulierte Reparaturkosten ohne Mehrwertsteuer 2.103,36 EUR Rechtsanwaltsgebühren 388,12 EUR Sachverständigenkosten 737,80 EUR Zahlungsbetrag 3.259,28 EUR Die Regulierung des Fahrzeugschadens erfol…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 13 — Akte 505/26 (Abrechnungsschreiben)
Datei: `S220LQPQ_jbmwDAsU.pdf` (Dokument-ID 51966)

- **K01 Stundenverrechnungssaetze (A04)**
  > …. In der Anlage finden Sie den Prüfbe- richt. Unsere Korrekturen beziehen sich auf die Stundenverrechnungssätze - die einzelnen Fach- und Vertragswerkstätten unterscheiden sich hier zum Teil erheb…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K06 Kuerzung Reparaturrechnung (B01/B02)**
  > …h angefallen ist. Bislang liegen uns keine Belege dafür vor. Bitte reichen Sie uns die Reparaturrechnung bzw. im Totalschadenfall die Rechnung über eine Ersatzbeschaffung ein. Dann werden wi…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K15 Unkostenpauschale (E06)**
  > …g 52,94 ------------------ ergibt einen Gesamtabzug von 2.243,16 3.083,68 EUR Kostenpauschale 25,00 EUR Anwaltskosten 480,17 EUR Summe: 4.478,38 EUR ./. abgetreten an…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K17 SV-Kosten (E01/E02)**
  > …518-553-4 Sehr geehrte Damen und Herren, den Schaden regulieren wir wie folgt: Sachverständigenkosten 889,53 EUR Reparaturkosten gemäß Gutachten 5.326,84 ./. Mehrwertsteuer (19%) 8…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-E07 RA-Gebuehren**
  > …ergibt einen Gesamtabzug von 2.243,16 3.083,68 EUR Kostenpauschale 25,00 EUR Anwaltskosten 480,17 EUR Summe: 4.478,38 EUR ./. abgetreten an Michael Wagner: gezahlt…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 14 — Akte 609/26 (Abrechnungsschreiben)
Datei: `Schadenzahlung_Kfz-Versicherung_AD2026-41014045_2026-07-03.pdf` (Dokument-ID 42599)

- **K15 Unkostenpauschale (E06)**
  > …erbeschaffungswert 2.800,00 EUR Abzug Restwert -570,00 EUR Differenzbetrag 2.230,00 EUR Kostenpauschale 30,00 EUR Sachverständigenkosten 896,13 EUR Rechtsanwaltsgebühren 480,17 EUR Zahlun…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K17 SV-Kosten (E01/E02)**
  > …0 EUR Abzug Restwert -570,00 EUR Differenzbetrag 2.230,00 EUR Kostenpauschale 30,00 EUR Sachverständigenkosten 896,13 EUR Rechtsanwaltsgebühren 480,17 EUR Zahlungsbetrag 3.636,30 EUR Haben Sie…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-C02 Restwert**
  > …nwälte Koch, Schatz und Kollegen) veranlasst. Wiederbeschaffungswert 2.800,00 EUR Abzug Restwert -570,00 EUR Differenzbetrag 2.230,00 EUR Kostenpauschale 30,00 EUR Sachverständigenkosten…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-C03 Wiederbeschaffungswert**
  > …Z / BIC PBNKDEF­ FXXX (Kontoinhaber: Rechtsanwälte Koch, Schatz und Kollegen) veranlasst. Wiederbeschaffungswert 2.800,00 EUR Abzug Restwert -570,00 EUR Differenzbetrag 2.230,00 EUR Kostenpauschale 30…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 15 — Akte 576/26 (Abrechnungsschreiben)
Datei: `Dokument-20260707093615.pdf` (Dokument-ID 49018)

- **K13 Kennzeichen (E05)**
  > …m 07.07.2026 Schadennummer MT-26-1000667741-01 Schadentag 03.06.2026 Ihr Zeichen 576/26PK Kennzeichen HU-IL 82 Ansprechpartner Frau S. Klawunde Telefonnummer +49 3328 424 4153 Rechtsanwälte…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K15 Unkostenpauschale (E06)**
  > …Reparaturkosten gemäß Prüfbericht netto 3.312,59 € + Sachverständigengebühren 967,17 € + Kostenpauschale 25,00 € Gesamt 4.304,76 € Entschädigungsanspruch 4.304,76 € + Anwaltskosten und Gebühren…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-E07 RA-Gebuehren**
  > …967,17 € + Kostenpauschale 25,00 € Gesamt 4.304,76 € Entschädigungsanspruch 4.304,76 € + Anwaltskosten und Gebühren 572,21 € Zahlbetrag 4.876,97 € Der Zahlbetrag wird auf Ihr Konto überwiesen…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 16 — Akte 971/25 (Abrechnungsschreiben)
Datei: `Schadendokument_20260702100808635.pdf` (Dokument-ID 41478)

- **K15 Unkostenpauschale (E06)**
  > …fungswert 2.350,00 EUR Abzug für Restwert -400,00 EUR Sachverständigengebühren 909,52 EUR Kostenpauschale 30,00 EUR Summe Abrechnungspositionen 2.889,52 EUR Rechtsanwaltsgebühren 388,12 EUR verbl…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-C02 Restwert**
  > …iesem Schadenfall rechnen wir wie folgt ab: Wiederbeschaffungswert 2.350,00 EUR Abzug für Restwert -400,00 EUR Sachverständigengebühren 909,52 EUR Kostenpauschale 30,00 EUR Summe Abrechnun…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-C03 Wiederbeschaffungswert**
  > …: 852/25PK Sehr geehrte Damen und Herren, in diesem Schadenfall rechnen wir wie folgt ab: Wiederbeschaffungswert 2.350,00 EUR Abzug für Restwert -400,00 EUR Sachverständigengebühren 909,52 EUR Kostenpau…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 17 — Akte 548/26 (Abrechnungsschreiben)
Datei: `Schadenzahlung_Kfz-Versicherung_VW2026-90694466_2026-06-26.pdf` (Dokument-ID 32811)

- **K15 Unkostenpauschale (E06)**
  > …ug neu für alt -200,00 EUR Differenzbetrag 2.360,54 EUR Sachverständigenkosten 878,52 EUR Kostenpauschale 30,00 EUR Rechtsanwaltsgebühren 480,17 EUR Zahlungsbetrag 3.749,23 EUR Wir haben…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K17 SV-Kosten (E01/E02)**
  > …Mehrwertsteuer 2.560,54 EUR Abzug neu für alt -200,00 EUR Differenzbetrag 2.360,54 EUR Sachverständigenkosten 878,52 EUR Kostenpauschale 30,00 EUR Rechtsanwaltsgebühren 480,17 EUR Zahlungsbetra…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-E07 RA-Gebuehren**
  > …en. Durch den aktuell vorliegenden Gegenstandswert von 3269,06 EUR erlauben wir uns, Ihre Geschäftsgebühr ebenfalls abzurechnen. Hierfür haben wir das aktuelle RVG VV 2300 inklusive Auslagen zu G…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 18 — Akte 246/26 (Abrechnungsschreiben)
Datei: `Schadenzahlung_Kfz-Versicherung_AS2026-90331530_2026-06-23.pdf` (Dokument-ID 19825)

- **K02 Wertminderung (C01)**
  > …g neu für alt -99,00 EUR Differenzbetrag 9.433,63 EUR Sachverständigenkosten 2.086,31 EUR Wertminderung 400,00 EUR Kostenpauschale 30,00 EUR Zahlungsbetrag 11.949,94 EUR Wir haben das S…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K15 Unkostenpauschale (E06)**
  > …Differenzbetrag 9.433,63 EUR Sachverständigenkosten 2.086,31 EUR Wertminderung 400,00 EUR Kostenpauschale 30,00 EUR Zahlungsbetrag 11.949,94 EUR Wir haben das Sachverständigengutachten er…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K17 SV-Kosten (E01/E02)**
  > …e Mehrwertsteuer 9.532,63 EUR Abzug neu für alt -99,00 EUR Differenzbetrag 9.433,63 EUR Sachverständigenkosten 2.086,31 EUR Wertminderung 400,00 EUR Kostenpauschale 30,00 EUR Zahlungsbetrag 11…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 19 — Akte 447/26 (Abrechnungsschreiben)
Datei: `Dokument-20260619162612.pdf` (Dokument-ID 15643)

- **K13 Kennzeichen (E05)**
  > …19.06.2026 Schadennummer MT-26-1000653269-01 Schadentag 26.04.2026 Ihr Zeichen 447/26 PK Kennzeichen HU-MJ 3185 Ansprechpartner Frau M. Stenzel Telefonnummer +49 3328 424 4105 Rechtsanwälte…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K15 Unkostenpauschale (E06)**
  > …Reparaturkosten gemäß Gutachten netto 3.828,18 € + Sachverständigengebühren 1.062,55 € + Kostenpauschale 25,00 € Gesamt 4.915,73 € Entschädigungsanspruch 4.915,73 € Zahlbetrag 4.915,73 € Der Za…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 20 — Akte 194/26 (Abrechnungsschreiben)
Datei: `Abrechnungs-Schreiben.pdf` (Dokument-ID 19778)

- **K02 Wertminderung (C01)**
  > …t vor: Abrechnung nach Prüfbericht 3.377,33 EUR Bisherige Zahlung -48,13 EUR 3.329,20 EUR Wertminderung 120,00 EUR Kostenpauschale 30,00 EUR Bisherige Zahlung -25,00 EUR 5,00 EUR Zahlung per Üb…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K13 Kennzeichen (E05)**
  > …eichen 194/26 Schaden vom 06.02.2026 zur Kraftfahrzeug-Haftpflicht-Versicherung Amtliches Kennzeichen: F-H 9612 Unser Versicherungsnehmer: Dr. Andreas Hermening Sehr geehrte Damen und Herren,…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K15 Unkostenpauschale (E06)**
  > …üfbericht 3.377,33 EUR Bisherige Zahlung -48,13 EUR 3.329,20 EUR Wertminderung 120,00 EUR Kostenpauschale 30,00 EUR Bisherige Zahlung -25,00 EUR 5,00 EUR Zahlung per Überweisung 3.454,20 EUR Wir…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-C02 Restwert**
  > …Totalschaden eingetreten. Ein Anspruch besteht auf den Wiederbeschaffungswert abzüglich Restwert. Das Restwertangebot hatten wir Ihrer Mandantschaft be- reits zugesandt. Ein Anspruch auf…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-C03 Wiederbeschaffungswert**
  > …ahrzeug aber ein wirtschaftlicher Totalschaden eingetreten. Ein Anspruch besteht auf den Wiederbeschaffungswert abzüglich Restwert. Das Restwertangebot hatten wir Ihrer Mandantschaft be- reits zugesand…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 21 — Akte 285/26 (Abrechnungsschreiben)
Datei: `Abrechnungsschreiben vom 02.04.26.pdf` (Dokument-ID 155)

- **K07 Tankrest**
  > …0,27 EUR - Kostenpauschale : 30,00 EUR - Restkraftstoff : 69,30 EUR - Nutzungsausfall 14 x…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K15 Unkostenpauschale (E06)**
  > …0 EUR - SV-Kosten : 1.290,27 EUR - Kostenpauschale : 30,00 EUR - Restkraftstoff…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K16 Nutzungsausfall (D01-D03)**
  > …EUR - Restkraftstoff : 69,30 EUR - Nutzungsausfall 14 x 43 EUR : 602,00 EUR - Abschleppkosten…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-E03 Abschleppkosten**
  > …: 69,30 EUR - Nutzungsausfall 14 x 43 EUR : 602,00 EUR - Abschleppkosten : 944,94 EUR Gesamtbetrag…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-C02 Restwert**
  > …sererseits nicht erho­ ben. Wir rechnen wie folgt ab: - Wiederbeschaffungswert KfZ abzgl. Restwert : 5.035,00 EUR - SV-Kosten : 1.290…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-C03 Wiederbeschaffungswert**
  > …dungen zum Haftungsgrund werden unsererseits nicht erho­ ben. Wir rechnen wie folgt ab: - Wiederbeschaffungswert KfZ abzgl. Restwert : 5.035,00 EUR - SV-Kosten…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-F01 Schmerzensgeld**
  > …eis des Nutzungswillens erfolgt im Erledigungsinteresse und ohne Präjudiz. Zahlungen zum Schmerzensgeld können erst geleistet werden, wenn die unfallbedingten Verletzungen nachge­ wiesen sind.…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 22 — Akte 477/26 (Abrechnungsschreiben)
Datei: `Dokument-20260623084115.pdf` (Dokument-ID 19453)

- **K13 Kennzeichen (E05)**
  > …m 23.06.2026 Schadennummer MT-26-1000660662-01 Schadentag 04.05.2026 Ihr Zeichen 477/26PK Kennzeichen OF-BV 187 Ansprechpartner Frau A. Meifert Telefonnummer +49 3328 424 4125 Rechtsanwälte…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K15 Unkostenpauschale (E06)**
  > …Reparaturkosten gemäß Prüfbericht netto 1.530,58 € + Sachverständigengebühren 695,56 € + Kostenpauschale 25,00 € Gesamt 2.251,14 € Entschädigungsanspruch 2.251,14 € + Anwaltskosten und Gebühren…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-E07 RA-Gebuehren**
  > …695,56 € + Kostenpauschale 25,00 € Gesamt 2.251,14 € Entschädigungsanspruch 2.251,14 € + Anwaltskosten und Gebühren 388,12 € Zahlbetrag 2.639,26 € Der Zahlbetrag wird auf Ihr Konto überwiesen…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 23 — Akte 526/26 (Abrechnungsschreiben)
Datei: `S260JZ5L_iahcgjie.pdf` (Dokument-ID 18631)

- **K01 Stundenverrechnungssaetze (A04)**
  > …. In der Anlage finden Sie den Prüfbe- richt. Unsere Korrekturen beziehen sich auf die Stundenverrechnungssätze - die einzelnen Fach- und Vertragswerkstätten unterscheiden sich hier zum Teil erheb…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K06 Kuerzung Reparaturrechnung (B01/B02)**
  > …h angefallen ist. Bislang liegen uns keine Belege dafür vor. Bitte reichen Sie uns die Reparaturrechnung bzw. im Totalschadenfall die Rechnung über eine Ersatzbeschaffung ein. Dann werden wi…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K15 Unkostenpauschale (E06)**
  > …ng 123,00 ------------------ ergibt einen Gesamtabzug von 583,29 1.743,52 EUR Kostenpauschale 25,00 EUR Sachverständigenkosten 735,18 EUR Summe: 2.503,70 EUR ./. an Si…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K17 SV-Kosten (E01/E02)**
  > …-- ergibt einen Gesamtabzug von 583,29 1.743,52 EUR Kostenpauschale 25,00 EUR Sachverständigenkosten 735,18 EUR Summe: 2.503,70 EUR ./. an Sie: gezahlt 2.503,70 EUR Wir za…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 24 — Akte 562/26 (Abrechnungsschreiben)
Datei: `Gutachten_OF_EW_31.pdf` (Dokument-ID 2562)

- **K02 Wertminderung (C01)**
  > ….......................................................................................19 Wertminderung Wertminderung Merkantiler Minderwert (steuerneutral).....................................…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K05 Beilackierung (A03)**
  > ….......................................................................................12 Beilackierung nicht erforderlich.......................................................................…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K11 Technische Kuerzung (A07/A08/A09)**
  > …rammt Heckklappe deformiert) festgestellt. Der eingetretene Unfallschaden überlagert den Vorschaden. Hieraus resultierende Abzüge sind berücksichtigt und ergeben sich im Detail aus der Kal…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K13 Kennzeichen (E05)**
  > …ter-online.com Supportzeiten: Mo-Fr: 10-18Uhr 8 von 50 Fahrzeugdaten Fahrzeug Amtliches Kennzeichen OF EW 31 Hersteller Citroën Modell/Haupttyp Jumpy Kombi Untertyp XL (L3) Baujahr 2018 Er…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K16 Nutzungsausfall (D01-D03)**
  > …aturkosten inkl. MwSt. (753,64 €) 4.720,18 € Reparatur Reparaturdauer ca. 2-3 Arbeitstage Nutzungsausfall Entschädigung pro Tag (Gruppe F) 50,00 € Mietwagenkosten pro Tag (7 - Obere Mittelklasse…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K18 Mietwagen (D04-D06)**
  > …araturdauer ca. 2-3 Arbeitstage Nutzungsausfall Entschädigung pro Tag (Gruppe F) 50,00 € Mietwagenkosten pro Tag (7 - Obere Mittelklasse) 107,75 € Wiederbeschaffungswert (differenzbesteuer…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-C02 Restwert**
  > …49 7243 3549140 support@kfzgutachter-online.com Supportzeiten: Mo-Fr: 10-18Uhr 4 von 50 Restwert 11.105,00 € REPAIRCHECK - KFZ Sachverständigenbüro support@kfzgutachter-online.com +49 7…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-C03 Wiederbeschaffungswert**
  > …ung pro Tag (Gruppe F) 50,00 € Mietwagenkosten pro Tag (7 - Obere Mittelklasse) 107,75 € Wiederbeschaffungswert (differenzbesteuert) 16.025,00 € Wiederbeschaffungswert ohne MwSt. 15.649,41 € Fahrzeugw…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-C04 Wiederbeschaffungsdauer**
  > …fferenzbesteuert) 16.025,00 € Wiederbeschaffungswert ohne MwSt. 15.649,41 € Fahrzeugwert Wiederbeschaffungsdauer 14-21 Kalendertage Aktenzeichen GA-RC-HS-2026-01-110 OF EW 31 Waldbronn, 28.01.2026 REPA…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-A10 Reparaturbestaetigung**
  > …ere Schäden festgestellt werden, so ist unbedingt der Sachverständige zwecks eventueller Nachbesichtigung zu informieren. Hierbei sind die ausgewechselten Ersatzteile bis zur Nachbesichtigung un…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-C01b Wertminderung-Steuer**
  > …turkosten ohne MwSt. 3.966,54 € Neu-für-alt ohne MwSt. - 750,91 € Merkantiler Minderwert (steuerneutral) + 80,00 € Schadenhöhe ohne MwSt. 3.295,63 € Schadenhöhe inkl. MwSt. (610,97 €) 3.906,60…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 25 — Akte 330/26 (Abrechnungsschreiben)
Datei: `Schadenzahlung_Kfz-Versicherung_AS2026-50442642_2026-06-23.pdf` (Dokument-ID 19857)

- **K02 Wertminderung (C01)**
  > …wertsteuer 18.461,38 EUR Nicht zu erstatten -7.734,55 EUR Differenzbetrag 10.726,83 EUR Wertminderung 1.012,50 EUR Sachverständigenkosten 2.015,70 EUR Zahlungsbetrag 13.755,03 EUR Wir…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K17 SV-Kosten (E01/E02)**
  > …Nicht zu erstatten -7.734,55 EUR Differenzbetrag 10.726,83 EUR Wertminderung 1.012,50 EUR Sachverständigenkosten 2.015,70 EUR Zahlungsbetrag 13.755,03 EUR Wir haben das Sachverständigengutachten…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-E07 RA-Gebuehren**
  > …ch, Schatz und Kollegen) veranlasst. kalkulierte Reparaturkosten ohne Mehrwertsteuer 18.461,38 EUR Nicht zu erstatten -7.734,55 EUR Differenzbetrag 10.726,83 EUR Wertminderung 1.012…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 26 — Akte 61/26 (Abrechnungsschreiben)
Datei: `Schadenzahlung_Kfz-Versicherung_AS2026-70079962_2026-06-23.pdf` (Dokument-ID 19859)

- **K15 Unkostenpauschale (E06)**
  > …Z / BIC PBNKDEF­ FXXX (Kontoinhaber: Rechtsanwälte Koch, Schatz und Kollegen) veranlasst. Kostenpauschale 30,00 EUR Sachverständigenkosten 1.023,40 EUR kalkulierte Reparaturkosten ohne Mehrwertst…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K17 SV-Kosten (E01/E02)**
  > …toinhaber: Rechtsanwälte Koch, Schatz und Kollegen) veranlasst. Kostenpauschale 30,00 EUR Sachverständigenkosten 1.023,40 EUR kalkulierte Reparaturkosten ohne Mehrwertsteuer 4.491,79 EUR Rechtsanwaltsge…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 27 — Akte 980/25 (Abrechnungsschreiben)
Datei: `2026-07-04_Schriftwechsel_HUK_06-49.pdf` (Dokument-ID 43429)

- **K02 Wertminderung (C01)**
  > …e Damen und Herren, den Schadenfall rechnen wir wie folgt ab: Reparaturkosten 12.675,15 € Wertminderung 400,00 € Sachverständigenhonorar 1.392,00 € Kostenpauschale 25,00 € ---------------------…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K04 Verbringungskosten (A02)**
  > …r 26-11-537/586132-F an. Wir melden uns anschließend wieder bei Ihnen. Die Kosten für die Verbringung des Fahrzeugs ziehen wir ab. Wir erstatten die erforderlichen Kosten für die Verbringung…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K06 Kuerzung Reparaturrechnung (B01/B02)**
  > …lten, wenn das Fahrzeug – in einer Werkstatt repariert wurde – dann reichen Sie bitte die Reparaturrechnung ein. per E-Mail 2611537586132F – in Eigenregie n…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K15 Unkostenpauschale (E06)**
  > …ab: Reparaturkosten 12.675,15 € Wertminderung 400,00 € Sachverständigenhonorar 1.392,00 € Kostenpauschale 25,00 € ----------------------- Zwischensumme 14.492,15 € davon 50 % gemäß Quote 7.246,08…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K17 SV-Kosten (E01/E02)**
  > …Schadenfall rechnen wir wie folgt ab: Reparaturkosten 12.675,15 € Wertminderung 400,00 € Sachverständigenhonorar 1.392,00 € Kostenpauschale 25,00 € ----------------------- Zwischensumme 14.492,15 € davo…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-E07 RA-Gebuehren**
  > …ag ist nach der örtlichen Rechtsprechung ausreichend. Ihre Gebühren in Höhe von 612,80 € (1,3 aus dem Entschädigungsbetrag) haben wir einschließlich Ne­ benkosten überwiesen. Wir habe…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 28 — Akte 563/26 (Abrechnungsschreiben)
Datei: `Abrechnungs-Schreiben.pdf` (Dokument-ID 25658)

- **K13 Kennzeichen (E05)**
  > …chen 563/26PK Schaden vom 09.06.2026 zur Kraftfahrzeug-Haftpflicht-Versicherung Amtliches Kennzeichen: F-PK 1926 Unser Versicherungsnehmer: Panagiotis Ktenidis Sehr geehrte Damen und Herren,…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K15 Unkostenpauschale (E06)**
  > …19.500,00 EUR Restwerte -15.310,00 EUR 4.190,00 EUR Sachverständigengebühren 1.175,80 EUR Kostenpauschale 25,00 EUR Zahlung per Überweisung 5.390,80 EUR Wir zahlen netto, weil Vorsteuerabzugsbere…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-C02 Restwert**
  > …um oben genannten Schaden nehmen wir wie folgt vor: Wiederbeschaffungswerte 19.500,00 EUR Restwerte -15.310,00 EUR 4.190,00 EUR Sachverständigengebühren 1.175,80 EUR Kostenpauschale 25,00…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **N-C03 Wiederbeschaffungswert**
  > …rte Damen und Herren, die Abrechnung zum oben genannten Schaden nehmen wir wie folgt vor: Wiederbeschaffungswerte 19.500,00 EUR Restwerte -15.310,00 EUR 4.190,00 EUR Sachverständigengebühren 1.175,80 EU…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 29 — Akte 564/26 (Abrechnungsschreiben)
Datei: `Schadenzahlung_Kfz-Versicherung_AS2026-90558514_2026-07-08.pdf` (Dokument-ID 52685)

- **K02 Wertminderung (C01)**
  > …t. kalkulierte Reparaturkosten ohne Mehrwertsteuer 1.636,44 EUR Kostenpauschale 30,00 EUR Wertminderung 300,00 EUR Sachverständigenkosten 813,84 EUR Zahlungsbetrag 2.780,28 EUR Die Regu…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K15 Unkostenpauschale (E06)**
  > …tz und Kollegen) veranlasst. kalkulierte Reparaturkosten ohne Mehrwertsteuer 1.636,44 EUR Kostenpauschale 30,00 EUR Wertminderung 300,00 EUR Sachverständigenkosten 813,84 EUR Zahlungsbetrag…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K17 SV-Kosten (E01/E02)**
  > …osten ohne Mehrwertsteuer 1.636,44 EUR Kostenpauschale 30,00 EUR Wertminderung 300,00 EUR Sachverständigenkosten 813,84 EUR Zahlungsbetrag 2.780,28 EUR Die Regulierung des Fahrzeugschadens erfol…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt

## Stichprobe 30 — Akte 567/26 (Abrechnungsschreiben)
Datei: `Schadenzahlung_Kfz-Versicherung_AS2026-90744558_2026-06-22.pdf` (Dokument-ID 19124)

- **K02 Wertminderung (C01)**
  > …tz und Kollegen) veranlasst. kalkulierte Reparaturkosten ohne Mehrwertsteuer 2.830,25 EUR Wertminderung 160,00 EUR Kostenpauschale 30,00 EUR Sachverständigenkosten 1.292,40 EUR Rechtsanwaltsgeb…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K15 Unkostenpauschale (E06)**
  > …st. kalkulierte Reparaturkosten ohne Mehrwertsteuer 2.830,25 EUR Wertminderung 160,00 EUR Kostenpauschale 30,00 EUR Sachverständigenkosten 1.292,40 EUR Rechtsanwaltsgebühren 572,21 EUR Zahl…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K17 SV-Kosten (E01/E02)**
  > …osten ohne Mehrwertsteuer 2.830,25 EUR Wertminderung 160,00 EUR Kostenpauschale 30,00 EUR Sachverständigenkosten 1.292,40 EUR Rechtsanwaltsgebühren 572,21 EUR Zahlungsbetrag 4.884,86 EUR Anbei ü…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt
- **K18 Mietwagen (D04-D06)**
  > …koll zu diesem verbindlichen Angebot haben wir beigefügt. Sollte Ihr Mandant selbst einen Mietwagen anmieten, reichen Sie uns mit der Mietwagenrechnung bitte eine Kopie des Mietvertra­ ges…
  - [ ] passt · [ ] falsch · [ ] Position erwähnt, aber nicht gekürzt


---

# Ergebnis der Tiefenprüfung (RA Schatz, 2026-07-23)

## Urteile je Stichprobe (Kurzform)

- **S1:** 1a/1b passt · 1c Floskel (LVM-Dienstleister-Hinweis, keine Kürzung)
- **S2:** 2a–d passt · 2e falsch (Briefkopf) · 2f erwähnt (Tabellenzeile)
- **S3:** 3a–d + 3g passt (3g: SV-Nebenkosten 15→10 gekürzt) · 3e erwähnt (Hinweistext) · 3f falsch (Briefkopf)
- **S4:** Hinweistext ohne Kürzungswert; Ablage korrekt (Text referenziert 782/25)
- **S5:** gestrichen — reine SV-Stellungnahme/weitere Haftungsablehnung ohne Beträge
- **S6:** 6a–d passt · 6e falsch — „Kleinteile**kostenpauschale**" ist Kleinteilepauschale (eigener Baustein Nr. 10), nicht Unkostenpauschale → Wortgrenzen-Problem
- **S7:** 7a/7g passt · 7b falsch (Gesamtsumme der Kürzungen, nicht UPE) · 7c falsch (Arbeitslohn; Verbringungskosten werden hier sogar addiert, weil der Referenzbetrieb sie berechnet) · 7e falsch (Briefkopf) · 7f falsch (Reparatur-Nebenkosten, kein SV-Bezug) · 7h erwähnt (Feld „0", unplausibel) · 7d nicht bewertet
- **S8:** 8a passt — **Schlüsselfund:** Wertminderung 1.450 € gefordert, 650 € gezahlt; im Abrechnungsschreiben ist KEINE Kürzung erkennbar („fiese Taktik") → nur Forderungs-Differenz deckt sie auf · 8b falsch (Briefkopf) · 8c passt (Unkostenpauschale nur 25 € gezahlt) · 8d passt
- **S9:** passt bis auf 9b (Briefkopf) und 9c (Mithaftungsquote = Kürzung dem Grunde nach, korrekt KEIN Typ)
- **S10:** passt
- **S11–S14:** Positionen und Beträge korrekt gelesen; Synonymik nötig („Differenzbetrag" = Fahrzeugschaden, „Kostenpauschale" = Unkostenpauschale); 12: drei Positionen (UP + Fahrzeugschaden + RA-Gebühren); 13d/23d: nur der erste Betrag ist SV, Folgebeträge sind Fahrzeugschaden/USt/Gesamtsumme; HDI-Schreiben besonders unübersichtlich
- **S15:** 15a Briefkopf · 15b passt — 5 € Kürzung (25 statt 30) · 15c passt
- **S16:** **FEHLABLAGE bestätigt** — Dokument 41478 referenziert „Ihr Zeichen 852/25PK", liegt unter Akte 971/25
- **S17/S18:** Beträge korrekt; zusätzlich Abzug „**neu für alt**" (−200 € / −99 €) ohne Katalogtreffer → Typ A07 + Baustein fehlen
- **S19:** 19a Briefkopf · 19b Unkostenpauschale 25 €
- **S20:** dokumentierte **Nachzahlung** (Kostenpauschale 25 € → +5 € = 30 €) — der Runde-1↔Runde-2-Fall in freier Wildbahn
- **S21:** alles korrekt; 21g Schmerzensgeld-Zurückstellung mangels Verletzungsnachweis = echte Begründung
- **S22:** korrekt (22a Briefkopf falsch); Anm. RA: Position „Reparaturkosten gemäß Prüfbericht" fehlte in der Treffer-Auswahl
- **S23:** 23a passt (echte SVS-Begründung) · 23b generischer Fiktiv-Abrechnungs-Baustein, ohne Wert · 23c/d Beträge: nur erster Betrag = genannte Position, Folgewerte = Fahrzeugschaden/Summen
- **S24:** **KLASSIFIKATIONSFEHLER bestätigt** — 50-seitiges REPAIRCHECK-Gutachten als „abrechnungsschreiben" klassifiziert; aus Wertung genommen
- **S25:** Abzug „Nicht zu erstatten −7.734,55 €" im Schreiben unbegründet — Begründung liegt im zugehörigen **Prüfbericht** → Dokument-Verkettung nötig · 25b SV = 2.015,70 · 25c falsch (RA-Gebühren nicht im Schreiben)
- **S26:** 26a passt · 26b nur erster Betrag SV, zweiter Fahrzeugschaden
- **S27:** **FEHLABLAGE bestätigt** — Dokument 43429 referenziert „418/28", unter 980/25 abgelegt; dort keine Zahlung erhalten
- **S28:** 28a Briefkopf · 28b UP 25 €, zweiter Betrag Gesamtbetrag · 28c/d passt
- **S29/S30:** korrekt; 30d Hinweis, keine Kürzungsbegründung (Anm. S29: Fahrzeugschaden 1.636,44 € fehlte in Treffer-Auswahl)

## Kennzahlen (final)

| Kennzahl | Wert |
|---|---|
| Abdeckung (Dokument mit Kürzungs-Indiz findet ≥1 Typ) | **94 %** (30/32, Gesamtkorpus maschinell) |
| Trefferquote Typ-Matching auf **Begründungsdokumenten** (Prüfberichte, 28 bewertete Treffer) | **61 % roh** (17 passt / 8 falsch / 3 erwähnt); **≈71 % nach trivialen Stichwort-Fixes** (Briefkopf-Kennzeichen, Wortgrenzen) |
| Typ-Matching auf **Zahlmitteilungen** | nicht sinnvoll — dort zählt Positions-/Betrags-Parsing (qualitativ: „Beträge prinzipiell korrekt erkannt", aber Betrag↔Position braucht strukturiertes Parsen statt Kontextfenster) |
| Dokument-Hygiene | 3/30 Stichproben fehlerhaft einsortiert oder klassifiziert (2 Fehlablagen, 1 Gutachten als Abrechnungsschreiben) |

## Kernerkenntnisse

1. **Kürzungs-ERKENNUNG = Differenz Forderung (Soll) vs. Zahlung (Ist)** — nie aus dem Abrechnungsschreiben allein (RA Schatz wörtlich: Abrechnungsschreiben = „Wissensmitteilung über die Zahlung"). Matching liefert nur den **Typ** und nur auf Begründungsdokumenten. → bestätigt Konzept 12.5/12.6 und Option (b).
2. **Begründung und Zahlung liegen oft in verschiedenen Dokumenten** (S25): Abrechnungsschreiben zahlt, Prüfbericht begründet → Phase 1 muss beide Dokumente derselben Abrechnungsrunde verketten.
3. Stichwort-Fixes für Phase 1: Wortgrenzen (Kleinteilepauschale ≠ Unkostenpauschale), „Kennzeichen" verengen auf Schilderkosten/Kennzeichen-Erneuerung, ControlExpert-Tabellen strukturiert parsen statt Keyword.
4. Fehlende Typen/Bausteine aus realen Fällen: **Neu-für-alt (A07)**; Schmerzensgeld-Zurückstellung mangels Nachweis (F01-Prozessfall).
5. Positions-Synonymik je Versicherer-Template nötig; Zahlungsbriefe listen kumulierte Summen direkt neben Positionen (Verwechslungsgefahr im Freitextfenster).
