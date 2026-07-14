# N-04 — Seiten-Triage vor OCR (Design)

Stand: 2026-07-14 · Branch `intake-stufe1` · Quelle: `FREIGABE-NACHTRAG-1.md` Abschnitt A, Punkt N-04

## Ziel

Gescannte Dokumente (v.a. Gutachten) enthalten oft viele **Foto-Anlagen**
(Schadensbilder) ohne nennenswerten Text. Diese Fotoseiten sollen **nicht**
durch die teure KI-OCR (GLM) laufen. N-04 erkennt Fotoseiten anhand einer
billigen Heuristik, markiert sie als **Bildseite** und ruft GLM nur noch auf
texttragenden Seiten auf. Die Fotoseiten bleiben unverändert in der
Arbeitskopie sichtbar; sie tragen nur keinen (oder minimalen) Text zum
Dokumenttext bei.

Erwarteter Nutzen (lt. FREIGABE): größter Durchsatzgewinn bei Gutachten mit
Foto-Anlagen — **sobald GLM aktiviert ist**. In Stufe 1 ist GLM per Default
aus (`GLM_OCR_ENABLED=false`), Tesseract ist Primär-OCR. Die Triage spart dann
noch keine GLM-Aufrufe (Tesseract läuft ohnehin), macht aber die
Bildseiten-Markierung sofort sichtbar. Das ist bewusst so (forward-looking +
sofortige Transparenz), kein Fehler.

## Nicht-Ziele / bewusst ausgeklammert

- **Kein N-05** (kooperatives Yielding, Teilergebnisse) — separat entschieden,
  erst nach echten Durchsatz-Zahlen.
- **Keine harte Seitenobergrenze** einführen.
- **Keine DB-Migration** — die Markierung lebt vollständig im bestehenden
  `parse_json` (kein neues Feld, kein CHECK-Rebuild, kein Deploy-Reihenfolge-
  Risiko wie zuletzt bei Mig 56/57).
- **Keine Änderung an Klassifikation, Feld-Extraktion oder N-06-Seitenauswahl.**

## Ansatz

**Tesseract als kostenlose Triage.** Tesseract (lokal, billig) läuft auf jeder
OCR-Seite ohnehin. Sein Ergebnis ist das Triage-Signal:

- Findet Tesseract **wenig** Text (unter Schwelle) → **Bildseite** →
  GLM wird übersprungen.
- Findet Tesseract **genug** Text → texttragende Seite → GLM läuft (wenn
  aktiviert), sonst Tesseract-Text.

Das kehrt die heutige Reihenfolge in `_ocr_seite` um (von „GLM zuerst,
Tesseract als Fallback" zu „Tesseract zuerst als Triage, GLM danach nur bei
Textseiten"). Verhalten bei GLM=aus ändert sich nicht (GLM lieferte schon
heute `None` → Tesseract-Text).

### Verworfene Alternativen

- **Separater Pixel-/Bild-Heuristik-Pass** (Anteil Nicht-Weiß-Pixel o.ä.) vor
  Tesseract: unnötig, da Tesseract eh läuft; zusätzlicher Code, ungenauer bei
  Text-auf-Foto.
- **`textquelle='bild'` als neuer Spaltenwert** mit CHECK-Rebuild-Migration:
  semantisch etwas sauberer, aber Migration + Deploy-Reihenfolge-Risiko für
  minimalen Gewinn. Verworfen zugunsten migrationsfreier Flag-Lösung.

## Komponenten & Änderungen

### 1. Triage-Funktion (rein, unit-testbar)

Neue reine Funktion in `backend/intake/text_extraktion.py`:

```
ist_bildseite(text: str) -> bool
```

