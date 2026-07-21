# Klage-Wizard Gesamtvorschau Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine wortgenaue, abschnittsweise bearbeitbare Gesamtvorschau der Klageschrift in Schritt 11 des Klage-Wizards, die aus derselben Quelle wie das DOCX entsteht und nicht driften kann.

**Architecture:** Am bestehenden Zusammenführungspunkt in `generiere_klageschrift` liegen die 15 Dokument-Abschnitte bereits als benannte OOXML-Strings vor. Wir legen eine dünne Abschnitts-Schicht darüber (`Abschnitt`-Objekte mit Metadaten), teilen den Aufbau in `_baue_klage_dokument()` (geteilt von DOCX- und Vorschau-Pfad) und projizieren jeden Abschnitt per OOXML→Text-Extraktor in Klartext. Ein neuer Endpoint `POST /klage/vorschau` liefert die Abschnitte als JSON; Schritt 11 rendert sie und schreibt Inline-Edits über den bestehenden Override-/Manuell-Flag-Mechanismus zurück.

**Tech Stack:** Python 3 / Flask (Backend, `python-docx`-freie String-OOXML-Erzeugung), React (Frontend, Vitest), unittest (Backend-Tests).

## Global Constraints

- **RA-MICRO ist read-only** — der Vorschau-Endpoint darf **keinen** DB-Write auslösen (kein `in_db`, keine Persistenz).
- **Zielsprache Deutsch** — alle UI-Texte, Fehlermeldungen, Titel deutsch.
- **Keine unnötigen Abstraktionen** — nur umsetzen, was die Spec verlangt.
- **Keine Kommentare** im Code außer bei nicht-offensichtlichem Verhalten.
- **Single Source / kein Drift** — Vorschau-Text MUSS aus denselben OOXML-Blöcken abgeleitet werden, die auch das DOCX bilden. Kein Parallel-Aufbau, keine Wiederverwendung der clientseitigen `buildVorschauText`-Nachbildungen.
- **DOCX byte-identisch nach Refactor** — die V10-Golden-Matrix (`backend/tests/test_klage_service_docx.py::TestV10Matrix`) MUSS nach jeder Backend-Task unverändert grün bleiben.
- **Editierbar in v1 nur die vier Freitext-Abschnitte** mit vorhandenem Wizard-State: Sachverhalt (`sachverhalt_override`), Unfallhergang (`schilderung`), Rechtliche Würdigung (`rw_text_override`), Verzug (`verzug_text_override`). Anträge, Aktivlegitimation, Tabellen-Abschnitte und Rubrum bleiben read-only mit Hinweis auf den zuständigen Schritt.

---

## File Structure

**Neu:**
- `backend/word/klage_bloecke.py` — `Abschnitt`-Dataclass + `ooxml_zu_text()`-Extraktor. Eigene Datei, weil beide von Service und Tests genutzt werden und `klage_service.py` bereits 1873 Zeilen hat.
- `backend/tests/test_klage_bloecke.py` — Unit-Tests für den Extraktor.
- `frontend/src/sections/KlageGesamtvorschau.jsx` — die Vorschau-Komponente (Laden, Rendern, Inline-Edit).
- `frontend/src/sections/__tests__/KlageGesamtvorschau.test.jsx` — Vitest.

**Geändert:**
- `backend/word/klage_service.py` — Body von `generiere_klageschrift` in `_baue_klage_dokument()` extrahieren; `baue_klage_vorschau()` ergänzen.
- `backend/routers/klage_routes.py` — `akte_daten`-Aufbau in `_baue_klage_akte_daten()` extrahieren; Endpoint `POST .../klage/vorschau`.
- `backend/tests/test_klage_service_docx.py` — Paritätstest.
- `frontend/src/api.js` — `apiKlage.vorschau`.
- `frontend/src/sections/KlageWizard.jsx` — `StepZusammenfassung`: Vorschau-Panel einbinden.
- `frontend/src/sections/KlageSection.jsx` — Vorschau-Props + Inline-Edit-Rückschreiber durchreichen.

---

## Task 1: OOXML→Text-Extraktor und Abschnitt-Dataclass

**Files:**
- Create: `backend/word/klage_bloecke.py`
- Test: `backend/tests/test_klage_bloecke.py`

**Interfaces:**
- Produces:
  - `ooxml_zu_text(xml: str) -> str` — extrahiert lesbaren Klartext aus einem OOXML-Block (`<w:p>`/`<w:tbl>`-Fragmente). Absätze → Zeilenumbruch, `<w:tab/>` → Tab, Tabellenzeilen/-zellen → Zeilenumbruch/Tab, Entities zurückgewandelt, Leerzeilen zusammengefasst.
  - `Abschnitt` (dataclass): Felder `key: str`, `titel: str`, `platzhalter: str`, `xml: str`, `editierbar: bool`, `override_feld: str | None`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_klage_bloecke.py`:

```python
import unittest

from backend.word.klage_bloecke import ooxml_zu_text, Abschnitt


