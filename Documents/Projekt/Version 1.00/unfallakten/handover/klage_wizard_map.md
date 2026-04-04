# Klage-Wizard Map – Kanzlei Koch, Schatz & Kollegen
> Stand: Session v44 – 4. April 2026
> Datei: `frontend/src/sections/KlageWizard.jsx`
> Hauptkomponente: `export default function KlageWizard` (ca. Zeile 1529)

---

## Übersicht – Datenfluss

```
KlageSection.jsx
  └─ oeffneWizard()          ← initialisiert ALLE Wizard-States
  └─ wizardGenerieren()      ← baut cfg-Objekt → API → DOCX-Download
  └─ <KlageWizard .../>      ← Modal, alle States als Props durchgereicht

KlageWizard.jsx
  ├─ STEPS[10]               ← Array mit Label für Fortschrittsbalken
  ├─ Fortschrittsbalken      ← klickbar bis wizardMaxStep
  ├─ kannWeiter()            ← Step 1: gerichtBestaetigt, Step 5: pos.checked>0
  └─ Steps 1–10 (je eine Sub-Funktion)
```

---

## Step-by-Step Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  1 · StepGericht                                                            │
│  ─────────────────                                                          │
│  Input:   gerichtSuche, gerichtTreffer (API-Daten)                         │
│  Aktion:  Suche → Treffer-Liste → Auswahl → Bestätigen-Button              │
│  Output:  gericht (obj), gerichtBestaetigt (bool)                          │
│  Sperre:  Weiter-Button gesperrt bis gerichtBestaetigt===true              │
│  Status:  ✅ Vollständig                                                    │
│  Potential: Gericht zurück in Akte speichern (aktuell nur Session-State)   │
└─────────────────────────────────────────────────────────────────────────────┘
         │ gericht gespeichert
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  2 · StepRubrum                                                             │
│  ─────────────────                                                          │
│  Input:   beklagte[] (aus KlageSection-State)                              │
│  Zeigt:   Kläger + Beklagte read-only                                      │
│  Button:  „Parteien bearbeiten →" → onClose() + scrollTo #karte-parteien  │
│  Output:  –  (nur Anzeige, kein eigener State)                             │
│  Status:  ✅ P-4 implementiert                                              │
│  Potential: Warnung wenn Vertreter fehlt stärker hervorheben               │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  3 · StepAktLeg                                                             │
│  ─────────────────                                                          │
│  Input:   aktLegTyp (eigentum|finanziert|geleast)                          │
│           aktLegFreigabe (freigabe|bedingungen|ungeklaert)                 │
│           aktLegDatum (DD.MM.YYYY)                                         │
│  Zeigt:   Radio-Buttons links + DokumentCard rechts (live buildVorschauText)│
│  FIX P-3: prevAutoRef → kein Überschreiben manueller Edits                │
│  Output:  aktLegTextOverride (str → geht in klage_service als              │
│           aktivlegitimation_text_override)                                  │
│  Status:  ✅ P-3 behoben                                                    │
│  Potential: „Datum unbekannt"-Option, Tooltip zu § 1006 BGB                │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  4 · StepUnfall                                                             │
│  ─────────────────                                                          │
│  Input:   schilderungOriginal (aus Akte-DB)                                │
│           wizardUnfallText (Mandant→Kläger bereits ersetzt in oeffneWizard)│
│  Zeigt:   Original oben (read-only), editierbare Version darunter          │
│  Output:  wizardUnfallText (str → rw_text_override im Backend)             │
│  Status:  ✅ Vollständig                                                    │
│  Potential: Diff-Hervorhebung (welche Wörter ersetzt), Zurücksetzen-Button │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  5 · StepSchaden                                                            │
│  ─────────────────                                                          │
│  Input:   positionen[] mit {key, label, betrag, checked}                   │
│           abrechnungen[] (für Regulierungsinfo)                            │
│           mitSG, sgMind                                                    │
│  Zeigt:   Checkbox-Liste + SG-Toggle + Klagebetrag-Badge                  │
│  Sperre:  Weiter gesperrt wenn keine Position checked                      │
│  Output:  positionen[] (checked-State), mitSG, sgMind                     │
│  Status:  ✅ Vollständig                                                    │
│  Potential: Regulierungsstand neben jeder Position zeigen                  │
│             (wie viel bereits gezahlt vs. gefordert)                       │
└─────────────────────────────────────────────────────────────────────────────┘
         │ klagebetrag berechnet
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  6 · StepAntraege   ★ NEU PRD-26                                           │
│  ─────────────────                                                          │
│  Input:   positionen, mitSG, sgMind, beklagte, zinsenAb, verzug            │
│           unfalldatum, mitFestSg, mitFestSach                              │
│  Zeigt:   Checkboxen (Feststellungsanträge) + DokumentCard                 │
│  Logik:   baueAntraegeText() → Auto-Text inkl. Platzhalter:               │
│           „[Außergerichtliche Anwaltsgebühren – wird in Schritt 9 ergänzt]"│
│  Button:  ↻ Anträge neu generieren                                        │
│  Output:  wizardAntraegeText (str) → wird in Step 9 mit RVG-Betrag befüllt│
│           → geht an Backend als antraege_override                          │
│  Status:  ✅ Vollständig                                                    │
│  Potential: Hinweis auf Platzhalter besser visualisieren                   │
│             Feststellungsantrag Personenschaden nur bei mitSG=true sichtbar│
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  7 · StepRw  (Rechtliche Würdigung)                                        │
│  ─────────────────                                                          │
│  Input:   wizardHq (Haftungsquote %), wizardHb (Haftungsbegründung str)   │
│           abrechnungen (für Regulierungsinfo), kuerzungsarten              │
│           beklagte (für EinwandePanel)                                     │
│  Zeigt:   HQ-Slider/Input + HB-Textarea + EinwandePanel + DokumentCard    │
│  EinwandePanel: Kürzungstext-Generator (nummerierte Einwände, Varianten)  │
│  Output:  wizardRwText (str → rw_text_override)                            │
│  Status:  ✅ Vollständig (Kürzungstext-Generator PRD-26 Session v43)       │
│  Potential: UX-Verbesserung EinwandePanel (komplex, viele Optionen)        │
│             HQ-Input als Schieberegler                                      │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  8 · StepVerzug                                                             │
│  ─────────────────                                                          │
│  Input:   verzug (Datum), zinsenAb, rvgData (gerichtl. RVG), rvgOverride  │
│  Zeigt:   Verzugs-Info + RVG-Tabelle (gerichtl. SW) + editierbarer Text   │
│  ⚠ Achtung: zeigt rvgData (gerichtl. SW), nicht rvg_ausserg!              │
│  Output:  wizardVerzugText (str → verzug_text_override)                    │
│  Status:  ✅ Vollständig                                                    │
│  Potential: Trennung gerichtl./außergerichtl. RVG klarer darstellen        │
│             Verzugsdatum editierbar machen (derzeit aus Akte gelesen)      │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  9 · StepGebuehren   ★ NEU PRD-26                                         │
│  ─────────────────                                                          │
│  Input:   swAusserg (= Summe ALLER Schadenspositionen, auch ungecheckte)   │
│           wizardRvgAussergData (lazy: wird beim Betreten berechnet)        │
│           wizardRvgAussergOv (optionaler Override)                         │
│           antraegeText (aus Step 6 → Platzhalter wird hier ersetzt)       │
│  Zeigt:   RVG-Tabelle (außergerichtl. SW) + Override-Input + DokumentCard │
│  Logik:   baueGebuehrenAntrag(betrag) → setzt antraegeText-Platzhalter    │
│  Output:  wizardGebuehrenText, rvg_ausserg → cfg                           │
│           wizardAntraegeText (Platzhalter ersetzt)                         │
│  Status:  ✅ Vollständig                                                    │
│  Potential: Zeigen was genau im Antrags-Text ersetzt wird (vorher/nachher) │
│             Unterschied zum gerichtl. RVG aus Step 8 erklären             │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  10 · StepZusammenfassung + Generieren                                     │
│  ─────────────────                                                          │
│  Input:   gericht, beklagte, positionen, mitSG, sgMind                    │
│           rvgData, rvgOverride (gerichtl. RVG – für Anzeige)              │
│           aktLegTyp, aktLegFreigabe, zinsenAb, verzug                     │
│  Zeigt:   Checkliste (Gericht, Kläger, Beklagte, Klagebetrag, Zinsen,    │
│           AktLeg, RVG) + Fehler-Badges + Generieren-Button               │
│  Sperre:  kein Gericht, keine Position, Firma ohne Vertreter              │
│  Output:  → onGenerieren() → wizardGenerieren() in KlageSection           │
│  ⚠ Zeigt rvgData (gerichtl.), nicht rvg_ausserg (außergerichtl.)          │
│  Status:  ✅ Vollständig                                                    │
│  Potential: Beide RVG-Beträge zeigen (gerichtl. + außergerichtl.)         │
│             Preview der Texte als Akkordeon                                │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼ wizardGenerieren() baut cfg:
┌─────────────────────────────────────────────────────────────────────────────┐
│  klage_service.py – cfg-Felder                                             │
│  ─────────────────                                                          │
│  gericht, beklagte, positionen, mit_schmerzensgeld, schmerzensgeld_mindest │
│  zinsen_ab, verzugsdatum, rvg (berechnet), rvg_override                   │
│  aktivlegitimation_typ, aktivlegitimation_text_override (Step 3)           │
│  unfalltext_override = wizardUnfallText (Step 4)                           │
│  rw_text_override = wizardRwText (Step 7)                                  │
│  verzug_text_override = wizardVerzugText (Step 8)                          │
│  antraege_override = wizardAntraegeText (Step 6+9) ← BE-1 NEU            │
│  mit_feststellung_sg, mit_feststellung_sach ← BE-2 NEU (Fallback)        │
│  rvg_ausserg, rvg_ausserg_override ← BE-3 NEU                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Bekannte offene Punkte / Qualitätsmängel