- Liefert `True`, wenn der (OCR-)Text als Fotoseite ohne nennenswerten Text
  gilt: Wortzahl unter Schwelle. Optionaler Zusatz-Guard über
  `woerterbuch_quote`, damit eine kurze *echte* Textseite nicht fälschlich als
  Bild gilt (Design: nur wenn Wortzahl unter Schwelle **und** Wörterbuchquote
  sehr niedrig → Bildseite; eine kurze Seite mit echten deutschen Wörtern
  bleibt Textseite).
- Neue Konstante `MIN_WOERTER_BILDSEITE` (Default 8), plus Nutzung der
  bestehenden `MIN_WOERTERBUCH_QUOTE`. Alle Schwellen als Modul-Konstanten,
  jederzeit nachjustierbar.
- Konsequenz einer Fehlklassifikation ist gering: eine als Bild markierte
  Seite bleibt in der Arbeitskopie sichtbar, sie wird nur nicht ge-GLM't.

### 2. `SeitenText` erweitern

`backend/intake/text_extraktion.py` (`SeitenText`, Z. 73-81): neues Feld

```
ist_bildseite: bool = False
```

Default `False` → alle bestehenden Konstruktionen (inkl. `_synth_seite` für
E-Mail-Text) bleiben unverändert korrekt.

### 3. `_ocr_seite` umbauen

`backend/intake/pipeline.py:110-132`. Neue Reihenfolge:

1. Seite rendern (`ocr_service.pdf_zu_bildern(first_page=nr, last_page=nr)`,
   unverändert, BUG-12-Verhalten bleibt).
2. **Tesseract zuerst** (`ocr_service.ocr_seite_mit_tsv` → TSV persistiert wie
   bisher).
3. `ist_bildseite(tess_text)`? → **ja:** GLM überspringen, als Bildseite
   zurückgeben (Text = Tesseract-Ergebnis, i.d.R. leer/minimal).
4. **nein** (texttragend): `glm_ocr_service.glm_ocr_seite(bild)`; bei Treffer
   dessen Text, sonst Tesseract-Text.

Signatur ändert sich von `-> str` auf `-> tuple[str, bool]`
(`(text, ist_bildseite)`), damit die Seiten-Schleife den Flag setzen kann.

### 4. Seiten-Schleife in `verarbeite_dokument`

`backend/intake/pipeline.py:181-186`:

```
for s in seiten:
    if s.braucht_ocr:
        s.text, s.ist_bildseite = _ocr_seite(pdf_bytes, s.nr, dok["sha256"])
        s.textquelle = "ocr"
```

Bildseiten behalten `textquelle="ocr"` (sie *wurden* OCR-behandelt); die
Bild-Eigenschaft steckt im Flag, nicht in der textquelle — so bleibt der
`textquelle`-Spalten-CHECK unangetastet.

### 5. `aggregierte_textquelle` — Bildseiten ausblenden

`backend/intake/text_extraktion.py:222-234`: Aggregation über die
**Nicht-Bildseiten**. Ein Dokument mit 2 Textebenen-Seiten + 30 Fotoseiten →
`"textebene"`, nicht `"gemischt"`. Randfall „nur Bildseiten" → `"ocr"`
(bleibt im gültigen Spalten-CHECK `textebene|ocr|gemischt|email_text`; **kein**
neuer Wert). `dokument_ocr_qualitaet` (N-02) braucht keine Änderung — es
filtert bereits auf `s.text.strip()`, Bildseiten (leerer Text) fallen von
selbst raus.

### 6. Persistenz in `parse_json` (migrationsfrei)

`backend/intake/pipeline.py:248-279`:

- Pro Seite im `seiten`-Array zusätzlich `"ist_bildseite": s.ist_bildseite`.
- Neues Top-Level-Feld `"bildseiten_anzahl": sum(1 for s in seiten if s.ist_bildseite)`
  — als Skalar, damit die Queue es billig per `json_extract` lesen kann.

Kein neues DB-Feld, kein UPDATE-Zusatz, keine Migration.

### 7. Backend-Ausgabe