class TestOoxmlZuText(unittest.TestCase):
    def test_leerer_input(self):
        self.assertEqual(ooxml_zu_text(""), "")
        self.assertEqual(ooxml_zu_text(None), "")

    def test_einfacher_absatz(self):
        xml = '<w:p><w:pPr><w:jc w:val="both"/></w:pPr><w:r><w:rPr/><w:t xml:space="preserve">Hallo Welt</w:t></w:r></w:p>'
        self.assertEqual(ooxml_zu_text(xml), "Hallo Welt")

    def test_zwei_absaetze_werden_zeilen(self):
        xml = ('<w:p><w:r><w:t>Erster Satz.</w:t></w:r></w:p>'
               '<w:p><w:r><w:t>Zweiter Satz.</w:t></w:r></w:p>')
        self.assertEqual(ooxml_zu_text(xml), "Erster Satz.\nZweiter Satz.")

    def test_tab_wird_tabulator(self):
        xml = ('<w:p><w:r><w:t>BEWEIS:</w:t></w:r>'
               '<w:r><w:tab/></w:r><w:r><w:t>Zeugnis Meier</w:t></w:r></w:p>')
        self.assertEqual(ooxml_zu_text(xml), "BEWEIS:\tZeugnis Meier")

    def test_entities_werden_zurueckgewandelt(self):
        xml = '<w:p><w:r><w:t>Koch &amp; Schatz &lt;RA&gt;</w:t></w:r></w:p>'
        self.assertEqual(ooxml_zu_text(xml), "Koch & Schatz <RA>")

    def test_leerabsatz_erzeugt_keine_doppelten_leerzeilen(self):
        xml = ('<w:p><w:r><w:t>A</w:t></w:r></w:p>'
               '<w:p><w:pPr><w:jc w:val="both"/></w:pPr></w:p>'
               '<w:p><w:r><w:t>B</w:t></w:r></w:p>')
        self.assertEqual(ooxml_zu_text(xml), "A\n\nB")

    def test_tabellenzeile_und_zelle(self):
        xml = ('<w:tbl><w:tr>'
               '<w:tc><w:p><w:r><w:t>Reparaturkosten</w:t></w:r></w:p></w:tc>'
               '<w:tc><w:p><w:r><w:t>3.000,00 &#8364;</w:t></w:r></w:p></w:tc>'
               '</w:tr></w:tbl>')
        self.assertIn("Reparaturkosten", ooxml_zu_text(xml))
        self.assertIn("3.000,00", ooxml_zu_text(xml))


class TestAbschnitt(unittest.TestCase):
    def test_dataclass_felder(self):
        a = Abschnitt(key="sachverhalt", titel="Sachverhalt",
                      platzhalter="{{EINLEITUNG}}", xml="<w:p/>",
                      editierbar=True, override_feld="sachverhalt_override")
        self.assertEqual(a.key, "sachverhalt")
        self.assertTrue(a.editierbar)
        self.assertEqual(a.override_feld, "sachverhalt_override")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_klage_bloecke.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'backend.word.klage_bloecke'`

- [ ] **Step 3: Write minimal implementation**

`backend/word/klage_bloecke.py`:

```python
"""
backend/word/klage_bloecke.py
=============================
Abschnitts-Schicht ueber der Klage-OOXML-Erzeugung.

`Abschnitt` beschreibt einen Dokument-Abschnitt mit Metadaten; `ooxml_zu_text`
projiziert einen OOXML-Block in lesbaren Klartext fuer die Gesamtvorschau.
Der Text entsteht aus DEMSELBEN OOXML, das ins DOCX geht -> kein Drift.
"""
import html
import re
from dataclasses import dataclass


@dataclass
class Abschnitt:
    key: str
    titel: str
    platzhalter: str
    xml: str
    editierbar: bool
    override_feld: str | None


def ooxml_zu_text(xml: str) -> str:
    if not xml:
        return ""
    s = xml.replace("<w:tab/>", "\t")
    s = s.replace("</w:p>", "\n").replace("</w:tr>", "\n").replace("</w:tc>", "\t")
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    zeilen = [z.rstrip() for z in s.split("\n")]
    out = []
    for z in zeilen:
        if z.strip() or (out and out[-1] != ""):
            out.append(z.strip())
    return "\n".join(out).strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_klage_bloecke.py -v`
Expected: PASS (alle 9 Tests)

- [ ] **Step 5: Commit**

```bash
git add backend/word/klage_bloecke.py backend/tests/test_klage_bloecke.py
git commit -m "feat(klage): OOXML-zu-Text-Extraktor + Abschnitt-Dataclass fuer Gesamtvorschau"
```

---

## Task 2: Aufbau in `_baue_klage_dokument()` extrahieren (DOCX byte-identisch)

**Files:**
- Modify: `backend/word/klage_service.py` — Body von `generiere_klageschrift` (Zeilen 859–1845) in einen geteilten Aufbau-Helfer verschieben.
- Test: `backend/tests/test_klage_service_docx.py` (bestehende V10-Matrix als Regressionsgate)

**Interfaces:**
- Consumes: `Abschnitt`, `ooxml_zu_text` aus Task 1.
- Produces:
  - `_baue_klage_dokument(akte_daten: dict) -> dict` mit Schlüsseln `replacements: dict`, `unterschrift: bytes | None`, `abschnitte: list[Abschnitt]` (in Dokumentreihenfolge, inkl. AKTENZEICHEN/DATUM als erste zwei nicht-editierbare Abschnitte).
  - `generiere_klageschrift(akte_daten: dict) -> bytes` (Signatur unverändert) — dünner Wrapper.

Diese Task ändert **nichts** an der Textlogik. Es ist ein reiner Schnitt: der bestehende Funktionskörper wird zu `_baue_klage_dokument`, und statt am Ende `ooxml_blocks` zu bauen und zu rendern, gibt er die Abschnitte zurück. `generiere_klageschrift` rendert daraus.

- [ ] **Step 1: Regressionsgate zuerst laufen lassen (Baseline grün)**

Run: `python -m pytest backend/tests/test_klage_service_docx.py -v`
Expected: PASS (Baseline vor dem Refactor). Diese Suite ist das Sicherheitsnetz.

- [ ] **Step 2: Import ergänzen**

In `backend/word/klage_service.py`, bei den bestehenden Imports am Dateikopf ergänzen:

```python
from .klage_bloecke import Abschnitt, ooxml_zu_text
```

- [ ] **Step 3: Funktion umbenennen und Rückgabe umstellen**

`def generiere_klageschrift(akte_daten: dict) -> bytes:` (Zeile 859) umbenennen in:

```python
def _baue_klage_dokument(akte_daten: dict) -> dict:
```

Der Docstring bleibt, ergänzt um einen Satz: `Baut alle Abschnitte auf und gibt sie strukturiert zurueck (geteilt von DOCX- und Vorschau-Pfad).`

Der gesamte Körper (Zeilen 865–1843) bleibt **unverändert** bis einschließlich des `ooxml_blocks`-Dicts. Danach — den bestehenden `return _render_docx(...)` (Zeile 1845) **ersetzen** durch den Aufbau der geordneten Abschnittsliste und die Rückgabe:

```python
    abschnitte = [
        Abschnitt("aktenzeichen",      "Aktenzeichen",             "{{AKTENZEICHEN}}",           az_xml,               False, None),
        Abschnitt("datum",             "Datum",                    "{{DATUM}}",                  datum_xml,            False, None),
        Abschnitt("gericht",           "Gericht",                  "{{GERICHT_ADRESSE}}",        gericht_adresse_xml,  False, None),
        Abschnitt("klaeger",           "Kläger (Rubrum)",          "{{KLAEGER_BLOCK}}",          klaeger_xml,          False, None),
        Abschnitt("beklagte",          "Beklagte (Rubrum)",        "{{HPV_BLOCK}}",              hpv_xml,              False, None),
        Abschnitt("antraege",          "Anträge",                  "{{ANTRAEGE}}",               antraege_xml,         False, None),
        Abschnitt("sachverhalt",       "Sachverhalt",              "{{EINLEITUNG}}",             einleitung_xml,       True,  "sachverhalt_override"),
        Abschnitt("aktivlegitimation", "Aktivlegitimation",        "{{AKTIVLEGITIMATION}}",      aktivleg_xml,         False, None),
        Abschnitt("unfallhergang",     "Unfallhergang",            "{{UNFALLHERGANG}}",          unfall_xml,           True,  "schilderung"),
        Abschnitt("schaden",           "Schadenaufstellung",       "{{SCHADEN}}",                schaden_xml,          False, None),
        Abschnitt("wuerdigung",        "Rechtliche Würdigung",     "{{RECHTLICHE_WUERDIGUNG}}",  rw_xml,               True,  "rw_text_override"),
        Abschnitt("schmerzensgeld",    "Schmerzensgeld",           "{{SCHMERZENSGELD}}",         sg_xml,               False, None),
        Abschnitt("verzug",            "Verzug",                   "{{VERZUG}}",                 verzug_xml,           True,  "verzug_text_override"),
        Abschnitt("vorger_kosten",     "Vorgerichtliche Kosten",   "{{VORGERICHTLICHE_KOSTEN}}", vk_xml,               False, None),
        Abschnitt("schlussformel",     "Schlussformel",            "{{SCHLUSSFORMEL}}",          sl_xml,               False, None),
    ]
    return {
        "replacements": replacements,
        "unterschrift": unterschrift,
        "abschnitte":   abschnitte,
    }