| Step | Problem | Priorität |
|---|---|---|
| 1 | Gericht wird nicht in Akte gespeichert (nur Session) | Mittel |
| 2 | Vertreter-Warnung nicht klickbar | Niedrig |
| 4 | Kein Diff-View, kein Zurücksetzen-Button | Niedrig |
| 5 | Kein Regulierungsstand neben Position | Niedrig |
| 8 | Zeigt gerichtl. RVG, könnte Nutzer verwirren | Niedrig |
| 10 | Zeigt nur gerichtl. RVG, nicht außergerichtl. | Niedrig |
| Datei | Header-Kommentar sagt noch „7-Step" statt „10-Step" | Trivial |

---

## State-Übersicht (in KlageSection.jsx)

```
Wizard-States (PRD-24b, ergänzt PRD-26):
  wizardOffen, wizardStep, wizardMaxStep
  gericht, gerichtSuche, gerichtTreffer, gerichtLaedt, gerichtBestaetigt
  aktLegTyp, aktLegFreigabe, aktLegDatum, wizardAktLegText
  wizardUnfallText
  wizardPos (=positionen), wizardMitSG, wizardSGMind
  wizardHq, wizardHb, wizardRwText
  wizardVerzugText
  wizardMitFestSg, wizardMitFestSach
  wizardAntraegeText
  wizardRvgAussergData, wizardRvgAussergOv, wizardGebuehrenText
```

---

## Deploy-Referenz

```powershell
docker cp frontend/src/sections/KlageWizard.jsx   unfallakten-frontend-dev:/app/src/sections/KlageWizard.jsx
docker cp frontend/src/sections/KlageSection.jsx  unfallakten-frontend-dev:/app/src/sections/KlageSection.jsx
docker cp backend/word/klage_service.py           unfallakten-backend-dev:/app/backend/word/klage_service.py
docker restart unfallakten-backend-dev
```
