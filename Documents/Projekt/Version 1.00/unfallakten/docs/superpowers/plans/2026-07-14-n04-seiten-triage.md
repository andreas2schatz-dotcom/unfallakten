# N-04 Seiten-Triage vor OCR — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fotoseiten (geringe Textabdeckung) werden vor der teuren KI-OCR (GLM) erkannt, als Bildseite markiert und übersprungen; GLM läuft nur auf texttragenden Seiten.

**Architecture:** Tesseract läuft ohnehin auf jeder OCR-Seite und liefert Wort-Boxen (TSV). Aus diesen Boxen wird die Textabdeckung (bedeckter Flächenanteil) berechnet; liegt sie unter der Schwelle, ist die Seite eine Bildseite. Die Markierung lebt vollständig im bestehenden `parse_json` (kein DB-Umbau).

**Tech Stack:** Python (Flask, SQLite, pytesseract/pdf2image, pdfplumber/fitz), pytest; React + Vitest.

## Global Constraints

- **Keine DB-Migration, kein CHECK-Rebuild.** Markierung nur im `parse_json`. Die Spalte `intake_dokumente.textquelle` behält ausschließlich die bestehenden Werte `textebene|ocr|gemischt|email_text`.
- **Zielsprache Deutsch**, Benutzer ist Rechtsanwalt (nicht technisch).
- **Keine Kommentare** außer bei nicht-offensichtlichem Verhalten.
- **TDD**, häufige Commits, ein Testzyklus je Task.
- **Golden-File-Tests bleiben grün** (`test_s16a_golden_e2e.py`, `test_registry_golden.py`) — reine Textebenen-Fixtures haben keine Bildseiten.
- Schwellen als Modul-Konstanten: `MIN_KONFIDENZ_WORT = 30`, `MAX_TEXT_ABDECKUNG_BILDSEITE = 0.12`.
- Abnahme: voller Backend-Lauf ohne neue Failures ggü. N-03-Baseline (204f/846p); Frontend grün.

---

### Task 1: Textabdeckung + Bildseiten-Prädikat (reine Funktionen)

**Files:**
- Modify: `backend/intake/text_extraktion.py` (Konstanten nach Zeile 24; neue Funktionen nach `woerterbuch_quote`, ~Zeile 108)
- Test: `backend/tests/test_intake_text_extraktion.py`