```

**Wichtig:** Das `ooxml_blocks`-Dict (Zeilen 1827–1843) wird durch obigen Code ersetzt und entfällt hier — es wird in `generiere_klageschrift` (Step 4) aus den Abschnitten neu gebaut. `az_xml`, `datum_xml`, `unterschrift`, `replacements` und alle `*_xml` bleiben als lokale Variablen unverändert bestehen.

- [ ] **Step 4: Dünnen Wrapper `generiere_klageschrift` neu anlegen**

Direkt nach `_baue_klage_dokument` einfügen:

```python
def generiere_klageschrift(akte_daten: dict) -> bytes:
    """Generiert die Klageschrift als DOCX-Bytes (Vorlage + Platzhalter)."""
    dok = _baue_klage_dokument(akte_daten)
    ooxml_blocks = {a.platzhalter: a.xml for a in dok["abschnitte"]}
    return _render_docx(_VORLAGE, dok["replacements"], ooxml_blocks, dok["unterschrift"])
```

- [ ] **Step 5: V10-Matrix laufen lassen — DOCX muss byte-identisch bleiben**

Run: `python -m pytest backend/tests/test_klage_service_docx.py -v`
Expected: PASS (identisch zur Baseline aus Step 1 — kein Test darf sich ändern)

- [ ] **Step 6: Commit**

```bash
git add backend/word/klage_service.py
git commit -m "refactor(klage): Aufbau in _baue_klage_dokument extrahieren (DOCX unveraendert)"
```

---

## Task 3: `baue_klage_vorschau()` — strukturierte Text-Vorschau aus derselben Quelle

**Files:**
- Modify: `backend/word/klage_service.py` — Funktion `baue_klage_vorschau` ergänzen.
- Test: `backend/tests/test_klage_service_docx.py` — neue Testklasse.

**Interfaces:**
- Consumes: `_baue_klage_dokument`, `ooxml_zu_text`.
- Produces: `baue_klage_vorschau(akte_daten: dict) -> dict` in der Form
  `{"abschnitte": [{"key", "titel", "text", "editierbar", "override_feld"}]}`,
  Reihenfolge = Dokumentreihenfolge, leere Abschnitte (leerer Text) werden ausgelassen.

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_klage_service_docx.py` am Kopf den Import erweitern (Zeile 23):

```python
from backend.word.klage_service import (
    generiere_klageschrift, berechne_rvg, _beweis, baue_klage_vorschau,
)
from backend.word.klage_bloecke import ooxml_zu_text
```

Neue Testklasse ans Dateiende (vor `if __name__`):

```python
class TestBaueKlageVorschau(unittest.TestCase):
    def _akte(self):
        akte = _akte_daten([_position("fahrzeugschaden", "Fahrzeugschaden", 3000.0)])
        akte["klage_config"]["verzugsdatum"] = "2026-05-04"
        return akte

    def test_liefert_abschnitte_in_reihenfolge(self):
        res = baue_klage_vorschau(self._akte())
        keys = [a["key"] for a in res["abschnitte"]]
        self.assertIn("sachverhalt", keys)
        self.assertIn("verzug", keys)
        self.assertLess(keys.index("sachverhalt"), keys.index("verzug"))

    def test_editierbar_und_override_feld_gesetzt(self):
        res = baue_klage_vorschau(self._akte())
        by_key = {a["key"]: a for a in res["abschnitte"]}
        self.assertTrue(by_key["sachverhalt"]["editierbar"])
        self.assertEqual(by_key["sachverhalt"]["override_feld"], "sachverhalt_override")
        self.assertFalse(by_key["gericht"]["editierbar"])
        self.assertIsNone(by_key["gericht"]["override_feld"])

    def test_text_ist_klartext_ohne_xml(self):
        res = baue_klage_vorschau(self._akte())
        for a in res["abschnitte"]:
            self.assertNotIn("<w:", a["text"])
            self.assertNotIn("{{", a["text"])

    def test_kein_db_write_reine_funktion(self):
        # baue_klage_vorschau arbeitet nur auf dem uebergebenen dict
        res = baue_klage_vorschau(self._akte())
        self.assertTrue(res["abschnitte"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_klage_service_docx.py::TestBaueKlageVorschau -v`
