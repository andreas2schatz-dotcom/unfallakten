# PRD-26: Klage-Wizard Umbau
> Erstellt: 2026-04-04
> Status: In Umsetzung
> Bearbeiter: Session v43+

---

## Ziel

Den Klage-Wizard als primären, vollständigen Pfad zur Klageschrift-Generierung etablieren.
Die bisherige Ein-Klick-Generierung im Klage-Tab wird als **deprecated** markiert.

Gleichzeitig werden strukturelle Grundlagen für den analogen **ReguWizard**
(Antwort auf Abrechnungsschreiben) gelegt, da beide Wizards wesentliche
Komponenten teilen.

---

## Neue Step-Struktur (10 Steps)

| # | Label (Progressbar) | Inhalt | Weiter-Sperre |
|---|---|---|---|
| 1 | Gericht | Lookup + Bestätigung. Auto-Vorschlag aus Unfallort wird angezeigt, muss manuell bestätigt werden | ✅ Pflicht |
| 2 | Rubrum | Parteien read-only. Button „Parteien bearbeiten" schließt Wizard und öffnet Parteien-Kachel | — |
| 3 | Aktiv. | Aktivlegitimation (unverändert) | — |
| 4 | Unfall | Unfallhergang (unverändert) | — |
| 5 | Schaden | Positionen + Personenschaden → legt Klagebetrag und SG-Flag fest | ✅ mind. 1 Position |
| 6 | Anträge | Klageanträge generieren, Feststellungsanträge, Streitwert | — |
| 7 | Würdigung | Rechtliche Würdigung + Kürzungen (unverändert + heutige Fixes) | — |
| 8 | Verzug | Verzugstext (unverändert) | — |
| 9 | Gebühren | Außergerichtliche Anwaltsgebühren + RVG-Antrag | — |
| 10 | Generieren | Zusammenfassung + Validierung + Button | ✅ Gericht, Positionen, Vertreter |

---

## Behobene Altprobleme (parallel)

| ID | Problem | Lösung |
|---|---|---|
| P-1 | Step-Zahlen nicht klickbar | `onClick` in `Fortschrittsbalken` für Steps ≤ `wizardMaxStep` |
| P-2 | `hq`+`hb` verloren bei Rück-Navigation | `wizardHq`, `wizardHb` nach KlageSection heben |
| P-3 | `useEffect` in StepAktLeg überschreibt manuellen Text | Nur generieren wenn `aktLegTextManuell === false` |
| P-4 | Rubrum-Korrekturen erfordern Wizard-Neustart | Button in Step 2: schließt Wizard, scrollt zu Parteien |
| P-5 | Verzugsdatum nur außerhalb Wizard änderbar | Bleibt vorerst im Klage-Tab, Step 8 zeigt Link |

---

## Step 1: Gericht (neu im Wizard)

**State:** `gericht`, `gerichtSuche`, `gerichtTreffer`, `gerichtLaedt` bleiben in
`KlageSection` und werden als Props durchgereicht.

**Verhalten:**
- Wenn `gericht_vorschlag` aus Backend vorhanden: wird als Vorauswahl angezeigt
  mit Badge „⚡ Vorschlag – bitte bestätigen"
- Bestätigen-Button → setzt `gericht` fest
- Alternativ: neue Suche
- „Weiter →" nur aktiv wenn `gericht` gesetzt

**Aus KlageSection-Kachel übernommen:** kompletter Lookup-Block
(Suchfeld, Treffer-Dropdown, Anzeige mit Quelle-Badge)

---

## Step 6: Klageanträge (neu)

### Checkboxen (linke Spalte)

| Antrag | Sichtbar | Standard |
|---|---|---|
| Hauptantrag Sachschaden + Zinsen | immer | ✅ nicht abwählbar |
| Schmerzensgeld + Zinsen | nur wenn `mitSG=true` | ✅ |
| Feststellungsantrag **Personenschaden** | nur wenn `mitSG=true` | ✅ |
| Feststellungsantrag **Sachschaden** | immer | ☐ (optional) |
| Kostentragung | immer | ✅ nicht abwählbar |

> RVG-Antrag fehlt hier bewusst – er wird in Step 9 ergänzt.
> Der generierte Text enthält am Ende den Platzhalter:
> `[Außergerichtliche Anwaltsgebühren – wird in Schritt 9 ergänzt]`

### Gerichtlicher Streitwert (prominent angezeigt)

```
Sachschaden:         X.XXX,XX €   (Summe angehakter Positionen)
+ Schmerzensgeld:      XXX,XX €   (Mindestbetrag, nur wenn mitSG)
= Gerichtl. Streitwert: X.XXX,XX €
```

### Formulierungen

**Hauptantrag:**
> „Die Beklagte wird verurteilt, an [Kläger] [Klagebetrag] nebst Zinsen in Höhe von
> 5 Prozentpunkten über dem jeweiligen Basiszinssatz seit [Datum] zu zahlen."

**Schmerzensgeld (mit Mindestbetrag):**
> „Die Beklagte wird verurteilt, an [Kläger] ein angemessenes, vom Gericht
> festzulegendes Schmerzensgeld zu zahlen, wobei die Höhe nicht weniger als
> [Mindestbetrag] betragen sollte, nebst Zinsen von 5 Prozentpunkten über dem
> Basiszinssatz seit Rechtshängigkeit."

**Feststellungsantrag Personenschaden:**
> „Es wird festgestellt, dass die Beklagte verpflichtet ist, dem Kläger / der
> Klägerin sämtliche künftigen materiellen und immateriellen Schäden zu ersetzen,
> die aus dem Unfallereignis vom [Unfalldatum] noch entstehen werden, soweit
> Ansprüche nicht auf Sozialversicherungsträger oder sonstige Dritte übergegangen
> sind oder noch übergehen werden."