- `hole_queue` (`backend/routers/intake_routes.py:111-167`): pro Eintrag
  `bildseiten_anzahl` via `json_extract(parse_json, '$.bildseiten_anzahl')`
  (Muster BUG-20). NULL/fehlend → 0.
- `hole_detail` (`:203-269`): liefert das `parse`-Dict bereits inkl. `seiten`
  (mit `ist_bildseite`) und `bildseiten_anzahl` — ggf. nur sicherstellen, dass
  der Wert durchgereicht wird.

### 8. Frontend — Badge (rein informativ)

`frontend/src/views/ReviewQueueView.jsx`:

- Reine Funktion `bildseiten(item)` (analog `ocrQualitaet`/`istDegradiert`):
  liefert die Anzahl bzw. `null`.
- `BildseitenBadge` in `QueueEintrag` neben den bestehenden
  `OcrBadge`/`DegradationBadge`: „🖼 N Bildseiten" (Tooltip: „N Seite(n) als
  Foto/Bild erkannt — nicht durch KI-OCR").
- Optionaler Detail-Hinweis im DetailPanel.
- **Keine Änderung an Sortierung** (Scope-Grenze wie N-02).

## Datenfluss (End-to-End)

```
Arbeitskopie-PDF
  └─ extrahiere_seiten()  → SeitenText[] (braucht_ocr je Seite, wie bisher)
       └─ Seiten-Schleife:
            braucht_ocr? → _ocr_seite():
                 Tesseract → ist_bildseite()?
                    ja  → (text, True)   GLM übersprungen
                    nein→ GLM (falls an) → (text, False)
       └─ aggregierte_textquelle(): Bildseiten ausgeblendet
       └─ parse_json: seiten[].ist_bildseite + bildseiten_anzahl
  → UPDATE intake_dokumente (unverändertes Spalten-Set)
  → hole_queue/hole_detail liefern bildseiten_anzahl
  → ReviewQueueView: BildseitenBadge
```

## Fehlerbehandlung

Keine neuen Fehlerpfade. Tesseract-/GLM-Ausfälle bleiben im bestehenden
Swallow-Verhalten (N-03): `glm_ocr_seite` → `None` bei Ausfall, Tesseract-Text
greift. Eine leere OCR-Seite (weder Text noch Bildsignal) verhält sich wie
heute (leerer Seitentext).

## Tests (TDD)

1. **Unit `ist_bildseite`** (`test_intake_text_extraktion.py`): wenig/kein Text
   → `True`; echter dichter DE-Text → `False`; kurze Seite mit echten Wörtern
   → `False` (Zusatz-Guard greift).
2. **Unit `aggregierte_textquelle`**: Textebenen-Seiten + Bildseiten → Bild
   wird ignoriert (`"textebene"`); nur Bildseiten → `"ocr"`.
3. **Pipeline-E2E** (`test_intake_pipeline_s16a.py` bzw. neue
   `test_n04_seiten_triage.py`): Dokument mit einer Textseite + einer
   „Fotoseite"; `ocr_service.ocr_seite_mit_tsv` und `glm_ocr_service.glm_ocr_seite`
   gemockt → Fotoseite `ist_bildseite=True`, **GLM für die Fotoseite NICHT
   aufgerufen** (Mock-Assertion), `parse_json.bildseiten_anzahl == 1`.
4. **Frontend-Vitest** (`ReviewQueueView.bildseiten.test.jsx`): Badge erscheint
   bei `bildseiten_anzahl > 0`, fehlt bei 0/undefined.
5. **Golden-Files unverändert grün** (`test_s16a_golden_e2e.py`,
   `test_registry_golden.py`) — reine Textebenen-Fixtures haben keine
   Bildseiten, Verhalten unverändert.

## Abnahmekriterium

Voller Backend-Lauf ohne neue Failures gegenüber der N-03-Baseline
(204f/846p); Golden-Files grün; Frontend grün. Bildseiten-Badge in der
Review-Queue sichtbar bei Dokumenten mit Fotoseiten.