Expected: FAIL mit `ImportError: cannot import name 'baue_klage_vorschau'`

- [ ] **Step 3: Write implementation**

In `backend/word/klage_service.py`, direkt nach `generiere_klageschrift` (aus Task 2):

```python
def baue_klage_vorschau(akte_daten: dict) -> dict:
    """Wortgenaue Text-Vorschau der Klageschrift, abschnittsweise (kein DB-Write)."""
    dok = _baue_klage_dokument(akte_daten)
    abschnitte = []
    for a in dok["abschnitte"]:
        text = ooxml_zu_text(a.xml)
        if not text.strip():
            continue
        abschnitte.append({
            "key":          a.key,
            "titel":        a.titel,
            "text":         text,
            "editierbar":   a.editierbar,
            "override_feld": a.override_feld,
        })
    return {"abschnitte": abschnitte}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_klage_service_docx.py::TestBaueKlageVorschau -v`
Expected: PASS (4 Tests)

- [ ] **Step 5: Commit**

```bash
git add backend/word/klage_service.py backend/tests/test_klage_service_docx.py
git commit -m "feat(klage): baue_klage_vorschau liefert strukturierte Text-Abschnitte"
```

---

## Task 4: Paritätstest — Vorschau-Text darf nicht vom DOCX driften

**Files:**
- Test: `backend/tests/test_klage_service_docx.py` — Paritätstest in `TestBaueKlageVorschau`.

**Interfaces:**
- Consumes: `baue_klage_vorschau`, `generiere_klageschrift`, `ooxml_zu_text`, `_document_xml`.

- [ ] **Step 1: Write the failing test**

Innerhalb `TestBaueKlageVorschau` ergänzen:

```python
    def test_vorschau_text_ist_teilmenge_des_docx(self):
        for mit_sg in (False, True):
            for ov in (False, True):
                with self.subTest(sg=mit_sg, overrides=ov):
                    akte = _akte_daten(
                        [_position("fahrzeugschaden", "Fahrzeugschaden", 3000.0)],
                        mit_schmerzensgeld=mit_sg,
                        schmerzensgeld_mindest=2000.0 if mit_sg else 0.0,
                    )
                    akte["klage_config"]["verzugsdatum"] = "2026-05-04"
                    if ov:
                        akte["unfalldetails"]["sachverhalt_override"] = (
                            "Ein frei getippter Sachverhalt.\n\nBEWEIS: Zeugnis Meier"
                        )
                    vorschau = baue_klage_vorschau(akte)
                    doc_text = ooxml_zu_text(_document_xml(generiere_klageschrift(akte)))
                    for ab in vorschau["abschnitte"]:
                        for zeile in ab["text"].split("\n"):
                            z = zeile.strip()
                            if z:
                                self.assertIn(z, doc_text,
                                    f"Abschnitt {ab['key']}: Zeile nicht im DOCX: {z!r}")
```

- [ ] **Step 2: Run test to verify it passes (kein Drift by construction)**

Run: `python -m pytest backend/tests/test_klage_service_docx.py::TestBaueKlageVorschau::test_vorschau_text_ist_teilmenge_des_docx -v`
Expected: PASS — der Vorschau-Text stammt aus denselben `*_xml`-Blöcken, daher muss jede Zeile im DOCX-Text vorkommen. Schlägt der Test fehl, ist die Single-Source-Invariante verletzt (echter Fund).

- [ ] **Step 3: Volle Klage-Testsuite als Schlussgate**

Run: `python -m pytest backend/tests/test_klage_service_docx.py backend/tests/test_klage_bloecke.py -v`
Expected: PASS (alle)

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_klage_service_docx.py
git commit -m "test(klage): Paritaetstest Vorschau-Text ist Teilmenge des DOCX"
```

---

## Task 5: Endpoint `POST /klage/vorschau` (kein DB-Write) + geteilter `akte_daten`-Aufbau

**Files:**
- Modify: `backend/routers/klage_routes.py` — `akte_daten`-Aufbau (Zeilen 1240–1447) in `_baue_klage_akte_daten()` extrahieren; neuen Endpoint ergänzen.
- Test: `backend/tests/test_klage_vorschau_route.py` (neu)

**Interfaces:**
- Consumes: `baue_klage_vorschau`.
- Produces:
  - `_baue_klage_akte_daten(akte, body: dict) -> dict` — baut das `akte_daten`-Dict (identisch zum Generieren-Pfad).
  - Route `POST /akten/<path:akte_id>/klage/vorschau` → JSON `{"abschnitte": [...]}`, Status 200; 404 wenn Akte fehlt; 422/501/500 analog Generieren.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_klage_vorschau_route.py`:

