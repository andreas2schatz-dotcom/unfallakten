# Referenzwerkstatt-Extraktion (VHV-Blockformat) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `felder.referenzwerkstatt` wird beim Prüfbericht-Intake zuverlässig deterministisch gefüllt (Name + Straße + PLZ/Ort + genannte km), inkl. Fix des Trigger-Kontext-Fehltreffers auf Floskel-Sätzen.

**Architecture:** Der vorhandene Regex-Parser `extrahiere_verweisbetrieb` in `backend/services/werkstatt_service.py` bekommt eine neue Stufe für das VHV-Blockformat („Für die Korrekturberechnung haben wir den Reparaturbetrieb …") und eine Plausibilitätsbremse für die Trigger-Kontext-Stufe (kein Treffer ohne PLZ). Die Intake-Extraktion (`backend/intake/extraktion.py`) ruft ihn als Fallback auf — exakt analog zum bestehenden Prüfdienstleister-Fallback: nur Klasse `pruefbericht`, nur wenn das LLM nichts geliefert hat. Das LLM-Seitenfenster (N-06) wird NICHT angefasst (entschieden mit RA Schatz 2026-08-07).

**Tech Stack:** Python 3 (Flask-Backend im Docker-Container `unfallakten-backend-dev`), `re`, `unittest`/`pytest`.

## Global Constraints

- Tests laufen IM CONTAINER: `docker exec unfallakten-backend-dev python -m pytest backend/tests/<datei> -q` (Host-Dateien sind ins Volume gemountet, Änderungen sofort sichtbar).
- Git-Wurzel ist das Home-Verzeichnis `C:\Users\HAL9000` — NIE `git add -A`, immer Dateien einzeln stagen. Arbeitsverzeichnis für git-Befehle: `C:\Users\HAL9000\Documents\Projekt\Version 1.00\unfallakten`.
- Branch: `abschlussbericht` (dort weiterarbeiten, NICHT mergen).
- Vorbestehende Failures NICHT fixen: 2× `test_intake_routes` (Label „Rechnung (Auffang)"), `test_modul7` (gelöschtes Modul email_import.parser).
- Keine Code-Kommentare außer bei nicht-offensichtlichem Verhalten.
- Commit-Messages enden mit `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Registry-YAMLs werden hier NICHT geändert (das Schema-Feld `referenzwerkstatt` existiert bereits in `backend/registry/klassen/pruefbericht.yaml:59`), daher kein Backend-Restart nötig.
- Docs (CHANGELOG/TODO) werden erst am Session-Ende nach allen 3 Paketen nachgeführt — nicht Teil dieses Plans.

---

### Task 1: VHV-Blockformat in `extrahiere_verweisbetrieb`

**Files:**
- Modify: `backend/services/werkstatt_service.py` (neue Regex-Konstanten nach Zeile 82, neue Stufe in `extrahiere_verweisbetrieb` nach Stufe 1, Zeile 115)
- Test: `backend/tests/test_werkstatt_verweisbetrieb.py` (neu)

**Interfaces:**
- Consumes: bestehende Funktion `extrahiere_verweisbetrieb(text: str) -> dict` mit Keys `gefunden, name, adresse, plz_ort, telefon, km_genannt, quelle`.
- Produces: neuer `quelle`-Wert `"vhv_block"`; Rückgabeform unverändert. Task 3 verlässt sich auf exakt diese Keys.

- [ ] **Step 1: Write the failing tests**

Neue Datei `backend/tests/test_werkstatt_verweisbetrieb.py`:

```python
"""
Tests fuer extrahiere_verweisbetrieb (werkstatt_service).

VHV-Blockformat (Befund Akte 1280/25, Dok 516): Der verwendete
Reparaturbetrieb steht nach "Fuer die Korrekturberechnung haben wir den
Reparaturbetrieb", gefolgt von Name/Strasse/PLZ-Block und
"Entfernungskilometer: X km", abgeschlossen mit "beruecksichtigt.".
Danach folgen Alternativ-Betriebe, die NICHT gezogen werden duerfen.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

VHV_TEXT = (
    "Wird eine Referenzwerkstatt benannt, berücksichtigen wir bei der\n"
    "Höhe der Stundenverrechnungssätze die Preise dieser Werkstatt.\n"
    "Die Stundenverrechnungssätze der benannten Werkstätten entsprechen\n"
    "der Preisangabenverordnung und sind für alle Verbraucher zugänglich.\n"
    "Detaillierte Angaben zum Reparaturbetrieb, zur Garantie und der\n"
    "räumlichen Nähe sind im Prüfbericht aufgeführt.\n"
    "Für die Korrekturberechnung haben wir den Reparaturbetrieb\n"
    "\n"
    "Möser Arno - Karosseriefachbetrieb\n"
    "Philipp-Reis-Straße 9\n"
    "63128 Dietzenbach\n"
    "Telefon: 06074-25936\n"
    "Web: www.kbmoeser.de\n"
    "Reparaturkosten (Netto): 5448,62 EUR\n"
    "Lohn Mechanik: 130,00 EUR/Stunde\n"
    "Lohn Lackierung: 135,00 EUR/Stunde\n"
    "Qualitätsmerkmale: ZKF\n"
    "Entfernungskilometer: 16,00 km\n"
    "Garantieleistung: 5-5 Jahre\n"
    "berücksichtigt.\n"
    "Ferner stehen Ihnen weitere Reparaturbetriebe zur Auswahl:\n"
    "Rauch Karosseriebau GmbH\n"
    "Industriestraße 18\n"
    "61381 Friedrichsdorf\n"
    "Telefon: 06172-72500\n"
    "Entfernungskilometer: 29,69 km\n"
)


class TestVhvBlock(unittest.TestCase):
    def test_vhv_block_wird_extrahiert(self):
        from backend.services.werkstatt_service import extrahiere_verweisbetrieb
        t = extrahiere_verweisbetrieb(VHV_TEXT)
        self.assertTrue(t["gefunden"])
        self.assertEqual(t["quelle"], "vhv_block")
        self.assertEqual(t["name"], "Möser Arno - Karosseriefachbetrieb")
        self.assertEqual(t["adresse"], "Philipp-Reis-Straße 9")
        self.assertEqual(t["plz_ort"], "63128 Dietzenbach")
        self.assertEqual(t["telefon"], "06074-25936")

    def test_vhv_block_nimmt_verwendeten_betrieb_nicht_alternative(self):
        from backend.services.werkstatt_service import extrahiere_verweisbetrieb
        t = extrahiere_verweisbetrieb(VHV_TEXT)
        self.assertEqual(t["km_genannt"], 16.0)
        self.assertNotIn("Rauch", t["name"])

    def test_controlexpert_format_weiterhin_erkannt(self):
        from backend.services.werkstatt_service import extrahiere_verweisbetrieb
        text = (
            "Verwendeter Referenzbetrieb\n"
            "Karosseriebau Muster GmbH\n"
            "Musterstraße 12\n"
            "60311 Frankfurt\n"
            "069/123456\n"
            "Entfernung zum Anspruchsteller: 7,5 km\n"
        )
        t = extrahiere_verweisbetrieb(text)
        self.assertTrue(t["gefunden"])
        self.assertEqual(t["quelle"], "controlexpert")
        self.assertEqual(t["name"], "Karosseriebau Muster GmbH")
        self.assertEqual(t["km_genannt"], 7.5)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify the VHV tests fail**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_werkstatt_verweisbetrieb.py -q`
Expected: 2 FAIL (`test_vhv_block_wird_extrahiert` — quelle ist derzeit `triggerkontext`, `test_vhv_block_nimmt_verwendeten_betrieb_nicht_alternative`), 1 PASS (`test_controlexpert_format_weiterhin_erkannt`).

- [ ] **Step 3: Implement VHV-Stufe**

In `backend/services/werkstatt_service.py` nach dem `CONTROLEXPERT_MUSTER`-Block (Zeile 82) einfügen:

```python
# VHV-Blockformat: "Für die Korrekturberechnung haben wir den Reparaturbetrieb
# \n\n Name \n Straße \n PLZ Ort \n ... Entfernungskilometer: X km ... berücksichtigt."
VHV_KORREKTUR_BLOCK = re.compile(
    r"F[üu]r\s+die\s+Korrekturberechnung\s+haben\s+wir\s+den\s+Reparaturbetrieb\s*\n+"
    r"([^\n]{3,80})\n"          # Name
    r"([^\n]{3,80})\n"          # Straße
    r"(\d{5}\s+[^\n]{2,40})",   # PLZ + Ort
    re.IGNORECASE
)

VHV_ENTFERNUNG_MUSTER = re.compile(
    r"Entfernungskilometer:\s*(\d+[,.]?\d*)\s*km", re.IGNORECASE)

VHV_TELEFON_MUSTER = re.compile(r"Telefon:\s*([\d\s/\-]+)")
```

In `extrahiere_verweisbetrieb` zwischen Stufe 1 (ControlExpert, endet Zeile 115) und Stufe 2 (`WERKSTATT_ADRESSE`) einfügen:

```python
    # ── Stufe 1b: VHV-Blockformat (verwendeter Betrieb der Korrekturberechnung) ──
    m = VHV_KORREKTUR_BLOCK.search(text)
    if m:
        # Nur bis "berücksichtigt." suchen — danach folgen Alternativ-Betriebe
        ende = text.find("berücksichtigt", m.end())
        fenster = text[m.end():ende] if ende != -1 else text[m.end():m.end() + 600]
        km_m = VHV_ENTFERNUNG_MUSTER.search(fenster)
        tel_m = VHV_TELEFON_MUSTER.search(fenster)
        return {
            "gefunden":   True,
            "name":       m.group(1).strip(),
            "adresse":    m.group(2).strip(),
            "plz_ort":    m.group(3).strip(),
            "telefon":    tel_m.group(1).strip() if tel_m else "",
            "km_genannt": float(km_m.group(1).replace(",", ".")) if km_m else None,
            "quelle":     "vhv_block",
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_werkstatt_verweisbetrieb.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/services/werkstatt_service.py backend/tests/test_werkstatt_verweisbetrieb.py
git commit -m "feat(intake): VHV-Blockformat in extrahiere_verweisbetrieb (Befund 1280/25)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Plausibilitätsbremse für Trigger-Kontext-Stufe

**Files:**
- Modify: `backend/services/werkstatt_service.py:153` (Bedingung der Stufe 3)
- Test: `backend/tests/test_werkstatt_verweisbetrieb.py` (erweitern)

**Interfaces:**
- Consumes: `extrahiere_verweisbetrieb(text: str) -> dict` aus Task 1.
- Produces: Stufe 3 (`quelle: "triggerkontext"`) liefert nur noch Treffer, wenn eine PLZ-Zeile im Kontext steht; sonst `{"gefunden": False}`.

- [ ] **Step 1: Write the failing test**

An `backend/tests/test_werkstatt_verweisbetrieb.py` anhängen (vor `if __name__`):

```python
class TestTriggerkontextBremse(unittest.TestCase):
    """Verifiziert 2026-08-07: Der Floskel-Satz 'Wird eine Referenzwerkstatt
    benannt, ...' lieferte einen Scheintreffer mit dem Folgetext als name
    (quelle triggerkontext, Adresse leer). Ohne PLZ kein Treffer."""

    def test_floskelsatz_ohne_adresse_liefert_keinen_treffer(self):
        from backend.services.werkstatt_service import extrahiere_verweisbetrieb
        text = (
            "Wird eine Referenzwerkstatt benannt, berücksichtigen wir bei der\n"
            "Höhe der Stundenverrechnungssätze die Preise dieser Werkstatt.\n"
            "Die Stundenverrechnungssätze der benannten Werkstätten entsprechen\n"
            "der Preisangabenverordnung und sind für alle Verbraucher zugänglich.\n"
        )
        t = extrahiere_verweisbetrieb(text)
        self.assertFalse(t["gefunden"])

    def test_triggerkontext_mit_plz_bleibt_treffer(self):
        from backend.services.werkstatt_service import extrahiere_verweisbetrieb
        text = (
            "Wir verweisen auf eine günstigere Werkstatt in Ihrer Nähe:\n"
            "Autohaus Beispiel GmbH\n"
            "63065 Offenbach, ca. 5 km entfernt\n"
        )
        t = extrahiere_verweisbetrieb(text)
        self.assertTrue(t["gefunden"])
        self.assertEqual(t["quelle"], "triggerkontext")
        self.assertEqual(t["km_genannt"], 5.0)
        self.assertTrue(t["plz_ort"].startswith("63065"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_werkstatt_verweisbetrieb.py -q`
Expected: 1 FAIL (`test_floskelsatz_ohne_adresse_liefert_keinen_treffer` — liefert derzeit `gefunden=True` mit Floskel-Folgezeile als name), Rest PASS.

- [ ] **Step 3: Implement**

In `backend/services/werkstatt_service.py`, Stufe 3, die Bedingung

```python
        if km or plz_ort or name:
```

ersetzen durch:

```python
        # Plausibilitätsbremse: ohne PLZ-Zeile ist der Trigger nur Floskel
        # ("Wird eine Referenzwerkstatt benannt, ...") — kein Treffer
        if plz_ort:
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_werkstatt_verweisbetrieb.py -q`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/services/werkstatt_service.py backend/tests/test_werkstatt_verweisbetrieb.py
git commit -m "fix(intake): Triggerkontext-Verweisbetrieb braucht PLZ-Zeile (Floskel-Scheintreffer)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Intake-Fallback `felder.referenzwerkstatt`

**Files:**
- Modify: `backend/intake/extraktion.py` (neue Hilfsfunktion nach `_erkenne_pruefdienstleister` Zeile 61, Aufruf nach dem Prüfdienstleister-Fallback Zeile 114–117)
- Test: `backend/tests/test_intake_extraktion.py` (neue Testklasse anhängen)

**Interfaces:**
- Consumes: `extrahiere_verweisbetrieb(text) -> dict` (Keys `gefunden, name, adresse, plz_ort, telefon, km_genannt, quelle`) aus Task 1+2.
- Produces: `felder["referenzwerkstatt"]` als dict `{name: str, adresse: str, plz_ort: str, telefon: str, km_genannt: float|None, quelle: str}` — Paket 2 (Entfernungsprüfung) liest genau diese Keys und ergänzt später `km_echt`/`bewertung`.

- [ ] **Step 1: Write the failing tests**

An `backend/tests/test_intake_extraktion.py` anhängen (vor `if __name__`):

```python
class TestReferenzwerkstattFallback(unittest.TestCase):
    """Befund 1280/25: Der VHV-Werkstatt-Block liegt auf Seite 4/5 ausserhalb
    des N-06-LLM-Seitenfensters -- felder.referenzwerkstatt blieb leer.
    Deterministischer Fallback via werkstatt_service (nur pruefbericht,
    nur wenn das LLM nichts liefert)."""

    VHV_TEXT = (
        "Für die Korrekturberechnung haben wir den Reparaturbetrieb\n"
        "\n"
        "Möser Arno - Karosseriefachbetrieb\n"
        "Philipp-Reis-Straße 9\n"
        "63128 Dietzenbach\n"
        "Telefon: 06074-25936\n"
        "Entfernungskilometer: 16,00 km\n"
        "berücksichtigt.\n"
    )

    def _registry(self):
        class _R:
            klassen = {"pruefbericht": {
                "schema": {"referenzwerkstatt": {"typ": "object"},
                           "vorgangsnummer": "string"},
                "regex_felder": {},
            }}
        return _R()

    def _extrahiere(self, text, llm_werte, klasse="pruefbericht",
                    registry=None):
        from backend.intake import extraktion
        with mock.patch("backend.intake.extraktion.llm_service.ist_aktiviert",
                        return_value=True), \
             mock.patch("backend.intake.extraktion.llm_service.extrahiere_nach_schema",
                        return_value=llm_werte):
            return extraktion.extrahiere_felder(
                text, klasse, registry or self._registry())["felder"]

    def test_vhv_block_fuellt_referenzwerkstatt(self):
        felder = self._extrahiere(self.VHV_TEXT,
                                  {"referenzwerkstatt": None})
        ws = felder.get("referenzwerkstatt")
        self.assertIsNotNone(ws)
        self.assertEqual(ws["name"], "Möser Arno - Karosseriefachbetrieb")
        self.assertEqual(ws["adresse"], "Philipp-Reis-Straße 9")
        self.assertEqual(ws["plz_ort"], "63128 Dietzenbach")
        self.assertEqual(ws["km_genannt"], 16.0)
        self.assertEqual(ws["quelle"], "vhv_block")

    def test_llm_wert_wird_nicht_ueberschrieben(self):
        felder = self._extrahiere(
            self.VHV_TEXT,
            {"referenzwerkstatt": {"name": "LLM-Werkstatt"}})
        self.assertEqual(felder["referenzwerkstatt"],
                         {"name": "LLM-Werkstatt"})

    def test_ohne_treffer_bleibt_feld_leer(self):
        felder = self._extrahiere("Prüfbericht ohne Werkstatt-Verweis",
                                  {"referenzwerkstatt": None})
        self.assertNotIn("referenzwerkstatt", felder)

    def test_andere_klassen_unberuehrt(self):
        class _R:
            klassen = {"gutachten": {
                "schema": {"referenzwerkstatt": {"typ": "object"}},
                "regex_felder": {},
            }}
        felder = self._extrahiere(self.VHV_TEXT,
                                  {"referenzwerkstatt": None},
                                  klasse="gutachten", registry=_R())
        self.assertNotIn("referenzwerkstatt", felder)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_intake_extraktion.py -q`
Expected: 1 FAIL (`test_vhv_block_fuellt_referenzwerkstatt` — Feld bleibt ohne Fallback leer). Die drei anderen neuen Tests sind Abwesenheits-/Durchreich-Checks und schon grün; bestehende Tests PASS.

- [ ] **Step 3: Implement**

In `backend/intake/extraktion.py` nach `_erkenne_pruefdienstleister` (Zeile 61) einfügen:

```python
def _erkenne_referenzwerkstatt(text: str):
    """Fallback fuer Pruefberichte, deren Werkstatt-Block ausserhalb des
    N-06-LLM-Seitenfensters liegt (Befund 1280/25: VHV-Blockformat auf
    Seite 4/5). Deterministisch statt LLM-Fenster-Erweiterung
    (Entscheidung RA Schatz 2026-08-07)."""
    from ..services.werkstatt_service import extrahiere_verweisbetrieb
    treffer = extrahiere_verweisbetrieb(text)
    if not treffer.get("gefunden"):
        return None
    return {
        "name":       treffer.get("name", ""),
        "adresse":    treffer.get("adresse", ""),
        "plz_ort":    treffer.get("plz_ort", ""),
        "telefon":    treffer.get("telefon", ""),
        "km_genannt": treffer.get("km_genannt"),
        "quelle":     treffer.get("quelle", ""),
    }
```

In `extrahiere_felder` direkt nach dem Prüfdienstleister-Fallback (Zeile 114–117) einfügen:

```python
    if klasse == "pruefbericht" and not felder.get("referenzwerkstatt"):
        werkstatt = _erkenne_referenzwerkstatt(text)
        if werkstatt:
            felder["referenzwerkstatt"] = werkstatt
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_intake_extraktion.py backend/tests/test_werkstatt_verweisbetrieb.py -q`
Expected: alle passed.

- [ ] **Step 5: Commit**

```bash
git add backend/intake/extraktion.py backend/tests/test_intake_extraktion.py
git commit -m "feat(intake): referenzwerkstatt-Fallback im Pruefbericht-Intake (Befund 1280/25)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: End-to-End-Verifikation am echten Dokument 516

**Files:**
- Keine Code-Änderungen erwartet; nur Verifikation + Regressionslauf.

**Interfaces:**
- Consumes: komplette Kette aus Task 1–3 via `verarbeite_dokument(516)`.
- Produces: Nachweis, dass `parse_json.felder.referenzwerkstatt` in `intake_dokumente` für Dok 516 gefüllt ist.

- [ ] **Step 1: Reparse Dok 516 im Container**

```bash
docker exec unfallakten-backend-dev python -c "
import sys; sys.path.insert(0, '/app')
from backend.intake.queue import enqueue
from backend.intake.pipeline import verarbeite_dokument
enqueue(516); print(verarbeite_dokument(516))"
```

Expected: Verarbeitung ohne Fehler, Status `bereit_zur_review`.

- [ ] **Step 2: felder.referenzwerkstatt in der DB prüfen**

```bash
docker exec unfallakten-backend-dev python -c "
import sqlite3, json
conn = sqlite3.connect('/app/data/unfallakten.db')
row = conn.execute('SELECT parse_json FROM intake_dokumente WHERE id=516').fetchone()
print(json.dumps(json.loads(row[0]).get('felder', {}).get('referenzwerkstatt'),
                 ensure_ascii=False, indent=2))"
```

Expected: dict mit `name: "Möser Arno - Karosseriefachbetrieb"`, `adresse: "Philipp-Reis-Straße 9"`, `plz_ort: "63128 Dietzenbach"`, `km_genannt: 16.0`, `quelle: "vhv_block"`. (Falls das LLM selbst einen brauchbaren Wert liefert, ist auch das ok — dann greift der Fallback bewusst nicht; entscheidend ist, dass das Feld gefüllt und plausibel ist.)

- [ ] **Step 3: Regressionslauf der betroffenen Suiten**

```bash
docker exec unfallakten-backend-dev python -m pytest backend/tests/test_werkstatt_verweisbetrieb.py backend/tests/test_intake_extraktion.py backend/tests/test_registry_golden.py backend/tests/test_s16b_klassifikation_e2e.py backend/tests/test_pruefbericht_verkettung.py -q
```

Expected: alle passed (vorbestehende Failures liegen in anderen Dateien).

- [ ] **Step 4: Kein Commit nötig**

Falls Schritt 1–3 Anpassungen erzwangen: Fix + betroffene Datei einzeln stagen + Commit im Stil der Tasks 1–3. Sonst nichts zu tun; CHANGELOG/TODO folgen am Session-Ende nach Paket 2+3.