**Interfaces:**
- Produces:
  - `text_abdeckung(wort_boxen: list[dict], seiten_flaeche: float) -> float` — Boxen sind Dicts `{"breite": int, "hoehe": int, "conf": float, "text": str}`.
  - `ist_bildseite(abdeckung: float) -> bool`
  - Konstanten `MIN_KONFIDENZ_WORT`, `MAX_TEXT_ABDECKUNG_BILDSEITE`.

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_intake_text_extraktion.py` ans Ende anfügen:

```python
class TestTextAbdeckung(unittest.TestCase):
    def test_schmales_textband_ist_bildseite(self):
        from backend.intake.text_extraktion import text_abdeckung, ist_bildseite
        # Bildunterschrift: 15 Woerter, aber schmales Band -> ~1.2% Flaeche
        boxen = [{"breite": 40, "hoehe": 20, "conf": 90, "text": f"w{i}"}
                 for i in range(15)]
        abdeckung = text_abdeckung(boxen, 1000 * 1000)
        self.assertLess(abdeckung, 0.12)
        self.assertTrue(ist_bildseite(abdeckung))

    def test_seitenfuellender_text_keine_bildseite(self):
        from backend.intake.text_extraktion import text_abdeckung, ist_bildseite
        boxen = [{"breite": 60, "hoehe": 30, "conf": 90, "text": f"w{i}"}
                 for i in range(300)]  # ~54% Flaeche
        abdeckung = text_abdeckung(boxen, 1000 * 1000)
        self.assertGreater(abdeckung, 0.12)
        self.assertFalse(ist_bildseite(abdeckung))

    def test_niedrige_konfidenz_zaehlt_nicht(self):
        from backend.intake.text_extraktion import text_abdeckung
        boxen = [{"breite": 500, "hoehe": 500, "conf": 10, "text": "x"}]
        self.assertEqual(text_abdeckung(boxen, 1000 * 1000), 0.0)

    def test_leere_boxen_und_flaeche_null(self):
        from backend.intake.text_extraktion import text_abdeckung
        self.assertEqual(text_abdeckung([], 1000 * 1000), 0.0)
        self.assertEqual(
            text_abdeckung([{"breite": 10, "hoehe": 10, "conf": 90, "text": "a"}], 0),
            0.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_intake_text_extraktion.py::TestTextAbdeckung -v`
Expected: FAIL mit `ImportError: cannot import name 'text_abdeckung'`

- [ ] **Step 3: Write minimal implementation**

In `backend/intake/text_extraktion.py` nach Zeile 24 (bei den Konstanten) ergänzen:

```python
MIN_KONFIDENZ_WORT = 30              # Tesseract-Konfidenz-Schwelle (N-04)
MAX_TEXT_ABDECKUNG_BILDSEITE = 0.12  # < 12% Textflaeche -> Bildseite (N-04)
```

Nach `woerterbuch_quote` (~Zeile 108) einfügen:

```python
def text_abdeckung(wort_boxen: List[dict], seiten_flaeche: float) -> float:
    """Anteil der Seitenflaeche, der von sicherem Text bedeckt ist (N-04).

    Summe der Flaechen der Wort-Boxen mit conf >= MIN_KONFIDENZ_WORT und
    nichtleerem Text, geteilt durch seiten_flaeche. Ueberlappungen werden nicht
    abgezogen (Woerter ueberlappen praktisch nie). Auf [0, 1] geklemmt.
    """
    if not wort_boxen or seiten_flaeche <= 0:
        return 0.0
    summe = 0.0
    for b in wort_boxen:
        try:
            conf = float(b.get("conf", -1))
        except (TypeError, ValueError):
            continue
        if conf < MIN_KONFIDENZ_WORT:
            continue
        if not (b.get("text") or "").strip():
            continue
        summe += float(b.get("breite", 0)) * float(b.get("hoehe", 0))
    return min(1.0, summe / seiten_flaeche)


def ist_bildseite(abdeckung: float) -> bool:
    """True, wenn die Textabdeckung unter der Bildseiten-Schwelle liegt (N-04)."""
    return abdeckung < MAX_TEXT_ABDECKUNG_BILDSEITE
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_intake_text_extraktion.py::TestTextAbdeckung -v`
Expected: PASS (4 Tests)

- [ ] **Step 5: Commit**

```bash
git add backend/intake/text_extraktion.py backend/tests/test_intake_text_extraktion.py
git commit -m "feat(intake): N-04 text_abdeckung + ist_bildseite (Flaechen-Triage)"
```

---

### Task 2: `SeitenText.ist_bildseite` + `aggregierte_textquelle` blendet Bildseiten aus

**Files:**
- Modify: `backend/intake/text_extraktion.py` (`SeitenText` Z. 73-81; `aggregierte_textquelle` Z. 222-234)
- Test: `backend/tests/test_intake_text_extraktion.py`

**Interfaces:**
- Consumes: `SeitenText` (Task 0/Bestand)
- Produces: `SeitenText.ist_bildseite: bool = False`; `aggregierte_textquelle` ignoriert Seiten mit `ist_bildseite=True`, Rand „nur Bildseiten" → `"ocr"`.

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_intake_text_extraktion.py` ans Ende anfügen:

```python
class TestAggregierteTextquelleBildseiten(unittest.TestCase):
    def _seite(self, nr, quelle, bild=False):
        from backend.intake.text_extraktion import SeitenText
        return SeitenText(nr=nr, text="", braucht_ocr=bild, ratio_salat=0.0,
                          textquelle=quelle, ist_bildseite=bild)

    def test_bildseiten_werden_ignoriert(self):
        from backend.intake.text_extraktion import aggregierte_textquelle
        seiten = [self._seite(1, "textebene"),
                  self._seite(2, "ocr", bild=True)]
        self.assertEqual(aggregierte_textquelle(seiten), "textebene")

    def test_nur_bildseiten_ergibt_ocr(self):
        from backend.intake.text_extraktion import aggregierte_textquelle
        seiten = [self._seite(1, "ocr", bild=True),
                  self._seite(2, "ocr", bild=True)]
        self.assertEqual(aggregierte_textquelle(seiten), "ocr")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_intake_text_extraktion.py::TestAggregierteTextquelleBildseiten -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'ist_bildseite'`

- [ ] **Step 3: Write minimal implementation**

In `SeitenText` (nach `hat_tabelle`, Z. 81) ergänzen:

```python
    ist_bildseite: bool = False       # N-04: Foto-/Bildseite, kein GLM
```

`aggregierte_textquelle` (Z. 222-234) ersetzen durch:

```python
def aggregierte_textquelle(seiten: List[SeitenText]) -> str:
    """Aggregiert die Seiten-textquelle zu einem Dokument-Level-Stempel.

    Bildseiten (N-04) bleiben unberuecksichtigt. Ein Dokument, das nur aus
    Bildseiten besteht, gilt als 'ocr' (bleibt im gueltigen Spalten-CHECK).
    """
    if not seiten:
        return "textebene"
    nicht_bild = [s for s in seiten if not s.ist_bildseite]
    if not nicht_bild:
        return "ocr"
    quellen = {s.textquelle for s in nicht_bild if s.textquelle}
    if len(quellen) == 1:
        return quellen.pop()
    return "gemischt"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_intake_text_extraktion.py -v`
Expected: PASS (neue Klasse + alle bestehenden Tests grün)

- [ ] **Step 5: Commit**

```bash
git add backend/intake/text_extraktion.py backend/tests/test_intake_text_extraktion.py
git commit -m "feat(intake): N-04 SeitenText.ist_bildseite + Aggregation blendet Bildseiten aus"
```

---

### Task 3: OCR liefert Wort-Boxen (`ocr_seite_daten` + `_parse_tsv`)

**Files:**
- Modify: `backend/services/ocr_service.py` (`ocr_seite_mit_tsv` Z. 130-178)
- Test: `backend/tests/test_n04_seiten_triage.py` (neu)

**Interfaces:**
- Produces:
  - `_parse_tsv(tsv: str) -> tuple[str, list[dict]]` — Boxen `{"breite": int, "hoehe": int, "conf": float, "text": str}`, nur für Zeilen mit nichtleerem Text.
  - `ocr_seite_daten(bild, tsv_ziel_pfad: str, lang: str = "deu") -> tuple[str, list[dict]]`
  - `ocr_seite_mit_tsv(...)` bleibt und liefert weiterhin nur den Text (delegiert).

- [ ] **Step 1: Write the failing test**

Neue Datei `backend/tests/test_n04_seiten_triage.py`:

```python
"""Tests fuer N-04: Seiten-Triage vor OCR (Bildseiten-Erkennung)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

_KOPF = "\t".join([
    "level", "page_num", "block_num", "par_num", "line_num", "word_num",
    "left", "top", "width", "height", "conf", "text",
])


class TestParseTsv(unittest.TestCase):
    def test_text_und_boxen(self):
        from backend.services.ocr_service import _parse_tsv
        tsv = "\n".join([
            _KOPF,
            "\t".join(["5", "1", "1", "1", "1", "1",
                       "10", "20", "40", "15", "95", "Hallo"]),
            # Strukturzeile ohne Text, conf -1 -> keine Box, kein Wort
            "\t".join(["4", "1", "1", "1", "1", "0",
                       "0", "0", "0", "0", "-1", ""]),
        ])
        text, boxen = _parse_tsv(tsv)
        self.assertEqual(text, "Hallo")
        self.assertEqual(
            boxen,
            [{"breite": 40, "hoehe": 15, "conf": 95.0, "text": "Hallo"}])

    def test_leeres_tsv(self):
        from backend.services.ocr_service import _parse_tsv
        self.assertEqual(_parse_tsv(""), ("", []))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_n04_seiten_triage.py::TestParseTsv -v`
Expected: FAIL — `ImportError: cannot import name '_parse_tsv'`

- [ ] **Step 3: Write minimal implementation**

In `backend/services/ocr_service.py` `ocr_seite_mit_tsv` (Z. 130-178) durch folgende drei Funktionen ersetzen:

```python
def _parse_tsv(tsv: str):
    """TSV-String -> (text, wort_boxen).

    Boxen nur fuer Zeilen mit nichtleerem Text; jede Box hat
    {"breite","hoehe","conf","text"}.
    """
    zeilen = tsv.strip().splitlines()
    if not zeilen:
        return "", []
    kopf = zeilen[0].split("\t")
    idx = {n: i for i, n in enumerate(kopf)}
    t_i = idx.get("text")
    if t_i is None:
        return "", []
    w_i, h_i, c_i = idx.get("width"), idx.get("height"), idx.get("conf")
    hat_box = None not in (w_i, h_i, c_i)
    woerter, boxen = [], []
    for z in zeilen[1:]:
        sp = z.split("\t")
        if len(sp) <= t_i:
            continue
        w = sp[t_i].strip()
        if not w:
            continue
        woerter.append(w)
        if hat_box and len(sp) > max(w_i, h_i, c_i):
            try:
                boxen.append({
                    "breite": int(sp[w_i]),
                    "hoehe": int(sp[h_i]),
                    "conf": float(sp[c_i]),
                    "text": w,
                })
            except (ValueError, TypeError):
                pass
    return " ".join(woerter), boxen


def ocr_seite_daten(bild, tsv_ziel_pfad: str, lang: str = "deu"):
    """OCR einer Seite mit TSV-Persistierung; liefert (text, wort_boxen).

    Wort-Boxen: [{"breite","hoehe","conf","text"}, ...] (N-04).
    Ohne Tesseract: ("", []).
    """
    if not _pruefeVerfuegbarkeit():
        return "", []
    try:
        import pytesseract
    except ImportError:
        return "", []
    try:
        tsv = pytesseract.image_to_data(
            bild, lang=lang, output_type=pytesseract.Output.STRING
        )
    except AttributeError:
        tsv = pytesseract.image_to_data(bild, lang=lang)
    except Exception as e:
        logger.error("image_to_data fehlgeschlagen: %s", e)
        return "", []

    os.makedirs(os.path.dirname(tsv_ziel_pfad), exist_ok=True)
    with open(tsv_ziel_pfad, "w", encoding="utf-8") as f:
        f.write(tsv)

    return _parse_tsv(tsv)


def ocr_seite_mit_tsv(bild, tsv_ziel_pfad: str, lang: str = "deu") -> str:
    """OCR einer einzelnen Seite mit TSV-Persistierung; liefert den Text.

    Duenner Wrapper um ``ocr_seite_daten`` (rueckwaertskompatibel).
    """
    text, _ = ocr_seite_daten(bild, tsv_ziel_pfad, lang)
    return text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_n04_seiten_triage.py::TestParseTsv -v`
Expected: PASS (2 Tests)

- [ ] **Step 5: Commit**

```bash
git add backend/services/ocr_service.py backend/tests/test_n04_seiten_triage.py
git commit -m "feat(intake): N-04 ocr_seite_daten liefert Wort-Boxen (TSV-Parser)"
```

---

### Task 4: Pipeline — `_ocr_seite` mit Triage + `parse_json`-Felder

**Files:**
- Modify: `backend/intake/pipeline.py` (Import Z. 40-43; `_ocr_seite` Z. 110-132; Seiten-Schleife Z. 181-186; `parse_dict` Z. 248-274)
- Test: `backend/tests/test_n04_seiten_triage.py`

**Interfaces:**
- Consumes: `text_abdeckung`, `ist_bildseite` (Task 1); `SeitenText.ist_bildseite` (Task 2); `ocr_service.ocr_seite_daten` (Task 3).
- Produces: `_ocr_seite(pdf_bytes, seite_nr, sha256) -> tuple[str, bool]`; `parse_json.seiten[i].ist_bildseite: bool`; `parse_json.bildseiten_anzahl: int`.

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_n04_seiten_triage.py` ans Ende anfügen:

```python
import json
import shutil
import tempfile
from unittest import mock


def _pdf_leerseiten(n: int) -> bytes:
    import fitz
    doc = fitz.open()
    for _ in range(n):
        doc.new_page(width=595, height=842)
    return doc.write()


class _FakeBild:
    size = (1000, 1000)


class TestPipelineTriage(unittest.TestCase):
    def setUp(self):
        import uuid
        self._uid = uuid.uuid4().hex
        fd, self._db = tempfile.mkstemp(prefix="n04_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt = _db.DB_PATH
        _db.DB_PATH = self._db
        os.environ["DB_PATH"] = self._db
        self._tmp = tempfile.mkdtemp(prefix="n04_files_")
        os.environ["INTAKE_ARTEFAKTE_ROOT"] = self._tmp
        from backend.db.schema_manager import init_db
        init_db()

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt
        os.environ.pop("DB_PATH", None)
        os.environ.pop("INTAKE_ARTEFAKTE_ROOT", None)
        shutil.rmtree(self._tmp, ignore_errors=True)
        try:
            os.unlink(self._db)
        except OSError:
            pass

    def _anlegen(self, pdf_bytes):
        from backend.db.database import get_connection
        arbeit = os.path.join(self._tmp, "arbeit.pdf")
        with open(arbeit, "wb") as f:
            f.write(pdf_bytes)
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO intake_dokumente "
                "(sha256, arbeitskopie_pfad, queue_status) "
                "VALUES (?, ?, 'laeuft')",
                (self._uid + "0" * (64 - len(self._uid)), arbeit))
            return cur.lastrowid

    def test_fotoseite_ueberspringt_glm(self):
        from backend.intake import pipeline
        from backend.db.database import get_connection

        did = self._anlegen(_pdf_leerseiten(2))

        foto = ("Abb. 3", [{"breite": 10, "hoehe": 10, "conf": 90, "text": "Abb"}])
        text = ("voller Seitentext hier",
                [{"breite": 600, "hoehe": 400, "conf": 90, "text": "viel"}])

        with mock.patch.object(pipeline.ocr_service, "pdf_zu_bildern",
                               return_value=[_FakeBild()]), \
             mock.patch.object(pipeline.ocr_service, "ocr_seite_daten",
                               side_effect=[foto, text]) as m_ocr, \
             mock.patch.object(pipeline.glm_ocr_service, "glm_ocr_seite",
                               return_value="GLM-TEXT") as m_glm:
            self.assertTrue(pipeline.verarbeite_dokument(did))

        self.assertEqual(m_ocr.call_count, 2)
        self.assertEqual(m_glm.call_count, 1)  # nur die Textseite

        with get_connection() as conn:
            row = conn.execute(
                "SELECT parse_json, queue_status FROM intake_dokumente WHERE id=?",
                (did,)).fetchone()
        self.assertEqual(row["queue_status"], "bereit_zur_review")
        parse = json.loads(row["parse_json"])
        self.assertEqual(parse["bildseiten_anzahl"], 1)
        self.assertTrue(parse["seiten"][0]["ist_bildseite"])
        self.assertFalse(parse["seiten"][1]["ist_bildseite"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_n04_seiten_triage.py::TestPipelineTriage -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'ocr_seite_daten'` bzw. `KeyError: 'bildseiten_anzahl'`

- [ ] **Step 3: Write minimal implementation**

Import (Z. 40-43) erweitern:

```python
from ..intake.text_extraktion import (
    extrahiere_seiten, aggregierte_textquelle, waehle_extraktions_text,
    dokument_ocr_qualitaet, SeitenText, text_abdeckung, ist_bildseite,
)
```

`_ocr_seite` (Z. 110-132) ersetzen durch:

```python
def _ocr_seite(pdf_bytes: bytes, seite_nr: int, sha256: str):
    """OCR einer Seite mit Bildseiten-Triage (N-04).

    Tesseract zuerst (billig, TSV ohnehin gebraucht) -> Textabdeckung. Foto-
    seiten (geringe Abdeckung) werden als Bildseite markiert und ueberspringen
    GLM; nur texttragende Seiten gehen (falls aktiviert) an GLM.

    Rueckgabe: (text, ist_bildseite).
    """
    tsv_verzeichnis = os.path.join(_artefakte_root(), sha256)
    tsv_pfad = os.path.join(tsv_verzeichnis, f"seite_{seite_nr}.tsv")

    bilder = ocr_service.pdf_zu_bildern(
        pdf_bytes, first_page=seite_nr, last_page=seite_nr)
    if not bilder:
        return "", False
    bild = bilder[0]

    tess_text, boxen = ocr_service.ocr_seite_daten(bild, tsv_pfad, lang="deu")
    breite, hoehe = bild.size
    if ist_bildseite(text_abdeckung(boxen, float(breite) * float(hoehe))):
        return tess_text, True

    text_glm = glm_ocr_service.glm_ocr_seite(bild)
    if text_glm:
        return text_glm, False
    return tess_text, False
```

Seiten-Schleife (Z. 181-186) ersetzen durch:

```python
            for s in seiten:
                if s.braucht_ocr:
                    s.text, s.ist_bildseite = _ocr_seite(
                        pdf_bytes, s.nr, dok["sha256"])
                    s.textquelle = "ocr"
```

Im `parse_dict` (Z. 248-274): den `seiten`-Eintrag um `ist_bildseite` erweitern und nach `akten_kandidaten` das Zählfeld ergänzen:

```python
            "seiten": [
                {"nr": s.nr, "textquelle": s.textquelle,
                 "ratio_salat": round(s.ratio_salat, 3),
                 "zeichen": len(s.text),
                 "ist_bildseite": s.ist_bildseite}
                for s in seiten
            ],
```

und (unmittelbar nach der `"akten_kandidaten": akten_kandidaten_json,`-Zeile, noch im `parse_dict`-Literal):

```python
            "bildseiten_anzahl": sum(1 for s in seiten if s.ist_bildseite),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_n04_seiten_triage.py -v`
Expected: PASS (Parser + Pipeline-Triage)

Golden-Regression:
Run: `python -m pytest backend/tests/test_s16a_golden_e2e.py backend/tests/test_intake_pipeline_s16a.py -v`
Expected: PASS (unverändert)

- [ ] **Step 5: Commit**

```bash
git add backend/intake/pipeline.py backend/tests/test_n04_seiten_triage.py
git commit -m "feat(intake): N-04 _ocr_seite Triage + bildseiten_anzahl im parse_json"
```

---

### Task 5: Backend-Ausgabe — `bildseiten_anzahl` in Queue + Detail

**Files:**
- Modify: `backend/routers/intake_routes.py` (`hole_queue` Z. 121-166; `hole_detail` `parse`-Block Z. 258-266)
- Test: `backend/tests/test_intake_routes.py`

**Interfaces:**
- Consumes: `parse_json.bildseiten_anzahl` (Task 4).
- Produces: Queue-Eintrag-Feld `bildseiten_anzahl` (int, 0 wenn fehlend); Detail `parse.bildseiten_anzahl`.

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_intake_routes.py` in Klasse `TestIntakeQueue` eine Methode ergänzen:

```python
    def test_queue_liefert_bildseiten_anzahl(self):
        parse = json.dumps({
            "text_gesamt": "x",
            "seiten": [
                {"nr": 1, "textquelle": "textebene", "ratio_salat": 0.0,
                 "zeichen": 10, "ist_bildseite": False},
                {"nr": 2, "textquelle": "ocr", "ratio_salat": 1.0,
                 "zeichen": 3, "ist_bildseite": True},
            ],
            "klassifikation": {"kandidaten": [], "hinweise": []},
            "felder": {}, "akten_kandidaten": [],
            "bildseiten_anzahl": 1,
        }, ensure_ascii=False)
        _lege_intake_pdf_an(sha_suffix="b", parse_json=parse)
        r = self.client.get("/intake/queue", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        eintraege = r.get_json()["eintraege"]
        self.assertEqual(eintraege[0]["bildseiten_anzahl"], 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_intake_routes.py::TestIntakeQueue::test_queue_liefert_bildseiten_anzahl -v`
Expected: FAIL — `KeyError: 'bildseiten_anzahl'`

- [ ] **Step 3: Write minimal implementation**

In `hole_queue`: im SELECT (nach der `akte_kandidat_top_json`-Zeile, Z. 126-127) ergänzen:

```python
            "       json_extract(i.parse_json, '$.bildseiten_anzahl') "
            "         AS bildseiten_anzahl, "
```

und im Eintrag-Dict (nach `"llm_degradiert": r["llm_degradiert"],`, Z. 161):

```python
            "bildseiten_anzahl": r["bildseiten_anzahl"] or 0,
```

In `hole_detail`: im `parse`-Block (nach `"degradation": parse.get("degradation"),`, Z. 265) ergänzen:

```python
            "bildseiten_anzahl": parse.get("bildseiten_anzahl", 0),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_intake_routes.py::TestIntakeQueue -v`
Expected: PASS (neue Methode + bestehende Queue-Tests grün)

- [ ] **Step 5: Commit**

```bash
git add backend/routers/intake_routes.py backend/tests/test_intake_routes.py
git commit -m "feat(intake): N-04 bildseiten_anzahl in Queue- und Detail-Endpoint"
```

---

### Task 6: Frontend — Bildseiten-Badge in der Review-Queue

**Files:**
- Modify: `frontend/src/views/ReviewQueueView.jsx` (Badge-Funktionen nach `DegradationBadge` ~Z. 162; Einbau in `QueueEintrag` nach Z. 195)
- Test: `frontend/src/views/ReviewQueueView.bildseiten.test.jsx` (neu)

**Interfaces:**
- Consumes: Queue-Feld `item.bildseiten_anzahl` (Task 5).
- Produces: `export function bildseiten(item) -> number | null`; interne `BildseitenBadge`.

- [ ] **Step 1: Write the failing test**

Neue Datei `frontend/src/views/ReviewQueueView.bildseiten.test.jsx`:

```javascript
import { describe, it, expect } from "vitest";
import { bildseiten } from "./ReviewQueueView.jsx";

describe("bildseiten (N-04 Bildseiten-Badge)", () => {
  it("liefert null ohne Bildseiten", () => {
    expect(bildseiten({})).toBeNull();
    expect(bildseiten({ bildseiten_anzahl: 0 })).toBeNull();
    expect(bildseiten({ bildseiten_anzahl: null })).toBeNull();
  });

  it("liefert die Anzahl bei Bildseiten", () => {
    expect(bildseiten({ bildseiten_anzahl: 3 })).toBe(3);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/views/ReviewQueueView.bildseiten.test.jsx`
Expected: FAIL — `bildseiten is not a function` / kein Export

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/views/ReviewQueueView.jsx` nach `DegradationBadge` (~Z. 162) einfügen:

```javascript
export function bildseiten(item) {
  const n = item?.bildseiten_anzahl;
  if (!n || n < 1) return null;
  return n;
}

function BildseitenBadge({ item }) {
  const n = bildseiten(item);
  if (!n) return null;
  return (
    <span title={`${n} Seite(n) als Foto/Bild erkannt — nicht durch KI-OCR.`}
      style={{
        background: T.textMuted + "22", color: T.textMuted, padding: "1px 7px",
        borderRadius: 8, fontSize: T.textXs, fontFamily: T.fontMono,
        whiteSpace: "nowrap",
      }}>
      🖼 {n}
    </span>
  );
}
```

In `QueueEintrag` direkt nach `<DegradationBadge item={item} />` (Z. 195) ergänzen:

```javascript
        <BildseitenBadge item={item} />
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/views/ReviewQueueView.bildseiten.test.jsx`
Expected: PASS (2 Tests)

Gesamter Frontend-Lauf:
Run: `cd frontend && npx vitest run`
Expected: PASS (bestehende + 2 neue)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/ReviewQueueView.jsx frontend/src/views/ReviewQueueView.bildseiten.test.jsx
git commit -m "feat(intake): N-04 Bildseiten-Badge in der Review-Queue"
```

---

## Abschluss

- [ ] **Voller Backend-Lauf:** `python -m pytest backend/tests/ -q` — keine neuen Failures ggü. N-03-Baseline (204f/846p); Golden-Files grün.
- [ ] **Voller Frontend-Lauf:** `cd frontend && npx vitest run` — grün.
- [ ] TODO.md-Eintrag N-04 als erledigt ergänzen (analog N-02/N-03).

## Self-Review (durchgeführt)

- **Spec-Abdeckung:** Textabdeckungs-Triage (Task 1), `ist_bildseite`-Feld + Aggregation (Task 2), OCR-Wort-Boxen (Task 3), `_ocr_seite`-Umbau + `parse_json`-Felder + GLM-nur-auf-Textseiten (Task 4), Queue/Detail-Ausgabe (Task 5), Badge (Task 6). Migrationsfrei durchgehend. ✔
- **Platzhalter:** keine. ✔
- **Typ-Konsistenz:** Box-Dict `{"breite","hoehe","conf","text"}` identisch in Task 1/3/4; `_ocr_seite -> (str, bool)` konsistent mit Schleife; `bildseiten_anzahl` int in Task 4/5/6. ✔