```python
import json
import unittest

from backend.app import app


class TestKlageVorschauRoute(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def _auth(self):
        # Nutzt denselben Login-Pfad wie test_klage_kw18_route.py.
        # Falls dort ein Helfer existiert, diesen verwenden.
        from backend.tests.helpers_auth import login_test_client  # ggf. vorhandenen Helfer nehmen
        return login_test_client(self.client)

    def test_vorschau_liefert_abschnitte_json(self):
        headers = self._auth()
        # Bekannte Test-Akte wie in test_klage_kw18_route.py verwenden.
        az = "55/26"
        body = {"klage_config": {"beklagte": [{
            "rolle_klage": "beklagter", "versicherung": "Test-Versicherung AG",
            "anschrift": "Teststr. 2", "plz": "12345", "ort": "Teststadt"}],
            "positionen": [{"key": "fahrzeugschaden", "label": "Fahrzeugschaden",
                            "betrag": 3000.0, "betragOriginal": 3000.0, "checked": True}]}}
        res = self.client.post(f"/akten/{az}/klage/vorschau",
                               data=json.dumps(body), content_type="application/json",
                               headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("abschnitte", data)
        keys = [a["key"] for a in data["abschnitte"]]
        self.assertIn("sachverhalt", keys)
        # editierbar-Markierung vorhanden
        self.assertTrue(any(a["editierbar"] for a in data["abschnitte"]))

    def test_unbekannte_akte_404(self):
        headers = self._auth()
        res = self.client.post("/akten/999-99/klage/vorschau",
                               data=json.dumps({"klage_config": {}}),
                               content_type="application/json", headers=headers)
        self.assertEqual(res.status_code, 404)
```

> **Hinweis für den Umsetzer:** Auth-/Test-Akten-Setup exakt so übernehmen, wie es `backend/tests/test_klage_kw18_route.py` (existiert, siehe `def generiere_klage`-Test) bereits macht. Falls dort kein `helpers_auth` existiert, den dortigen Login-Aufbau kopieren statt neu erfinden.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_klage_vorschau_route.py -v`
Expected: FAIL mit 404 auf `/klage/vorschau` (Route existiert nicht) bzw. ImportError beim Auth-Helfer — dann Auth-Setup an `test_klage_kw18_route.py` angleichen.

- [ ] **Step 3: `akte_daten`-Aufbau extrahieren**

In `backend/routers/klage_routes.py`: den Block, der `akte_daten` zusammenstellt (aktuell in `generiere_klage`, Zeilen 1244–1447: ab `body = request.get_json...` bis inkl. `akte_daten["personenschaden"] = ...`) in eine neue modulnahe Funktion verschieben:

```python
def _baue_klage_akte_daten(akte, body: dict) -> dict:
    klage_cfg = body.get("klage_config") or {}
    overrides = body.get("overrides") or {}
    for _key in ("rvg_ausserg", "rvg_ausserg_override", "rvg_bereits_gezahlt",
                 "antraege_override", "mit_feststellung_sg", "mit_feststellung_sach"):
        if overrides.get(_key) is not None:
            klage_cfg[_key] = overrides[_key]

    def _override(key, db_val):
        v = overrides.get(key)
        return v if v is not None else db_val

    az = akte.aktenzeichen
    # ... GESAMTER bestehender Aufbau unveraendert (schaden_dict, reg_agg, mandant,
    #     wdm, akte_daten, personenschaden) ...
    return akte_daten
```

`generiere_klage` (Zeile 1234) wird entsprechend gekürzt:

```python
@klage_bp.route("/generieren", methods=["POST"])
@login_erforderlich
def generiere_klage(akte_id: str):
    akte = hole_akte_by_id(akte_id)
    if not akte:
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    body = request.get_json(silent=True) or {}
    akte_daten = _baue_klage_akte_daten(akte, body)
    try:
        doc_bytes = generiere_klageschrift(akte_daten)
    except FileNotFoundError as e:
        return _err(str(e), 501)
    except ValueError as e:
        logger.warning("Klage-Generierung abgelehnt (422): %s", e)
        return _err(str(e), 422)
    except Exception as e:
        logger.error("Klage-Generierung fehlgeschlagen: %s", e, exc_info=True)
        return _err(f"Fehler beim Erstellen der Klageschrift: {e}", 500)
    # ... bestehender Download-/DB-Teil unveraendert ab az_clean ...
```

- [ ] **Step 4: Vorschau-Route ergänzen**

Import oben in `klage_routes.py` erweitern (dort wo `generiere_klageschrift` importiert wird):

```python
from backend.word.klage_service import generiere_klageschrift, baue_klage_vorschau
```

Neue Route direkt nach `generiere_klage`:

```python
@klage_bp.route("/vorschau", methods=["POST"])
@login_erforderlich
def vorschau_klage(akte_id: str):
    """POST /akten/<az>/klage/vorschau — strukturierte Text-Vorschau, kein DB-Write."""
    akte = hole_akte_by_id(akte_id)
    if not akte:
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    body = request.get_json(silent=True) or {}
    akte_daten = _baue_klage_akte_daten(akte, body)
    try:
        return jsonify(baue_klage_vorschau(akte_daten))
    except FileNotFoundError as e:
        return _err(str(e), 501)
    except ValueError as e:
        logger.warning("Klage-Vorschau abgelehnt (422): %s", e)
        return _err(str(e), 422)
    except Exception as e:
        logger.error("Klage-Vorschau fehlgeschlagen: %s", e, exc_info=True)
        return _err(f"Fehler bei der Vorschau: {e}", 500)
```

> `jsonify` ist in `klage_routes.py` bereits importiert (Flask). Falls nicht, `from flask import jsonify` ergänzen.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_klage_vorschau_route.py backend/tests/test_klage_kw18_route.py -v`
Expected: PASS (neue Route grün, Generieren-Route unverändert grün)

- [ ] **Step 6: Commit**

```bash
git add backend/routers/klage_routes.py backend/tests/test_klage_vorschau_route.py
git commit -m "feat(klage): POST /klage/vorschau + geteilter akte_daten-Aufbau"
```

---

## Task 6: API-Client `apiKlage.vorschau`

**Files:**
- Modify: `frontend/src/api.js` — im `apiKlage`-Objekt (vor `generieren`, Zeile 319).

**Interfaces:**
- Consumes: bestehende `request()`-Hilfe.
- Produces: `apiKlage.vorschau(az, klagenConfig, overrides=null) -> Promise<{abschnitte: [...]}>`.

- [ ] **Step 1: Implementierung ergänzen**

In `frontend/src/api.js`, direkt vor `generieren:` (Zeile 319) einfügen:

