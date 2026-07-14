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

**Tesseract-Textabdeckung als kostenlose Triage.** Tesseract (lokal, billig)
läuft auf jeder OCR-Seite ohnehin und liefert je erkanntem Wort eine
Bounding-Box (Position + Größe), die wir bereits als TSV persistieren. Das
Triage-Signal ist die **Textabdeckung**: welcher Anteil der Seitenfläche von
(hinreichend sicherem) Text bedeckt ist.

- **Geringe** Textabdeckung (unter Schwelle) → **Bildseite** → GLM übersprungen.
  Robust gegen Bildunterschriften: eine 1–2-zeilige Unterschrift bedeckt nur
  wenige Prozent der Seite, unabhängig von ihrer Wortzahl.
- **Hohe** Textabdeckung → texttragende Seite → GLM läuft (wenn aktiviert),
  sonst Tesseract-Text.

Warum Fläche statt Wortzahl: eine gescannte Fotoseite mit eingebrannter
Bildunterschrift kann 15+ Wörter haben und würde eine Wortzahl-Schwelle
reißen; ihre Textabdeckung bleibt aber niedrig (schmales Textband). Eine echte
Textseite füllt große Teile der Seite. Die Fläche trennt beide Fälle sauber,
die reine Wortzahl nicht.

Das kehrt die heutige Reihenfolge in `_ocr_seite` um (von „GLM zuerst,
Tesseract als Fallback" zu „Tesseract zuerst als Triage, GLM danach nur bei
Textseiten"). Verhalten bei GLM=aus ändert sich nicht (GLM lieferte schon
heute `None` → Tesseract-Text).

**Häufigster Fall ist ohnehin sicher:** Bei digital erzeugten Gutachten steht
die Bildunterschrift meist als echte Textebene im PDF → die Seite hat genug
Textebene, `braucht_ocr=False`, kommt gar nicht erst in die OCR/GLM. Der
kritische Fall ist allein die **gescannte** Fotoseite mit eingebrannter
Unterschrift — und den fängt die Textabdeckung.

### Verworfene Alternativen

- **Wortzahl-Schwelle** (Seite gilt als Bild, wenn < N Wörter): brüchig bei
  Fotoseiten mit Bildunterschrift (Beschriftung überschreitet die Schwelle) →
  fälschlich Textseite. Verworfen zugunsten der Flächen-basierten Abdeckung.
- **Separater Pixel-/Bildflächen-Pass** (großes eingebettetes Bild deckt die
  Seite): kann Foto und **gescannten Text** nicht unterscheiden — beide sind
  ein seitenfüllendes Rasterbild. Taugt höchstens als Zusatz-Bestätigung, nicht
  als Primärsignal. Verworfen.
- **`textquelle='bild'` als neuer Spaltenwert** mit CHECK-Rebuild-Migration:
  semantisch etwas sauberer, aber Migration + Deploy-Reihenfolge-Risiko für
  minimalen Gewinn. Verworfen zugunsten migrationsfreier Flag-Lösung.

## Komponenten & Änderungen

### 1. Textabdeckung + Triage-Prädikat (rein, unit-testbar)

Zwei neue reine Funktionen in `backend/intake/text_extraktion.py`:

```
text_abdeckung(wort_boxen: list[dict], seiten_flaeche: float) -> float
ist_bildseite(abdeckung: float) -> bool
```

- **`text_abdeckung`**: Anteil der Seitenfläche, der von Text bedeckt ist.
  Summe der Wort-Box-Flächen (`breite * hoehe`) über alle Boxen mit
  Konfidenz ≥ `MIN_KONFIDENZ_WORT` und nichtleerem Text, geteilt durch
  `seiten_flaeche` (Bildbreite × Bildhöhe in Pixeln). Überlappungen werden
  nicht abgezogen (Wörter überlappen praktisch nie; die Summe ist eine gute,
  billige Näherung). Ergebnis auf `[0, 1]` geklemmt. Leere Boxenliste /
  Fläche 0 → `0.0`.
