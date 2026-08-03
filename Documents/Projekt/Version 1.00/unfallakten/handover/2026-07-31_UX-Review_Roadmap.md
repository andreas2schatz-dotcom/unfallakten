# UX-Review & Verbesserungs-Roadmap

**Datum:** 2026-07-31 · **Methode:** Playwright-Durchklick aller 7 Hauptmenüs + einer echten Akte (1281/25) mit allen 9 Reitern · **Vergleich:** WebAkte, MyCase, Clio
**Zweck:** Meilenstein-/Richtungsprüfung (kein Coding). Grundlage für nachfolgende Einzel-Specs.

---

## Kernaussage

Der **fachliche Kern ist der Vorsprung** und stimmt: Phasen-Workflow in der Akte (Onboarding → Erstforderung → Regulierung → Stellungnahme → Abschluss), Kürzungskatalog als Wissensdatenbank, RVG-Gebührenassistent, Klage-Wizard, Intake-Pipeline (IMAP → Review-Queue → Aktenanlage). Das kann generische Kanzleisoftware (MyCase/Clio) nicht.

**Richtungsrisiko:** nicht im Kosmetik-Redesign versinken und nicht in die Breite bauen, sondern die **letzten 20 % „von Alarm zu erledigt"** schließen. Das spart täglich Zeit.

---

## Beobachtete Reibungspunkte (Belege aus dem Durchklick)

- **B1 Halb fertiges Redesign:** Dashboard hell, Akte weiter dunkler Navy-Kopf → wirkt wie zwei Programme.
- **B2 Kein gemeinsames Layout:** Dashboard=Karten, Wiedervorlage=Tabelle, Review-Queue=Master-Detail, Aktensuche=eigen. Keine geteilte Listen-Sprache.
- **B3 Fristen erschlagen:** „50 überfällig", flache Liste, dominiert von Dutzenden „Beschwerde −18 T"; viele sind **keine Unfallsachen** (Strafsache, Ermittlungsverfahren, Finanzamt, Fluggastrechte, Vonovia, DRV) → RA-Micro liefert die Fristen der ganzen Kanzlei. Fehlt: Bündelung, erledigt/später, Verkehrsunfall-Scope.
- **B4 Alarm führt ins Leere:** Dashboard flaggt „1281/25 Klage 213 T überfällig" als #1; Akte ist aber leere Hülle (0 € überall, Onboarding 1/6). Kein Sprung von „dringend" zu „konkret zu tun".
- **B5 Anzeigefehler:** Schaden-Summenzeile bei fehlender Haftungsquote → „NETTO (HAFTUNG UNDEFINED %) NaN €".
- **B6 Review-Queue voller Müll:** 89 „bereit", darunter DHL/Amazon, Facebook, Newsletter, „verpasster Anruf" (Placetel). Kein Vorfilter → jeder einzeln „Verwerfen".
- **B7 Belege nicht mit Positionen verbunden:** geparste PDFs (Brass-Rechnung 40 %, Allianz-Regulierung 80 %) liegen als „Referenz-Dokumente OHNE POSITIONSZUWEISUNG"; Schadenpositionen müssen trotzdem von Hand getippt werden.
- **B8 Statistiken versteckt:** `StatistikenView` ist gebaut und routbar, steht in keinem Menü.

---

## Vergleich (Kurzform)

| Thema | Dieses System | WebAkte | MyCase/Clio |
|---|---|---|---|
| Unfall-Fachworkflow | **stark** | schwach | schwach |
| Strukturierter Versicherer-Datenaustausch | fehlt → per Parsing nachgebaut | **Kernstück** | — |
| Mandantenportal | fragmentiert | vorhanden | **stark, zentral** |
| Aufgaben-/Fristen-Workflow | Backlog-artig | — | **stark** |
| Reporting | gebaut, versteckt | — | **stark** |

**Strategische Notiz:** Der größte Parsing-Aufwand adressiert genau das, was WebAkte strukturiert löst — das ist ein Organisations-, kein Softwarethema (nutzt die Kanzlei die WebAkte-/beA-Strukturkanäle?).

---

## Roadmap (empfohlene Reihenfolge)

**Voraussetzung / Meilenstein-Gate:** Zuerst die zwei offenen Branches abnehmen und mergen — `aktenanlage` → `main`, dann `dashboard-hell` → `main`. Keine neue UX-Baustelle auf ungemergtem Stand beginnen (Dev-Container laufen aktuell auf `aktenanlage`).

Danach, in dieser Reihenfolge (alle vier vom Nutzer bestätigt 2026-07-31):

1. **Volumen zähmen** (B3, B6) — höchster täglicher Zeitgewinn, geringes Risiko.
   Review-Queue-Vorfilter (offensichtlicher Nicht-Fall-Kram automatisch in Papierkorb/ausgeblendet), Bündel-Aktionen; Fristen-Triage mit Dringlichkeits-Bündeln, erledigt/später, Filter „nur Verkehrsunfall".
2. **Alarm → nächste Aktion** (B4, B5) — macht die Dringlichkeitsanzeige handlungsfähig.
   Pro Vorgang konkrete nächste Aktion statt nur „X Tage überfällig"; NaN/UNDEFINED-Bug in der Schaden-Summe beheben.
3. **Belege → Positionen** (B7) — schließt die Automatik-Schleife, größer/riskanter (Parsing→Mapping), daher nach 1+2.
   Geparste Rechnungen/Gutachten den Schadenpositionen automatisch zuordnen statt abtippen.
4. **Redesign vereinheitlichen** (B1, B2, B8) — bewusst zuletzt und **eingebettet**: die gemeinsame Listen-/Tabellen-Sprache und das helle Theme beim Umbau von Fristen-/Review-Listen (Schritt 1) gleich mitziehen, statt als separates Big-Bang-Redesign. Statistiken dabei ins Menü aufnehmen.

Jede Baustelle bekommt vor Umsetzung ein eigenes `superpowers:brainstorming` → Spec → Plan.

---

## Bewahren (nicht anfassen)

Phasen-Workflow, Kürzungskatalog + Textbausteine, RVG-Assistent mit BGH-Leitentscheidung, Klage-Wizard, Intake-Trichter. Das ist der Wettbewerbsvorsprung.