```javascript
  vorschau: (az, klagenConfig, overrides = null) => request(`/akten/${az}/klage/vorschau`, {
    method: 'POST',
    body: JSON.stringify(
      overrides !== null
        ? { klage_config: klagenConfig, overrides }
        : { klage_config: klagenConfig }
    ),
  }),
```

- [ ] **Step 2: Manuell verifizieren, dass die Struktur passt**

Run: `cd frontend && npx vite build --mode development 2>&1 | head -5` (nur Syntax-Check des Bundles) — Alternativ im nächsten Vitest mitgetestet. Expected: kein Syntaxfehler.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api.js
git commit -m "feat(klage): apiKlage.vorschau Client-Aufruf"
```

---

## Task 7: Gesamtvorschau-Komponente (Laden + Rendern, read-only)

**Files:**
- Create: `frontend/src/sections/KlageGesamtvorschau.jsx`
- Test: `frontend/src/sections/__tests__/KlageGesamtvorschau.test.jsx`

**Interfaces:**
- Consumes: `apiKlage.vorschau`.
- Produces: React-Komponente
  `<KlageGesamtvorschau akteId cfg overrides onEditAbschnitt />`, wobei
  `cfg` das Generieren-Config-Objekt und `overrides` das Override-Objekt sind (dieselben, die `wizardGenerieren` baut). `onEditAbschnitt(overrideFeld, neuerText)` wird bei Inline-Speichern gerufen (in Task 8 verdrahtet; hier nur Prop-Durchreichung).

- [ ] **Step 1: Write the failing test**

`frontend/src/sections/__tests__/KlageGesamtvorschau.test.jsx`:

```jsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { KlageGesamtvorschau } from '../KlageGesamtvorschau';

vi.mock('../../api.js', () => ({
  apiKlage: {
    vorschau: vi.fn(() => Promise.resolve({ abschnitte: [
      { key: 'gericht', titel: 'Gericht', text: 'Amtsgericht Offenbach',
        editierbar: false, override_feld: null },
      { key: 'sachverhalt', titel: 'Sachverhalt', text: 'Der Beklagte fuhr auf.',
        editierbar: true, override_feld: 'sachverhalt_override' },
    ] })),
  },
}));

import { apiKlage } from '../../api.js';