- **`ist_bildseite`**: `abdeckung < MAX_TEXT_ABDECKUNG_BILDSEITE`.
- Neue Konstanten: `MIN_KONFIDENZ_WORT` (Default 30) und
  `MAX_TEXT_ABDECKUNG_BILDSEITE` (Default 0.12). Als Modul-Konstanten,
  jederzeit nachjustierbar.
- Konsequenz einer Fehlklassifikation ist gering: eine als Bild markierte
  Seite bleibt in der Arbeitskopie sichtbar, sie wird nur nicht ge-GLM't; ihr
  (i.d.R. spärlicher) Tesseract-Text fließt weiterhin in den Dokumenttext.

### 1b. OCR liefert die Wort-Boxen mit

`backend/services/ocr_service.py`: Die Tesseract-Funktion berechnet die
Wort-Boxen für den TSV ohnehin (`image_to_data`). Sie wird so erweitert, dass
sie neben dem Text auch die **strukturierten Wortdaten**
(`left/top/width/height/conf/text`) und die **Bildmaße** zurückgibt, damit die
Abdeckung ohne erneutes Parsen des TSV-Files berechnet werden kann. Der
bestehende TSV-Schreibpfad und die Text-Rückgabe bleiben unverändert
(rückwärtskompatibel bzw. neuer paralleler Rückgabewert).

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
2. **Tesseract zuerst** (TSV persistiert wie bisher) → Text + Wort-Boxen +
   Bildmaße.
3. `text_abdeckung(...)` berechnen; `ist_bildseite(abdeckung)`? → **ja:** GLM
   überspringen, als Bildseite zurückgeben (Text = Tesseract-Ergebnis, i.d.R.
   leer/minimal, z.B. die Bildunterschrift).
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
                 Tesseract (Text + Wort-Boxen) → text_abdeckung → ist_bildseite?
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

1. **Unit `text_abdeckung` + `ist_bildseite`** (`test_intake_text_extraktion.py`):
   synthetische Wort-Boxen. Schmales Textband (Bildunterschrift, auch mit
   vielen Wörtern) → geringe Abdeckung → `ist_bildseite=True`; seitenfüllende
   Text-Boxen → hohe Abdeckung → `False`; leere Boxenliste → `0.0`; Boxen unter
   `MIN_KONFIDENZ_WORT` zählen nicht mit. **Explizit der Kern-Fall:** Fotoseite
   mit 15-Wort-Unterschrift bleibt Bildseite (Wortzahl hoch, Fläche niedrig).
2. **Unit `aggregierte_textquelle`**: Textebenen-Seiten + Bildseiten → Bild
   wird ignoriert (`"textebene"`); nur Bildseiten → `"ocr"`.
3. **Pipeline-E2E** (neue `test_n04_seiten_triage.py`): Dokument mit einer
   Textseite + einer „Fotoseite". Die Tesseract-Funktion wird gemockt und
   liefert für die Fotoseite spärliche, kleinflächige Boxen (niedrige
   Abdeckung), für die Textseite seitenfüllende Boxen; `glm_ocr_service.glm_ocr_seite`
   gemockt → Fotoseite `ist_bildseite=True` und **GLM für die Fotoseite NICHT
   aufgerufen** (Mock-Assertion), Textseite ge-GLM't; `parse_json.bildseiten_anzahl == 1`.
4. **Frontend-Vitest** (`ReviewQueueView.bildseiten.test.jsx`): Badge erscheint
   bei `bildseiten_anzahl > 0`, fehlt bei 0/undefined.
5. **Golden-Files unverändert grün** (`test_s16a_golden_e2e.py`,
   `test_registry_golden.py`) — reine Textebenen-Fixtures haben keine
   Bildseiten, Verhalten unverändert.

## Abnahmekriterium

Voller Backend-Lauf ohne neue Failures gegenüber der N-03-Baseline
(204f/846p); Golden-Files grün; Frontend grün. Bildseiten-Badge in der
Review-Queue sichtbar bei Dokumenten mit Fotoseiten.