**Feststellungsantrag Sachschaden:**
> „Es wird festgestellt, dass die Beklagte verpflichtet ist, dem Kläger / der
> Klägerin sämtliche weiteren materiellen Schäden zu ersetzen, die aus dem
> Unfallereignis vom [Unfalldatum] noch entstehen werden."

### State
- `wizardMitFestSg` (bool, default = `mitSG`)
- `wizardMitFestSach` (bool, default = `false`)
- `wizardAntraegeText` (string, editierbar in DokumentCard)

---

## Step 9: Außergerichtliche Gebühren (neu)

### Bug-Fix: falscher Streitwert

Aktuell berechnet `klage_service.py:655` die RVG-Gebühren auf `klagebetrag`
(gerichtlicher Streitwert = nur eingeklagte Positionen).

**Korrekt:** Basis = **außergerichtlicher Streitwert** = Summe **aller**
Schadenpositionen (auch nicht eingeklagter).

Lösung: neuer separater `berechne_rvg(swAusserg)`-Aufruf beim Betreten von Step 9.

### Inhalt (linke Spalte)

RVG-Tabelle:
- Gegenstandswert: `swAusserg` (alle Positionen)
- Geschäftsgebühr §§ 13, 14 Nr. 2300 VV RVG (Faktor 1,3)
- Post- und Telekommunikation Nr. 7002 VV RVG
- Zwischensumme netto
- 19 % Umsatzsteuer
- **Gesamtbetrag** (Override-Feld)

### Generierter RVG-Klageantrag (DokumentCard)

> „Die Beklagte wird verurteilt, an [Kläger] weitere [RVG-Gesamt] nebst Zinsen
> in Höhe von 5 Prozentpunkten über dem jeweiligen Basiszinssatz seit
> Rechtshängigkeit zu zahlen."

Dieser Text ersetzt den Platzhalter aus Step 6 im `wizardAntraegeText`.

### State
- `wizardRvgAussergData` (Objekt: `{streitwert, gebuehr_netto, post_pauschale, zwischen_netto, ust, gesamt}`)
- `wizardRvgAussergOv` (string, Override-Betrag)
- `wizardGebuehrenText` (string, editierter RVG-Antrag)

---

## Neue/geänderte Props an KlageWizard

```javascript
// Neu:
gericht, setGericht
gerichtSuche, setGSuche
gerichtTreffer, setGTreffer
gerichtLaedt
sucheGerichte           // async function
wizardMaxStep, setWizardMaxStep
wizardHq, setWizardHq   // P-2
wizardHb, setWizardHb   // P-2
wizardMitFestSg, setWizardMitFestSg
wizardMitFestSach, setWizardMitFestSach
wizardAntraegeText, setWizardAntraegeText
wizardRvgAussergData, setWizardRvgAussergData
wizardRvgAussergOv, setWizardRvgAussergOv
wizardGebuehrenText, setWizardGebuehrenText
swAusserg               // außergerichtl. Streitwert (berechnet in KlageSection)
unfalldatum             // für Feststellungsantrag-Formulierung
```

---

## Änderungen klage_service.py

```python
# Neu im cfg-Dict:
"mit_feststellung_sg":    True/False
"mit_feststellung_sach":  True/False
"antraege_override":      str   # vollständiger Antrags-Block aus Step 6+9
"rvg_ausserg":            dict  # RVG-Berechnung auf swAusserg
"rvg_ausserg_override":   float # optionaler Override
```

Der Service baut die Anträge aus `antraege_override` wenn vorhanden,
sonst aus den einzelnen Flags (Fallback für Rückwärtskompatibilität).

---

## Deprecated: Ein-Klick-Generierung

Der bestehende „Klageschrift generieren"-Button in `KlageSection.jsx` (Zeilen 725, 1005)
wird als deprecated markiert:
- Visuell: grau, kleinere Schrift, Hinweistext „Bitte Wizard verwenden"
- Funktionell: bleibt erhalten als Fallback

---

## Analog-Wizard ReguWizard (Folge-PRD, nicht dieser Sprint)

| # | Step | Reused |
|---|---|---|
| 1 | Abrechnungsschreiben wählen | — |
| 2 | Kürzungen & Einwände | ♻ `EinwandePanel` |
| 3 | Antworttext | ♻ `DokumentCard` |
| 4 | Action-Items | — (Kenntnisnahme Mandant / SV-Stellungnahme) |
| 5 | Generieren | ♻ `Fortschrittsbalken` |

---

## Implementierungsreihenfolge

1. **KlageSection.jsx** – neue States, `swAusserg`-Berechnung, Props erweitern
2. **KlageWizard.jsx** – STEPS-Array auf 10, `Fortschrittsbalken` klickbar (P-1)
3. **KlageWizard.jsx** – `StepGericht` (Step 1, neu)
4. **KlageWizard.jsx** – `StepRubrum` (Step 2, P-4 Button)
5. **KlageWizard.jsx** – `StepAktLeg` (P-3 Fix)
6. **KlageWizard.jsx** – `StepRw` (P-2 Fix: Props statt lokalem State)
7. **KlageWizard.jsx** – `StepAntraege` (Step 6, neu)
8. **KlageWizard.jsx** – `StepGebuehren` (Step 9, neu)
9. **klage_service.py** – `antraege_override`, Feststellungsanträge, `rvg_ausserg`
10. **KlageSection.jsx** – Deprecated-Markierung der Ein-Klick-Buttons