describe('KlageGesamtvorschau', () => {
  beforeEach(() => vi.clearAllMocks());

  it('laedt erst nach Klick (kein Auto-Load)', () => {
    render(<KlageGesamtvorschau akteId="55/26" cfg={{}} overrides={{}} onEditAbschnitt={() => {}} />);
    expect(apiKlage.vorschau).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: /Vorschau erzeugen/i })).toBeInTheDocument();
  });

  it('rendert Abschnitte nach Klick', async () => {
    render(<KlageGesamtvorschau akteId="55/26" cfg={{ a: 1 }} overrides={{ b: 2 }} onEditAbschnitt={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /Vorschau erzeugen/i }));
    await waitFor(() => expect(screen.getByText('Der Beklagte fuhr auf.')).toBeInTheDocument());
    expect(apiKlage.vorschau).toHaveBeenCalledWith('55/26', { a: 1 }, { b: 2 });
    expect(screen.getByText('Amtsgericht Offenbach')).toBeInTheDocument();
  });

  it('zeigt "Bearbeiten" nur bei editierbaren Abschnitten', async () => {
    render(<KlageGesamtvorschau akteId="55/26" cfg={{}} overrides={{}} onEditAbschnitt={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /Vorschau erzeugen/i }));
    await waitFor(() => screen.getByText('Der Beklagte fuhr auf.'));
    // genau ein Bearbeiten-Button (fuer den editierbaren Sachverhalt)
    expect(screen.getAllByRole('button', { name: /Bearbeiten/i })).toHaveLength(1);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/sections/__tests__/KlageGesamtvorschau.test.jsx`
Expected: FAIL — `KlageGesamtvorschau` existiert nicht.

- [ ] **Step 3: Komponente implementieren**

`frontend/src/sections/KlageGesamtvorschau.jsx`:

```jsx
import { useState } from 'react';
import { apiKlage } from '../api.js';

export function KlageGesamtvorschau({ akteId, cfg, overrides, onEditAbschnitt }) {
  const [abschnitte, setAbschnitte] = useState(null);
  const [laedt, setLaedt] = useState(false);
  const [fehler, setFehler] = useState('');
  const [editKey, setEditKey] = useState(null);
  const [editText, setEditText] = useState('');

  async function laden() {
    setLaedt(true); setFehler('');
    try {
      const res = await apiKlage.vorschau(akteId, cfg, overrides);
      setAbschnitte(res.abschnitte || []);
    } catch (e) {
      setFehler(e?.message || 'Vorschau fehlgeschlagen.');
    } finally {
      setLaedt(false);
    }
  }

  function startEdit(ab) {
    setEditKey(ab.key);
    setEditText(ab.text);
  }

  async function speichereEdit(ab) {
    onEditAbschnitt(ab.override_feld, editText);
    setEditKey(null);
    await laden();
  }

  return (
    <div>
      <button type="button" onClick={laden} disabled={laedt}>
        {laedt ? 'Erzeuge Vorschau …' : 'Vorschau erzeugen'}
      </button>
      {fehler && <div role="alert" style={{ color: '#c0392b', marginTop: 8 }}>{fehler}</div>}
      {abschnitte && (
        <div style={{ marginTop: 12 }}>
          {abschnitte.map((ab) => (
            <section key={ab.key} style={{ borderBottom: '1px solid #e5e5e5', padding: '10px 0' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <strong style={{ flex: 1 }}>{ab.titel}</strong>
                {ab.editierbar && editKey !== ab.key && (
                  <button type="button" onClick={() => startEdit(ab)}>✎ Bearbeiten</button>
                )}
                {!ab.editierbar && (
                  <span style={{ fontSize: '0.75rem', color: '#888' }}>
                    Änderbar über den zugehörigen Schritt
                  </span>
                )}
              </div>
              {editKey === ab.key ? (
                <div>
                  <textarea value={editText} onChange={(e) => setEditText(e.target.value)}
                    rows={Math.max(4, ab.text.split('\n').length + 1)} style={{ width: '100%' }} />
                  <button type="button" onClick={() => speichereEdit(ab)}>Übernehmen</button>
                  <button type="button" onClick={() => setEditKey(null)}>Abbrechen</button>
                </div>
              ) : (
                <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', margin: '6px 0 0' }}>
                  {ab.text}
                </pre>
              )}
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/sections/__tests__/KlageGesamtvorschau.test.jsx`
Expected: PASS (3 Tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/sections/KlageGesamtvorschau.jsx frontend/src/sections/__tests__/KlageGesamtvorschau.test.jsx
git commit -m "feat(klage): KlageGesamtvorschau-Komponente (Laden + abschnittsweises Rendern)"
```

---

## Task 8: Inline-Edit-Rückschreiber + Einbindung in Schritt 11

**Files:**
- Modify: `frontend/src/sections/KlageSection.jsx` — Rückschreib-Mapping + Props an `StepZusammenfassung`.
- Modify: `frontend/src/sections/KlageWizard.jsx` — `StepZusammenfassung` rendert die Vorschau.
- Test: `frontend/src/sections/__tests__/KlageGesamtvorschau.test.jsx` — Rückschreib-Test ergänzen.

**Interfaces:**
- Consumes: `KlageGesamtvorschau`, bestehende Wizard-State-Setter aus `KlageSection.jsx`.
- Produces: `onEditAbschnitt(override_feld, text)` schreibt in den passenden Wizard-State und setzt das jeweilige Manuell-Flag (identisch zum Schritt-Mechanismus). Danach lädt die Vorschau neu (bereits in Task 7 nach `onEditAbschnitt` gekapselt).

Mapping `override_feld → State` (aus `KlageSection.jsx` verifiziert):

| override_feld | Text-Setter | Manuell-Setter |
|---|---|---|
| `sachverhalt_override` | `setWizardSachverhaltText` | `setWizardSachverhaltManuell` |
| `schilderung` | `setWizardUnfallText` | — (kein Flag) |
| `rw_text_override` | `setWizardRwText` | — (kein Flag) |
| `verzug_text_override` | `setWizardVerzugText` | `setWizardVerzugManuell` |

- [ ] **Step 1: Rückschreib-Test ergänzen**

In `frontend/src/sections/__tests__/KlageGesamtvorschau.test.jsx` neuen Test anhängen:

```jsx
  it('ruft onEditAbschnitt mit override_feld und neuem Text', async () => {
    const onEdit = vi.fn();
    render(<KlageGesamtvorschau akteId="55/26" cfg={{}} overrides={{}} onEditAbschnitt={onEdit} />);
    fireEvent.click(screen.getByRole('button', { name: /Vorschau erzeugen/i }));
    await waitFor(() => screen.getByText('Der Beklagte fuhr auf.'));
    fireEvent.click(screen.getByRole('button', { name: /Bearbeiten/i }));
    const ta = screen.getByRole('textbox');
    fireEvent.change(ta, { target: { value: 'Neu getippter Sachverhalt.' } });
    fireEvent.click(screen.getByRole('button', { name: /Übernehmen/i }));
    await waitFor(() =>
      expect(onEdit).toHaveBeenCalledWith('sachverhalt_override', 'Neu getippter Sachverhalt.'));
  });
```

- [ ] **Step 2: Run test to verify it passes (Komponente kann das schon)**

Run: `cd frontend && npx vitest run src/sections/__tests__/KlageGesamtvorschau.test.jsx`
Expected: PASS — `onEditAbschnitt` wird bereits in Task 7 aufgerufen; dieser Test pinnt das Verhalten.

- [ ] **Step 3: Rückschreiber in `KlageSection.jsx` ergänzen**

In `frontend/src/sections/KlageSection.jsx`, im Komponentenkörper nahe `wizardGenerieren` (Zeile 672) einfügen:

```javascript
  const onVorschauEdit = (overrideFeld, text) => {
    const map = {
      sachverhalt_override: [setWizardSachverhaltText, setWizardSachverhaltManuell],
      schilderung:          [setWizardUnfallText,      null],
      rw_text_override:     [setWizardRwText,          null],
      verzug_text_override: [setWizardVerzugText,      setWizardVerzugManuell],
    };
    const eintrag = map[overrideFeld];
    if (!eintrag) return;
    const [setText, setManuell] = eintrag;
    setText(text);
    if (setManuell) setManuell(true);
  };
```

Das `cfg`/`overrides`-Paar für die Vorschau ist identisch zu dem in `wizardGenerieren` (Zeilen 675–701). Um Duplikation zu vermeiden, diese beiden Objekte als Memo herausziehen — direkt vor `wizardGenerieren`:

```javascript
  const baueCfgUndOverrides = () => ({
    cfg: {
      gericht,
      beklagte:               beklagte.filter(b => b.rolle_klage === "klaeger" || b.checked),
      positionen:             wizardPos,
      mit_schmerzensgeld:     wizardMitSG,
      schmerzensgeld_mindest: wizardMitSG ? wizardSGMind : 0,
      verzugsdatum:           zinsenAb === "verzug" ? (wizardVerzugDatum || null) : null,
      verzug_schreiben_datum: wizardVerzugDokDatum || null,
      zinsen_ab:              zinsenAb,
      haftungsquote:          wizardHq,
      haftungsquote_typ:      wizardHqTyp,
    },
    overrides: {
      aktivlegitimation_typ:      aktLegTyp,
      aktivlegitimation_freigabe: aktLegFreigabe,
      aktivlegitimation_datum:    aktLegDatum || null,
      sachverhalt_override:       wizardSachverhaltText || null,
      schilderung:                wizardUnfallText || null,
      rw_text_override:           wizardRwText     || null,
      verzug_text_override:       wizardVerzugText || null,
      mit_feststellung_sg:        wizardMitFestSg,
      mit_feststellung_sach:      wizardMitFestSach,
      antraege_override:          komponiereAntraege(wizardAntraegeText, wizardGebuehrenText) || null,
      rvg_ausserg:                wizardRvgAussergData,
      rvg_ausserg_override:       baueRvgAussergOverride(wizardRvgAussergOv),
      rvg_bereits_gezahlt:        wizardRvgBereitsGezahlt ? parseFloat(wizardRvgBereitsGezahlt) : null,
    },
  });
```

Und `wizardGenerieren` (Zeilen 674–701) so umstellen, dass es `baueCfgUndOverrides()` nutzt:

```javascript
      const { cfg, overrides } = baueCfgUndOverrides();
      await apiKlage.generieren(akteId, cfg, overrides);
```

- [ ] **Step 4: Props an `StepZusammenfassung` durchreichen**

Im `<StepZusammenfassung .../>`-Aufruf in `KlageSection.jsx` (um Zeile 819) ergänzen:

```jsx
          akteId={akteId}
          vorschauCfgFn={baueCfgUndOverrides}
          onVorschauEdit={onVorschauEdit}
```

- [ ] **Step 5: Vorschau in `StepZusammenfassung` rendern**

In `frontend/src/sections/KlageWizard.jsx`: Import oben ergänzen:

```jsx
import { KlageGesamtvorschau } from './KlageGesamtvorschau';
```

Die `StepZusammenfassung`-Signatur (Zeile 1713) um `akteId, vorschauCfgFn, onVorschauEdit` erweitern. Direkt **vor** dem Download-Button (Zeile 1858, `<button onClick={onGenerieren} ...>`) einfügen:

```jsx
      {akteId && vorschauCfgFn && (
        <div style={{ marginBottom: "1rem", padding: "1rem 1.25rem",
          background: T.surface, borderRadius: 10, border: `1px solid ${T.border}` }}>
          <div style={{ fontFamily: PLEX, fontSize: "0.72rem", fontWeight: 700,
            color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.1em",
            marginBottom: "0.75rem" }}>
            Gesamtvorschau
          </div>
          <KlageGesamtvorschau
            akteId={akteId}
            cfg={vorschauCfgFn().cfg}
            overrides={vorschauCfgFn().overrides}
            onEditAbschnitt={onVorschauEdit}
          />
        </div>
      )}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/sections/__tests__/KlageGesamtvorschau.test.jsx`
Expected: PASS (4 Tests)

- [ ] **Step 7: Manuelle End-to-End-Verifikation im laufenden Wizard**

Docker-Dev-Umgebung starten (siehe `docs/STATE.md`), Klage-Wizard einer Test-Akte bis Schritt 11 öffnen:
1. „Vorschau erzeugen" klicken → Abschnitte erscheinen.
2. Beim Sachverhalt „✎ Bearbeiten" → Text ändern → „Übernehmen" → Vorschau lädt neu und zeigt den geänderten Text.
3. „Als Word generieren" → im DOCX steht derselbe geänderte Sachverhalt (Single-Source-Beleg).
Expected: alle drei Schritte wie beschrieben; keine Konsolenfehler.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/sections/KlageSection.jsx frontend/src/sections/KlageWizard.jsx frontend/src/sections/__tests__/KlageGesamtvorschau.test.jsx
git commit -m "feat(klage): Gesamtvorschau in Schritt 11 mit Inline-Edit-Rueckschreiber"
```

---

## Self-Review

**1. Spec coverage:**
- Backend: JSON-Antwort mit `{abschnitte:[{key,titel,text,editierbar,override_feld}]}` → Task 3. `schritt_nr`-Hinweis: bewusst ins Frontend verlagert (entkoppelt von der noch nicht gemergten Paket-2-Nummerierung; nicht-editierbare Abschnitte tragen den generischen Hinweis „Änderbar über den zugehörigen Schritt"). Endpoint `POST /klage/vorschau/<akte>` ohne Persistenz → Task 5.
- „Eine Quelle, kein Drift" → Tasks 2–4 (geteiltes `_baue_klage_dokument`, Paritätstest).
- Frontend: „Vorschau erzeugen"-Knopf, kein Auto-Load, durchscrollbar → Task 7. Abschnittsweises Inline-Edit schreibt Override + Manuell-Flag, danach Neu-Laden → Task 8. Nicht-editierbare Kennzeichnung → Task 7. Download-Knopf bleibt daneben → unverändert in Schritt 11.
- Kopplung Paket 1/2: Inline-Edits laufen über dieselben State-Setter → Dirty-Status, Entwurf-Speichern und `TextVeraltetBadge` greifen unverändert (Task 8).
- Tests: Parität (Task 4), Endpoint (Task 5), Vitest Laden/Edit/nicht-editierbar (Tasks 7–8).
- Bewusst nicht im Scope (Spec): keine Druckbild-Simulation, kein PDF, kein Edit nicht-überschreibbarer Abschnitte, keine Autosaves — eingehalten. Zusätzlich in v1 read-only: Anträge/Aktivlegitimation (siehe Global Constraints; Ausbau später, da Anträge FE-seitig komponiert und `aktivlegitimation_text_override` keinen Wizard-State hat).

**2. Placeholder scan:** Keine TBD/TODO; alle Code-Schritte enthalten vollständigen Code. Einziger bewusster Verweis: das Auth-/Test-Akten-Setup in Task 5 folgt `test_klage_kw18_route.py` — konkret dort abzulesen, kein erfundener Helfer.

**3. Type consistency:** `Abschnitt`-Felder (`key, titel, platzhalter, xml, editierbar, override_feld`) identisch in Task 1 (Definition), Task 2 (Konstruktion) und Task 3 (Auslesen). `baue_klage_vorschau`-Rückgabe (`abschnitte`-Liste mit `key/titel/text/editierbar/override_feld`) identisch in Task 3, 4 (Test), 5 (Endpoint), 6/7 (Frontend-Konsum). `ooxml_zu_text` einheitlich importiert. `apiKlage.vorschau(az, cfg, overrides)`-Signatur konsistent zwischen Task 6 und dem Aufruf in Task 7.
