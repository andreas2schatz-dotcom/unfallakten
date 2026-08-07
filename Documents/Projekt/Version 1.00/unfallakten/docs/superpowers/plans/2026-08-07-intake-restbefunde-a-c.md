# Intake-Restbefunde (a) Marker-Wortgrenze + (c) Datums-Scheinkonflikt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zwei Restbefunde aus Akte 1280/25 fixen: (a) Klassifikations-Marker treffen keine Teilwörter mehr („Rechnung" ≠ „**Ab**rechnung"), (c) `llm_konflikt` meldet keinen Scheinkonflikt mehr, wenn LLM und Regex denselben Tag in unterschiedlichen Formaten liefern („2026-04-28" vs. „28.04.2026").

**Architecture:** (a) In `backend/intake/klassifikator.py` wird der Substring-Vergleich `m.lower() in text_norm` durch Wortgrenzen-Matching mit Lookarounds ersetzt (`(?<!\w)…(?!\w)` statt `\b`, weil Marker wie „Control€xpert" mit Nicht-Wort-Zeichen enden können — Lektion aus dem Gutachten-Parser-Debugging). (c) In `backend/intake/extraktion.py` werden in der Konflikt-Schleife beide Werte vor dem Vergleich auf ISO normalisiert — nur für die Muster DD.MM.YYYY ↔ YYYY-MM-DD, alles andere bleibt unverändert.

**Tech Stack:** Python 3 (Docker-Container `unfallakten-backend-dev`), `re`, `unittest`/`pytest`.

## Global Constraints

- Tests IM CONTAINER: `docker exec unfallakten-backend-dev python -m pytest backend/tests/<datei> -q`.
- Golden-/E2E-Gates für (a): `test_registry_golden.py`, `test_s16b_klassifikation_e2e.py`, `test_intake_klassifikator.py` müssen grün bleiben — Mehrwort-Marker („HDI Global", „VHV Allgemeine") und Sonderzeichen-Marker („Control€xpert") dürfen nicht kaputtgehen. Bricht ein Golden-Test, NICHT den Test umbiegen, sondern melden (Verhaltensfrage, z. B. Flexionsformen wie „Prüfberichte").
- Git-Wurzel = Home — NIE `git add -A`; Branch `abschlussbericht`; Commit-Trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Vorbestehende Failures (2× `test_intake_routes`, `test_modul7`) nicht anfassen.
- Keine Code-Kommentare außer bei nicht-offensichtlichem Verhalten.

---

### Task 1: Marker-Wortgrenzen-Matching (Befund a)

**Files:**
- Modify: `backend/intake/klassifikator.py` (Vergleich in `klassifiziere_stufe1`, Zeile 83–86; neuer Modul-Helfer `_marker_im_text`; `import re` ergänzen falls nicht vorhanden)
- Test: `backend/tests/test_intake_klassifikator.py` (neue Testklasse anhängen)

**Interfaces:**
- Consumes: `registry.klassen[klasse]["marker"]` (Liste von Strings), `text_norm` (lowercased Volltext).
- Produces: `_marker_im_text(marker: str, text_norm: str) -> bool`; Trefferverhalten von `klassifiziere_stufe1` sonst unverändert (Konfidenzformel, Hinweise-Format).

- [ ] **Step 1: Write the failing tests**

An `backend/tests/test_intake_klassifikator.py` anhängen (Import-/Setup-Stil der Datei übernehmen; die Datei hat bereits ein Registry-Stub-Muster — falls nicht direkt passend, Mini-Registry wie folgt):

```python
class TestMarkerWortgrenze(unittest.TestCase):
    """Befund 1280/25 (a): Marker 'Rechnung' traf als Teilwort in
    'Abrechnungsschreiben' -> Dok 517 wurde als rechnung eingestuft."""

    def _registry(self, marker):
        class _R:
            klassen = {"testklasse": {"marker": marker}}
        return _R()

    def _klassifiziere(self, text, marker):
        from backend.intake.klassifikator import klassifiziere_stufe1
        kandidaten, _ = klassifiziere_stufe1(text, [], self._registry(marker))
        return kandidaten

    def test_marker_trifft_kein_teilwort(self):
        k = self._klassifiziere(
            "Wir übersenden das Abrechnungsschreiben zur Abrechnung.",
            ["Rechnung"])
        self.assertEqual(k, [])

    def test_marker_trifft_ganzes_wort(self):
        k = self._klassifiziere("Anbei die Rechnung: 123", ["Rechnung"])
        self.assertEqual(len(k), 1)
        self.assertEqual(k[0].klasse, "testklasse")

    def test_marker_trifft_wort_vor_satzzeichen_und_zeilenende(self):
        k = self._klassifiziere("Betreff: Rechnung\nvom 01.01.2026", ["Rechnung"])
        self.assertEqual(len(k), 1)

    def test_mehrwort_marker_weiterhin_treffer(self):
        k = self._klassifiziere(
            "Die VHV Allgemeine Versicherung AG teilt mit", ["VHV Allgemeine"])
        self.assertEqual(len(k), 1)

    def test_sonderzeichen_marker_weiterhin_treffer(self):
        k = self._klassifiziere(
            "Prüfbericht der Control€xpert GmbH", ["Control€xpert"])
        self.assertEqual(len(k), 1)

    def test_bindestrich_marker_weiterhin_treffer(self):
        k = self._klassifiziere("Der CE-Prüfbericht liegt bei", ["CE-Prüfbericht"])
        self.assertEqual(len(k), 1)
```

(Falls `test_intake_klassifikator.py` `pytest`-Stil statt `unittest` nutzt: Testinhalte identisch übernehmen, Stil der Datei folgen.)

- [ ] **Step 2: Run tests to verify the RED case fails**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_intake_klassifikator.py -q`
Expected: `test_marker_trifft_kein_teilwort` FAIL (Substring-Match liefert heute einen Kandidaten), die übrigen neuen Tests PASS (dokumentieren das zu erhaltende Verhalten), Bestand PASS.

- [ ] **Step 3: Implement**

In `backend/intake/klassifikator.py` (Modulebene, vor `klassifiziere_stufe1`; `import re` bei den Imports ergänzen, falls es fehlt):

```python
def _marker_im_text(marker: str, text_norm: str) -> bool:
    """Wortgrenzen-Match statt Substring ('Rechnung' != 'Abrechnung').

    Lookarounds statt \\b, weil Marker mit Nicht-Wort-Zeichen enden
    koennen ('Control€xpert') -- dort waere \\b wirkungslos."""
    muster = r"(?<!\w)" + re.escape(marker.lower()) + r"(?!\w)"
    return re.search(muster, text_norm) is not None
```

Und in der Schleife (Zeile 84) den Vergleich ersetzen:

```python
            if m and _marker_im_text(m, text_norm):
```

- [ ] **Step 4: Run tests + Golden-Gates**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_intake_klassifikator.py backend/tests/test_registry_golden.py backend/tests/test_s16b_klassifikation_e2e.py backend/tests/test_s16a_golden_e2e.py -q`
Expected: alle passed. Bricht ein Golden-/E2E-Test: STOPP und melden (nicht fixen) — das wäre eine echte Verhaltensfrage.

- [ ] **Step 5: Commit**

```bash
git add backend/intake/klassifikator.py backend/tests/test_intake_klassifikator.py
git commit -m "fix(intake): Marker-Matching mit Wortgrenzen - Rechnung trifft nicht mehr Abrechnung (Befund 1280/25)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Datums-Normalisierung im Konflikt-Vergleich (Befund c)

**Files:**
- Modify: `backend/intake/extraktion.py` (neuer Modul-Helfer `_datum_iso`; Konflikt-Schleife am Ende von `extrahiere_felder`)
- Test: `backend/tests/test_intake_extraktion.py` (neue Testklasse anhängen)

**Interfaces:**
- Consumes: Konflikt-Schleife in `extrahiere_felder` (iteriert `regex_werte`, vergleicht `str(llm_wert).strip() != str(regex_wert).strip()`).
- Produces: `_datum_iso(wert: str) -> str | None` (DD.MM.YYYY und YYYY-MM-DD → „YYYY-MM-DD", sonst None); Scheinkonflikte gleicher Tage entfallen, echte Konflikte bleiben.

- [ ] **Step 1: Write the failing tests**

An `backend/tests/test_intake_extraktion.py` anhängen (vor `if __name__`; nutzt das vorhandene `_mini_registry_mit_abrechnung`-Muster):

```python
class TestDatumScheinkonflikt(unittest.TestCase):
    """Befund 1280/25 (c): llm_konflikt meldete schreibdatum '2026-04-28'
    (LLM) vs. '28.04.2026' (Regex) als Konflikt, obwohl derselbe Tag."""

    def _extrahiere(self, text, llm_werte):
        from backend.intake import extraktion
        registry = _mini_registry_mit_abrechnung()
        with mock.patch(
            "backend.intake.extraktion.llm_service.extrahiere_nach_schema",
            return_value=llm_werte,
        ):
            return extraktion.extrahiere_felder(
                text, "abrechnungsschreiben", registry)

    def test_gleicher_tag_verschiedene_formate_kein_konflikt(self):
        ergebnis = self._extrahiere(
            "Schadennummer: 12-345-67890 Datum 28.04.2026",
            {"schadennummer": "12-345-67890",
             "schreibdatum": "2026-04-28"})
        self.assertNotIn("llm_konflikt", ergebnis)

    def test_echter_datums_konflikt_bleibt(self):
        ergebnis = self._extrahiere(
            "Schadennummer: 12-345-67890 Datum 28.04.2026",
            {"schadennummer": "12-345-67890",
             "schreibdatum": "2026-04-29"})
        self.assertIn("llm_konflikt", ergebnis)
        self.assertIn("schreibdatum", ergebnis["llm_konflikt"])

    def test_nicht_datums_werte_unveraendert(self):
        ergebnis = self._extrahiere(
            "Schadennummer: 12-345-67890 Datum 28.04.2026",
            {"schadennummer": "99-999-99999",
             "schreibdatum": "28.04.2026"})
        self.assertIn("llm_konflikt", ergebnis)
        self.assertIn("schadennummer", ergebnis["llm_konflikt"])
```

- [ ] **Step 2: Run tests to verify the RED case fails**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_intake_extraktion.py -q`
Expected: `test_gleicher_tag_verschiedene_formate_kein_konflikt` FAIL (heute wird der Formatunterschied als Konflikt gestempelt), die beiden anderen PASS, Bestand PASS.

- [ ] **Step 3: Implement**

In `backend/intake/extraktion.py` (Modulebene, nach `_erkenne_referenzwerkstatt`):

```python
_DATUM_DE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")
_DATUM_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def _datum_iso(wert: str):
    """DD.MM.YYYY / YYYY-MM-DD -> 'YYYY-MM-DD'; None wenn kein Datum."""
    m = _DATUM_DE.match(wert)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    if _DATUM_ISO.match(wert):
        return wert
    return None
```

In der Konflikt-Schleife von `extrahiere_felder` (aktuell:
`if str(llm_wert).strip() != str(regex_wert).strip():`) davor die Datums-Gleichheit prüfen:

```python
        llm_s = str(llm_wert).strip()
        regex_s = str(regex_wert).strip()
        iso_llm, iso_regex = _datum_iso(llm_s), _datum_iso(regex_s)
        if iso_llm and iso_regex and iso_llm == iso_regex:
            continue
        if llm_s != regex_s:
            konflikte[feld] = {"llm": llm_wert, "regex": regex_wert}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_intake_extraktion.py -q`
Expected: alle passed (Bestand + 3 neue).

- [ ] **Step 5: Commit**

```bash
git add backend/intake/extraktion.py backend/tests/test_intake_extraktion.py
git commit -m "fix(intake): Datums-Scheinkonflikt llm_konflikt bei DD.MM.YYYY vs ISO (Befund 1280/25)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Verifikation am echten Dok 517 (Controller-Task)

**Files:** keine Änderungen; Reparse + DB-Check im Container.

- [ ] **Step 1: Reparse Dok 517** (Muster wie Dok 516: `enqueue(517); verarbeite_dokument(517)` im Container).
- [ ] **Step 2: Prüfen:** Klassifikations-Kandidaten von Dok 517 enthalten NICHT mehr `rechnung` als Marker-Treffer (Befund a) und `llm_konflikt` enthält keinen `schreibdatum`-Scheinkonflikt mehr (Befund c). Klasse bleibt `abrechnungsschreiben`.
- [ ] **Step 3: Kein Commit** — Ergebnis in den Abschlussbericht.
